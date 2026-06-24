import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, getdate, add_days, nowdate
from agrolocale.utils import ensure_item


class CultivationSubscription(Document):
    def validate(self):
        self.project_numbers()
        self.enforce_eligibility()

    def project_numbers(self):
        if not self.cultivation_cycle:
            return
        cyc = frappe.db.get_value("Cultivation Cycle", self.cultivation_cycle, "crop")
        if not cyc:
            return
        self.crop = cyc
        c = frappe.db.get_value("Crop", cyc, [
            "setup_fee_per_plot","setup_fee_per_acre","expected_yield_per_plot_kg",
            "expected_yield_per_acre_kg","min_price_per_kg","max_price_per_kg",
            "subscriber_share_pct"], as_dict=True)
        if not c:
            return
        p, a = flt(self.number_of_plots), flt(self.number_of_acres)
        share = (flt(c.subscriber_share_pct) or 80) / 100
        self.setup_fee = p * flt(c.setup_fee_per_plot) + a * flt(c.setup_fee_per_acre)
        self.expected_yield_kg = p * flt(c.expected_yield_per_plot_kg) + a * flt(c.expected_yield_per_acre_kg)
        self.projected_revenue_min = self.expected_yield_kg * flt(c.min_price_per_kg) * share
        self.projected_revenue_max = self.expected_yield_kg * flt(c.max_price_per_kg) * share

    def enforce_eligibility(self):
        owned_pe = frappe.db.sql(
            "select coalesce(sum(total_plot_count),0) from `tabPlot Subscription` "
            "where subscriber=%s and docstatus=1 and subscription_status='Allocated'",
            self.subscriber)[0][0]
        if not owned_pe:
            frappe.throw(f"{self.subscriber} has no allocated land. A subscriber must own "
                         "fully-paid, allocated land before signing on for a cultivation cycle.")
        ppa = frappe.db.sql(
            "select coalesce(max(fe.plots_per_acre),1) from `tabPlot Subscription` ps "
            "join `tabFarm Estate` fe on fe.name=ps.estate "
            "where ps.subscriber=%s and ps.subscription_status='Allocated'",
            self.subscriber)[0][0] or 1
        req = flt(self.number_of_plots) + flt(self.number_of_acres) * ppa
        committed = frappe.db.sql(
            "select coalesce(sum(number_of_plots + number_of_acres*%s),0) "
            "from `tabCultivation Subscription` where subscriber=%s and docstatus=1 "
            "and status in ('Subscribed','Cultivating') and name!=%s",
            (ppa, self.subscriber, self.name or ""))[0][0]
        if committed + req > owned_pe:
            frappe.throw(f"Entitlement exceeded. Owns {owned_pe} plot-equivalents, "
                         f"committed {committed}, requesting {req}.")

    def on_submit(self):
        si = frappe.get_doc({
            "doctype": "Sales Invoice", "customer": self.subscriber,
            "items": [{"item_code": ensure_item(f"Cultivation Setup & Management - {self.crop}"),
                       "qty": 1, "rate": flt(self.setup_fee)}],
        })
        si.insert(ignore_permissions=True)
        self.db_set("setup_invoice", si.name)
        cyc = frappe.get_doc("Cultivation Cycle", self.cultivation_cycle)
        cyc.db_set("subscribed_plots", flt(cyc.subscribed_plots) + flt(self.number_of_plots))
        cyc.db_set("subscribed_acres", flt(cyc.subscribed_acres) + flt(self.number_of_acres))
        frappe.msgprint(f"Setup invoice {si.name} created as draft for review.")
