frappe.query_reports['Subscription Intake Pipeline'] = {
    "filters": [
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nDraft\nWith Customer Care\nWith Accounts\nProcessed\nReturned to Sales"},
        {"fieldname": "estate", "label": "Estate", "fieldtype": "Link", "options": "Farm Estate"}
    ]
};
