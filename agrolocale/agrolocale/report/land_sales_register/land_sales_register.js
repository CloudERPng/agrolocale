frappe.query_reports['Land Sales Register'] = {
    "filters": [
        {"fieldname": "estate", "label": "Estate", "fieldtype": "Link", "options": "Farm Estate"},
        {"fieldname": "subscription_status", "label": "Status", "fieldtype": "Select", "options": "\nActive\nIn Default\nAllocated\nRevoked\nRefunded"},
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"}
    ]
};
