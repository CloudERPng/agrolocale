import frappe


def execute():
    """Per-crop subscriptions created by a batch had no setup invoice stamped on
    them, so the harvest eligibility check excluded those subscribers even when the
    batch invoice was fully paid. Copy the batch invoice down."""
    if "agrolocale" not in frappe.get_installed_apps():
        return
    if not frappe.db.table_exists("Programme Subscription"):
        return
    rows = frappe.db.sql("""
        select psc.cultivation_subscription as cs, ps.setup_invoice as inv
        from `tabProgramme Subscription Crop` psc
        join `tabProgramme Subscription` ps on ps.name = psc.parent
        where ps.setup_invoice is not null and psc.cultivation_subscription is not null
    """, as_dict=True)
    for r in rows:
        current = frappe.db.get_value("Cultivation Subscription", r.cs, "setup_invoice")
        if not current:
            frappe.db.set_value("Cultivation Subscription", r.cs, "setup_invoice",
                                r.inv, update_modified=False)
    frappe.db.commit()
