import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class CultivationCycle(Document):

    def validate(self):
        """Crops are grouped into a batch because they share a cultivation window.
        A crop whose harvest falls well outside the batch's window is almost always
        the wrong crop or the wrong batch."""
        if not self.cultivation_programme:
            return
        prog = frappe.db.get_value("Cultivation Programme", self.cultivation_programme,
            ["harvest_start", "harvest_end", "programme_name"], as_dict=True)
        if not prog or not self.harvest_start or not self.harvest_end:
            return
        from frappe.utils import getdate, date_diff
        drift = max(abs(date_diff(getdate(self.harvest_start), getdate(prog.harvest_start))),
                    abs(date_diff(getdate(self.harvest_end), getdate(prog.harvest_end))))
        if drift > 45:
            frappe.msgprint(
                f"This crop's harvest window differs from batch {prog.programme_name} by "
                f"about {drift} days. Crops are batched so they harvest together and pay out "
                "once \u2014 check the crop or the batch is correct.",
                indicator="orange", title="Harvest window differs from the batch")
    def on_submit(self):
        self.create_project()

    def create_project(self):
        """One Project per cycle. Every cost and every income document for this
        batch is tagged to it, so profitability is answerable per batch."""
        if self.project:
            return
        try:
            prj = frappe.get_doc({
                "doctype": "Project",
                "project_name": f"{self.batch_name} – {self.crop} ({self.season or ''})".strip(),
                "status": "Open",
                "expected_start_date": self.cultivation_start,
                "expected_end_date": self.harvest_end,
                "cost_center": self.cost_center,
                "company": frappe.defaults.get_user_default("Company"),
            })
            prj.insert(ignore_permissions=True)
            self.db_set("project", prj.name)
            frappe.msgprint(f"Project {prj.name} created for this cycle. Tag all material "
                            "issues to it so the batch's costs are captured.",
                            indicator="green")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Agrolocale: cycle project creation failed")

    @frappe.whitelist()
    def refresh_input_cost(self):
        """Total value of stock issued to this cycle's project."""
        if not self.project:
            return 0
        total = frappe.db.sql("""
            select coalesce(sum(sed.amount), 0)
            from `tabStock Entry Detail` sed
            join `tabStock Entry` se on se.name = sed.parent
            where se.docstatus = 1 and se.project = %s
        """, self.project)[0][0]
        self.db_set("total_input_cost", flt(total, 2))
        return flt(total, 2)

    @frappe.whitelist()
    def sync_costing_defaults(self):
        """Pull the warehouse and cost centre down from the programme or the farm.
        Useful for cycles created before the farm was fully configured."""
        wh, cc = _resolve_costing(self)
        if not wh:
            frappe.throw(f"No Farm Warehouse found. Set it on the Farm Estate "
                         f"({self.farm or 'no farm set'}) or directly on this cycle.")
        frappe.msgprint(f"Warehouse set to {wh}" + (f", cost centre {cc}" if cc else "") + ".",
                        indicator="green")
        return {"warehouse": wh, "cost_center": cc}

    @frappe.whitelist()
    def _unused_make_material_issue(self):
        if not self.warehouse:
            frappe.throw("Set the Farm Warehouse on this cycle (or on the farm) first.")
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Issue"
        se.purpose = "Material Issue"
        se.from_warehouse = self.warehouse
        se.project = self.project
        se.posting_date = nowdate()
        se.remarks = f"Farm inputs issued to {self.name} ({self.crop})"
        return se.as_dict()


@frappe.whitelist()
def make_material_issue(source_name, target_doc=None):
    """Open a Material Issue pre-tagged with the cycle's warehouse, cost centre
    and project. Falls back to the farm's defaults if the cycle was created before
    the farm was configured."""
    cycle = frappe.get_doc("Cultivation Cycle", source_name)
    warehouse, cost_center = _resolve_costing(cycle)
    if not warehouse:
        frappe.throw(
            "No Farm Warehouse could be found for this cycle.<br><br>"
            "Set <b>Farm Warehouse</b> on the Farm Estate "
            f"(<b>{cycle.farm or 'no farm set on this cycle'}</b>), then reopen this cycle "
            "\u2014 or set the warehouse directly on the cycle, which is editable.")
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Issue"
    se.purpose = "Material Issue"
    se.from_warehouse = warehouse
    se.project = cycle.project
    se.posting_date = nowdate()
    se.remarks = f"Farm inputs issued to {cycle.name} ({cycle.crop})"
    for row in se.get("items", []):
        row.cost_center = cost_center
    return se


def _resolve_costing(cycle):
    """Warehouse and cost centre from the cycle, else the programme, else the farm.
    Writes them back so the next issue does not have to look them up again."""
    warehouse, cost_center = cycle.warehouse, cycle.cost_center
    if not warehouse or not cost_center:
        if cycle.get("cultivation_programme"):
            prog = frappe.db.get_value("Cultivation Programme", cycle.cultivation_programme,
                ["warehouse", "cost_center"], as_dict=True) or {}
            warehouse = warehouse or prog.get("warehouse")
            cost_center = cost_center or prog.get("cost_center")
    if (not warehouse or not cost_center) and cycle.get("farm"):
        farm = frappe.db.get_value("Farm Estate", cycle.farm,
            ["default_warehouse", "cost_center"], as_dict=True) or {}
        warehouse = warehouse or farm.get("default_warehouse")
        cost_center = cost_center or farm.get("cost_center")
    if warehouse and warehouse != cycle.warehouse:
        cycle.db_set("warehouse", warehouse)
    if cost_center and cost_center != cycle.cost_center:
        cycle.db_set("cost_center", cost_center)
    return warehouse, cost_center
