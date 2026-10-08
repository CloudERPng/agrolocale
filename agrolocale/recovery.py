"""One-off recovery for completion invoices cancelled by the nightly aging job.

Background
----------
`recompute_subscription` used to read the Sales Order's `advance_paid` as the
amount received. Once the completion Sales Invoice was submitted with
`allocate_advances_automatically`, ERPNext moved the Payment Entry references
from the order to the invoice and `advance_paid` fell to zero. The next nightly
run therefore read the contract as unpaid and cancelled the invoice - as
Administrator, across every fully-paid subscription in turn.

The logic is fixed in `events.py`. This module repairs the damage already done.
A cancelled document cannot be un-cancelled in Frappe, so each one is amended
into a fresh submitted invoice carrying the same lines, dates and cost centre.

Run the audit first, then the repair:

    bench --site agro.clouderp.one execute agrolocale.recovery.audit_cancelled_invoices
    bench --site agro.clouderp.one execute agrolocale.recovery.restore_cancelled_invoices
"""

import frappe
from frappe.utils import flt


def _candidates():
    """Cancelled Sales Invoices that were raised by the completion routine.

    The subscription link is read two ways. The `plot_subscription` field on the
    invoice is the direct one, but the old cancel routine also blanked
    `sales_invoice` on the subscription, so for anything raised before that field
    was stamped the only surviving trail is the Sales Order on the invoice lines.
    Both are tried, so nothing is missed."""
    return frappe.db.sql("""
        select si.name,
               coalesce(nullif(si.plot_subscription, ''), ps2.name) as plot_subscription,
               si.posting_date, si.customer,
               coalesce(si.rounded_total, si.grand_total) as total,
               si.modified, si.modified_by
        from `tabSales Invoice` si
        left join (
            select distinct sii.parent, ps.name
            from `tabSales Invoice Item` sii
            join `tabPlot Subscription` ps
              on ps.sales_order = sii.sales_order and ps.docstatus = 1
            where ifnull(sii.sales_order, '') != ''
        ) ps2 on ps2.parent = si.name
        where si.docstatus = 2
          and coalesce(nullif(si.plot_subscription, ''), ps2.name) is not null
          and not exists (
              select 1 from `tabSales Invoice` x
              where x.amended_from = si.name and x.docstatus in (0, 1))
        order by si.posting_date, si.name
    """, as_dict=True)


def _split_duplicates(rows):
    """Separate the invoices to restore from the loop's re-issues.

    Cancelling the invoice also blanked `sales_invoice` on the subscription and
    released the advances back to the Sales Order, so the contract read as
    fully-paid-and-uninvoiced again and a REPLACEMENT invoice was raised the next
    day - which the job then cancelled too. A subscription can therefore appear
    several times here, but it is owed exactly one invoice.

    The earliest is kept: it was raised on the day the contract actually
    completed, which is the right revenue date. The rest are artefacts and must
    stay cancelled, or the subscriber is billed twice."""
    keep, dupes = {}, []
    for r in sorted(rows, key=lambda x: (str(x.posting_date), x.name)):
        sub = r.plot_subscription
        if sub in keep:
            dupes.append(r)
        else:
            keep[sub] = r
    return list(keep.values()), dupes


def audit_cancelled_invoices():
    """Report what would be restored. Changes nothing."""
    rows = _candidates()
    if not rows:
        print("No cancelled completion invoices found. Nothing to restore.")
        return rows

    keep, dupes = _split_duplicates(rows)

    print(f"{len(rows)} cancelled completion invoice(s) found.\n")
    print(f"TO RESTORE - {len(keep)} invoice(s), one per subscription:")
    print(f"{'Invoice':<24} {'Subscription':<18} {'Date':<12} {'Total':>16}  Cancelled by")
    print("-" * 100)
    for r in sorted(keep, key=lambda x: (str(x.posting_date), x.name)):
        print(f"{r.name:<24} {(r.plot_subscription or ''):<18} {str(r.posting_date):<12} "
              f"{flt(r.total):>16,.2f}  {r.modified_by} on {r.modified}")
    print("-" * 100)
    print(f"{'TOTAL TO RESTORE':<56} {sum(flt(r.total) for r in keep):>16,.2f}\n")

    if dupes:
        print(f"TO LEAVE CANCELLED - {len(dupes)} replacement invoice(s) the loop raised")
        print("after cancelling the first one. Restoring these would bill the subscriber twice.")
        print("-" * 100)
        for r in sorted(dupes, key=lambda x: (str(x.posting_date), x.name)):
            print(f"{r.name:<24} {(r.plot_subscription or ''):<18} {str(r.posting_date):<12} "
                  f"{flt(r.total):>16,.2f}  duplicate of this subscription's earlier invoice")
        print("-" * 100)
        print(f"{'TOTAL LEFT CANCELLED':<56} {sum(flt(r.total) for r in dupes):>16,.2f}\n")

    print("Run restore_cancelled_invoices to amend and resubmit the first list only.")
    return rows


