import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate

SETTLED_STATES = ("Settled", "Closed", "Closed \u2013 No Harvest")


class CultivationProgramme(Document):
    def validate(self):
        total = flt(sum(flt(r.share_pct) for r in (self.crop_mix or [])))
        if not self.crop_mix:
            frappe.throw("Add at least one crop to the Crop Mix.")
        if abs(total - 100) > 0.01:
            frappe.throw(f"The crop mix must total 100%. It currently totals {total:g}%.")
        crops = [r.crop for r in self.crop_mix]
        if len(crops) != len(set(crops)):
            frappe.throw("Each crop may only appear once in the mix.")
        if self.harvest_start and self.cultivation_start and \
                self.harvest_start < self.cultivation_start:
            frappe.throw("Harvest Start cannot be before Cultivation Start.")
        if self.harvest_end and self.harvest_start and self.harvest_end < self.harvest_start:
            frappe.throw("Harvest End cannot be before Harvest Start.")

    def on_submit(self):
        self.create_cycles()

    def create_cycles(self):
        """One Cultivation Cycle per crop, inheriting the batch's dates, farm and
        costing. Crops are grouped in a batch precisely because they share a
        cultivation window, so the dates come from here."""
        made = []
        for row in self.crop_mix:
            if row.cultivation_cycle:
                continue
            cyc = frappe.get_doc({
                "doctype": "Cultivation Cycle",
                "cultivation_programme": self.name,
                "batch_name": f"{self.programme_name} \u2013 {row.crop}",
                "crop": row.crop,
                "season": self.season,
                "farm": self.farm,
                "cultivation_start": self.cultivation_start,
                "harvest_start": self.harvest_start,
                "harvest_end": self.harvest_end,
                "capacity_plots": flt(self.capacity_plots) * flt(row.share_pct) / 100,
                "capacity_acres": flt(self.capacity_acres) * flt(row.share_pct) / 100,
                "warehouse": self.warehouse,
                "cost_center": self.cost_center,
                "status": "Open",
            })
            cyc.insert(ignore_permissions=True)
            cyc.submit()
            row.db_set("cultivation_cycle", cyc.name)
            row.db_set("cycle_status", cyc.status)
            made.append(cyc.name)
        if made:
            frappe.msgprint(f"Created {len(made)} crop cycle(s) for this batch: "
                            + ", ".join(made), indicator="green")

    @frappe.whitelist()
    def refresh_status(self):
        """A batch is ready to pay out once every crop cycle is settled, or has been
        closed with no harvest. Without the no-harvest option, one failed crop would
        hold every subscriber's money indefinitely."""
        rows = [r for r in self.crop_mix if r.cultivation_cycle]
        if not rows:
            return False
        all_done = True
        for r in rows:
            st = frappe.db.get_value("Cultivation Cycle", r.cultivation_cycle, "status")
            r.db_set("cycle_status", st)
            settled_doc = frappe.db.exists("Harvest Settlement",
                {"cultivation_cycle": r.cultivation_cycle, "docstatus": 1})
            if not (st in SETTLED_STATES or settled_doc):
                all_done = False
        self.db_set("all_cycles_settled", 1 if all_done else 0)
        if not all_done and self.status == "Open" and any(
                frappe.db.exists("Harvest Settlement",
                    {"cultivation_cycle": r.cultivation_cycle, "docstatus": 1})
                for r in rows):
            self.db_set("status", "Harvesting")
        if all_done and self.status not in ("Settled", "Closed"):
            self.db_set("status", "Harvesting")
        return all_done

    # ---------- consolidated payout ----------
    @frappe.whitelist()
    def get_pending_payouts(self):
        """Every subscriber's outstanding 80% across ALL crops in this batch,
        consolidated into one figure each."""
        cycles = [r.cultivation_cycle for r in self.crop_mix if r.cultivation_cycle]
        if not cycles:
            return []
        rows = frappe.db.sql("""
            select ha.name, ha.subscriber, ha.subscriber_payout, ha.paid_amount,
                   ha.rollover_amount, hs.cultivation_cycle
            from `tabHarvest Allocation` ha
            join `tabHarvest Settlement` hs on hs.name = ha.parent
            where hs.docstatus = 1 and hs.cultivation_cycle in %(cycles)s
        """, {"cycles": tuple(cycles)}, as_dict=True)
        agg = {}
        for r in rows:
            out = flt(flt(r.subscriber_payout) - flt(r.paid_amount) - flt(r.rollover_amount), 2)
            if out <= 0.005:
                continue
            a = agg.setdefault(r.subscriber, {"subscriber": r.subscriber, "outstanding": 0,
                                              "crops": 0, "rows": []})
            a["outstanding"] = flt(a["outstanding"] + out, 2)
            a["crops"] += 1
            a["rows"].append({"name": r.name, "outstanding": out})
        return list(agg.values())

    @frappe.whitelist()
    def settle_programme_payouts(self, settlements, mode_of_payment=None,
                                 posting_date=None, narration=None):
        """Pay each subscriber ONE consolidated amount for the whole batch, in any
        mix of cash and rollover. The amount is spread across their underlying
        per-crop allocation rows oldest-first so each crop's records stay accurate."""
        import json as _json
        from agrolocale.agrolocale.doctype.harvest_settlement.harvest_settlement import (
            get_settings, _missing_accounts)
        if isinstance(settlements, str):
            settlements = _json.loads(settlements)
        if self.docstatus != 1:
            frappe.throw("Submit the batch before settling payouts.")
        if not self.refresh_status():
            frappe.throw("Every crop in this batch must be settled (or closed with no "
                         "harvest) before subscribers are paid. This batch pays out once, "
                         "when all crops are complete.")

        s = get_settings()
        pending = {p["subscriber"]: p for p in self.get_pending_payouts()}
        cash_lines, total_cash, credits, touched = [], 0.0, [], []

        for item in settlements:
            sub = item.get("subscriber")
            p = pending.get(sub)
            if not p:
                continue
            pay_now, rollover = flt(item.get("pay_now")), flt(item.get("rollover"))
            if pay_now < 0 or rollover < 0:
                frappe.throw(f"Amounts for {sub} cannot be negative.")
            if pay_now + rollover <= 0:
                continue
            if flt(pay_now + rollover, 2) > flt(p["outstanding"], 2) + 0.005:
                frappe.throw(f"{sub}: {pay_now + rollover:,.2f} exceeds the outstanding "
                             f"{p['outstanding']:,.2f} for this batch.")
            if pay_now > 0:
                cash_lines.append((sub, pay_now)); total_cash += pay_now
            if rollover > 0:
                credits.append((sub, rollover))
            touched.append((sub, pay_now, rollover, p["rows"]))

        if not touched:
            frappe.msgprint("Nothing to settle \u2014 enter an amount for at least one subscriber.")
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
                frappe.throw(f"Mode of Payment {mode_of_payment} has no default account, and "
                             "no fallback Harvest Proceeds Account is set.")
            accounts = [{
                "account": s["subscriber_harvest_payable_account"],
                "party_type": "Customer", "party": sub,
                "debit_in_account_currency": flt(amt, 2),
                "user_remark": f"Batch payout to {sub} \u2013 {self.programme_name}",
            } for sub, amt in cash_lines]
            accounts.append({"account": pay_account,
                             "credit_in_account_currency": flt(total_cash, 2)})
            pdate = posting_date or nowdate()
            je = frappe.get_doc({
                "doctype": "Journal Entry", "voucher_type": "Bank Entry",
                "posting_date": pdate, "company": s.get("company"),
                "cheque_no": narration or f"Batch payout \u2013 {self.programme_name}",
                "cheque_date": pdate, "mode_of_payment": mode_of_payment,
                "user_remark": narration or f"Consolidated batch payouts for {self.name}",
                "accounts": accounts,
            })
            je.insert(ignore_permissions=True)
            je.submit()
            je_name = je.name

        for sub, amt in credits:
            cr = frappe.get_doc({
                "doctype": "Cultivation Credit", "subscriber": sub,
                "credit_date": nowdate(), "amount": flt(amt, 2),
            })
            cr.insert(ignore_permissions=True)
            cr.submit()

        # spread each subscriber's settled amount across their per-crop rows
        for sub, pay_now, rollover, rows in touched:
            rem_cash, rem_roll = flt(pay_now), flt(rollover)
            for r in rows:
                if rem_cash <= 0 and rem_roll <= 0:
                    break
                out = flt(r["outstanding"])
                take_cash = min(out, rem_cash)
                rem_after = out - take_cash
                take_roll = min(rem_after, rem_roll)
                rem_cash = flt(rem_cash - take_cash, 2)
                rem_roll = flt(rem_roll - take_roll, 2)
                alloc = frappe.db.get_value("Harvest Allocation", r["name"],
                    ["paid_amount", "rollover_amount", "subscriber_payout"], as_dict=True)
                new_paid = flt(flt(alloc.paid_amount) + take_cash, 2)
                new_roll = flt(flt(alloc.rollover_amount) + take_roll, 2)
                outstanding = flt(flt(alloc.subscriber_payout) - new_paid - new_roll, 2)
                frappe.db.set_value("Harvest Allocation", r["name"], {
                    "paid_amount": new_paid, "rollover_amount": new_roll,
                    "payout_status": "Settled" if outstanding <= 0.005 else "Partially Settled"})

        if not self.get_pending_payouts():
            # Everyone has been paid or rolled over: the batch is finished and must
            # not accept new subscribers.
            self.db_set("status", "Closed")
            for r in self.crop_mix:
                if r.cultivation_cycle:
                    st = frappe.db.get_value("Cultivation Cycle", r.cultivation_cycle, "status")
                    if st not in ("Closed", "Closed \u2013 No Harvest"):
                        frappe.db.set_value("Cultivation Cycle", r.cultivation_cycle,
                                            "status", "Closed", update_modified=False)
            frappe.msgprint("All subscribers settled — this batch is now Closed and will "
                            "not accept new subscribers.", indicator="blue")
        bits = []
        if cash_lines:
            bits.append(f"paid {len(cash_lines)} subscriber(s) {total_cash:,.2f}"
                        + (f" (JE {je_name})" if je_name else ""))
        if credits:
            bits.append(f"created {len(credits)} cultivation credit(s) totalling "
                        f"{sum(flt(x) for _, x in credits):,.2f}")
        frappe.msgprint("Batch settlement complete \u2014 " + "; ".join(bits) + ".",
                        indicator="green", title="Payouts settled")
        return True
