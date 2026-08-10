from frappe import _


def get_data():
    return {
        "fieldname": "subscription_intake",
        "non_standard_fieldnames": {
            "Plot Subscription": "name",
            "Customer": "name",
        },
        "transactions": [
            {"label": _("Outcome"), "items": ["Plot Subscription", "Customer"]},
        ],
    }
