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


def get_subscription_paid(sub_name, sub=None):
    """Total cash received against a subscription's contract, and the contract total.

    Reading the Sales Order's `advance_paid` on its own is WRONG once the
    completion invoice exists. When that Sales Invoice is submitted with
    `allocate_advances_automatically`, ERPNext moves the Payment Entry references
    off the Sales Order and onto the invoice, then recomputes `advance_paid` -
    which collapses to zero. A fully-paid contract then looks completely unpaid
    the day after it is invoiced.

    Adding what the invoice itself has settled (grand total less outstanding)
    keeps the figure stable across that hand-over: whatever leaves `advance_paid`
    arrives in the invoice, so the sum does not move.

    Returns (paid, total). Both are 0 when there is no usable Sales Order, which
    callers should read as "nothing to judge" rather than "nothing was paid".
    """
    if sub is None:
        sub = frappe.db.get_value("Plot Subscription", sub_name,
            ["sales_order", "sales_invoice"], as_dict=True)
    if not sub or not sub.sales_order:
        return 0.0, 0.0

    so = frappe.db.get_value("Sales Order", sub.sales_order,
        ["advance_paid", "rounded_total", "grand_total", "docstatus"], as_dict=True)
    if not so or so.docstatus != 1:
        # Deleted, draft or cancelled order - nothing reliable to measure against.
        return 0.0, 0.0

    total = flt(so.rounded_total) or flt(so.grand_total)
    paid = flt(so.advance_paid)

    if sub.get("sales_invoice"):
        si = frappe.db.get_value("Sales Invoice", sub.sales_invoice,
            ["rounded_total", "grand_total", "outstanding_amount", "docstatus"], as_dict=True)
        if si and si.docstatus == 1:
            si_total = flt(si.rounded_total) or flt(si.grand_total)
            paid += flt(si_total) - flt(si.outstanding_amount)

    return flt(paid, 2), flt(total, 2)


def recompute_subscription(sub_name):
    """Update installment statuses and allocation status of a Plot Subscription
    from how much has been paid against its contract. On full payment, post a
    completion Sales Invoice (queued).

    This routine NEVER cancels a submitted Sales Invoice. It runs unattended from
    the nightly aging job as Administrator, and a submitted invoice is a tax
    document: if the numbers stop agreeing, that is for a person to look at."""
    sub = frappe.db.get_value("Plot Subscription", sub_name,
        ["sales_order", "subscription_status", "sales_invoice"], as_dict=True)
    if not sub or not sub.sales_order:
        return

    if not frappe.db.exists("Sales Order", sub.sales_order):
        # The order was deleted. Leave the schedule untouched rather than crashing
        # the nightly job or the payment that triggered this.
        return

    paid, total = get_subscription_paid(sub_name, sub)
    if not total:
        return
    today = getdate(nowdate())

    # Installment statuses, oldest-first against the amount paid.
    rows = frappe.get_all("Land Payment Schedule",
        filters={"parent": sub_name, "parenttype": "Plot Subscription"},
        fields=["name", "due_date", "amount"], order_by="idx asc")
    # Cascade the paid amount down the rows: a row can be fully covered (Paid),
    # partially covered (Partly Paid), or untouched (Pending / Overdue if past due).
    remaining = paid
    for r in rows:
        amt = flt(r.amount)
        applied = min(amt, max(remaining, 0))
        remaining = flt(remaining - applied, 2)
        outstanding = flt(amt - applied, 2)
        if amt <= 0 or outstanding <= 0.005:
            status, outstanding, applied = "Paid", 0, amt
        elif applied > 0.005:
            status = "Partly Paid"
        elif r.due_date and getdate(r.due_date) < today:
            status = "Overdue"
        else:
            status = "Pending"
        frappe.db.set_value("Land Payment Schedule", r.name, {
            "amount_paid": flt(applied, 2),
            "outstanding": outstanding,
            "status": status})

    sched_total = flt(sum(flt(r.amount) for r in rows), 2)
    frappe.db.set_value("Plot Subscription", sub_name, {
        "schedule_total": sched_total,
        "schedule_paid": flt(min(paid, sched_total), 2),
        "schedule_outstanding": flt(max(sched_total - paid, 0), 2)})

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
    elif sub.sales_invoice:
        # An invoice has already been raised, so the contract was complete at some
        # point. The balance moving now means a payment was reversed, amended or
        # reallocated - all of which need a human decision. Flag it; change nothing.
        flag_invoice_shortfall(sub_name, sub.sales_invoice, paid, total)
    else:
        if sub.subscription_status == "Allocated":
            frappe.db.set_value("Plot Subscription", sub_name, "subscription_status", "Active")
            for lp in frappe.get_all("Land Plot",
                    {"plot_subscription": sub_name, "status": "Allocated"}, pluck="name"):
                frappe.db.set_value("Land Plot", lp, "status", "Reserved")


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
        si.plot_subscription = sub_name
        si.allocate_advances_automatically = 1
        # Carry the estate's cost centre onto the revenue lines so land income can be
        # filtered by estate on the P&L.
        cc = frappe.db.get_value("Plot Subscription", sub_name, "cost_center")
        if cc:
            si.cost_center = cc
            for row in si.get("items", []):
                if not row.cost_center:
                    row.cost_center = cc   # pulls the installment advances
        si.insert(ignore_permissions=True)
        si.submit()
        frappe.db.set_value("Plot Subscription", sub_name, "sales_invoice", si.name)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Agrolocale: completion invoice failed")


def flag_invoice_shortfall(sub_name, si_name, paid, total):
    """Record that an invoiced subscription no longer looks fully paid, and leave
    everything exactly as it is.

    This replaces an earlier routine that cancelled the Sales Invoice outright.
    That was wrong twice over: it destroyed a submitted tax document on the
    strength of a derived balance, and it ran unattended from the nightly job as
    Administrator, so a single bad reading cancelled invoices in bulk overnight.
    Accounting corrections are reversed by a person, with a credit note."""
    shortfall = flt(total) - flt(paid)
    if shortfall <= 0.005:
        return

    # One comment per shortfall amount, so the nightly job does not re-post the
    # same note every day.
    marker = f"agrolocale-shortfall:{si_name}:{shortfall:.2f}"
    if frappe.db.exists("Comment", {"reference_doctype": "Plot Subscription",
                                    "reference_name": sub_name,
                                    "content": ["like", f"%{marker}%"]}):
        return
    try:
        frappe.get_doc({
            "doctype": "Comment", "comment_type": "Comment",
            "reference_doctype": "Plot Subscription", "reference_name": sub_name,
            "content": (
                f"<b>Payment shortfall after invoicing.</b> {si_name} was raised when this "
                f"contract was fully paid, but the amount received now reads "
                f"{paid:,.2f} against a contract value of {total:,.2f} "
                f"(short by {shortfall:,.2f}).<br><br>"
                "Usually a Payment Entry was cancelled, amended or reallocated. "
                "The invoice has been left submitted and untouched &mdash; reverse it with a "
                "credit note if that is genuinely what is needed. "
                f"<!-- {marker} -->"),
        }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Agrolocale: shortfall flag failed")
