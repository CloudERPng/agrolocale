import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint
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
        self.create_purchase_invoice()
        frappe.msgprint(f"{count} plots generated for {self.estate}.")

    def create_purchase_invoice(self):
        """Create a draft Purchase Invoice to the vendor for the land cost.
        Wrapped so a failure here never blocks plot generation."""
        if self.purchase_invoice or not self.vendor or flt(self.total_acquisition_cost) <= 0:
            return
        try:
            pi = frappe.get_doc({
                "doctype": "Purchase Invoice",
                "supplier": self.vendor,
                "items": [{
                    "item_code": ensure_item(f"Land Acquisition - {self.estate}"),
                    "qty": 1,
                    "rate": flt(self.total_acquisition_cost),
                }],
            })
            pi.insert(ignore_permissions=True)
            self.db_set("purchase_invoice", pi.name)
            frappe.msgprint(f"Draft Purchase Invoice {pi.name} created for {self.vendor}.")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Agrolocale: Purchase Invoice creation failed")
            frappe.msgprint("Plots were generated, but the Purchase Invoice could not be created "
                            "automatically. Create it manually or check the vendor / accounts setup.",
                            indicator="orange")
