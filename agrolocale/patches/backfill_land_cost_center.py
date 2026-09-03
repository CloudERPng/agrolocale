import frappe


def execute():
    """Stamp the estate's land cost centre onto existing plot subscriptions so future
    invoices and payments carry it. Already-submitted invoices are not changed."""
    if "agrolocale" not in frappe.get_installed_apps():
        return
    if not frappe.db.table_exists("Plot Subscription"):
        return
    if not frappe.db.has_column("Plot Subscription", "cost_center"):
        return
    for sub in frappe.get_all("Plot Subscription",
            filters={"cost_center": ["in", ["", None]]}, fields=["name", "estate"]):
        cc = frappe.db.get_value("Farm Estate", sub.estate, "land_cost_center")
        if cc:
            frappe.db.set_value("Plot Subscription", sub.name, "cost_center", cc,
                                update_modified=False)
    frappe.db.commit()
