import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = [
        {"label": "Batch", "fieldname": "programme", "fieldtype": "Link",
         "options": "Cultivation Programme", "width": 140},
        {"label": "Crop", "fieldname": "crop", "fieldtype": "Link", "options": "Crop", "width": 110},
        {"label": "Cycle", "fieldname": "cycle", "fieldtype": "Link",
         "options": "Cultivation Cycle", "width": 140},
        {"label": "Cycle Status", "fieldname": "status", "fieldtype": "Data", "width": 130},
        {"label": "Setup Income", "fieldname": "setup_income", "fieldtype": "Currency", "width": 130},
        {"label": "Commission (20%)", "fieldname": "commission", "fieldtype": "Currency", "width": 150},
        {"label": "Total Income", "fieldname": "total_income", "fieldtype": "Currency", "width": 130},
        {"label": "Input Cost", "fieldname": "input_cost", "fieldtype": "Currency", "width": 120},
        {"label": "Gross Margin", "fieldname": "margin", "fieldtype": "Currency", "width": 130},
        {"label": "Margin %", "fieldname": "margin_pct", "fieldtype": "Percent", "width": 100},
        {"label": "Yield", "fieldname": "yield_kg", "fieldtype": "Float", "width": 100},
    ]
    conds, vals = ["p.docstatus=1"], {}
    if filters.get("cultivation_programme"):
        conds.append("p.name=%(cultivation_programme)s")
        vals["cultivation_programme"] = filters["cultivation_programme"]
    if filters.get("farm"):
        conds.append("p.farm=%(farm)s"); vals["farm"] = filters["farm"]

    progs = frappe.db.sql(f"""select p.name, p.programme_name from `tabCultivation Programme` p
        where {" and ".join(conds)} order by p.name desc""", vals, as_dict=True)

    data = []
    for p in progs:
        cycles = frappe.get_all("Cultivation Cycle",
            filters={"cultivation_programme": p["name"], "docstatus": 1},
            fields=["name", "crop", "status", "project"])
        p_inc = p_cost = p_yld = 0
        for c in cycles:
            setup = flt(frappe.db.sql("""select coalesce(sum(setup_fee),0) from
                `tabCultivation Subscription` where cultivation_cycle=%s and docstatus=1""",
                c["name"])[0][0])
            comm = flt(frappe.db.sql("""select coalesce(sum(company_share),0) from
                `tabHarvest Settlement` where cultivation_cycle=%s and docstatus=1""",
                c["name"])[0][0])
            yld = flt(frappe.db.sql("""select coalesce(sum(actual_total_yield_kg),0) from
                `tabHarvest Settlement` where cultivation_cycle=%s and docstatus=1""",
                c["name"])[0][0])
            inputs = 0
            if c.get("project"):
                inputs = flt(frappe.db.sql("""select coalesce(sum(sed.amount),0)
                    from `tabStock Entry Detail` sed
                    join `tabStock Entry` se on se.name=sed.parent
                    where se.docstatus=1 and se.project=%s""", c["project"])[0][0])
            inc = setup + comm
            data.append({"programme": p["name"], "crop": c["crop"], "cycle": c["name"],
                "status": c["status"], "setup_income": setup, "commission": comm,
                "total_income": inc, "input_cost": inputs, "margin": inc - inputs,
                "margin_pct": ((inc - inputs) / inc * 100) if inc else 0, "yield_kg": yld})
            p_inc += inc; p_cost += inputs; p_yld += yld
        if cycles:
            data.append({"programme": p["name"], "crop": "", "cycle": "\u2014 BATCH TOTAL \u2014",
                "status": "", "setup_income": None, "commission": None,
                "total_income": p_inc, "input_cost": p_cost, "margin": p_inc - p_cost,
                "margin_pct": ((p_inc - p_cost) / p_inc * 100) if p_inc else 0,
                "yield_kg": p_yld})
    return columns, data
