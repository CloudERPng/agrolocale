import frappe


def ensure_item(item_name):
    """Return a non-stock service Item, creating it on first use."""
    if frappe.db.exists("Item", item_name):
        return item_name
    group = (frappe.db.get_value("Item Group", {"item_group_name": "Services"})
             or frappe.db.get_value("Item Group", {"is_group": 0})
             or "All Item Groups")
    uom = "Nos" if frappe.db.exists("UOM", "Nos") else (frappe.db.get_value("UOM", {}, "name") or "Unit")
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_name,
        "item_name": item_name,
        "item_group": group,
        "stock_uom": uom,
        "is_stock_item": 0,
        "is_sales_item": 1,
    }).insert(ignore_permissions=True)
    return doc.name
