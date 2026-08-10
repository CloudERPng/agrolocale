import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Source', 'fieldname': 'source', 'fieldtype': 'Data', 'width': 140},
        {'label': 'Realtor', 'fieldname': 'realtor', 'fieldtype': 'Data', 'width': 160},
        {'label': 'Leads', 'fieldname': 'leads', 'fieldtype': 'Int', 'width': 80},
        {'label': 'Qualified', 'fieldname': 'qualified', 'fieldtype': 'Int', 'width': 90},
        {'label': 'Converted', 'fieldname': 'converted', 'fieldtype': 'Int', 'width': 95},
        {'label': 'Lost', 'fieldname': 'lost', 'fieldtype': 'Int', 'width': 80},
        {'label': 'Conversion %', 'fieldname': 'conv_pct', 'fieldtype': 'Percent', 'width': 110}
    ]
    conds, vals = ["1=1"], {}
    if filters.get("from_date"):
        conds.append("date(creation)>=%(from_date)s"); vals["from_date"]=filters["from_date"]
    if filters.get("to_date"):
        conds.append("date(creation)<=%(to_date)s"); vals["to_date"]=filters["to_date"]
    group = "realtor" if filters.get("group_by")=="Realtor" else "source"
    rows = frappe.db.sql(f'''select coalesce(nullif({group},''),'(none)') grp,
        count(*) leads, sum(status='Qualified') qualified, sum(status='Converted') converted,
        sum(status='Lost') lost
        from `tabSales Lead` where {" and ".join(conds)} group by grp order by leads desc''',
        vals, as_dict=True)
    data = []
    for r in rows:
        d = {"source": r["grp"] if group=="source" else "", "realtor": r["grp"] if group=="realtor" else "",
             "leads": r["leads"], "qualified": r["qualified"], "converted": r["converted"],
             "lost": r["lost"],
             "conv_pct": (flt(r["converted"])/r["leads"]*100) if r["leads"] else 0}
        data.append(d)
    return columns, data
