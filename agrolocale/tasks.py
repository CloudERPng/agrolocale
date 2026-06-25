import frappe
from frappe.utils import getdate, add_days, nowdate
from agrolocale.events import recompute_subscription


def process_installment_aging():
    GRACE = 30
    DEFAULT_MONTHS = 3
    today = getdate(nowdate())

    # Keep installment + allocation statuses current for every live subscription.
    for name in frappe.get_all("Plot Subscription",
            filters={"docstatus": 1, "sales_order": ["is", "set"]}, pluck="name"):
        recompute_subscription(name)

    # Flag long-overdue subscriptions as In Default.
    rows = frappe.db.sql("""
        select so.name as so, ps.due_date
        from `tabPayment Schedule` ps
        join `tabSales Order` so on so.name = ps.parent
        where ps.outstanding > 0 and ps.due_date < %s and so.docstatus = 1
    """, (add_days(today, -GRACE),), as_dict=True)
    for r in rows:
        sub = frappe.db.get_value("Plot Subscription", {"sales_order": r.so}, "name")
        if sub and (today - getdate(r.due_date)).days > DEFAULT_MONTHS * 30:
            frappe.db.set_value("Plot Subscription", sub, "subscription_status", "In Default")
