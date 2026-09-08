import frappe


def execute():
    """Batches and cycles that finished before this fix left their subscriptions in a
    live state, so the entitlement cap still counted them and subscribers could not
    commit their land to a new batch. Release them."""
    if "agrolocale" not in frappe.get_installed_apps():
        return

    live = ["Subscribed", "Cultivating", "Harvested"]

    # 1. Subscriptions on closed / settled batches
    if frappe.db.table_exists("Programme Subscription"):
        closed = frappe.get_all("Cultivation Programme",
            filters={"status": ["in", ["Settled", "Closed"]]}, pluck="name")
        for prog in closed:
            for ps in frappe.get_all("Programme Subscription",
                    filters={"cultivation_programme": prog, "docstatus": 1,
                             "status": ["in", live]}, pluck="name"):
                frappe.db.set_value("Programme Subscription", ps, "status", "Settled",
                                    update_modified=False)

    # 2. Cultivation subscriptions on cycles that are closed, or fully settled
    if frappe.db.table_exists("Cultivation Subscription"):
        done_cycles = set(frappe.get_all("Cultivation Cycle",
            filters={"status": ["in", ["Settled", "Closed", "Closed \u2013 No Harvest"]]},
            pluck="name"))
        for hs in frappe.get_all("Harvest Settlement", filters={"docstatus": 1},
                fields=["name", "cultivation_cycle"]):
            rows = frappe.get_all("Harvest Allocation",
                filters={"parent": hs.name}, fields=["payout_status"])
            if rows and all(r.payout_status == "Settled" for r in rows):
                done_cycles.add(hs.cultivation_cycle)
        for cyc in done_cycles:
            for cs in frappe.get_all("Cultivation Subscription",
                    filters={"cultivation_cycle": cyc, "docstatus": 1,
                             "status": ["in", live]}, pluck="name"):
                frappe.db.set_value("Cultivation Subscription", cs, "status", "Settled",
                                    update_modified=False)

    frappe.db.commit()
