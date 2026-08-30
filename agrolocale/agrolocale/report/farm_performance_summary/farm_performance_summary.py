import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Farm', 'fieldname': 'farm', 'fieldtype': 'Link', 'width': 180, 'options': 'Farm Estate'},
        {'label': 'Cycles', 'fieldname': 'cycles', 'fieldtype': 'Int', 'width': 90},
        {'label': 'Setup Income', 'fieldname': 'setup_income', 'fieldtype': 'Currency', 'width': 140},
        {'label': 'Commission', 'fieldname': 'commission', 'fieldtype': 'Currency', 'width': 140},
        {'label': 'Total Income', 'fieldname': 'total_income', 'fieldtype': 'Currency', 'width': 140},
        {'label': 'Input Cost', 'fieldname': 'input_cost', 'fieldtype': 'Currency', 'width': 130},
        {'label': 'Gross Margin', 'fieldname': 'margin', 'fieldtype': 'Currency', 'width': 140},
        {'label': 'Margin %', 'fieldname': 'margin_pct', 'fieldtype': 'Percent', 'width': 100},
        {'label': 'Total Yield (kg)', 'fieldname': 'yield_kg', 'fieldtype': 'Float', 'width': 130}
    ]
    farms = frappe.get_all("Farm Estate", pluck="name")
    data = []
    for f in farms:
        cycles = frappe.get_all("Cultivation Cycle",
            filters={"farm": f, "docstatus": 1}, fields=["name","project"])
        if not cycles:
            continue
        setup = commission = inputs = yld = 0
        for c in cycles:
            setup += flt(frappe.db.sql('''select coalesce(sum(setup_fee),0) from
                `tabCultivation Subscription` where cultivation_cycle=%s and docstatus=1''',
                c["name"])[0][0])
            commission += flt(frappe.db.sql('''select coalesce(sum(company_share),0) from
                `tabHarvest Settlement` where cultivation_cycle=%s and docstatus=1''',
                c["name"])[0][0])
            yld += flt(frappe.db.sql('''select coalesce(sum(actual_total_yield_kg),0) from
                `tabHarvest Settlement` where cultivation_cycle=%s and docstatus=1''',
                c["name"])[0][0])
            if c.get("project"):
                inputs += flt(frappe.db.sql('''select coalesce(sum(sed.amount),0)
                    from `tabStock Entry Detail` sed join `tabStock Entry` se on se.name=sed.parent
                    where se.docstatus=1 and se.project=%s''', c["project"])[0][0])
        income = setup + commission
        data.append({"farm":f,"cycles":len(cycles),"setup_income":setup,"commission":commission,
            "total_income":income,"input_cost":inputs,"margin":income-inputs,
            "margin_pct":((income-inputs)/income*100) if income else 0,"yield_kg":yld})
    return columns, data
