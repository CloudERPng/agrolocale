frappe.query_reports['Lead Conversion Summary'] = {
    "filters": [
        {"fieldname": "group_by", "label": "Group By", "fieldtype": "Select", "options": "Source\nRealtor", "default": "Source"},
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"}
    ]
};
