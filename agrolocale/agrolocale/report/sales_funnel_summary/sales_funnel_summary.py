import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Stage', 'fieldname': 'stage', 'fieldtype': 'Data', 'width': 260},
        {'label': 'Count', 'fieldname': 'cnt', 'fieldtype': 'Int', 'width': 110},
        {'label': 'Value', 'fieldname': 'value', 'fieldtype': 'Currency', 'width': 160}
    ]
    conds, vals = ["1=1"], {}
    if filters.get("from_date"):
        conds.append("date(creation)>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("date(creation)<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    w = " and ".join(conds)
    leads = frappe.db.sql(f"select count(*) from `tabSales Lead` where {w}", vals)[0][0]
    intakes = frappe.db.sql(f"select count(*) from `tabSubscription Intake` where {w}", vals)[0][0]
    with_acc = frappe.db.sql(f"select count(*) from `tabSubscription Intake` where {w} and status='With Accounts'", vals)[0][0]
    processed = frappe.db.sql(f"select count(*) from `tabSubscription Intake` where {w} and status='Processed'", vals)[0][0]
    sconds, svals = ["docstatus=1"], {}
    if filters.get("from_date"):
        sconds.append("posting_date>=%(from_date)s"); svals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        sconds.append("posting_date<=%(to_date)s"); svals["to_date"]=filters["to_date"]
    subs = frappe.db.sql(f'''select count(*), coalesce(sum(total_contract_value),0)
        from `tabPlot Subscription` where {" and ".join(sconds)}''', svals)[0]
    data = [
        {"stage":"1. Leads captured (Sales)","cnt":leads,"value":0},
        {"stage":"2. Intakes raised","cnt":intakes,"value":0},
        {"stage":"3. Verified, with Accounts","cnt":with_acc,"value":0},
        {"stage":"4. Processed into subscriptions","cnt":processed,"value":0},
        {"stage":"5. Submitted subscriptions","cnt":subs[0],"value":flt(subs[1])},
    ]
    return columns, data
