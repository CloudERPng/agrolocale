import frappe
from frappe.model.document import Document

ACCOUNT_RULES = {
    "cultivation_commission_income_account": (
        ("Income",), "Cultivation Commission Income Account",
        "Agrolocale's 20% share of harvest value is income, so this must be an Income "
        "account. Pointing it at an expense account understates revenue."),
    "subscriber_harvest_payable_account": (
        ("Liability",), "Subscriber Harvest Payable Account",
        "The subscribers' 80% is money held on their behalf, so this must be a Liability "
        "account."),
    "harvest_proceeds_account": (
        ("Asset",), "Harvest Proceeds Account",
        "This is the bank or cash account money moves through, so it must be an Asset "
        "account."),
    "payout_bank_account": (
        ("Asset",), "Payout Bank Account",
        "This is the sister company's bank account, so it must be an Asset account."),
    "intercompany_payable_account": (
        ("Liability",), "Payable Account (payout company)",
        "This carries what the payout company owes this company, so it must be a "
        "Liability account."),
    "offtaker_receivable_account": (
        ("Asset",), "Receivable Account (this company)",
        "This carries what the off-taker owes for harvest, so it must be an Asset account."),
}

# field -> the company it must belong to ("own" = this company, "payout" = sister)
ACCOUNT_COMPANY = {
    "harvest_proceeds_account": "own",
    "subscriber_harvest_payable_account": "own",
    "cultivation_commission_income_account": "own",
    "offtaker_receivable_account": "own",
    "payout_bank_account": "payout",
    "intercompany_payable_account": "payout",
}


class AgrolocaleSettings(Document):
    def validate(self):
        self.validate_account_types()
        self.validate_intercompany()

    def validate_account_types(self):
        for field, (roots, label, why) in ACCOUNT_RULES.items():
            acc = self.get(field)
            if not acc:
                continue
            info = frappe.db.get_value("Account", acc,
                ["root_type", "is_group", "company"], as_dict=True) or {}
            if info.get("is_group"):
                frappe.throw(f"<b>{label}</b>: {acc} is a group account. Choose the "
                             "postable account beneath it.")
            root = info.get("root_type")
            if root and root not in roots:
                frappe.throw(f"<b>{label}</b> is set to <b>{acc}</b>, which is a "
                             f"<b>{root}</b> account.<br><br>{why}<br><br>Expected root "
                             f"type: <b>{' or '.join(roots)}</b>.")
            # the account must sit in the right company
            expect = ACCOUNT_COMPANY.get(field)
            target = self.company if expect == "own" else self.payout_company
            if expect and target and info.get("company") and info["company"] != target:
                frappe.throw(f"<b>{label}</b> belongs to <b>{info['company']}</b>, but it "
                             f"must be an account of <b>{target}</b>.")

    def validate_intercompany(self):
        if not self.payouts_via_sister_company:
            return
        missing = [lbl for fld, lbl in [
            ("payout_company", "Payout Company"),
            ("payout_bank_account", "Payout Bank Account"),
            ("intercompany_supplier", "This Company as Supplier"),
            ("intercompany_payable_account", "Payable Account (payout company)"),
        ] if not self.get(fld)]
        if missing:
            frappe.throw("Sister-company payouts need these set: " + ", ".join(missing))
        if self.payout_company == self.company:
            frappe.throw("The Payout Company must be different from this company. Untick "
                         "the sister-company option if payouts are made from this company.")
