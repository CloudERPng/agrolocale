frappe.query_reports['Installment Aging'] = {
    "filters": [
        {"fieldname": "estate", "label": "Estate", "fieldtype": "Link", "options": "Farm Estate"},
        {"fieldname": "subscriber", "label": "Subscriber", "fieldtype": "Link", "options": "Customer"},
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nPending\nPaid\nOverdue"}
    ]
};
