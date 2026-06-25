import frappe
from frappe.model.document import Document
from frappe.utils import flt


class HarvestSettlement(Document):
    def validate(self):
        share = flt(frappe.db.get_value("Cultivation Cycle", self.cultivation_cycle, "company_share_pct")) or 20
        price = flt(self.actual_sale_price_per_kg)
        self.gross_revenue = flt(self.actual_total_yield_kg) * price
        self.company_share = self.gross_revenue * share / 100
        self.subscriber_pool = self.gross_revenue - self.company_share
        for a in self.allocations:
            g = flt(a.yield_kg) * price
            a.gross = g
            a.company_cut = g * share / 100
            a.subscriber_payout = g - a.company_cut

    def on_submit(self):
        # Accounting accounts are site-specific (see README "Harvest posting").
        # Figures are computed in validate(); enable posting after mapping accounts.
        frappe.msgprint("Harvest computed. Configure GL accounts to auto-post the 80/20 payouts (see README).")


@frappe.whitelist()
def get_cycle_subscribers(cultivation_cycle, actual_total_yield_kg=0):
    """Return the subscribers enrolled in a cycle, with a suggested yield share.
    If an actual total yield is given, it is split by each subscriber's expected
    yield weight; otherwise each subscriber's own expected yield is used."""
    subs = frappe.get_all("Cultivation Subscription",
        filters={"cultivation_cycle": cultivation_cycle, "docstatus": 1,
                 "status": ["in", ["Subscribed", "Cultivating", "Harvested"]]},
        fields=["name", "subscriber", "expected_yield_kg"])
    total_expected = sum(flt(s.expected_yield_kg) for s in subs)
    actual = flt(actual_total_yield_kg)
    out = []
    for s in subs:
        if actual and total_expected:
            y = actual * flt(s.expected_yield_kg) / total_expected
        else:
            y = flt(s.expected_yield_kg)
        out.append({
            "subscriber": s.subscriber,
            "cultivation_subscription": s.name,
            "yield_kg": y,
        })
    return out
