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
    def make_material_issue(self):
        """Pre-filled Material Issue for this cycle: right warehouse, cost centre
        and project already set, so staff cannot forget to tag the cost."""
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
    and project."""
    cycle = frappe.get_doc("Cultivation Cycle", source_name)
    if not cycle.warehouse:
        frappe.throw("Set the Farm Warehouse on this cycle (or on the farm) first.")
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Issue"
    se.purpose = "Material Issue"
    se.from_warehouse = cycle.warehouse
    se.project = cycle.project
    se.posting_date = nowdate()
    se.remarks = f"Farm inputs issued to {cycle.name} ({cycle.crop})"
    for row in se.get("items", []):
        row.cost_center = cycle.cost_center
    return se
