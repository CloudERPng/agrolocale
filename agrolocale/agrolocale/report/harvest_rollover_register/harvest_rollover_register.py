import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Credit', 'fieldname': 'credit', 'fieldtype': 'Link', 'width': 130, 'options': 'Cultivation Credit'},
        {'label': 'Date', 'fieldname': 'credit_date', 'fieldtype': 'Date', 'width': 95},
        {'label': 'Subscriber', 'fieldname': 'subscriber', 'fieldtype': 'Link', 'width': 170, 'options': 'Customer'},
        {'label': 'Farm / Estate', 'fieldname': 'farm', 'fieldtype': 'Link', 'width': 150, 'options': 'Farm Estate'},
        {'label': 'Batch', 'fieldname': 'programme', 'fieldtype': 'Link', 'width': 140, 'options': 'Cultivation Programme'},
        {'label': 'From Settlement', 'fieldname': 'source_settlement', 'fieldtype': 'Link', 'width': 140, 'options': 'Harvest Settlement'},
        {'label': 'Rolled Over', 'fieldname': 'amount', 'fieldtype': 'Currency', 'width': 130},
        {'label': 'Redeemed', 'fieldname': 'redeemed_amount', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Balance', 'fieldname': 'balance', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 130}
    ]
    conds, vals = ["c.docstatus=1"], {}
    if filters.get("subscriber"):
        conds.append("c.subscriber=%(subscriber)s"); vals["subscriber"]=filters["subscriber"]
    if filters.get("status"):
        conds.append("c.status=%(status)s"); vals["status"]=filters["status"]
    if filters.get("from_date"):
        conds.append("c.credit_date>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("c.credit_date<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    rows = frappe.db.sql(f'''select c.name credit, c.credit_date, c.subscriber,
        c.source_settlement, c.amount, c.redeemed_amount, c.balance, c.status
        from `tabCultivation Credit` c where {" and ".join(conds)}
        order by c.credit_date desc''', vals, as_dict=True)
    data = []
    for r in rows:
        farm = programme = None
        if r.get("source_settlement"):
            cyc = frappe.db.get_value("Harvest Settlement", r["source_settlement"],
                "cultivation_cycle")
            if cyc:
                info = frappe.db.get_value("Cultivation Cycle", cyc,
                    ["farm", "cultivation_programme"], as_dict=True) or {}
                farm = info.get("farm"); programme = info.get("cultivation_programme")
        r["farm"], r["programme"] = farm, programme
        if filters.get("farm") and farm != filters["farm"]:
            continue
        if filters.get("cultivation_programme") and programme != filters["cultivation_programme"]:
            continue
        data.append(r)
    return columns, data
