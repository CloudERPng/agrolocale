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

    @frappe.whitelist()
    def get_available_credit(self):
        rows = frappe.get_all("Cultivation Credit",
            filters={"subscriber": self.subscriber, "docstatus": 1,
                     "status": ["in", ["Available", "Partially Redeemed"]]},
            fields=["name", "balance"], order_by="credit_date asc, name asc")
        return {"total": flt(sum(flt(r.balance) for r in rows), 2), "credits": rows}

    @frappe.whitelist()
    def apply_harvest_credit(self, amount=None):
        """Redeem the subscriber's harvest rollover credits (oldest first) against
        this subscription's setup invoice. Posts Dr Subscriber Harvest Payable /
        Cr Debtors referencing the invoice, so the invoice outstanding falls and
        the payable clears."""
        from agrolocale.agrolocale.doctype.harvest_settlement.harvest_settlement import get_settings
        from frappe.utils import nowdate

        if self.docstatus != 1:
            frappe.throw("Submit the Cultivation Subscription first.")
        if not self.setup_invoice:
            frappe.throw("No setup invoice is linked to this subscription.")
        inv = frappe.db.get_value("Sales Invoice", self.setup_invoice,
            ["docstatus", "outstanding_amount", "customer", "debit_to", "company"], as_dict=True)
        if inv.docstatus == 0:
            frappe.throw("Submit the setup invoice first — credit is applied against a "
                         "submitted invoice.")
        if inv.docstatus == 2:
            frappe.throw("The setup invoice has been cancelled.")
        outstanding = flt(inv.outstanding_amount)
        if outstanding <= 0:
            frappe.msgprint("The setup invoice is already fully paid.")
            return

        info = self.get_available_credit()
        available = flt(info["total"])
        if available <= 0:
            frappe.throw(f"{self.subscriber} has no available harvest credit.")

        to_apply = min(outstanding, available, flt(amount) if amount else available)
        to_apply = flt(to_apply, 2)
        if to_apply <= 0:
            return

        s = get_settings()
        payable = (s or {}).get("subscriber_harvest_payable_account")
        if not payable:
            frappe.throw("Set the Subscriber Harvest Payable Account in Agrolocale Settings first.")

        je = frappe.get_doc({
            "doctype": "Journal Entry", "voucher_type": "Journal Entry",
            "posting_date": nowdate(), "company": s.get("company") or inv.company,
            "user_remark": f"Harvest credit applied to setup invoice {self.setup_invoice} "
                           f"for {self.subscriber}",
            "accounts": [
                {"account": payable, "party_type": "Customer", "party": self.subscriber,
                 "debit_in_account_currency": to_apply},
                {"account": inv.debit_to, "party_type": "Customer", "party": self.subscriber,
                 "credit_in_account_currency": to_apply,
                 "reference_type": "Sales Invoice", "reference_name": self.setup_invoice},
            ],
        })
        je.insert(ignore_permissions=True)
        je.submit()

        # Consume credits oldest-first
        remaining = to_apply
        for r in info["credits"]:
            if remaining <= 0:
                break
            take = min(flt(r.balance), remaining)
            cr = frappe.get_doc("Cultivation Credit", r.name)
            cr.append("redemptions", {
                "redemption_date": nowdate(), "amount": flt(take, 2),
                "cultivation_subscription": self.name,
                "sales_invoice": self.setup_invoice, "journal_entry": je.name,
            })
            cr.redeemed_amount = flt(flt(cr.redeemed_amount) + take, 2)
            cr.balance = flt(flt(cr.amount) - cr.redeemed_amount, 2)
            cr.status = ("Redeemed" if cr.balance <= 0.005
                         else "Partially Redeemed")
            cr.flags.ignore_validate_update_after_submit = True
            cr.save(ignore_permissions=True)
            remaining = flt(remaining - take, 2)

        self.db_set("applied_credit", flt(flt(self.applied_credit) + to_apply, 2))
        self.db_set("credit_journal_entry", je.name)
        frappe.msgprint(f"Applied {to_apply:,.2f} of harvest credit to {self.setup_invoice} "
                        f"(Journal Entry {je.name}).", indicator="green",
                        title="Credit applied")
        return je.name

