import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, getdate, add_days, nowdate
from agrolocale.utils import ensure_item


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
        # Figures are computed in validate(); enable post_settlement() after mapping accounts.
        frappe.msgprint("Harvest computed. Configure GL accounts to auto-post the 80/20 payouts (see README).")
