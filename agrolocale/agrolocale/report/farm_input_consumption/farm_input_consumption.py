import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Date', 'fieldname': 'posting_date', 'fieldtype': 'Date', 'width': 95},
        {'label': 'Entry', 'fieldname': 'stock_entry', 'fieldtype': 'Link', 'width': 130, 'options': 'Stock Entry'},
        {'label': 'Cycle', 'fieldname': 'cycle', 'fieldtype': 'Link', 'width': 130, 'options': 'Cultivation Cycle'},
        {'label': 'Farm', 'fieldname': 'farm', 'fieldtype': 'Link', 'width': 130, 'options': 'Farm Estate'},
        {'label': 'Item', 'fieldname': 'item_code', 'fieldtype': 'Link', 'width': 180, 'options': 'Item'},
        {'label': 'Item Group', 'fieldname': 'item_group', 'fieldtype': 'Data', 'width': 130},
        {'label': 'Qty', 'fieldname': 'qty', 'fieldtype': 'Float', 'width': 90},
        {'label': 'UOM', 'fieldname': 'uom', 'fieldtype': 'Data', 'width': 70},
        {'label': 'Value', 'fieldname': 'amount', 'fieldtype': 'Currency', 'width': 130},
        {'label': 'Warehouse', 'fieldname': 'warehouse', 'fieldtype': 'Link', 'width': 150, 'options': 'Warehouse'}
    ]
    conds, vals = ["se.docstatus=1","se.purpose='Material Issue'"], {}
    if filters.get("from_date"):
        conds.append("se.posting_date>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("se.posting_date<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    if filters.get("warehouse"):
        conds.append("sed.s_warehouse=%(warehouse)s"); vals["warehouse"]=filters["warehouse"]
    if filters.get("item_group"):
        conds.append("i.item_group=%(item_group)s"); vals["item_group"]=filters["item_group"]
    proj = None
    if filters.get("cultivation_cycle"):
        proj = frappe.db.get_value("Cultivation Cycle", filters["cultivation_cycle"], "project")
        conds.append("se.project=%(proj)s"); vals["proj"]=proj
    rows = frappe.db.sql(f'''select se.posting_date, se.name stock_entry, se.project,
        sed.item_code, i.item_group, sed.qty, sed.uom, sed.amount, sed.s_warehouse warehouse
        from `tabStock Entry Detail` sed
        join `tabStock Entry` se on se.name=sed.parent
        left join `tabItem` i on i.name=sed.item_code
        where {" and ".join(conds)} order by se.posting_date desc''', vals, as_dict=True)
    cyc_map = {}
    for r in rows:
        if r.get("project") and r["project"] not in cyc_map:
            cyc_map[r["project"]] = frappe.db.get_value("Cultivation Cycle",
                {"project": r["project"]}, ["name","farm"], as_dict=True) or {}
        c = cyc_map.get(r.get("project")) or {}
        r["cycle"] = c.get("name"); r["farm"] = c.get("farm")
    data = rows
    return columns, data
