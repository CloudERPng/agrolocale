frappe.query_reports['Cultivation Cycle Profitability'] = {
    "filters": [
        {"fieldname": "cultivation_cycle", "label": "Cycle", "fieldtype": "Link", "options": "Cultivation Cycle"},
        {"fieldname": "farm", "label": "Farm", "fieldtype": "Link", "options": "Farm Estate"},
        {"fieldname": "crop", "label": "Crop", "fieldtype": "Link", "options": "Crop"}
    ]
};
