frappe.query_reports['Programme Subscribers'] = {
    "filters": [
        {"fieldname": "cultivation_programme", "label": "Batch", "fieldtype": "Link", "options": "Cultivation Programme"},
        {"fieldname": "farm", "label": "Farm", "fieldtype": "Link", "options": "Farm Estate"},
        {"fieldname": "crop", "label": "Crop", "fieldtype": "Link", "options": "Crop"},
        {"fieldname": "subscriber", "label": "Subscriber", "fieldtype": "Link", "options": "Customer"},
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nSubscribed\nCultivating\nHarvested\nSettled"}
    ]
};
