import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Settlement', 'fieldname': 'settlement', 'fieldtype': 'Link', 'width': 130, 'options': 'Harvest Settlement'},
        {'label': 'Cycle', 'fieldname': 'cultivation_cycle', 'fieldtype': 'Link', 'width': 130, 'options': 'Cultivation Cycle'},
        {'label': 'Subscriber', 'fieldname': 'subscriber', 'fieldtype': 'Link', 'width': 160, 'options': 'Customer'},
        {'label': 'Yield (kg)', 'fieldname': 'yield_kg', 'fieldtype': 'Float', 'width': 100},
        {'label': 'Gross', 'fieldname': 'gross', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Company 20%', 'fieldname': 'company_cut', 'fieldtype': 'Currency', 'width': 120},
        {'label': 'Subscriber 80%', 'fieldname': 'subscriber_payout', 'fieldtype': 'Currency', 'width': 130},
        {'label': 'Payout', 'fieldname': 'payout_status', 'fieldtype': 'Data', 'width': 90}
    ]
    conds, vals = ["hs.docstatus=1", "ha.parenttype='Harvest Settlement'"], {}
    if filters.get("cultivation_cycle"):
        conds.append("hs.cultivation_cycle=%(cultivation_cycle)s"); vals["cultivation_cycle"]=filters["cultivation_cycle"]
    if filters.get("payout_status"):
        conds.append("ha.payout_status=%(payout_status)s"); vals["payout_status"]=filters["payout_status"]
    where = " and ".join(conds)
    data = frappe.db.sql(f'''
        select hs.name settlement, hs.cultivation_cycle, ha.subscriber, ha.yield_kg,
               ha.gross, ha.company_cut, ha.subscriber_payout, ha.payout_status
        from `tabHarvest Allocation` ha
        join `tabHarvest Settlement` hs on hs.name=ha.parent
        where {where}
        order by hs.name, ha.subscriber''', vals, as_dict=True)
    return columns, data
