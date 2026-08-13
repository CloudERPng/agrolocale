import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Stage', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 170},
        {'label': 'Count', 'fieldname': 'cnt', 'fieldtype': 'Int', 'width': 90},
        {'label': 'Avg Days in Stage', 'fieldname': 'avg_days', 'fieldtype': 'Float', 'width': 150},
        {'label': 'Oldest (days)', 'fieldname': 'max_days', 'fieldtype': 'Int', 'width': 120},
        {'label': 'Contract Value in Stage', 'fieldname': 'value', 'fieldtype': 'Currency', 'width': 170}
    ]
    rows = frappe.db.sql('''select i.status,
        count(*) cnt, avg(datediff(curdate(), date(i.modified))) avg_days,
        max(datediff(curdate(), date(i.modified))) max_days,
        coalesce(sum(i.total_contract_value),0) value
        from `tabSubscription Intake` i
        where i.status not in ('Processed')
        group by i.status order by cnt desc''', as_dict=True)
    data = rows
    return columns, data
