app_name = "agrolocale"
app_title = "Agrolocale"
app_publisher = "Olamide"
app_description = "Land sales and cultivation (yield-share) management for ERPNext"
app_email = "you@example.com"
app_license = "MIT"
required_apps = ["erpnext"]

doc_events = {
    "Payment Entry": {
        "on_submit": "agrolocale.events.payment_entry_on_submit",
        "on_cancel": "agrolocale.events.payment_entry_on_cancel",
    }
}

scheduler_events = {
    "daily": [
        "agrolocale.tasks.process_installment_aging",
    ]
}

# fixtures = ["Estate Price Band", "Crop"]  # uncomment to ship master data
