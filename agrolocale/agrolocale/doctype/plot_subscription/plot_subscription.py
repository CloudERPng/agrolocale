import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, getdate, add_days, add_months, nowdate
from agrolocale.utils import ensure_item


class PlotSubscription(Document):
    PLAN_MONTHS = {"Outright (0-3M)": 3, "4-6M": 6, "7-12M": 12}

    def validate(self):
        if not self.sold_units:
            frappe.throw("Add at least one row in Sold Units.")
        self.compute_totals()
        if not self.payment_schedule:
            self.build_payment_schedule()

    def default_installments(self):
        return cint(self.number_of_installments) or self.PLAN_MONTHS.get(self.payment_plan, 1)

    def build_payment_schedule(self):
        """Spread the contract value over equal monthly installments per the payment plan."""
        total = flt(self.total_contract_value)
        if total <= 0:
            return
        n = max(1, self.default_installments())
        start = getdate(self.first_installment_date or self.posting_date or nowdate())
        self.set("payment_schedule", [])
        per = flt(total / n, 2)
        running = 0.0
        for i in range(n):
            amt = per if i < n - 1 else flt(total - running, 2)
            running += amt
            self.append("payment_schedule", {
                "due_date": add_months(start, i),
                "amount": amt,
                "amount_paid": 0,
                "outstanding": amt,
                "status": "Pending",
            })

    @frappe.whitelist()
    def regenerate_payment_schedule(self):
        """Rebuild the installment rows, discarding manual edits."""
        if self.docstatus != 0:
            frappe.throw("The schedule can only be rebuilt while the subscription is a draft.")
        self.compute_totals()
        self.build_payment_schedule()
        self.save()
        return True

    def compute_totals(self):
        ppa = flt(frappe.db.get_value("Farm Estate", self.estate, "plots_per_acre")) or 1
        mult = {"Plot": 1, "Acre": ppa, "5 Acres": 5 * ppa, "10 Acres": 10 * ppa}
        total_plots, land_value = 0, 0.0
        for u in self.sold_units:
            pc = cint(u.qty) * mult.get(u.unit_type, 1)
            u.plot_count = pc
            u.line_total = flt(u.qty) * flt(u.rate)
            total_plots += pc
            land_value += u.line_total
        self.total_plot_count = total_plots
        self.land_value = land_value
        self.total_contract_value = land_value + flt(self.developmental_fee) + flt(self.legal_documentation_fee)

    def before_submit(self):
        self.compute_totals()
        if cint(self.total_plot_count) <= 0:
            frappe.throw("No units sold.")
        available = frappe.get_all("Land Plot",
            filters={"estate": self.estate, "status": "Available"},
            order_by="source_acquisition asc, plot_number asc",
            limit_page_length=cint(self.total_plot_count), pluck="name")
        if len(available) < cint(self.total_plot_count):
            frappe.throw(f"Only {len(available)} plots available in {self.estate}; this transaction needs {self.total_plot_count}.")
        ppa = flt(frappe.db.get_value("Farm Estate", self.estate, "plots_per_acre")) or 1
        mult = {"Plot": 1, "Acre": ppa, "5 Acres": 5 * ppa, "10 Acres": 10 * ppa}
        mapping, idx = [], 0
        for u in self.sold_units:
            label = "Plot" if u.unit_type == "Plot" else f"Part of {u.unit_type}"
            for _ in range(cint(u.qty) * mult.get(u.unit_type, 1)):
                mapping.append((available[idx], label)); idx += 1
        so = frappe.get_doc({
            "doctype": "Sales Order", "customer": self.subscriber,
            "transaction_date": self.posting_date, "delivery_date": self.posting_date,
            "order_type": "Sales", "items": [], "payment_schedule": [],
        })
        for u in self.sold_units:
            rate = flt(u.rate) * (1.2 if (u.is_corner_piece and u.unit_type == "Plot") else 1.0)
            so.append("items", {"item_code": ensure_item(f"Land - {u.unit_type} - {self.estate}"),
                                "qty": u.qty, "rate": rate})
        if flt(self.developmental_fee):
            so.append("items", {"item_code": ensure_item("Developmental Fee"), "qty": 1, "rate": self.developmental_fee})
        if flt(self.legal_documentation_fee):
            so.append("items", {"item_code": ensure_item("Legal Documentation"), "qty": 1, "rate": self.legal_documentation_fee})
        for s in self.payment_schedule:
            so.append("payment_schedule", {"due_date": s.due_date, "payment_amount": s.amount})
        so.insert(ignore_permissions=True)
        so.submit()
        self.sales_order = so.name
        self.set("allocated_plots", [])
        for plot_name, sold_as in mapping:
            frappe.db.set_value("Land Plot", plot_name, {
                "status": "Reserved", "current_subscriber": self.subscriber,
                "plot_subscription": self.name, "sold_as": sold_as})
            self.append("allocated_plots", {"land_plot": plot_name, "sold_as": sold_as})

    def on_cancel(self):
        for ap in self.allocated_plots:
            frappe.db.set_value("Land Plot", ap.land_plot, {
                "status": "Available", "current_subscriber": None,
                "plot_subscription": None, "sold_as": None})
        if self.sales_order and frappe.db.get_value("Sales Order", self.sales_order, "docstatus") == 1:
            so = frappe.get_doc("Sales Order", self.sales_order)
            so.flags.ignore_links = True
            so.cancel()
