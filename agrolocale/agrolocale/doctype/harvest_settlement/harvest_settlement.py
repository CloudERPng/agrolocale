import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class HarvestSettlement(Document):
    def validate(self):
        self.compute_split()

    def compute_split(self):
        """Apportion the ACTUAL gross revenue across subscribers by their share of
        the recorded yield. Each row's payout is a slice of the real money earned,
        never an independent yield x price calculation, so the rows always sum to
        the gross revenue."""
        share = flt(frappe.db.get_value("Cultivation Cycle", self.cultivation_cycle,
                                        "company_share_pct")) or 20
        price = flt(self.actual_sale_price_per_kg)

        self.gross_revenue = flt(flt(self.actual_total_yield_kg) * price, 2)
        self.company_share = flt(self.gross_revenue * share / 100, 2)
        self.subscriber_pool = flt(self.gross_revenue - self.company_share, 2)

        rows = list(self.allocations or [])
        total_weight = sum(flt(a.yield_kg) for a in rows)
        if not rows or not total_weight:
            for a in rows:
                a.share_pct = a.gross = a.company_cut = a.subscriber_payout = 0
            return

        running = 0.0
        for i, a in enumerate(rows):
            a.share_pct = flt(flt(a.yield_kg) / total_weight * 100, 4)
            if i < len(rows) - 1:
                a.gross = flt(self.gross_revenue * flt(a.yield_kg) / total_weight, 2)
            else:
                a.gross = flt(self.gross_revenue - running, 2)   # last row absorbs rounding
            running += flt(a.gross)
            a.company_cut = flt(flt(a.gross) * share / 100, 2)
            a.subscriber_payout = flt(flt(a.gross) - flt(a.company_cut), 2)

        if abs(total_weight - flt(self.actual_total_yield_kg)) > 0.01:
            frappe.msgprint(
                f"Allocated yield ({total_weight:,.2f} kg) differs from the actual total "
                f"({flt(self.actual_total_yield_kg):,.2f} kg). The gross revenue has still been "
                "shared in proportion to each subscriber's allocated yield. Use "
                "<b>Distribute Yield by Entitlement</b> to match the actual total exactly.",
                indicator="orange", title="Yield does not match actual")

    @frappe.whitelist()
    def distribute_yield(self):
        """Split the actual total yield across subscribers in proportion to the
        expected yield of their cultivation subscriptions."""
        if not flt(self.actual_total_yield_kg):
            frappe.throw("Enter the Actual Total Yield (kg) first.")
        exp = {}
        for a in self.allocations:
            if a.cultivation_subscription:
                exp[a.name] = flt(frappe.db.get_value(
                    "Cultivation Subscription", a.cultivation_subscription, "expected_yield_kg"))
        total_exp = sum(exp.values())
        if not total_exp:
            frappe.throw("No expected yield found. Ensure the rows link to Cultivation "
                         "Subscriptions that have an expected yield.")
        actual = flt(self.actual_total_yield_kg)
        for a in self.allocations:
            if a.name in exp:
                a.yield_kg = flt(actual * exp[a.name] / total_exp, 2)
        self.compute_split()
        self.save()
        return True

    def on_submit(self):
        if not self.off_taker:
            frappe.throw("Select the Off-taker (buyer of the harvest) before submitting.")
        s = get_settings()
        if not s or not s.get("auto_post_harvest_revenue"):
            frappe.msgprint("Harvest computed. Configure Agrolocale Settings to raise the "
                            "off-taker invoice automatically.", indicator="orange")
            return
        self.create_offtaker_invoice(s)

    def create_offtaker_invoice(self, s=None):
        """Bill the off-taker for the full harvest value, then reclass the
        subscribers' 80% out of income into Subscriber Harvest Payable. Cash from
        the off-taker arrives later via a normal Payment Entry against the invoice."""
        s = s or get_settings()
        missing = _missing_accounts(s, ["subscriber_harvest_payable_account",
                                        "cultivation_commission_income_account"])
        if missing:
            frappe.msgprint("Cannot raise the off-taker invoice — set these in Agrolocale "
                            "Settings: " + ", ".join(missing), indicator="orange")
            return
        if self.off_taker_invoice or not flt(self.gross_revenue):
            return
        from agrolocale.utils import ensure_item
        crop = frappe.db.get_value("Cultivation Cycle", self.cultivation_cycle, "crop")
        si = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": self.off_taker,
            "company": s.get("company"),
            "items": [{
                "item_code": ensure_item(f"Harvest Sale - {crop}"),
                "qty": flt(self.actual_total_yield_kg) or 1,
                "rate": flt(self.actual_sale_price_per_kg)
                        if flt(self.actual_total_yield_kg) else flt(self.gross_revenue),
                "income_account": s["cultivation_commission_income_account"],
            }],
        })
        si.insert(ignore_permissions=True)
        si.submit()
        self.db_set("off_taker_invoice", si.name)

        # Reclass the subscribers' share out of income into the payable.
        je = frappe.get_doc({
            "doctype": "Journal Entry", "voucher_type": "Journal Entry",
            "posting_date": nowdate(), "company": s.get("company"),
            "user_remark": f"Reclass of subscribers' 80% for {self.name} "
                           f"({self.cultivation_cycle})",
            "accounts": [
                {"account": s["cultivation_commission_income_account"],
                 "debit_in_account_currency": flt(self.subscriber_pool)},
                {"account": s["subscriber_harvest_payable_account"],
                 "credit_in_account_currency": flt(self.subscriber_pool)},
            ],
        })
        je.insert(ignore_permissions=True)
        je.submit()
        self.db_set("revenue_journal_entry", je.name)
        frappe.msgprint(f"Off-taker invoiced ({si.name}) and the 80% moved to Subscriber "
                        f"Harvest Payable ({je.name}). Record the off-taker's payment "
                        "against the invoice when it arrives.",
                        indicator="green", title="Harvest revenue recorded")

    @frappe.whitelist()
    def get_pending_allocations(self):
        """Rows still owed money, with what remains outstanding on each."""
        out = []
        for a in self.allocations:
            outstanding = flt(flt(a.subscriber_payout) - flt(a.paid_amount) - flt(a.rollover_amount), 2)
            if outstanding > 0.005:
                out.append({"name": a.name, "subscriber": a.subscriber,
                            "outstanding": outstanding})
        return out

    @frappe.whitelist()
    def settle_payouts(self, settlements, mode_of_payment=None, posting_date=None, narration=None):
        """Settle selected subscribers, each with a cash portion and/or a rollover
        portion. `settlements` is a list of {name, pay_now, rollover}. Cash posts one
        bank Journal Entry; rollovers create Cultivation Credit records (the value
        stays in Subscriber Harvest Payable until redeemed against a future cycle)."""
        import json as _json
        if isinstance(settlements, str):
            settlements = _json.loads(settlements)
        if self.docstatus != 1:
            frappe.throw("Submit the Harvest Settlement before settling payouts.")

        s = get_settings()
        rows = {a.name: a for a in self.allocations}
        cash_lines, total_cash, credits_made, touched = [], 0.0, [], []

        for item in settlements:
            a = rows.get(item.get("name"))
            if not a:
                continue
            pay_now = flt(item.get("pay_now"))
            rollover = flt(item.get("rollover"))
            if pay_now < 0 or rollover < 0:
                frappe.throw(f"Amounts for {a.subscriber} cannot be negative.")
            if pay_now + rollover <= 0:
                continue
            outstanding = flt(flt(a.subscriber_payout) - flt(a.paid_amount) - flt(a.rollover_amount), 2)
            if flt(pay_now + rollover, 2) > outstanding + 0.005:
                frappe.throw(f"{a.subscriber}: pay-now + rollover ({pay_now + rollover:,.2f}) "
                             f"exceeds the outstanding {outstanding:,.2f}.")
            if pay_now > 0:
                cash_lines.append((a, pay_now))
                total_cash += pay_now
            if rollover > 0:
                credits_made.append((a, rollover))
            touched.append((a, pay_now, rollover))

        if not touched:
            frappe.msgprint("Nothing to settle — enter a pay-now or rollover amount for at least one subscriber.")
            return

        je_name = None
        if cash_lines:
            if not mode_of_payment:
                frappe.throw("Choose a Mode of Payment for the cash portion.")
            missing = _missing_accounts(s, ["subscriber_harvest_payable_account"])
            if missing:
                frappe.throw("Set these in Agrolocale Settings first: " + ", ".join(missing))
            from agrolocale.utils import get_mode_of_payment_account
            pay_account = (get_mode_of_payment_account(mode_of_payment, s.get("company"))
                           or (s or {}).get("harvest_proceeds_account"))
            if not pay_account:
                frappe.throw(f"Mode of Payment {mode_of_payment} has no default account for "
                             "the company, and no fallback Harvest Proceeds Account is set.")
            accounts = [{
                "account": s["subscriber_harvest_payable_account"],
                "party_type": "Customer", "party": a.subscriber,
                "debit_in_account_currency": flt(amt, 2),
                "user_remark": f"Harvest payout to {a.subscriber}",
            } for a, amt in cash_lines]
            accounts.append({"account": pay_account,
                             "credit_in_account_currency": flt(total_cash, 2)})
            pdate = posting_date or nowdate()
            je = frappe.get_doc({
                "doctype": "Journal Entry", "voucher_type": "Bank Entry",
                "posting_date": pdate, "company": s.get("company"),
                "cheque_no": narration or f"Harvest payout – {self.name}",
                "cheque_date": pdate,
                "mode_of_payment": mode_of_payment,
                "user_remark": narration or f"Harvest payouts for {self.name}",
                "accounts": accounts,
            })
            je.insert(ignore_permissions=True)
            je.submit()
            je_name = je.name

        for a, amt in credits_made:
            cr = frappe.get_doc({
                "doctype": "Cultivation Credit",
                "subscriber": a.subscriber,
                "source_settlement": self.name,
                "credit_date": nowdate(),
                "amount": flt(amt, 2),
            })
            cr.insert(ignore_permissions=True)
            cr.submit()

        for a, pay_now, rollover in touched:
            new_paid = flt(flt(a.paid_amount) + pay_now, 2)
            new_roll = flt(flt(a.rollover_amount) + rollover, 2)
            outstanding = flt(flt(a.subscriber_payout) - new_paid - new_roll, 2)
            status = "Settled" if outstanding <= 0.005 else "Partially Settled"
            frappe.db.set_value("Harvest Allocation", a.name, {
                "paid_amount": new_paid, "rollover_amount": new_roll,
                "payout_status": status})

        if je_name:
            self.db_set("payout_journal_entry", je_name)
        self.reload()

        bits = []
        if cash_lines:
            bits.append(f"paid {len(cash_lines)} subscriber(s) {total_cash:,.2f} in cash"
                        + (f" (JE {je_name})" if je_name else ""))
        if credits_made:
            bits.append(f"created {len(credits_made)} cultivation credit(s) totalling "
                        f"{sum(flt(x) for _, x in credits_made):,.2f}")
        frappe.msgprint("Settlement complete — " + "; ".join(bits) + ".",
                        indicator="green", title="Payouts settled")
        return True

