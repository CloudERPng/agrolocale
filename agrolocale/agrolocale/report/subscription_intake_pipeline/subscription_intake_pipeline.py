import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Intake', 'fieldname': 'name', 'fieldtype': 'Link', 'width': 130, 'options': 'Subscription Intake'},
        {'label': 'Subscriber', 'fieldname': 'full_name', 'fieldtype': 'Data', 'width': 170},
        {'label': 'Estate', 'fieldname': 'estate', 'fieldtype': 'Link', 'width': 140, 'options': 'Farm Estate'},
        {'label': 'Plan', 'fieldname': 'payment_plan', 'fieldtype': 'Data', 'width': 110},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 140},
        {'label': 'Receipts', 'fieldname': 'receipt_count', 'fieldtype': 'Int', 'width': 85},
        {'label': 'Receipt Value', 'fieldname': 'receipt_value', 'fieldtype': 'Currency', 'width': 130},
        {'label': 'Days in Stage', 'fieldname': 'days_in_stage', 'fieldtype': 'Int', 'width': 110},
        {'label': 'Subscription', 'fieldname': 'plot_subscription', 'fieldtype': 'Link', 'width': 130, 'options': 'Plot Subscription'}
    ]
    conds, vals = ["1=1"], {}
    for f,c in [("status","i.status=%(status)s"),("estate","i.estate=%(estate)s")]:
        if filters.get(f): conds.append(c); vals[f]=filters[f]
    rows = frappe.db.sql(f'''select i.name, i.full_name, i.estate, i.payment_plan, i.status,
        i.plot_subscription, i.modified,
        (select count(*) from `tabIntake Receipt` r where r.parent=i.name) receipt_count,
        (select coalesce(sum(r.amount),0) from `tabIntake Receipt` r where r.parent=i.name) receipt_value
        from `tabSubscription Intake` i where {" and ".join(conds)} order by i.modified desc''',
        vals, as_dict=True)
    today = getdate(nowdate())
    for r in rows:
        r["days_in_stage"] = (today - getdate(r["modified"])).days
    data = rows
    return columns, data
