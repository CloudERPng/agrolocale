frappe.query_reports['Cultivation Cycle Summary'] = {
    "filters": [
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nOpen\nCultivating\nHarvesting\nSettled\nClosed"},
        {"fieldname": "crop", "label": "Crop", "fieldtype": "Link", "options": "Crop"}
    ]
};
