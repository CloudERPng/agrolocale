import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Cycle', 'fieldname': 'name', 'fieldtype': 'Link', 'width': 140, 'options': 'Cultivation Cycle'},
        {'label': 'Crop', 'fieldname': 'crop', 'fieldtype': 'Link', 'width': 110, 'options': 'Crop'},
        {'label': 'Season', 'fieldname': 'season', 'fieldtype': 'Data', 'width': 90},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 100},
        {'label': 'Cap. Plots', 'fieldname': 'capacity_plots', 'fieldtype': 'Float', 'width': 90},
        {'label': 'Subs. Plots', 'fieldname': 'subscribed_plots', 'fieldtype': 'Float', 'width': 90},
        {'label': 'Plot Util %', 'fieldname': 'plot_util', 'fieldtype': 'Percent', 'width': 90},
        {'label': 'Cap. Acres', 'fieldname': 'capacity_acres', 'fieldtype': 'Float', 'width': 90},
        {'label': 'Subs. Acres', 'fieldname': 'subscribed_acres', 'fieldtype': 'Float', 'width': 90}
    ]
    conds, vals = ["docstatus=1"], {}
    if filters.get("status"):
        conds.append("status=%(status)s"); vals["status"]=filters["status"]
    if filters.get("crop"):
        conds.append("crop=%(crop)s"); vals["crop"]=filters["crop"]
    where = " and ".join(conds)
    rows = frappe.db.sql(f'''
        select name, crop, season, status, capacity_plots, subscribed_plots,
               capacity_acres, subscribed_acres
        from `tabCultivation Cycle` where {where}
        order by name''', vals, as_dict=True)
    for r in rows:
        cap = flt(r["capacity_plots"])
        r["plot_util"] = (flt(r["subscribed_plots"])/cap*100) if cap else 0
    data = rows
    return columns, data
