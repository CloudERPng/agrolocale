frappe.query_reports['Enquiry Analysis'] = {
    "filters": [
        {"fieldname": "group_by", "label": "Group By", "fieldtype": "Select", "options": "Category\nChannel", "default": "Category"},
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"}
    ]
};
