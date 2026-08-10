frappe.query_reports['Client Enquiry Log'] = {
    "filters": [
        {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "\nOpen\nIn Progress\nResolved"},
        {"fieldname": "category", "label": "Category", "fieldtype": "Select", "options": "\nPayments\nAllocation & Documents\nCultivation\nHarvest & Payouts\nResale / Transfer\nGeneral"},
        {"fieldname": "channel", "label": "Channel", "fieldtype": "Select", "options": "\nPhone\nWhatsApp\nEmail\nWalk-in\nSocial Media"},
        {"fieldname": "subscriber", "label": "Subscriber", "fieldtype": "Link", "options": "Customer"},
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"}
    ]
};
