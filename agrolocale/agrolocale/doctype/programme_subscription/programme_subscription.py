import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint
from agrolocale.utils import ensure_item


class ProgrammeSubscription(Document):
    OPEN_STATES = ("Open", "Cultivating")

    def validate(self):
        self.check_programme_open()
        self.price_allocations()
        self.enforce_eligibility()

    def check_programme_open(self):
        st = frappe.db.get_value("Cultivation Programme", self.cultivation_programme, "status")
        if st and st not in self.OPEN_STATES:
            frappe.throw(f"Batch {self.cultivation_programme} is <b>{st}</b> and is no longer "
                         "accepting subscribers. Enrol this subscriber in the next batch.")

    def price_allocations(self):
        """The subscriber chooses which crops they want and how many plots go to each.
        They may take one crop, some, or all \u2014 and a plot is never split between
        crops, so plots are whole numbers."""
        if not self.cultivation_programme:
            return
        if not self.crop_allocations:
            frappe.throw("Add at least one crop \u2014 choose which crops this subscriber wants.")

        prog = frappe.get_doc("Cultivation Programme", self.cultivation_programme)
        offered = {r.crop: r.cultivation_cycle for r in prog.crop_mix}
        ppa = flt(frappe.db.get_value("Farm Estate", prog.farm, "plots_per_acre")) or 1

        seen, total_pe, total_plots, total_acres, total_fee = set(), 0.0, 0, 0.0, 0.0
        for row in self.crop_allocations:
            if row.crop not in offered:
                frappe.throw(f"{row.crop} is not part of batch {prog.programme_name}. "
                             f"Available crops: {', '.join(offered) or 'none'}.")
            if row.crop in seen:
                frappe.throw(f"{row.crop} appears more than once. Use one row per crop.")
            seen.add(row.crop)

            if flt(row.number_of_plots) != cint(row.number_of_plots):
                frappe.throw(f"{row.crop}: plots must be whole numbers \u2014 a plot cannot be "
                             "split between crops.")
            row.number_of_plots = cint(row.number_of_plots)
            if row.number_of_plots < 0 or flt(row.number_of_acres) < 0:
                frappe.throw(f"{row.crop}: quantities cannot be negative.")
            if not row.number_of_plots and not flt(row.number_of_acres):
                frappe.throw(f"{row.crop}: enter the number of plots or acres for this crop.")

            row.cultivation_cycle = offered[row.crop]
            pe = flt(row.number_of_plots) + flt(row.number_of_acres) * ppa
            row.plot_equivalents = flt(pe, 4)

            c = frappe.db.get_value("Crop", row.crop, [
                "setup_fee_per_plot", "setup_fee_per_acre",
                "expected_yield_per_plot_kg", "expected_yield_per_acre_kg"], as_dict=True) or {}
            row.setup_fee = flt(
                flt(row.number_of_plots) * flt(c.get("setup_fee_per_plot"))
                + flt(row.number_of_acres) * flt(c.get("setup_fee_per_acre")), 2)
            row.expected_yield_kg = flt(
                flt(row.number_of_plots) * flt(c.get("expected_yield_per_plot_kg"))
                + flt(row.number_of_acres) * flt(c.get("expected_yield_per_acre_kg")), 2)

            total_pe += pe
            total_plots += cint(row.number_of_plots)
            total_acres += flt(row.number_of_acres)
            total_fee += flt(row.setup_fee)

        self.number_of_plots = total_plots
        self.number_of_acres = total_acres
        self.total_plot_equivalents = flt(total_pe, 4)
        self.total_setup_fee = flt(total_fee, 2)

    def enforce_eligibility(self):
        owned_pe = frappe.db.sql("""
            select coalesce(sum(total_plot_count), 0) from `tabPlot Subscription`
            where subscriber=%s and docstatus=1 and subscription_status='Allocated'
        """, self.subscriber)[0][0]
        if not owned_pe:
            frappe.throw(f"{self.subscriber} has no allocated land. A subscriber must own "
                         "fully-paid, allocated land before joining a cultivation batch.")
        committed = frappe.db.sql("""
            select coalesce(sum(total_plot_equivalents), 0) from `tabProgramme Subscription`
            where subscriber=%s and docstatus=1 and status in ('Subscribed','Cultivating')
              and name != %s
        """, (self.subscriber, self.name or ""))[0][0]
        req = flt(self.total_plot_equivalents)
        if committed + req > owned_pe:
            frappe.throw(f"Entitlement exceeded. {self.subscriber} owns {owned_pe} "
                         f"plot-equivalents, has {committed} committed, and is requesting {req}.")

    def on_submit(self):
        self.create_crop_subscriptions()
        self.create_setup_invoice()
        self.update_programme_totals()

    def create_crop_subscriptions(self):
        for row in self.crop_allocations:
            if row.cultivation_subscription or not row.cultivation_cycle:
                continue
            cs = frappe.get_doc({
                "doctype": "Cultivation Subscription",
                "subscriber": self.subscriber,
                "cultivation_cycle": row.cultivation_cycle,
                "eligibility_subscription": self.eligibility_subscription,
                "number_of_plots": flt(row.number_of_plots),
                "number_of_acres": flt(row.number_of_acres),
                "status": "Subscribed",
            })
            cs.flags.from_programme = True
            cs.insert(ignore_permissions=True)
            cs.db_set("setup_fee", flt(row.setup_fee))
            cs.db_set("expected_yield_kg", flt(row.expected_yield_kg))
            cs.submit()
            row.db_set("cultivation_subscription", cs.name)

    def create_setup_invoice(self):
        if self.setup_invoice:
            return
        prog = frappe.db.get_value("Cultivation Programme", self.cultivation_programme,
            ["cost_center"], as_dict=True) or {}
        items = []
        for row in self.crop_allocations:
            if flt(row.setup_fee) <= 0:
                continue
            project = frappe.db.get_value("Cultivation Cycle", row.cultivation_cycle,
                "project") if row.cultivation_cycle else None
            qty_desc = []
            if cint(row.number_of_plots):
                qty_desc.append(f"{cint(row.number_of_plots)} plot(s)")
            if flt(row.number_of_acres):
                qty_desc.append(f"{flt(row.number_of_acres):g} acre(s)")
            items.append({
                "item_code": ensure_item(f"Cultivation Setup & Management - {row.crop}"),
                "qty": 1, "rate": flt(row.setup_fee),
                "description": f"{row.crop} \u2013 " + ", ".join(qty_desc),
                "project": project, "cost_center": prog.get("cost_center"),
            })
        if not items:
            return
        si = frappe.get_doc({"doctype": "Sales Invoice", "customer": self.subscriber,
                             "items": items})
        si.insert(ignore_permissions=True)
        self.db_set("setup_invoice", si.name)
        for row in self.crop_allocations:
            if row.cultivation_subscription:
                frappe.db.set_value("Cultivation Subscription",
                    row.cultivation_subscription, "setup_invoice", si.name,
                    update_modified=False)
        frappe.msgprint(f"Draft setup invoice {si.name} created, itemised per crop. "
                        "Review and submit it before collecting the fee.", indicator="green")

    def update_programme_totals(self):
        prog = frappe.get_doc("Cultivation Programme", self.cultivation_programme)
        prog.db_set("subscribed_plots", flt(prog.subscribed_plots) + flt(self.number_of_plots))
        prog.db_set("subscribed_acres", flt(prog.subscribed_acres) + flt(self.number_of_acres))
