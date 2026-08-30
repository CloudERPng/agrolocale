frappe.query_reports['Farm Input Consumption'] = {
    "filters": [
        {"fieldname": "cultivation_cycle", "label": "Cycle", "fieldtype": "Link", "options": "Cultivation Cycle"},
        {"fieldname": "warehouse", "label": "Farm Warehouse", "fieldtype": "Link", "options": "Warehouse"},
        {"fieldname": "item_group", "label": "Item Group", "fieldtype": "Link", "options": "Item Group"},
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"}
    ]
};