def restore_cancelled_invoices(limit=None):
    """Amend each cancelled completion invoice into a new submitted one and
    re-link it to its subscription. Safe to re-run: anything already amended is
    skipped by the candidate query."""
    all_rows = _candidates()
    rows, dupes = _split_duplicates(all_rows)
    rows.sort(key=lambda x: (str(x.posting_date), x.name))
    if limit:
        rows = rows[: int(limit)]
    if not rows:
        print("Nothing to restore.")
        return

    if dupes:
        print(f"Leaving {len(dupes)} duplicate re-issue(s) cancelled "
              f"({sum(flt(d.total) for d in dupes):,.2f}): "
              + ", ".join(d.name for d in dupes) + "\n")

    restored, skipped, failed = [], [], []

    for r in rows:
        sub_name = r.plot_subscription
        try:
            if not sub_name or not frappe.db.exists("Plot Subscription", sub_name):
                skipped.append((r.name, "subscription missing"))
                continue

            current = frappe.db.get_value("Plot Subscription", sub_name, "sales_invoice")
            if current and frappe.db.get_value("Sales Invoice", current, "docstatus") == 1:
                skipped.append((r.name, f"already invoiced by {current}"))
                continue

            old = frappe.get_doc("Sales Invoice", r.name)
            new = frappe.copy_doc(old)
            new.amended_from = r.name
            new.docstatus = 0
            new.set_posting_time = 1
            new.posting_date = old.posting_date
            new.due_date = old.due_date
            new.plot_subscription = sub_name
            new.allocate_advances_automatically = 1
            # copy_doc carries the advance table over from the cancelled document;
            # it is rebuilt on submit from what the order currently holds.
            new.set("advances", [])
            new.insert(ignore_permissions=True)
            new.submit()

            frappe.db.set_value("Plot Subscription", sub_name, "sales_invoice", new.name)
            frappe.db.commit()
            restored.append((r.name, new.name, flt(r.total)))
            print(f"  restored {r.name} -> {new.name}  ({flt(r.total):,.2f})")

        except Exception as e:
            frappe.db.rollback()
            failed.append((r.name, str(e)[:160]))
            frappe.log_error(frappe.get_traceback(), f"Agrolocale: restore failed {r.name}")
            print(f"  FAILED  {r.name}: {str(e)[:160]}")

    print("\n" + "=" * 70)
    print(f"Restored: {len(restored)}   Skipped: {len(skipped)}   Failed: {len(failed)}")
    if restored:
        print(f"Value restored: {sum(x[2] for x in restored):,.2f}")
    for name, why in skipped:
        print(f"  skipped {name}: {why}")
    for name, why in failed:
        print(f"  failed  {name}: {why}")
    if failed:
        print("\nFailed ones are usually a closed accounting period or a changed "
              "item/account. Fix the cause and re-run - restored invoices are skipped.")


def resync_subscriptions():
    """Recompute every submitted subscription with the corrected paid-amount
    logic, so schedules and statuses stop showing the invoiced contracts as
    unpaid. Posts no accounting entries."""
    from agrolocale.events import recompute_subscription

    names = frappe.get_all("Plot Subscription",
        filters={"docstatus": 1, "sales_order": ["is", "set"]}, pluck="name")
    ok = 0
    for name in names:
        try:
            recompute_subscription(name)
            ok += 1
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Agrolocale: resync failed {name}")
            print(f"  failed {name}")
    frappe.db.commit()
    print(f"Resynced {ok} of {len(names)} subscriptions.")
