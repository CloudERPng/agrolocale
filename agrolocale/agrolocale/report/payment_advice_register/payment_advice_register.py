import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Advice', 'fieldname': 'name', 'fieldtype': 'Link', 'width': 130, 'options': 'Payment Advice'},
        {'label': 'Date', 'fieldname': 'payment_date', 'fieldtype': 'Date', 'width': 95},
        {'label': 'Subscriber', 'fieldname': 'subscriber', 'fieldtype': 'Link', 'width': 160, 'options': 'Customer'},
        {'label': 'Subscription', 'fieldname': 'plot_subscription', 'fieldtype': 'Link', 'width': 130, 'options': 'Plot Subscription'},
        {'label': 'Amount', 'fieldname': 'amount', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Mode', 'fieldname': 'mode_of_payment', 'fieldtype': 'Data', 'width': 110},
        {'label': 'Bank Ref', 'fieldname': 'bank_reference', 'fieldtype': 'Data', 'width': 130},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 140},
        {'label': 'Payment Entry', 'fieldname': 'payment_entry', 'fieldtype': 'Link', 'width': 140, 'options': 'Payment Entry'}
    ]
    conds, vals = ["1=1"], {}
    for f,c in [("status","status=%(status)s"),("subscriber","subscriber=%(subscriber)s"),
                ("mode_of_payment","mode_of_payment=%(mode_of_payment)s")]:
        if filters.get(f): conds.append(c); vals[f]=filters[f]
    if filters.get("from_date"):
        conds.append("payment_date>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("payment_date<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    data = frappe.db.sql(f'''select name, payment_date, subscriber, plot_subscription, amount,
        mode_of_payment, bank_reference, status, payment_entry
        from `tabPayment Advice` where {" and ".join(conds)} order by payment_date desc''',
        vals, as_dict=True)
    return columns, data
