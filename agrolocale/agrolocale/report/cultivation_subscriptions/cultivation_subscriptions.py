import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Subscription', 'fieldname': 'name', 'fieldtype': 'Link', 'width': 140, 'options': 'Cultivation Subscription'},
        {'label': 'Subscriber', 'fieldname': 'subscriber', 'fieldtype': 'Link', 'width': 150, 'options': 'Customer'},
        {'label': 'Cycle', 'fieldname': 'cultivation_cycle', 'fieldtype': 'Link', 'width': 130, 'options': 'Cultivation Cycle'},
        {'label': 'Crop', 'fieldname': 'crop', 'fieldtype': 'Link', 'width': 100, 'options': 'Crop'},
        {'label': 'Plots', 'fieldname': 'number_of_plots', 'fieldtype': 'Float', 'width': 70},
        {'label': 'Acres', 'fieldname': 'number_of_acres', 'fieldtype': 'Float', 'width': 70},
        {'label': 'Setup Fee', 'fieldname': 'setup_fee', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Exp. Yield (kg)', 'fieldname': 'expected_yield_kg', 'fieldtype': 'Float', 'width': 110},
        {'label': 'Proj Min', 'fieldname': 'projected_revenue_min', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Proj Max', 'fieldname': 'projected_revenue_max', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 100}
    ]
    conds, vals = ["docstatus=1"], {}
    if filters.get("cultivation_cycle"):
        conds.append("cultivation_cycle=%(cultivation_cycle)s"); vals["cultivation_cycle"]=filters["cultivation_cycle"]
    if filters.get("crop"):
        conds.append("crop=%(crop)s"); vals["crop"]=filters["crop"]
    if filters.get("status"):
        conds.append("status=%(status)s"); vals["status"]=filters["status"]
    where = " and ".join(conds)
    data = frappe.db.sql(f'''
        select name, subscriber, cultivation_cycle, crop, number_of_plots, number_of_acres,
               setup_fee, expected_yield_kg, projected_revenue_min, projected_revenue_max, status
        from `tabCultivation Subscription` where {where}
        order by cultivation_cycle, subscriber''', vals, as_dict=True)
    return columns, data
