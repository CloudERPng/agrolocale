frappe.query_reports['Cultivation Subscriptions'] = {
    "filters": [
        {"fieldname": "cultivation_cycle", "label": "Cycle", "fieldtype": "Link", "options": "Cultivation Cycle"},
        {"fieldname": "crop", "label": "Crop", "fieldtype": "Link", "options": "Crop"},
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nSubscribed\nCultivating\nHarvested\nSettled"}
    ]
};
