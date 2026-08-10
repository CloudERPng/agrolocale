import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Category', 'fieldname': 'category', 'fieldtype': 'Data', 'width': 190},
        {'label': 'Total', 'fieldname': 'total', 'fieldtype': 'Int', 'width': 90},
        {'label': 'Open', 'fieldname': 'open_n', 'fieldtype': 'Int', 'width': 80},
        {'label': 'In Progress', 'fieldname': 'inprog', 'fieldtype': 'Int', 'width': 110},
        {'label': 'Resolved', 'fieldname': 'resolved', 'fieldtype': 'Int', 'width': 100},
        {'label': 'Resolution %', 'fieldname': 'res_pct', 'fieldtype': 'Percent', 'width': 120}
    ]
    conds, vals = ["1=1"], {}
    if filters.get("from_date"):
        conds.append("enquiry_date>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("enquiry_date<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    grp = "channel" if filters.get("group_by")=="Channel" else "category"
    rows = frappe.db.sql(f'''select coalesce({grp},'(none)') category, count(*) total,
        sum(status='Open') open_n, sum(status='In Progress') inprog,
        sum(status='Resolved') resolved
        from `tabClient Enquiry` where {" and ".join(conds)}
        group by category order by total desc''', vals, as_dict=True)
    for r in rows:
        r["res_pct"] = (flt(r["resolved"])/r["total"]*100) if r["total"] else 0
    data = rows
    return columns, data
