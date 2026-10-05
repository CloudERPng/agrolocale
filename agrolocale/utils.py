import frappe


def ensure_item(item_name, is_stock=False):
    """Return an Item, creating it on first use.

    Service and land items are non-stock. Harvest bought into a sister company's
    warehouse must be a stock item, so pass is_stock=True for those."""
    if frappe.db.exists("Item", item_name):
        return item_name
    group = (frappe.db.get_value("Item Group", {"item_group_name": "Services"})
             or frappe.db.get_value("Item Group", {"is_group": 0})
             or "All Item Groups")
    uom = "Nos" if frappe.db.exists("UOM", "Nos") else (frappe.db.get_value("UOM", {}, "name") or "Unit")
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_name,
        "item_name": item_name,
        "item_group": group,
        "stock_uom": uom,
        "is_stock_item": 1 if is_stock else 0,
        "is_sales_item": 1,
        "is_purchase_item": 1,
    }).insert(ignore_permissions=True)
    return doc.name


def get_mode_of_payment_account(mode_of_payment, company):
    """Default account configured for a Mode of Payment for this company.
    Read directly so we do not depend on ERPNext internal import paths."""
    return frappe.db.get_value("Mode of Payment Account",
        {"parent": mode_of_payment, "company": company}, "default_account")


def post_subscriber_payouts(cash_lines, total_cash, settings, posting_date, narration,
                            mode_of_payment=None, offtaker=None, offtaker_invoice=None,
                            remark_prefix="Harvest payout"):
    """Post the cash side of subscriber payouts and return the Journal Entry names.

    Two arrangements are supported:

    1. Paid by this company - one bank entry:
           Dr Subscriber Harvest Payable (per subscriber)   Cr Bank

    2. Paid by a sister company on this company's behalf (e.g. Foodlocale buys the
       harvest and pays the subscribers). Two entries are posted automatically, and
       between them they also settle the inter-company debt, so nothing has to be
       netted off by hand later:

       In the payout company:
           Dr Creditors (this company, as supplier)          Cr Payout bank
       In this company:
           Dr Subscriber Harvest Payable (per subscriber)    Cr Debtors (off-taker)

       The payout therefore reduces what the sister company owes for the harvest and
       what this company is holding for subscribers, in one action.
    """
    import frappe
    from frappe.utils import flt

    if not cash_lines:
        return []

    s = settings or {}
    pdate = posting_date
    ref = narration or remark_prefix
    jes = []

    payable = s.get("subscriber_harvest_payable_account")
    if not payable:
        frappe.throw("Set the Subscriber Harvest Payable Account in Agrolocale Settings.")

    # ---------- simple case: this company pays ----------
    if not s.get("payouts_via_sister_company"):
        pay_account = (get_mode_of_payment_account(mode_of_payment, s.get("company"))
                       if mode_of_payment else None) or s.get("harvest_proceeds_account")
        if not pay_account:
            frappe.throw(f"Mode of Payment {mode_of_payment} has no default account for "
                         f"{s.get('company')}, and no fallback Harvest Proceeds Account is set.")
        accounts = [{
            "account": payable, "party_type": "Customer", "party": sub,
            "debit_in_account_currency": flt(amt, 2),
            "user_remark": f"{remark_prefix} to {sub}",
        } for sub, amt in cash_lines]
        accounts.append({"account": pay_account,
                         "credit_in_account_currency": flt(total_cash, 2)})
        je = frappe.get_doc({
            "doctype": "Journal Entry", "voucher_type": "Bank Entry",
            "posting_date": pdate, "company": s.get("company"),
            "cheque_no": ref, "cheque_date": pdate,
            "mode_of_payment": mode_of_payment,
            "user_remark": ref, "accounts": accounts,
        })
        je.insert(ignore_permissions=True)
        je.submit()
        return [je.name]

    # ---------- sister company pays on our behalf ----------
    payout_company = s.get("payout_company")
    bank = s.get("payout_bank_account")
    ic_supplier = s.get("intercompany_supplier")
    ic_payable = s.get("intercompany_payable_account")
    if not all([payout_company, bank, ic_supplier, ic_payable]):
        frappe.throw("Sister-company payouts are enabled but not fully configured. "
                     "Check Agrolocale Settings.")

    # 1. the sister company actually moves the money, and in doing so reduces what it
    #    owes this company for the harvest it bought.
    # Set the payment against the outstanding purchase invoices, oldest first, so it
    # visibly knocks them down instead of sitting as an unallocated debit.
    debit_rows, remaining = [], flt(total_cash, 2)
    open_pis = frappe.db.sql("""
        select name, outstanding_amount
        from `tabPurchase Invoice`
        where docstatus = 1 and supplier = %s and company = %s
          and outstanding_amount > 0
        order by posting_date asc, name asc
    """, (ic_supplier, payout_company), as_dict=True)
    for pi in open_pis:
        if remaining <= 0.005:
            break
        take = min(flt(pi.outstanding_amount), remaining)
        debit_rows.append({
            "account": ic_payable, "party_type": "Supplier", "party": ic_supplier,
            "debit_in_account_currency": flt(take, 2),
            "reference_type": "Purchase Invoice", "reference_name": pi.name,
            "user_remark": f"{remark_prefix} set against {pi.name}",
        })
        remaining = flt(remaining - take, 2)
    if remaining > 0.005:
        # more paid out than has been invoiced - record the excess on account
        debit_rows.append({
            "account": ic_payable, "party_type": "Supplier", "party": ic_supplier,
            "debit_in_account_currency": flt(remaining, 2),
            "user_remark": f"{remark_prefix} - on account (exceeds invoiced harvest)",
        })

    je_pay = frappe.get_doc({
        "doctype": "Journal Entry", "voucher_type": "Bank Entry",
        "posting_date": pdate, "company": payout_company,
        "cheque_no": ref, "cheque_date": pdate,
        "mode_of_payment": mode_of_payment,
        "user_remark": f"{ref} - paid on behalf of {s.get('company')}",
        "accounts": debit_rows + [
            {"account": bank, "credit_in_account_currency": flt(total_cash, 2)},
        ],
    })
    je_pay.insert(ignore_permissions=True)
    je_pay.submit()
    jes.append(je_pay.name)

    # 2. in our books the subscribers are discharged, and the off-taker's debt to us
    #    falls by the same amount.
    receivable = s.get("offtaker_receivable_account")
    if not receivable and offtaker_invoice:
        receivable = frappe.db.get_value("Sales Invoice", offtaker_invoice, "debit_to")
    if not receivable:
        receivable = frappe.db.get_value("Company", s.get("company"), "default_receivable_account")
    if not receivable:
        frappe.throw("No receivable account found for the off-taker. Set the Receivable "
                     "Account in Agrolocale Settings.")
    if not offtaker:
        frappe.throw("The off-taker is required to post the inter-company side of the payout.")

    accounts = [{
        "account": payable, "party_type": "Customer", "party": sub,
        "debit_in_account_currency": flt(amt, 2),
        "user_remark": f"{remark_prefix} to {sub} (paid by {payout_company})",
    } for sub, amt in cash_lines]
    credit_row = {
        "account": receivable, "party_type": "Customer", "party": offtaker,
        "credit_in_account_currency": flt(total_cash, 2),
        "user_remark": f"Offset against harvest sold to {offtaker}",
    }
    if offtaker_invoice:
        # tie it to the harvest invoice so the receivable is reduced against it
        credit_row["reference_type"] = "Sales Invoice"
        credit_row["reference_name"] = offtaker_invoice
    accounts.append(credit_row)
    je_ic = frappe.get_doc({
        "doctype": "Journal Entry", "voucher_type": "Journal Entry",
        "posting_date": pdate, "company": s.get("company"),
        "cheque_no": ref, "cheque_date": pdate,
        "user_remark": f"{ref} - paid by {payout_company} on our behalf",
        "accounts": accounts,
    })
    je_ic.insert(ignore_permissions=True)
    je_ic.submit()
    jes.append(je_ic.name)
    return jes
