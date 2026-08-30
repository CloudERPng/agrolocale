frappe.query_reports["Programme Profitability"] = {
    "filters": [
        {"fieldname": "cultivation_programme", "label": "Batch", "fieldtype": "Link",
         "options": "Cultivation Programme"},
        {"fieldname": "farm", "label": "Farm", "fieldtype": "Link", "options": "Farm Estate"}
    ]
};
