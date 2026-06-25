import frappe
from frappe.utils import flt, getdate, nowdate


def _subs_from_payment(doc):
    so_names = set()
    for ref in (doc.references or []):
        if ref.reference_doctype == "Sales Order" and ref.reference_name:
            so_names.add(ref.reference_name)
    subs = set()
    for so in so_names:
        s = frappe.db.get_value("Plot Subscription", {"sales_order": so, "docstatus": 1}, "name")
        if s:
            subs.add(s)
    return subs


def payment_entry_on_submit(doc, method=None):
    for sub in _subs_from_payment(doc):
        recompute_subscription(sub)


def payment_entry_on_cancel(doc, method=None):
    for sub in _subs_from_payment(doc):
        recompute_subscription(sub)


def recompute_subscription(sub_name):
    """Update installment statuses and allocation status of a Plot Subscription
    from how much has been paid against its Sales Order. On full payment, post a
    completion Sales Invoice (queued); on reversal, cancel it."""
    sub = frappe.db.get_value("Plot Subscription", sub_name,
        ["sales_order", "subscription_status", "sales_invoice"], as_dict=True)
    if not sub or not sub.sales_order:
        return

    so = frappe.db.get_value("Sales Order", sub.sales_order,
        ["advance_paid", "rounded_total", "grand_total"], as_dict=True)
    paid = flt(so.advance_paid)
    total = flt(so.rounded_total) or flt(so.grand_total)
    today = getdate(nowdate())

    # Installment statuses, oldest-first against the amount paid.
    rows = frappe.get_all("Land Payment Schedule",
        filters={"parent": sub_name, "parenttype": "Plot Subscription"},
        fields=["name", "due_date", "amount"], order_by="idx asc")
    remaining = paid
    for r in rows:
        amt = flt(r.amount)
        if amt > 0 and remaining >= amt:
            status = "Paid"
            remaining -= amt
        elif r.due_date and getdate(r.due_date) < today:
            status = "Overdue"
        else:
            status = "Pending"
        frappe.db.set_value("Land Payment Schedule", r.name, "status", status)

    fully_paid = bool(total and paid >= total)

    if fully_paid:
        if sub.subscription_status != "Allocated":
            frappe.db.set_value("Plot Subscription", sub_name, "subscription_status", "Allocated")
            for lp in frappe.get_all("Land Plot", {"plot_subscription": sub_name}, pluck="name"):
                frappe.db.set_value("Land Plot", lp, "status", "Allocated")
        if not sub.sales_invoice:
            # Post the revenue-recognising invoice out-of-band so it can never
            # roll back or block the payment that triggered it.
            frappe.enqueue("agrolocale.events.create_completion_invoice",
                           queue="short", enqueue_after_commit=True, sub_name=sub_name)
    else:
        if sub.subscription_status == "Allocated":
            frappe.db.set_value("Plot Subscription", sub_name, "subscription_status", "Active")
            for lp in frappe.get_all("Land Plot",
                    {"plot_subscription": sub_name, "status": "Allocated"}, pluck="name"):
                frappe.db.set_value("Land Plot", lp, "status", "Reserved")
        if sub.sales_invoice:
            cancel_completion_invoice(sub_name, sub.sales_invoice)


def create_completion_invoice(sub_name):
    """Create and submit a Sales Invoice from the subscription's Sales Order when
    the contract is fully paid, auto-allocating the advance payments so the
    invoice is settled. Safe to run repeatedly \u2013 it no-ops if already invoiced."""
    sub = frappe.db.get_value("Plot Subscription", sub_name,
        ["sales_order", "sales_invoice", "subscription_status"], as_dict=True)
    if not sub or not sub.sales_order or sub.sales_invoice or sub.subscription_status != "Allocated":
        return
    try:
        from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
        si = make_sales_invoice(sub.sales_order)
        si.allocate_advances_automatically = 1   # pulls the installment advances
        si.insert(ignore_permissions=True)
        si.submit()
        frappe.db.set_value("Plot Subscription", sub_name, "sales_invoice", si.name)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Agrolocale: completion invoice failed")


def cancel_completion_invoice(sub_name, si_name):
    try:
        if frappe.db.get_value("Sales Invoice", si_name, "docstatus") == 1:
            si = frappe.get_doc("Sales Invoice", si_name)
            si.flags.ignore_links = True
            si.cancel()
        frappe.db.set_value("Plot Subscription", sub_name, "sales_invoice", None)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Agrolocale: completion invoice cancel failed")
