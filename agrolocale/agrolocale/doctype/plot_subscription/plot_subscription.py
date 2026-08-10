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
        self.schedule_total = total
        self.schedule_paid = 0
        self.schedule_outstanding = total
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

    def apply_price_band(self):
        """Rates and fees are always taken from the Estate Price Band so they cannot
        be edited on the form. Blank the estate/plan to price manually is not allowed."""
        if not self.estate or not self.payment_plan:
            return
        for u in (self.sold_units or []):
            band = frappe.db.get_value("Estate Price Band",
                {"estate": self.estate, "payment_plan": self.payment_plan,
                 "unit_type": u.unit_type}, "price")
            if band is None:
                frappe.throw(f"No Estate Price Band for {self.estate} – {u.unit_type} – "
                             f"{self.payment_plan}. Add the price band row first.")
            u.rate = flt(band) * (1.2 if (u.is_corner_piece and u.unit_type == "Plot") else 1.0)
        head = frappe.db.get_value("Estate Price Band",
            {"estate": self.estate, "payment_plan": self.payment_plan, "unit_type": "Plot"},
            ["developmental_fee", "legal_documentation_fee"], as_dict=True) or {}
        self.developmental_fee = flt(head.get("developmental_fee"))
        self.legal_documentation_fee = flt(head.get("legal_documentation_fee"))

    def compute_totals(self):
        self.apply_price_band()
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
            "order_type": "Sales", "plot_subscription": self.name,
        "items": [], "payment_schedule": [],
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

    @frappe.whitelist()
    def get_so_outstanding(self):
        if not self.sales_order:
            return 0
        so = frappe.db.get_value("Sales Order", self.sales_order,
            ["advance_paid", "rounded_total", "grand_total"], as_dict=True)
        total = flt(so.rounded_total) or flt(so.grand_total)
        return flt(total - flt(so.advance_paid), 2)

    @frappe.whitelist()
    def receive_payment(self, amount, mode_of_payment, posting_date=None, reference_no=None):
        """Create and submit a Payment Entry against this subscription's Sales Order.
        Validates the amount against the order's outstanding balance."""
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
        from agrolocale.utils import get_mode_of_payment_account

        if self.docstatus != 1 or not self.sales_order:
            frappe.throw("Submit the subscription first — payments are recorded against its Sales Order.")
        amount = flt(amount)
        if amount <= 0:
            frappe.throw("Enter an amount greater than zero.")
        outstanding = self.get_so_outstanding()
        if amount > outstanding + 0.005:
            frappe.throw(f"Amount ({amount:,.2f}) exceeds the outstanding balance on "
                         f"{self.sales_order} ({outstanding:,.2f}).")

        pe = get_payment_entry("Sales Order", self.sales_order)
        pe.posting_date = posting_date or nowdate()
        pe.mode_of_payment = mode_of_payment
        acc = get_mode_of_payment_account(mode_of_payment, pe.company)
        if acc:
            pe.paid_to = acc
        pe.paid_amount = amount
        pe.received_amount = amount
        for ref in pe.references:
            if ref.reference_name == self.sales_order:
                ref.allocated_amount = amount
        pe.reference_no = reference_no or f"Installment – {self.name}"
        pe.reference_date = pe.posting_date
        pe.plot_subscription = self.name
        pe.insert(ignore_permissions=True)
        pe.submit()
        frappe.msgprint(f"Payment Entry {pe.name} recorded for {amount:,.2f}.",
                        indicator="green", title="Payment received")
        return pe.name
