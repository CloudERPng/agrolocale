import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Subscription', 'fieldname': 'sub', 'fieldtype': 'Link', 'width': 130, 'options': 'Plot Subscription'},
        {'label': 'Subscriber', 'fieldname': 'subscriber', 'fieldtype': 'Link', 'width': 160, 'options': 'Customer'},
        {'label': 'Estate', 'fieldname': 'estate', 'fieldtype': 'Link', 'width': 140, 'options': 'Farm Estate'},
        {'label': 'Due Date', 'fieldname': 'due_date', 'fieldtype': 'Date', 'width': 90},
        {'label': 'Amount', 'fieldname': 'amount', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 90},
        {'label': 'Outstanding', 'fieldname': 'outstanding', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Days Overdue', 'fieldname': 'days_overdue', 'fieldtype': 'Int', 'width': 100}
    ]
    conds, vals = ["ps.docstatus=1", "lps.parenttype='Plot Subscription'"], {}
    if filters.get("estate"):
        conds.append("ps.estate=%(estate)s"); vals["estate"]=filters["estate"]
    if filters.get("subscriber"):
        conds.append("ps.subscriber=%(subscriber)s"); vals["subscriber"]=filters["subscriber"]
    if filters.get("status"):
        conds.append("lps.status=%(status)s"); vals["status"]=filters["status"]
    where = " and ".join(conds)
    rows = frappe.db.sql(f'''
        select ps.name sub, ps.subscriber, ps.estate, lps.due_date, lps.amount, lps.status
        from `tabLand Payment Schedule` lps
        join `tabPlot Subscription` ps on ps.name=lps.parent
        where {where}
        order by lps.due_date asc''', vals, as_dict=True)
    today = getdate(nowdate())
    data = []
    for r in rows:
        r["outstanding"] = 0 if r["status"]=="Paid" else flt(r["amount"])
        r["days_overdue"] = max(0, (today-getdate(r["due_date"])).days) if (r["due_date"] and r["status"]!="Paid") else 0
        data.append(r)
    return columns, data
