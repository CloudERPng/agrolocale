import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Cycle', 'fieldname': 'cycle', 'fieldtype': 'Link', 'width': 130, 'options': 'Cultivation Cycle'},
        {'label': 'Crop', 'fieldname': 'crop', 'fieldtype': 'Link', 'width': 100, 'options': 'Crop'},
        {'label': 'Farm', 'fieldname': 'farm', 'fieldtype': 'Link', 'width': 140, 'options': 'Farm Estate'},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 100},
        {'label': 'Setup Fee Income', 'fieldname': 'setup_income', 'fieldtype': 'Currency', 'width': 140},
        {'label': 'Harvest Commission (20%)', 'fieldname': 'commission', 'fieldtype': 'Currency', 'width': 170},
        {'label': 'Total Income', 'fieldname': 'total_income', 'fieldtype': 'Currency', 'width': 140},
        {'label': 'Farm Inputs', 'fieldname': 'input_cost', 'fieldtype': 'Currency', 'width': 130},
        {'label': 'Other Direct Cost', 'fieldname': 'other_cost', 'fieldtype': 'Currency', 'width': 150},
        {'label': 'Total Direct Cost', 'fieldname': 'total_cost', 'fieldtype': 'Currency', 'width': 150},
        {'label': 'Gross Margin', 'fieldname': 'margin', 'fieldtype': 'Currency', 'width': 140},
        {'label': 'Margin %', 'fieldname': 'margin_pct', 'fieldtype': 'Percent', 'width': 100},
        {'label': 'Yield (kg)', 'fieldname': 'yield_kg', 'fieldtype': 'Float', 'width': 110},
        {'label': 'Cost / kg', 'fieldname': 'cost_per_kg', 'fieldtype': 'Currency', 'width': 110}
    ]
    conds, vals = ["c.docstatus=1"], {}
    if filters.get("cultivation_cycle"):
        conds.append("c.name=%(cultivation_cycle)s"); vals["cultivation_cycle"]=filters["cultivation_cycle"]
    if filters.get("farm"):
        conds.append("c.farm=%(farm)s"); vals["farm"]=filters["farm"]
    if filters.get("crop"):
        conds.append("c.crop=%(crop)s"); vals["crop"]=filters["crop"]
    cycles = frappe.db.sql(f'''select c.name cycle, c.crop, c.farm, c.status, c.project,
        c.cost_center from `tabCultivation Cycle` c where {" and ".join(conds)}
        order by c.name desc''', vals, as_dict=True)
    data = []
    for c in cycles:
        setup = frappe.db.sql('''select coalesce(sum(cs.setup_fee),0)
            from `tabCultivation Subscription` cs
            where cs.cultivation_cycle=%s and cs.docstatus=1''', c["cycle"])[0][0]
        commission = frappe.db.sql('''select coalesce(sum(hs.company_share),0)
            from `tabHarvest Settlement` hs
            where hs.cultivation_cycle=%s and hs.docstatus=1''', c["cycle"])[0][0]
        yield_kg = frappe.db.sql('''select coalesce(sum(hs.actual_total_yield_kg),0)
            from `tabHarvest Settlement` hs
            where hs.cultivation_cycle=%s and hs.docstatus=1''', c["cycle"])[0][0]
        inputs = other = 0
        if c.get("project"):
            inputs = frappe.db.sql('''select coalesce(sum(sed.amount),0)
                from `tabStock Entry Detail` sed join `tabStock Entry` se on se.name=sed.parent
                where se.docstatus=1 and se.project=%s''', c["project"])[0][0]
            other = frappe.db.sql('''select coalesce(sum(gle.debit-gle.credit),0)
                from `tabGL Entry` gle join `tabAccount` a on a.name=gle.account
                where gle.is_cancelled=0 and gle.project=%s and a.root_type='Expense'
                and gle.voucher_type not in ('Stock Entry')''', c["project"])[0][0]
        income = flt(setup)+flt(commission)
        cost = flt(inputs)+flt(other)
        data.append({"cycle":c["cycle"],"crop":c["crop"],"farm":c["farm"],"status":c["status"],
            "setup_income":flt(setup),"commission":flt(commission),"total_income":income,
            "input_cost":flt(inputs),"other_cost":flt(other),"total_cost":cost,
            "margin":income-cost,"margin_pct":((income-cost)/income*100) if income else 0,
            "yield_kg":flt(yield_kg),
            "cost_per_kg":(cost/flt(yield_kg)) if flt(yield_kg) else 0})
    return columns, data
