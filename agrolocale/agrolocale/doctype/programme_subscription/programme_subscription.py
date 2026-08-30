import frappe
from frappe.model.document import Document
from frappe.utils import flt
from agrolocale.utils import ensure_item


class ProgrammeSubscription(Document):
    def validate(self):
        self.build_split()
        self.enforce_eligibility()

    def build_split(self):
        """Split the subscriber's units across the batch's crops using the crop mix,
        and price each crop at its own rate. The fee is the sum of the parts, never a
        blended figure, so it survives a subscriber asking how it was calculated."""
        if not self.cultivation_programme:
            return
        prog = frappe.get_doc("Cultivation Programme", self.cultivation_programme)
        ppa = flt(frappe.db.get_value("Farm Estate", prog.farm, "plots_per_acre")) or 1
        total_pe = flt(self.number_of_plots) + flt(self.number_of_acres) * ppa
        self.total_plot_equivalents = flt(total_pe, 4)

        self.set("crop_allocations", [])
        total_fee = 0.0
        for row in prog.crop_mix:
            c = frappe.db.get_value("Crop", row.crop, [
                "setup_fee_per_plot", "setup_fee_per_acre",
                "expected_yield_per_plot_kg", "expected_yield_per_acre_kg"], as_dict=True) or {}
            pe = flt(total_pe * flt(row.share_pct) / 100, 4)
            # price per plot-equivalent, using the acre rate divided by plots-per-acre
            fee_per_pe = flt(c.get("setup_fee_per_plot"))
            yld_per_pe = flt(c.get("expected_yield_per_plot_kg"))
            if flt(self.number_of_acres) and flt(c.get("setup_fee_per_acre")) and ppa:
                fee_per_pe = flt(c.get("setup_fee_per_acre")) / ppa
                yld_per_pe = flt(c.get("expected_yield_per_acre_kg")) / ppa
            fee = flt(pe * fee_per_pe, 2)
            total_fee += fee
            self.append("crop_allocations", {
                "crop": row.crop,
                "cultivation_cycle": row.cultivation_cycle,
                "share_pct": row.share_pct,
                "plot_equivalents": pe,
                "setup_fee": fee,
                "expected_yield_kg": flt(pe * yld_per_pe, 2),
            })
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
        """The subscriber signs once for the batch; the per-crop subscriptions the
        settlement machinery needs are generated behind the scenes."""
        for row in self.crop_allocations:
            if row.cultivation_subscription or not row.cultivation_cycle:
                continue
            cs = frappe.get_doc({
                "doctype": "Cultivation Subscription",
                "subscriber": self.subscriber,
                "cultivation_cycle": row.cultivation_cycle,
                "eligibility_subscription": self.eligibility_subscription,
                "number_of_plots": flt(row.plot_equivalents),
                "number_of_acres": 0,
                "status": "Subscribed",
            })
            cs.flags.from_programme = True
            cs.insert(ignore_permissions=True)
            cs.db_set("setup_fee", flt(row.setup_fee))
            cs.db_set("expected_yield_kg", flt(row.expected_yield_kg))
            cs.submit()
            row.db_set("cultivation_subscription", cs.name)

    def create_setup_invoice(self):
        """One itemised invoice for the batch \u2013 a line per crop, so the subscriber
        can see exactly how the fee was built up."""
        if self.setup_invoice:
            return
        prog = frappe.db.get_value("Cultivation Programme", self.cultivation_programme,
            ["cost_center"], as_dict=True) or {}
        items = []
        for row in self.crop_allocations:
            if flt(row.setup_fee) <= 0:
                continue
            cyc = frappe.db.get_value("Cultivation Cycle", row.cultivation_cycle,
                "project") if row.cultivation_cycle else None
            items.append({
                "item_code": ensure_item(f"Cultivation Setup & Management - {row.crop}"),
                "qty": 1, "rate": flt(row.setup_fee),
                "description": f"{row.crop} \u2013 {flt(row.plot_equivalents):g} plot-equivalents "
                               f"({flt(row.share_pct):g}% of batch)",
                "project": cyc, "cost_center": prog.get("cost_center"),
            })
        if not items:
            return
        si = frappe.get_doc({"doctype": "Sales Invoice", "customer": self.subscriber,
                             "items": items})
        si.insert(ignore_permissions=True)
        self.db_set("setup_invoice", si.name)
        frappe.msgprint(f"Draft setup invoice {si.name} created, itemised per crop. "
                        "Review and submit it before collecting the fee.", indicator="green")

    def update_programme_totals(self):
        prog = frappe.get_doc("Cultivation Programme", self.cultivation_programme)
        prog.db_set("subscribed_plots", flt(prog.subscribed_plots) + flt(self.number_of_plots))
        prog.db_set("subscribed_acres", flt(prog.subscribed_acres) + flt(self.number_of_acres))
