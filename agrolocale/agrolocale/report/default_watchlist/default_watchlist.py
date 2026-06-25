import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Subscription', 'fieldname': 'name', 'fieldtype': 'Link', 'width': 130, 'options': 'Plot Subscription'},
        {'label': 'Subscriber', 'fieldname': 'subscriber', 'fieldtype': 'Link', 'width': 170, 'options': 'Customer'},
        {'label': 'Estate', 'fieldname': 'estate', 'fieldtype': 'Link', 'width': 150, 'options': 'Farm Estate'},
        {'label': 'Contract Value', 'fieldname': 'total_contract_value', 'fieldtype': 'Currency', 'width': 130},
        {'label': 'Paid', 'fieldname': 'paid', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Outstanding', 'fieldname': 'outstanding', 'fieldtype': 'Currency', 'width': 130}
    ]
    conds, vals = ["ps.docstatus=1", "ps.subscription_status='In Default'"], {}
    if filters.get("estate"):
        conds.append("ps.estate=%(estate)s"); vals["estate"]=filters["estate"]
    where = " and ".join(conds)
    rows = frappe.db.sql(f'''
        select ps.name, ps.subscriber, ps.estate, ps.total_contract_value,
               coalesce(so.advance_paid,0) paid,
               coalesce(so.rounded_total, so.grand_total, ps.total_contract_value) - coalesce(so.advance_paid,0) outstanding
        from `tabPlot Subscription` ps
        left join `tabSales Order` so on so.name=ps.sales_order
        where {where}
        order by outstanding desc''', vals, as_dict=True)
    data = rows
    return columns, data
