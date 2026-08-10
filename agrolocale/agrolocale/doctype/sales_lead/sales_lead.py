import frappe
from frappe.model.document import Document


class SalesLead(Document):
    @frappe.whitelist()
    def create_intake(self):
        """Hand the lead over to Customer Care as a Subscription Intake."""
        if self.subscription_intake:
            frappe.throw(f"Intake {self.subscription_intake} already exists for this lead.")
        intake = frappe.get_doc({
            "doctype": "Subscription Intake",
            "source_lead": self.name,
            "full_name": self.lead_name,
            "mobile": self.mobile,
            "email": self.email,
            "estate": self.interested_estate,
            "realtor": self.realtor,
            "status": "Draft",
        })
        intake.insert(ignore_permissions=True)
        self.db_set("subscription_intake", intake.name)
        self.db_set("status", "Converted")
        return intake.name
