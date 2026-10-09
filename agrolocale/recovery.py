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


# ---------------------------------------------------------------------------
# Land Acquisition cleanup
#
# `on_cancel` now removes the plots an acquisition generated, but anything
# cancelled before that existed left its plots standing. These two run the same
# logic after the fact.
# ---------------------------------------------------------------------------

def inspect_acquisition(name):
    """Show what an acquisition generated and whether it can be cleaned up."""
    acq = frappe.db.get_value("Land Acquisition", name,
        ["name", "estate", "docstatus", "number_of_plots", "hectares_acquired",
         "plots_per_hectare", "plots_generated", "purchase_invoice",
         "total_acquisition_cost"], as_dict=True)
    if not acq:
        print(f"No Land Acquisition named {name}.")
        return

    states = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
    print(f"{acq.name}  estate={acq.estate}  status={states.get(acq.docstatus)}")
    print(f"  number_of_plots={acq.number_of_plots}  hectares={acq.hectares_acquired} "
          f"x per_hectare={acq.plots_per_hectare}")
    print(f"  plots_generated={acq.plots_generated}  purchase_invoice={acq.purchase_invoice}")

    plots = frappe.get_all("Land Plot", filters={"source_acquisition": name},
                           fields=["name", "status", "plot_subscription"])
    print(f"\n  {len(plots)} plot(s) still exist from this acquisition:")
    by_status = {}
    for p in plots:
        by_status.setdefault(p.status, []).append(p)
    for status, group in sorted(by_status.items()):
        print(f"    {status:<12} {len(group)}")

    in_use = [p for p in plots if p.status not in ("Available", "Withdrawn") or p.plot_subscription]
    if in_use:
        subs = sorted({p.plot_subscription for p in in_use if p.plot_subscription})
        print(f"\n  CANNOT CLEAN UP - {len(in_use)} plot(s) are spoken for.")
        if subs:
            print(f"  Subscriptions: {', '.join(subs)}")
        print("  Raise a separate acquisition for the extra plots instead.")
    else:
        print(f"\n  SAFE TO CLEAN UP - all {len(plots)} plots are Available.")
        print(f"  Run: clean_cancelled_acquisition('{name}')")
    return acq


def clean_cancelled_acquisition(name):
    """Delete the unsold plots left behind by an acquisition that was cancelled
    before `on_cancel` existed. Refuses if any plot is spoken for."""
    acq = frappe.db.get_value("Land Acquisition", name, ["docstatus"], as_dict=True)
    if not acq:
        print(f"No Land Acquisition named {name}.")
        return
    if acq.docstatus != 2:
        print(f"{name} is not cancelled (docstatus={acq.docstatus}). "
              "Cancel it in the UI - that now cleans up by itself.")
        return

    plots = frappe.get_all("Land Plot", filters={"source_acquisition": name},
                           fields=["name", "status", "plot_subscription"])
    in_use = [p for p in plots if p.status not in ("Available", "Withdrawn") or p.plot_subscription]
    if in_use:
        subs = sorted({p.plot_subscription for p in in_use if p.plot_subscription})
        print(f"REFUSED - {len(in_use)} of {len(plots)} plots are reserved, allocated or sold.")
        if subs:
            print(f"Subscriptions: {', '.join(subs)}")
        return

    for p in plots:
        frappe.delete_doc("Land Plot", p.name, ignore_permissions=True, force=True)
    frappe.db.set_value("Land Acquisition", name,
                        {"plots_generated": 0, "cost_per_plot": 0})
    frappe.db.commit()
    print(f"Removed {len(plots)} unsold plot(s) from {name}.")
    print("Now amend the acquisition, set the correct plot count, and submit.")


