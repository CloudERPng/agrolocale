import frappe
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = [
        {'label': 'Intake', 'fieldname': 'name', 'fieldtype': 'Link', 'width': 130, 'options': 'Subscription Intake'},
        {'label': 'Subscriber', 'fieldname': 'full_name', 'fieldtype': 'Data', 'width': 170},
        {'label': 'Status', 'fieldname': 'status', 'fieldtype': 'Data', 'width': 140},
        {'label': 'Form', 'fieldname': 'has_form', 'fieldtype': 'Data', 'width': 70},
        {'label': 'FAQ', 'fieldname': 'has_faq', 'fieldtype': 'Data', 'width': 70},
        {'label': 'ID', 'fieldname': 'has_id', 'fieldtype': 'Data', 'width': 70},
        {'label': 'Photo', 'fieldname': 'has_photo', 'fieldtype': 'Data', 'width': 80},
        {'label': 'Missing', 'fieldname': 'missing', 'fieldtype': 'Data', 'width': 240}
    ]
    conds, vals = ["1=1"], {}
    if filters.get("status"): conds.append("status=%(status)s"); vals["status"]=filters["status"]
    rows = frappe.db.sql(f'''select name, full_name, status, subscription_form, faq_signed,
        id_document, passport_photo from `tabSubscription Intake`
        where {" and ".join(conds)} order by modified desc''', vals, as_dict=True)
    data = []
    for r in rows:
        pairs = [("Form","subscription_form"),("Signed FAQ","faq_signed"),
                 ("ID","id_document"),("Photo","passport_photo")]
        missing = [lbl for lbl,fn in pairs if not r.get(fn)]
        if filters.get("only_incomplete") and not missing:
            continue
        data.append({"name":r["name"],"full_name":r["full_name"],"status":r["status"],
            "has_form":"Yes" if r["subscription_form"] else "No",
            "has_faq":"Yes" if r["faq_signed"] else "No",
            "has_id":"Yes" if r["id_document"] else "No",
            "has_photo":"Yes" if r["passport_photo"] else "No",
            "missing":", ".join(missing) or "\u2014"})
    return columns, data