def get_settings():
    try:
        return frappe.get_cached_doc("Agrolocale Settings").as_dict()
    except Exception:
        return {}


def _missing_accounts(s, keys):
    labels = {
        "harvest_proceeds_account": "Harvest Proceeds Account",
        "subscriber_harvest_payable_account": "Subscriber Harvest Payable Account",
        "cultivation_commission_income_account": "Cultivation Commission Income Account",
    }
    return [labels[k] for k in keys if not (s or {}).get(k)]


@frappe.whitelist()
def get_cycle_subscribers(cultivation_cycle, actual_total_yield_kg=0):
    """Subscribers enrolled in a cycle, with a suggested yield share. If an actual
    total yield is given, it is split by each subscriber's expected-yield weight."""
    all_subs = frappe.get_all("Cultivation Subscription",
        filters={"cultivation_cycle": cultivation_cycle, "docstatus": 1,
                 "status": ["in", ["Subscribed", "Cultivating", "Harvested"]]},
        fields=["name", "subscriber", "expected_yield_kg", "setup_invoice"])
    subs, skipped = [], []
    for cs in all_subs:
        inv = frappe.db.get_value("Sales Invoice", cs.setup_invoice,
            ["docstatus", "outstanding_amount"], as_dict=True) if cs.setup_invoice else None
        if inv and inv.docstatus == 1 and flt(inv.outstanding_amount) <= 0.005:
            subs.append(cs)
        else:
            skipped.append(cs.subscriber)
    if skipped:
        frappe.msgprint("Excluded (setup fee not fully paid): " + ", ".join(sorted(set(skipped))),
                        indicator="orange", title="Some subscribers do not qualify")
    total_expected = sum(flt(s.expected_yield_kg) for s in subs)
    actual = flt(actual_total_yield_kg)
    out = []
    for s in subs:
        if actual and total_expected:
            y = flt(actual * flt(s.expected_yield_kg) / total_expected, 2)
        else:
            y = flt(s.expected_yield_kg)
        out.append({"subscriber": s.subscriber, "cultivation_subscription": s.name, "yield_kg": y})
    return out
