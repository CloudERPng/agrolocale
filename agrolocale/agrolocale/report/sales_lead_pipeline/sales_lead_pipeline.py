import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Lead', 'fieldname': 'name', 'fieldtype': 'Link', 'width': 130, 'options': 'Sales Lead'},
        {'label': 'Lead Name', 'fieldname': 'lead_name', 'fieldtype': 'Data', 'width': 170},
        {'label': 'Mobile', 'fieldname': 'mobile', 'fieldtype': 'Data', 'width': 110},
        {'label': 'Source', 'fieldname': 'source', 'fieldtype': 'Data', 'width': 110},
        {'label': 'Realtor', 'fieldname': 'realtor', 'fieldtype': 'Data', 'width': 140},
        {'label': 'Estate', 'fieldname': 'interested_estate', 'fieldtype': 'Link', 'width': 140, 'options': 'Farm Estate'},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 100},
        {'label': 'Intake', 'fieldname': 'subscription_intake', 'fieldtype': 'Link', 'width': 130, 'options': 'Subscription Intake'},
        {'label': 'Created', 'fieldname': 'creation', 'fieldtype': 'Date', 'width': 95}
    ]
    conds, vals = ["1=1"], {}
    for f, c in [("status","status=%(status)s"),("source","source=%(source)s"),
                 ("realtor","realtor=%(realtor)s"),
                 ("interested_estate","interested_estate=%(interested_estate)s")]:
        if filters.get(f):
            conds.append(c); vals[f]=filters[f]
    if filters.get("from_date"):
        conds.append("date(creation)>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("date(creation)<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    data = frappe.db.sql(f'''select name, lead_name, mobile, source, realtor,
        interested_estate, status, subscription_intake, creation
        from `tabSales Lead` where {" and ".join(conds)} order by creation desc''', vals, as_dict=True)
    return columns, data
