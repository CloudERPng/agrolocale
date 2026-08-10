import frappe
from frappe.model.document import Document


class ClientEnquiry(Document):
    def validate(self):
        if self.status == "Resolved" and not self.resolution:
            frappe.throw("Enter the Resolution before marking this enquiry Resolved.")
