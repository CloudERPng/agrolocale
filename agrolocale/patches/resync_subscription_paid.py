"""Recompute every subscription with the corrected paid-amount logic.

The old logic read only the Sales Order's `advance_paid`, which empties out when
the completion invoice absorbs the advances. Every invoiced subscription was
therefore left showing a zero `schedule_paid` and Overdue installments. This
rewrites those figures. It posts no accounting entries and creates nothing.
"""

import frappe


def execute():
    from agrolocale.events import recompute_subscription

    names = frappe.get_all("Plot Subscription",
        filters={"docstatus": 1, "sales_order": ["is", "set"]}, pluck="name")
    for name in names:
        try:
            recompute_subscription(name)
        except Exception:
            frappe.log_error(frappe.get_traceback(),
                             f"Agrolocale: paid resync failed for {name}")
    frappe.db.commit()