def restore_cancelled_acquisition(name):
    """Return a wrongly-cancelled Land Acquisition to Submitted.

    Only valid where the cancellation had no accounting effect and the plots it
    generated are still on the books - which is the case when the acquisition
    was cancelled purely to edit the plot count. The document is put back
    exactly as it was: the plots already exist, `plots_generated` is already
    set, so nothing is re-run and nothing is created.

    Every condition is checked first and the restore is refused if any fails."""
    acq = frappe.db.get_value("Land Acquisition", name,
        ["name", "estate", "docstatus", "purchase_invoice", "total_acquisition_cost",
         "plots_generated"], as_dict=True)
    if not acq:
        print(f"No Land Acquisition named {name}.")
        return

    problems = []
    if acq.docstatus != 2:
        problems.append(f"it is not cancelled (docstatus={acq.docstatus})")

    plots = frappe.db.count("Land Plot", {"source_acquisition": name})
    if not plots:
        problems.append("it has no plots left, so there is nothing to re-parent - "
                        "raise a fresh acquisition instead")

    if acq.purchase_invoice:
        pi = frappe.db.get_value("Purchase Invoice", acq.purchase_invoice, "docstatus")
        if pi == 2:
            problems.append(f"its Purchase Invoice {acq.purchase_invoice} was cancelled too "
                            "and would need raising again by hand")

    gl = frappe.db.count("GL Entry", {"voucher_type": "Land Acquisition", "voucher_no": name})
    if gl:
        problems.append(f"it has {gl} GL entries, so the cancellation moved money")

    amended = frappe.db.get_value("Land Acquisition", {"amended_from": name}, "name")
    if amended:
        problems.append(f"it has already been amended into {amended}")

    if problems:
        print(f"REFUSED - {name} cannot be restored this way:")
        for p in problems:
            print(f"  - {p}")
        return

    frappe.db.set_value("Land Acquisition", name, "docstatus", 1)
    frappe.get_doc({
        "doctype": "Comment", "comment_type": "Comment",
        "reference_doctype": "Land Acquisition", "reference_name": name,
        "content": (
            "<b>Cancellation reversed.</b> This acquisition was cancelled while its "
            f"{plots} plots were still reserved or sold, which left them parented to a "
            "cancelled document. It has been returned to Submitted. No plots were created "
            "or removed and there was no accounting entry to reverse."),
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"{name} restored to Submitted. Its {plots} plots now have a valid parent again.")
    print("To add more plots to this estate, raise a NEW acquisition for the extra ones only.")


HELD_STATUSES = ("Reserved", "Allocated", "Sold", "Resold")


def reduce_acquisition_plots(name, new_count, delete=False):
    """Shrink an estate to `new_count` plots by taking surplus plots out of
    inventory. Never touches a plot a subscriber holds.

    Plots are marked Withdrawn by default, which keeps the record and its
    numbering intact while removing it from what can be sold. Pass delete=True
    to remove them outright, only sensible for plots created in error.

    An estate cannot shrink below the number of plots already reserved or sold.
    If it needs to, that is a commercial problem - somebody has been sold land
    that will not exist - and the subscriptions have to be unwound first."""
    new_count = int(new_count)
    acq = frappe.db.get_value("Land Acquisition", name,
        ["name", "estate", "docstatus", "number_of_plots",
         "total_acquisition_cost"], as_dict=True)
    if not acq:
        print(f"No Land Acquisition named {name}.")
        return
    if acq.docstatus == 2:
        print(f"{name} is cancelled. Restore it first with "
              f"restore_cancelled_acquisition('{name}').")
        return

    plots = frappe.get_all("Land Plot", filters={"source_acquisition": name},
                           fields=["name", "plot_number", "status", "plot_subscription"],
                           order_by="plot_number asc")
    total = len(plots)
    held = [p for p in plots if p.status in HELD_STATUSES or p.plot_subscription]
    free = [p for p in plots if p not in held and p.status == "Available"]

    print(f"{name} ({acq.estate}): {total} plot(s) on the books - "
          f"{len(held)} held, {len(free)} available.")

    if new_count >= total:
        print(f"\nNothing to do - {new_count} is not fewer than the {total} that exist.")
        print("To add plots, raise a NEW acquisition covering only the extra ones.")
        return

    surplus = total - new_count

    if new_count < len(held):
        subs = sorted({p.plot_subscription for p in held if p.plot_subscription})
        print(f"\nREFUSED - {len(held)} plot(s) are already reserved or sold, so this "
              f"estate cannot go below {len(held)} plots.")
        print(f"Going to {new_count} would strand {len(held) - new_count} subscriber(s).")
        if subs:
            print(f"\n{len(subs)} subscription(s) hold these plots:")
            for s in subs:
                cnt = sum(1 for p in held if p.plot_subscription == s)
                sub = frappe.db.get_value("Plot Subscription", s,
                    ["subscriber", "subscription_status"], as_dict=True) or {}
                print(f"  {s}  {str(sub.get('subscriber') or ''):<34} "
                      f"{sub.get('subscription_status') or '':<12} {cnt} plot(s)")
        print("\nTo go lower, those subscriptions must be cancelled or re-allocated to "
              "another estate first. That is a decision for the client, not a data fix.")
        return

    if surplus > len(free):
        print(f"\nREFUSED - {surplus} plot(s) need removing but only {len(free)} are "
              "available. Free up the difference first.")
        return

    # Take them off the end, so the numbering of the plots people hold is untouched.
    chosen = sorted(free, key=lambda p: p.plot_number or 0, reverse=True)[:surplus]
    for p in chosen:
        if delete:
            frappe.delete_doc("Land Plot", p.name, ignore_permissions=True, force=True)
        else:
            frappe.db.set_value("Land Plot", p.name, "status", "Withdrawn")

    unit = flt(acq.total_acquisition_cost) / new_count if new_count else 0
    frappe.db.set_value("Land Acquisition", name,
                        {"number_of_plots": new_count, "cost_per_plot": unit})
    frappe.get_doc({
        "doctype": "Comment", "comment_type": "Comment",
        "reference_doctype": "Land Acquisition", "reference_name": name,
        "content": (f"<b>Plot count reduced.</b> {total} &rarr; {new_count}. "
                    f"{surplus} unsold plot(s) "
                    f"{'deleted' if delete else 'marked Withdrawn'}; "
                    f"cost per plot recalculated to {unit:,.2f}."),
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    verb = "deleted" if delete else "withdrawn"
    print(f"\n{surplus} plot(s) {verb}: "
          + ", ".join(str(p.plot_number) for p in sorted(chosen, key=lambda x: x.plot_number or 0)))
    print(f"{name} now records {new_count} plot(s); cost per plot {unit:,.2f}.")
