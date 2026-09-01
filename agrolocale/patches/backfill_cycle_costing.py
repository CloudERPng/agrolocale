import frappe


def execute():
    """Cycles and programmes created before the farm had a warehouse/cost centre
    were stamped blank. Pull the values down now."""
    if "agrolocale" not in frappe.get_installed_apps():
        return
    if not frappe.db.table_exists("Cultivation Cycle"):
        return

    for prog in frappe.get_all("Cultivation Programme",
            filters={"docstatus": ["<", 2]}, fields=["name", "farm", "warehouse", "cost_center"]):
        if prog.warehouse and prog.cost_center:
            continue
        farm = frappe.db.get_value("Farm Estate", prog.farm,
            ["default_warehouse", "cost_center"], as_dict=True) or {}
        vals = {}
        if not prog.warehouse and farm.get("default_warehouse"):
            vals["warehouse"] = farm["default_warehouse"]
        if not prog.cost_center and farm.get("cost_center"):
            vals["cost_center"] = farm["cost_center"]
        if vals:
            frappe.db.set_value("Cultivation Programme", prog.name, vals, update_modified=False)

    for cyc in frappe.get_all("Cultivation Cycle",
            filters={"docstatus": ["<", 2]},
            fields=["name", "farm", "cultivation_programme", "warehouse", "cost_center"]):
        if cyc.warehouse and cyc.cost_center:
            continue
        wh, cc = cyc.warehouse, cyc.cost_center
        if cyc.cultivation_programme:
            prog = frappe.db.get_value("Cultivation Programme", cyc.cultivation_programme,
                ["warehouse", "cost_center"], as_dict=True) or {}
            wh = wh or prog.get("warehouse")
            cc = cc or prog.get("cost_center")
        if (not wh or not cc) and cyc.farm:
            farm = frappe.db.get_value("Farm Estate", cyc.farm,
                ["default_warehouse", "cost_center"], as_dict=True) or {}
            wh = wh or farm.get("default_warehouse")
            cc = cc or farm.get("cost_center")
        vals = {}
        if wh and wh != cyc.warehouse:
            vals["warehouse"] = wh
        if cc and cc != cyc.cost_center:
            vals["cost_center"] = cc
        if vals:
            frappe.db.set_value("Cultivation Cycle", cyc.name, vals, update_modified=False)

    frappe.db.commit()
