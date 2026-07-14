import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CultivationCredit(Document):
    def validate(self):
        self.redeemed_amount = flt(sum(flt(r.amount) for r in (self.redemptions or [])), 2)
        self.balance = flt(flt(self.amount) - self.redeemed_amount, 2)
        self.status = ("Redeemed" if self.balance <= 0
                       else "Partially Redeemed" if self.redeemed_amount > 0
                       else "Available")
