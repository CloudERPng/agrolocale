frappe.query_reports['Intake Documentation Compliance'] = {
    "filters": [
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nDraft\nWith Customer Care\nWith Accounts\nProcessed\nReturned to Sales"},
        {"fieldname": "only_incomplete", "label": "Only incomplete", "fieldtype": "Check", "default": 1}
    ]
};
