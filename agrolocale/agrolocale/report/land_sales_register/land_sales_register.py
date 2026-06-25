import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Subscription', 'fieldname': 'name', 'fieldtype': 'Link', 'width': 130, 'options': 'Plot Subscription'},
        {'label': 'Date', 'fieldname': 'posting_date', 'fieldtype': 'Date', 'width': 90},
        {'label': 'Subscriber', 'fieldname': 'subscriber', 'fieldtype': 'Link', 'width': 160, 'options': 'Customer'},
        {'label': 'Estate', 'fieldname': 'estate', 'fieldtype': 'Link', 'width': 150, 'options': 'Farm Estate'},
        {'label': 'Plots', 'fieldname': 'total_plot_count', 'fieldtype': 'Int', 'width': 70},
        {'label': 'Contract Value', 'fieldname': 'total_contract_value', 'fieldtype': 'Currency', 'width': 130},
        {'label': 'Plan', 'fieldname': 'payment_plan', 'fieldtype': 'Data', 'width': 110},
        {'label': 'Status', 'fieldname': 'subscription_status', 'fieldtype': 'Data', 'width': 100},
        {'label': 'Sales Order', 'fieldname': 'sales_order', 'fieldtype': 'Link', 'width': 130, 'options': 'Sales Order'}
    ]
    conds, vals = ["docstatus=1"], {}
    if filters.get("estate"):
        conds.append("estate=%(estate)s"); vals["estate"]=filters["estate"]
    if filters.get("subscription_status"):
        conds.append("subscription_status=%(subscription_status)s"); vals["subscription_status"]=filters["subscription_status"]
    if filters.get("from_date"):
        conds.append("posting_date>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("posting_date<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    where = " and ".join(conds)
    data = frappe.db.sql(f'''
        select name, posting_date, subscriber, estate, total_plot_count,
               total_contract_value, payment_plan, subscription_status, sales_order
        from `tabPlot Subscription` where {where}
        order by posting_date desc''', vals, as_dict=True)
    return columns, data
