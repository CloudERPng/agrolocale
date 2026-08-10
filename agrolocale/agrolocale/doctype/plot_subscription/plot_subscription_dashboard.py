from frappe import _


def get_data():
    return {
        "fieldname": "plot_subscription",
        "transactions": [
            {"label": _("Sales & Payments"), "items": ["Sales Order", "Payment Entry", "Sales Invoice"]},
            {"label": _("Client Service"), "items": ["Payment Advice", "Client Enquiry"]},
        ],
    }
