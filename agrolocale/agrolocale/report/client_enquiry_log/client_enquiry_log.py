import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Enquiry', 'fieldname': 'name', 'fieldtype': 'Link', 'width': 120, 'options': 'Client Enquiry'},
        {'label': 'Date', 'fieldname': 'enquiry_date', 'fieldtype': 'Date', 'width': 95},
        {'label': 'Subscriber', 'fieldname': 'subscriber', 'fieldtype': 'Link', 'width': 150, 'options': 'Customer'},
        {'label': 'Contact', 'fieldname': 'contact_name', 'fieldtype': 'Data', 'width': 140},
        {'label': 'Channel', 'fieldname': 'channel', 'fieldtype': 'Data', 'width': 100},
        {'label': 'Category', 'fieldname': 'category', 'fieldtype': 'Data', 'width': 160},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 100},
        {'label': 'Age (days)', 'fieldname': 'age', 'fieldtype': 'Int', 'width': 95}
    ]
    conds, vals = ["1=1"], {}
    for f,c in [("status","status=%(status)s"),("category","category=%(category)s"),
                ("channel","channel=%(channel)s"),("subscriber","subscriber=%(subscriber)s")]:
        if filters.get(f): conds.append(c); vals[f]=filters[f]
    if filters.get("from_date"):
        conds.append("enquiry_date>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("enquiry_date<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    rows = frappe.db.sql(f'''select name, enquiry_date, subscriber, contact_name, channel,
        category, status, modified from `tabClient Enquiry`
        where {" and ".join(conds)} order by enquiry_date desc''', vals, as_dict=True)
    today = getdate(nowdate())
    for r in rows:
        r["age"] = (today - getdate(r["enquiry_date"])).days if r["enquiry_date"] else 0
    data = rows
    return columns, data
