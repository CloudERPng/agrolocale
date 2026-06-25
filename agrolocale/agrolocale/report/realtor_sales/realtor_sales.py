import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Realtor', 'fieldname': 'realtor', 'fieldtype': 'Data', 'width': 180},
        {'label': 'Group', 'fieldname': 'realtor_group', 'fieldtype': 'Data', 'width': 140},
        {'label': 'Subscriptions', 'fieldname': 'subs', 'fieldtype': 'Int', 'width': 110},
        {'label': 'Plots Sold', 'fieldname': 'plots', 'fieldtype': 'Float', 'width': 100},
        {'label': 'Contract Value', 'fieldname': 'value', 'fieldtype': 'Currency', 'width': 140}
    ]
    conds, vals = ["docstatus=1"], {}
    if filters.get("estate"):
        conds.append("estate=%(estate)s"); vals["estate"]=filters["estate"]
    if filters.get("from_date"):
        conds.append("posting_date>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("posting_date<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    where = " and ".join(conds)
    data = frappe.db.sql(f'''
        select coalesce(nullif(realtor,''),'(none)') realtor,
               coalesce(realtor_group,'') realtor_group,
               count(*) subs, sum(total_plot_count) plots, sum(total_contract_value) value
        from `tabPlot Subscription` where {where}
        group by realtor, realtor_group
        order by value desc''', vals, as_dict=True)
    return columns, data
