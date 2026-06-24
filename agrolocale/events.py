import frappe
from frappe.utils import flt


def payment_entry_on_submit(doc, method=None):
    so_names = set()
    for ref in (doc.references or []):
        if ref.reference_doctype == "Sales Order" and ref.reference_name:
            so_names.add(ref.reference_name)
    for so in so_names:
        sub = frappe.db.get_value("Plot Subscription", {"sales_order": so, "docstatus": 1}, "name")
        if not sub:
            continue
        so_doc = frappe.db.get_value("Sales Order", so,
            ["advance_paid", "rounded_total", "grand_total"], as_dict=True)
        paid = flt(so_doc.advance_paid)
        total = flt(so_doc.rounded_total) or flt(so_doc.grand_total)
        if total and paid >= total:
            frappe.db.set_value("Plot Subscription", sub, "subscription_status", "Allocated")
            for lp in frappe.get_all("Land Plot", {"plot_subscription": sub}, pluck="name"):
                frappe.db.set_value("Land Plot", lp, "status", "Allocated")
