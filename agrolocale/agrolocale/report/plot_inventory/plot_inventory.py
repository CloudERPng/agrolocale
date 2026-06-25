import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Estate', 'fieldname': 'estate', 'fieldtype': 'Link', 'width': 160, 'options': 'Farm Estate'},
        {'label': 'Acquisition', 'fieldname': 'source_acquisition', 'fieldtype': 'Link', 'width': 150, 'options': 'Land Acquisition'},
        {'label': 'Total', 'fieldname': 'total', 'fieldtype': 'Int', 'width': 80},
        {'label': 'Available', 'fieldname': 'available', 'fieldtype': 'Int', 'width': 90},
        {'label': 'Reserved', 'fieldname': 'reserved', 'fieldtype': 'Int', 'width': 90},
        {'label': 'Allocated', 'fieldname': 'allocated', 'fieldtype': 'Int', 'width': 90},
        {'label': 'Sold', 'fieldname': 'sold', 'fieldtype': 'Int', 'width': 80},
        {'label': 'Refunded', 'fieldname': 'refunded', 'fieldtype': 'Int', 'width': 90}
    ]
    conds, vals = [], {}
    if filters.get("estate"):
        conds.append("estate=%(estate)s"); vals["estate"]=filters["estate"]
    if filters.get("source_acquisition"):
        conds.append("source_acquisition=%(source_acquisition)s"); vals["source_acquisition"]=filters["source_acquisition"]
    where = (" where " + " and ".join(conds)) if conds else ""
    data = frappe.db.sql(f'''
        select estate, source_acquisition,
            count(*) total,
            sum(status='Available') available,
            sum(status='Reserved') reserved,
            sum(status='Allocated') allocated,
            sum(status in ('Sold','Resold')) sold,
            sum(status='Refunded') refunded
        from `tabLand Plot` {where}
        group by estate, source_acquisition
        order by estate, source_acquisition''', vals, as_dict=True)
    return columns, data
