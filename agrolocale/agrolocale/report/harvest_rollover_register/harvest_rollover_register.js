frappe.query_reports['Harvest Rollover Register'] = {
    "filters": [
        {"fieldname": "farm", "label": "Farm / Estate", "fieldtype": "Link", "options": "Farm Estate"},
        {"fieldname": "cultivation_programme", "label": "Batch", "fieldtype": "Link", "options": "Cultivation Programme"},
        {"fieldname": "subscriber", "label": "Subscriber", "fieldtype": "Link", "options": "Customer"},
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nAvailable\nPartially Redeemed\nRedeemed"},
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"}
    ]
};
