import frappe
from frappe.model.document import Document
from frappe.utils import flt


class PaymentAdvice(Document):
    @frappe.whitelist()
    def record_payment(self):
        """Accounts verifies the advice and turns it into a real Payment Entry
        against the subscription's Sales Order, reusing the standard routine."""
        if self.status == "Recorded":
            frappe.throw(f"Already recorded as {self.payment_entry}.")
        if flt(self.amount) <= 0:
            frappe.throw("Amount must be greater than zero.")
        sub = frappe.get_doc("Plot Subscription", self.plot_subscription)
        pe = sub.receive_payment(
            amount=flt(self.amount),
            mode_of_payment=self.mode_of_payment,
            posting_date=self.payment_date,
            reference_no=self.bank_reference or f"Advice {self.name}",
        )
        self.db_set("payment_entry", pe)
        self.db_set("status", "Recorded")
        return pe

    @frappe.whitelist()
    def reject(self, reason):
        if not reason:
            frappe.throw("Enter a reason for rejecting this advice.")
        self.db_set("rejection_reason", reason)
        self.db_set("status", "Rejected")
