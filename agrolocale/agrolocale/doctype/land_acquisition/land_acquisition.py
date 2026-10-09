import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint
from agrolocale.utils import ensure_item


class LandAcquisition(Document):
    def on_submit(self):
        if self.plots_generated:
            frappe.throw("Plots already generated for this acquisition.")
        self.block_duplicate_amendment()
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

    def block_duplicate_amendment(self):
        """Refuse to generate a second set of plots for land already on the books.

        An acquisition cancelled before `on_cancel` existed left its plots in
        place. Amending and submitting it would generate a fresh set on top of
        them, silently doubling the estate's inventory - and the duplicates would
        look identical to the real ones."""
        if not self.amended_from:
            return
        survivors = frappe.db.count("Land Plot", {"source_acquisition": self.amended_from})
        if not survivors:
            return
        frappe.throw(
            f"{self.amended_from} still has {survivors} plot(s) on the books, so submitting "
            f"this amendment would create a second set and double {self.estate}'s inventory."
            "<br><br>"
            "If those plots are unsold, cancel them off the original first. If they are "
            "reserved or sold, leave them alone and raise a separate acquisition covering "
            "only the additional plots.")

    def on_cancel(self):
        """Undo the acquisition: remove the plots it generated, so an amendment can
        regenerate the right number.

        Plots that have left the shelf are never touched. If any plot from this
        acquisition is reserved, allocated or sold, cancelling would either strand
        a subscriber's plot or silently shrink the estate, so it is refused and the
        subscriptions are named."""
        plots = frappe.get_all("Land Plot", filters={"source_acquisition": self.name},
                               fields=["name", "status", "plot_subscription"])
        in_use = [p for p in plots if p.status not in ("Available", "Withdrawn") or p.plot_subscription]
        if in_use:
            subs = sorted({p.plot_subscription for p in in_use if p.plot_subscription})
            detail = f" Subscriptions involved: {', '.join(subs)}." if subs else ""
            frappe.throw(
                f"{len(in_use)} of the {len(plots)} plots from this acquisition are already "
                f"reserved, allocated or sold, so it cannot be cancelled.{detail}<br><br>"
                "To change the plot count, cancel the affected subscriptions first, or raise a "
                "separate acquisition for the additional plots.")

        for p in plots:
            frappe.delete_doc("Land Plot", p.name, ignore_permissions=True, force=True)

        if self.purchase_invoice:
            pi_status = frappe.db.get_value("Purchase Invoice", self.purchase_invoice, "docstatus")
            if pi_status == 0:
                frappe.delete_doc("Purchase Invoice", self.purchase_invoice,
                                  ignore_permissions=True)
            elif pi_status == 1:
                frappe.msgprint(
                    f"Purchase Invoice {self.purchase_invoice} is submitted and has been left "
                    "alone. Cancel or credit-note it separately if the land cost has changed.",
                    indicator="orange")

        self.db_set("plots_generated", 0)
        self.db_set("cost_per_plot", 0)
        frappe.msgprint(f"{len(plots)} unsold plots removed. Amend this document to "
                        "regenerate with the corrected plot count.")

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
