import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Batch', 'fieldname': 'programme', 'fieldtype': 'Link', 'width': 150, 'options': 'Cultivation Programme'},
        {'label': 'Farm', 'fieldname': 'farm', 'fieldtype': 'Link', 'width': 140, 'options': 'Farm Estate'},
        {'label': 'Subscription', 'fieldname': 'subscription', 'fieldtype': 'Link', 'width': 140, 'options': 'Programme Subscription'},
        {'label': 'Subscriber', 'fieldname': 'subscriber', 'fieldtype': 'Link', 'width': 180, 'options': 'Customer'},
        {'label': 'Crop', 'fieldname': 'crop', 'fieldtype': 'Link', 'width': 110, 'options': 'Crop'},
        {'label': 'Plots', 'fieldname': 'plots', 'fieldtype': 'Int', 'width': 80},
        {'label': 'Acres', 'fieldname': 'acres', 'fieldtype': 'Float', 'width': 80},
        {'label': 'Plot-Equiv.', 'fieldname': 'plot_equivalents', 'fieldtype': 'Float', 'width': 110},
        {'label': 'Setup Fee', 'fieldname': 'setup_fee', 'fieldtype': 'Currency', 'width': 130},
        {'label': 'Expected Yield', 'fieldname': 'expected_yield_kg', 'fieldtype': 'Float', 'width': 130},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 110}
    ]
    conds, vals = ["ps.docstatus=1"], {}
    if filters.get("cultivation_programme"):
        conds.append("ps.cultivation_programme=%(cultivation_programme)s")
        vals["cultivation_programme"]=filters["cultivation_programme"]
    if filters.get("subscriber"):
        conds.append("ps.subscriber=%(subscriber)s"); vals["subscriber"]=filters["subscriber"]
    if filters.get("status"):
        conds.append("ps.status=%(status)s"); vals["status"]=filters["status"]
    rows = frappe.db.sql(f'''select ps.name subscription, ps.subscriber, ps.status,
        ps.cultivation_programme programme, p.farm,
        psc.crop, psc.number_of_plots plots, psc.number_of_acres acres,
        psc.plot_equivalents, psc.setup_fee, psc.expected_yield_kg
        from `tabProgramme Subscription Crop` psc
        join `tabProgramme Subscription` ps on ps.name = psc.parent
        left join `tabCultivation Programme` p on p.name = ps.cultivation_programme
        where {" and ".join(conds)}
        order by ps.cultivation_programme, ps.subscriber, psc.crop''', vals, as_dict=True)
    if filters.get("farm"):
        rows = [r for r in rows if r.get("farm") == filters["farm"]]
    if filters.get("crop"):
        rows = [r for r in rows if r.get("crop") == filters["crop"]]
    data = rows
    return columns, data
