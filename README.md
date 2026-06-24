# Agrolocale — ERPNext app

Land sales + cultivation (yield-share) management. Built on Frappe/ERPNext v15.

## What it adds
Masters: **Farm Estate**, **Estate Price Band**, **Crop**.
Land: **Land Acquisition** (hectares in -> auto-generates plots), **Land Plot** (inventory register).
Sales: **Plot Subscription** (mixed plots & acres in one transaction; auto-resolves the actual plot
count, allocates plots, and creates a native Sales Order with installments).
Cultivation: **Cultivation Cycle**, **Cultivation Subscription** (enforced land-ownership gate +
plot-equivalent entitlement cap, live setup-fee & yield projection).
Harvest: **Harvest Settlement** (computes the 20/80 split per subscriber).

## Install
    cd ~/frappe-bench
    bench get-app https://github.com/YOURUSER/agrolocale.git
    bench --site yoursite.com install-app agrolocale
    bench --site yoursite.com migrate
    bench build && bench restart

## First-run setup
1. Create your **Farm Estate**(s); set `plots_per_hectare` and `plots_per_acre`.
2. Fill **Estate Price Band** rows (estate x unit_type x payment_plan -> price + fees).
3. Create **Crop** records (fees, yields, min/max price, shares).
4. Record a **Land Acquisition** and submit -> plots are generated automatically.

## Harvest posting (site-specific)
GL account names differ per company, so `Harvest Settlement.on_submit` only computes figures.
To auto-post the agency entries, add a helper that, on submit, books:
Dr Bank/Receivable; Cr "Subscriber Harvest Payable" (80%); Cr "Cultivation Commission Income" (20%);
then pays each subscriber against the payable. Map the accounts first, then enable it.
