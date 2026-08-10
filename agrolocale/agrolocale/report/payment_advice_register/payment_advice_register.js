frappe.query_reports['Payment Advice Register'] = {
    "filters": [
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nAwaiting Verification\nRecorded\nRejected"},
        {"fieldname": "subscriber", "label": "Subscriber", "fieldtype": "Link", "options": "Customer"},
        {"fieldname": "mode_of_payment", "label": "Mode", "fieldtype": "Link", "options": "Mode of Payment"},
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"}
    ]
};
