import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, getdate, add_days, nowdate
from agrolocale.utils import ensure_item


class LandAcquisition(Document):
    def on_submit(self):
        if self.plots_generated:
            frappe.throw("Plots already generated for this acquisition.")
        count = cint(self.number_of_plots) or cint(flt(self.hectares_acquired) * flt(self.plots_per_hectare))
        if count <= 0:
            frappe.throw("Set Number of Plots, or Hectares x Plots per Hectare.")
        unit_cost = flt(self.total_acquisition_cost) / count if count else 0
        for i in range(1, count + 1):
            frappe.get_doc({
                "doctype": "Land Plot",
                "estate": self.estate,
                "source_acquisition": self.name,
                "plot_number": i,
                "size_sqm": self.plot_size_sqm,
                "status": "Available",
            }).insert(ignore_permissions=True)
        self.db_set("cost_per_plot", unit_cost)
        self.db_set("plots_generated", 1)
        frappe.msgprint(f"{count} plots generated for {self.estate}.")
