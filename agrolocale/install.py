import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ROLES = ["Agrolocale Sales", "Agrolocale Customer Care", "Agrolocale Accounts"]


def create_roles():
    for r in ROLES:
        if not frappe.db.exists("Role", r):
            frappe.get_doc({"doctype": "Role", "role_name": r,
                            "desk_access": 1}).insert(ignore_permissions=True)


def after_migrate():
    create_roles()
    create_custom_fields({
        "Sales Order": [dict(fieldname="plot_subscription", label="Plot Subscription",
            fieldtype="Link", options="Plot Subscription", read_only=1,
            insert_after="customer", no_copy=1)],
        "Payment Entry": [dict(fieldname="plot_subscription", label="Plot Subscription",
            fieldtype="Link", options="Plot Subscription", read_only=1,
            insert_after="party", no_copy=1)],
        "Sales Invoice": [dict(fieldname="plot_subscription", label="Plot Subscription",
            fieldtype="Link", options="Plot Subscription", read_only=1,
            insert_after="customer", no_copy=1)],
    }, ignore_validate=True)
