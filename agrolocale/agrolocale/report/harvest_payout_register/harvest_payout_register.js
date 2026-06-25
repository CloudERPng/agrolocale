frappe.query_reports['Harvest Payout Register'] = {
    "filters": [
        {"fieldname": "cultivation_cycle", "label": "Cycle", "fieldtype": "Link", "options": "Cultivation Cycle"},
        {"fieldname": "payout_status", "label": "Payout Status", "fieldtype": "Select", "options": "\nPending\nPaid"}
    ]
};
