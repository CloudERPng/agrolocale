frappe.ui.form.on('Plot Subscription', {
  refresh(frm) {
    if (frm.doc.docstatus === 1 && frm.doc.sales_order &&
        frm.doc.subscription_status !== 'Allocated') {
      frm.call('sales_order_status').then((s) => {
        if (s.message && !s.message.ok) {
          frm.set_intro(s.message.reason, 'red');
          return;
        }
      frm.call('get_so_outstanding').then((r) => {
        const out = r.message || 0;
        if (out > 0) {
          frm.add_custom_button(`Receive Payment (${format_currency(out)} due)`, () => {
            const d = new frappe.ui.Dialog({
              title: 'Receive Payment',
              fields: [
                { fieldtype: 'Link', fieldname: 'mode_of_payment', label: 'Mode of Payment',
                  options: 'Mode of Payment', reqd: 1 },
                { fieldtype: 'Currency', fieldname: 'amount', label: 'Amount', reqd: 1,
                  default: out, description: `Outstanding on ${frm.doc.sales_order}: ${format_currency(out)}` },
                { fieldtype: 'Date', fieldname: 'posting_date', label: 'Payment Date',
                  default: frappe.datetime.get_today(), reqd: 1 },
                { fieldtype: 'Data', fieldname: 'reference_no', label: 'Reference No (optional)' },
              ],
              primary_action_label: 'Record Payment',
              primary_action(v) {
                if ((v.amount || 0) <= 0) { frappe.msgprint('Enter an amount greater than zero.'); return; }
                if (v.amount > out + 0.005) { frappe.msgprint('Amount exceeds the outstanding balance.'); return; }
                d.hide();
                frm.call('receive_payment', {
                  amount: v.amount, mode_of_payment: v.mode_of_payment,
                  posting_date: v.posting_date, reference_no: v.reference_no,
                }).then(() => frm.reload_doc());
              },
            });
            d.show();
          }).addClass('btn-primary');
        }
      });
      });
    }
    if (frm.doc.docstatus === 0) {
      frm.add_custom_button('Rebuild Payment Schedule', () => {
        frappe.confirm('Rebuild the installments from the payment plan? Manual edits will be lost.', () => {
          frm.call('regenerate_payment_schedule').then(() => frm.refresh());
        });
      });
    }
  },
  payment_plan: refresh_all,
  estate: refresh_all,
});

frappe.ui.form.on('Sold Units', {
  unit_type: fetch_rate,
  is_corner_piece: fetch_rate,
  qty: (frm) => recompute(frm),
  sold_units_remove: (frm) => recompute(frm),
});

function refresh_all(frm) {
  // Fees are NOT fetched here. Each sold unit carries its own developmental and
  // legal documentation fee on its Estate Price Band row, so the totals are
  // calculated on the server when the document is saved. Setting them from the
  // browser previously forced every sale onto the Plot band's rate.
  (frm.doc.sold_units || []).forEach(r => fetch_rate(frm, r.doctype, r.name));
}

function fetch_rate(frm, cdt, cdn) {
  const row = cdt ? locals[cdt][cdn] : null;
  if (!row || !frm.doc.estate || !frm.doc.payment_plan || !row.unit_type) return;
  frappe.db.get_value('Estate Price Band',
    { estate: frm.doc.estate, payment_plan: frm.doc.payment_plan, unit_type: row.unit_type },
    'price').then(r => {
      const price = (r.message && r.message.price) || 0;
      const corner = (row.is_corner_piece && row.unit_type === 'Plot') ? 1.2 : 1;
      frappe.model.set_value(cdt, cdn, 'rate', price * corner);
      recompute(frm);
    });
}

function recompute(frm) {
  if (!frm.doc.estate) return;
  frappe.db.get_value('Farm Estate', frm.doc.estate, 'plots_per_acre').then(r => {
    const ppa = (r.message && r.message.plots_per_acre) || 1;
    const MULT = { 'Plot': 1, 'Acre': ppa, '5 Acres': 5 * ppa, '10 Acres': 10 * ppa };
    let count = 0, value = 0;
    (frm.doc.sold_units || []).forEach(row => {
      const pc = (row.qty || 0) * (MULT[row.unit_type] || 1);
      frappe.model.set_value(row.doctype, row.name, 'plot_count', pc);
      frappe.model.set_value(row.doctype, row.name, 'line_total', (row.qty || 0) * (row.rate || 0));
      count += pc; value += (row.qty || 0) * (row.rate || 0);
    });
    frm.set_value('total_plot_count', count);
    frm.set_value('land_value', value);
    estimate_fees(frm, value);
  });
}

// Preview the fees the server will calculate: each unit's own band row x its qty.
function estimate_fees(frm, land_value) {
  const rows = frm.doc.sold_units || [];
  if (!rows.length || !frm.doc.estate || !frm.doc.payment_plan) {
    frm.set_value('developmental_fee', 0);
    frm.set_value('legal_documentation_fee', 0);
    frm.set_value('total_contract_value', land_value || 0);
    return;
  }
  const calls = rows.map(row => frappe.db.get_value('Estate Price Band',
    { estate: frm.doc.estate, payment_plan: frm.doc.payment_plan, unit_type: row.unit_type },
    ['developmental_fee', 'legal_documentation_fee'])
    .then(r => ({ qty: row.qty || 0, band: (r && r.message) || {} })));

  Promise.all(calls).then(results => {
    let dev = 0, legal = 0;
    results.forEach(x => {
      dev += (x.band.developmental_fee || 0) * x.qty;
      legal += (x.band.legal_documentation_fee || 0) * x.qty;
    });
    frm.set_value('developmental_fee', dev);
    frm.set_value('legal_documentation_fee', legal);
    frm.set_value('total_contract_value', (land_value || 0) + dev + legal);
  });
}
