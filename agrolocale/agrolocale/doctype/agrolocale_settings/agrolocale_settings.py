import frappe
from frappe.model.document import Document

# field -> (expected root types, human label, what it is for)
ACCOUNT_RULES = {
    "cultivation_commission_income_account": (
        ("Income",), "Cultivation Commission Income Account",
        "Agrolocale's 20% share of harvest value is income, so this must be an Income "
        "account. Pointing it at an expense account (for example a 'Commission on Sales' "
        "expense head) understates revenue and distorts the Profit and Loss."),
    "subscriber_harvest_payable_account": (
        ("Liability",), "Subscriber Harvest Payable Account",
        "The subscribers' 80% is money held on their behalf, so this must be a Liability "
        "account \u2014 never income and never an expense."),
    "harvest_proceeds_account": (
        ("Asset",), "Harvest Proceeds Account",
        "This is the bank or cash account money moves through, so it must be an Asset "
        "account."),
}


class AgrolocaleSettings(Document):
    def validate(self):
        for field, (roots, label, why) in ACCOUNT_RULES.items():
            acc = self.get(field)
            if not acc:
                continue
            info = frappe.db.get_value("Account", acc,
                ["root_type", "is_group"], as_dict=True) or {}
            if info.get("is_group"):
                frappe.throw(f"<b>{label}</b>: {acc} is a group account. Choose the "
                             "postable account beneath it.")
            root = info.get("root_type")
            if root and root not in roots:
                frappe.throw(
                    f"<b>{label}</b> is set to <b>{acc}</b>, which is a "
                    f"<b>{root}</b> account.<br><br>{why}<br><br>"
                    f"Expected: an account whose root type is "
                    f"<b>{' or '.join(roots)}</b>.")
