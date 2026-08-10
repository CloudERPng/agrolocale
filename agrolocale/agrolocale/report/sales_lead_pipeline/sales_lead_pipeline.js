frappe.query_reports['Sales Lead Pipeline'] = {
    "filters": [
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nNew\nContacted\nQualified\nConverted\nLost"},
        {"fieldname": "source", "label": "Source", "fieldtype": "Select", "options": "\nRealtor\nReferral\nSocial Media\nSite Visit\nWalk-in\nOther"},
        {"fieldname": "realtor", "label": "Realtor", "fieldtype": "Data"},
        {"fieldname": "interested_estate", "label": "Estate", "fieldtype": "Link", "options": "Farm Estate"},
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"}
    ]
};
