import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Realtor', 'fieldname': 'realtor', 'fieldtype': 'Data', 'width': 180},
        {'label': 'Leads', 'fieldname': 'leads', 'fieldtype': 'Int', 'width': 90},
        {'label': 'Converted', 'fieldname': 'converted', 'fieldtype': 'Int', 'width': 110},
        {'label': 'Intakes', 'fieldname': 'intakes', 'fieldtype': 'Int', 'width': 90},
        {'label': 'Subscriptions', 'fieldname': 'subs', 'fieldtype': 'Int', 'width': 120},
        {'label': 'Contract Value', 'fieldname': 'value', 'fieldtype': 'Currency', 'width': 150}
    ]
    conds, vals = ["1=1"], {}
    if filters.get("from_date"):
        conds.append("date(l.creation)>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("date(l.creation)<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    rows = frappe.db.sql(f'''select coalesce(nullif(l.realtor,''),'(none)') realtor,
        count(*) leads, sum(l.status='Converted') converted,
        count(l.subscription_intake) intakes
        from `tabSales Lead` l where {" and ".join(conds)}
        group by realtor order by leads desc''', vals, as_dict=True)
    for r in rows:
        agg = frappe.db.sql('''select count(*), coalesce(sum(total_contract_value),0)
            from `tabPlot Subscription` where docstatus=1 and coalesce(nullif(realtor,''),'(none)')=%s''',
            r["realtor"])[0]
        r["subs"], r["value"] = agg[0], flt(agg[1])
    data = rows
    return columns, data
