import frappe
from frappe.model.document import Document
from frappe.utils import flt


REQUIRED_DOCS = [
    ("subscription_form", "Subscription Form"),
    ("faq_signed", "Signed FAQ"),
    ("id_document", "Means of Identification"),
]


class SubscriptionIntake(Document):
    def validate(self):
        if not self.existing_customer and not self.full_name:
            frappe.throw("Enter the subscriber's Full Name, or link an existing Customer.")
        self.apply_pricing()

    def apply_pricing(self):
        """Rates and fees always come from the Estate Price Band — never typed in.
        Runs on every save so the figures cannot drift from the published price list."""
        if not self.estate or not self.payment_plan:
            return
        ppa = flt(frappe.db.get_value("Farm Estate", self.estate, "plots_per_acre")) or 1
        mult = {"Plot": 1, "Acre": ppa, "5 Acres": 5 * ppa, "10 Acres": 10 * ppa}

        total_plots, land_value = 0, 0.0
        for u in (self.sold_units or []):
            band = frappe.db.get_value("Estate Price Band",
                {"estate": self.estate, "payment_plan": self.payment_plan,
                 "unit_type": u.unit_type},
                ["price", "developmental_fee", "legal_documentation_fee"], as_dict=True)
            if not band:
                frappe.throw(f"No Estate Price Band found for {self.estate} – {u.unit_type} – "
                             f"{self.payment_plan}. Ask Accounts to add the price before continuing.")
            rate = flt(band.price) * (1.2 if (u.is_corner_piece and u.unit_type == "Plot") else 1.0)
            u.rate = rate
            u.line_total = flt(u.qty) * rate
            u.plot_count = int(flt(u.qty) * mult.get(u.unit_type, 1))
            total_plots += u.plot_count
            land_value += u.line_total

        # Header fees follow the Plot band for the chosen plan
        head = frappe.db.get_value("Estate Price Band",
            {"estate": self.estate, "payment_plan": self.payment_plan, "unit_type": "Plot"},
            ["developmental_fee", "legal_documentation_fee"], as_dict=True) or {}
        self.developmental_fee = flt(head.get("developmental_fee"))
        self.legal_documentation_fee = flt(head.get("legal_documentation_fee"))
        self.land_value = flt(land_value, 2)
        self.total_plot_count = total_plots
        self.total_contract_value = flt(land_value + flt(self.developmental_fee)
                                        + flt(self.legal_documentation_fee), 2)

    # ---------- Customer Care ----------
    @frappe.whitelist()
    def send_to_accounts(self):
        """Customer Care verifies the bundle and routes it to Accounts."""
        missing = [label for fn, label in REQUIRED_DOCS if not self.get(fn)]
        if missing:
            frappe.throw("Attach the following before sending to Accounts: " + ", ".join(missing))
        if not self.sold_units:
            frappe.throw("Add at least one row in Units (what the subscriber is buying).")
        if not self.receipts:
            frappe.throw("Add at least one receipt, or note in Customer Care Notes why none is attached.")
        unverified = [r.idx for r in self.receipts if not r.verified]
        if unverified:
            frappe.throw(f"Tick Verified on receipt row(s) {', '.join(map(str, unverified))} "
                         "after checking them against the bank record.")
        self.db_set("status", "With Accounts")
        self.notify_accounts()
        frappe.msgprint("Sent to Accounts for processing.", indicator="green")

    def notify_accounts(self):
        email = (frappe.get_cached_value("Agrolocale Settings", None, "accounts_email") or "").strip()
        if not email:
            return
        try:
            total = flt(sum(flt(r.amount) for r in self.receipts))
            frappe.sendmail(
                recipients=[e.strip() for e in email.split(",") if e.strip()],
                subject=f"Subscription intake ready for processing \u2013 {self.name}",
                message=(f"<p>A subscription intake has been verified by Customer Care and is "
                         f"ready for processing.</p>"
                         f"<p><b>Subscriber:</b> {self.full_name or self.existing_customer}<br>"
                         f"<b>Estate:</b> {self.estate}<br>"
                         f"<b>Payment plan:</b> {self.payment_plan}<br>"
                         f"<b>Receipts attached:</b> {len(self.receipts)} totalling {total:,.2f}</p>"
                         f"<p>Open it in CloudERP.One to process.</p>"),
                reference_doctype=self.doctype, reference_name=self.name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Agrolocale: intake notification failed")

    @frappe.whitelist()
    def return_to_sales(self, reason):
        if not reason:
            frappe.throw("Enter what needs to be corrected.")
        self.db_set("return_reason", reason)
        self.db_set("status", "Returned to Sales")

    @frappe.whitelist()
    def start_review(self):
        self.db_set("status", "With Customer Care")

    # ---------- Accounts ----------
    @frappe.whitelist()
    def process(self):
        """Accounts turns the verified bundle into a Customer (if new) and a
        draft Plot Subscription, pre-filled \u2014 nothing is retyped."""
        if self.plot_subscription:
            frappe.throw(f"Already processed as {self.plot_subscription}.")
        if self.status != "With Accounts":
            frappe.throw("This intake has not been verified and sent by Customer Care yet.")

        customer = self.existing_customer
        if not customer:
            customer = frappe.db.get_value("Customer", {"customer_name": self.full_name})
        if not customer:
            cust = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": self.full_name,
                "customer_type": "Individual",
                "customer_group": _default("Customer Group", "customer_group_name"),
                "territory": _default("Territory", "territory_name"),
            })
            cust.insert(ignore_permissions=True)
            customer = cust.name
            if self.mobile or self.email:
                try:
                    contact = frappe.get_doc({
                        "doctype": "Contact", "first_name": self.full_name,
                        "mobile_no": self.mobile, "email_id": self.email,
                        "links": [{"link_doctype": "Customer", "link_name": customer}],
                    })
                    contact.insert(ignore_permissions=True)
                except Exception:
                    frappe.log_error(frappe.get_traceback(), "Agrolocale: contact creation failed")

        sub = frappe.get_doc({
            "doctype": "Plot Subscription",
            "subscriber": customer,
            "estate": self.estate,
            "payment_plan": self.payment_plan,
            "posting_date": frappe.utils.nowdate(),
            "realtor": self.realtor,
            "realtor_group": self.realtor_group,
            "developmental_fee": flt(self.developmental_fee),
            "legal_documentation_fee": flt(self.legal_documentation_fee),
            "sold_units": [{"unit_type": u.unit_type, "qty": u.qty,
                            "is_corner_piece": u.is_corner_piece, "rate": u.rate}
                           for u in self.sold_units],
        })
        sub.insert(ignore_permissions=True)

        self.db_set("customer", customer)
        self.db_set("plot_subscription", sub.name)
        self.db_set("status", "Processed")
        frappe.msgprint(
            f"Created draft Plot Subscription {sub.name} for {customer}. Review the rates and "
            "installments, then submit it. Afterwards use <b>Record Receipts</b> here to post "
            "the payments that came with the form.",
            indicator="green", title="Intake processed")
        return sub.name

    @frappe.whitelist()
    def record_receipts(self):
        """Post the verified receipts as payments against the created subscription."""
        if not self.plot_subscription:
            frappe.throw("Process the intake first.")
        sub = frappe.get_doc("Plot Subscription", self.plot_subscription)
        if sub.docstatus != 1:
            frappe.throw(f"Submit {sub.name} before recording its payments.")
        done = 0
        for r in self.receipts:
            if r.payment_entry or not flt(r.amount) or not r.verified:
                continue
            pe = sub.receive_payment(
                amount=flt(r.amount),
                mode_of_payment=r.mode_of_payment,
                posting_date=r.receipt_date,
                reference_no=r.bank_reference or f"Intake {self.name}",
            )
            frappe.db.set_value("Intake Receipt", r.name, "payment_entry", pe)
            done += 1
        self.reload()
        frappe.msgprint(f"Recorded {done} payment(s) against {sub.name}."
                        if done else "No new verified receipts to record.",
                        indicator="green" if done else "orange")


def _default(doctype, field):
    return (frappe.db.get_value(doctype, {"is_group": 0}, "name")
            or frappe.db.get_value(doctype, {}, "name"))
