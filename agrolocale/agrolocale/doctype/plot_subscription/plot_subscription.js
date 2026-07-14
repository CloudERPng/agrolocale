frappe.ui.form.on('Plot Subscription', {
  refresh(frm) {
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
  (frm.doc.sold_units || []).forEach(r => fetch_rate(frm, r.doctype, r.name));
  if (frm.doc.estate && frm.doc.payment_plan) {
    frappe.db.get_value('Estate Price Band',
      { estate: frm.doc.estate, payment_plan: frm.doc.payment_plan, unit_type: 'Plot' },
      ['developmental_fee', 'legal_documentation_fee']).then(r => {
        if (r.message) {
          frm.set_value('developmental_fee', r.message.developmental_fee);
          frm.set_value('legal_documentation_fee', r.message.legal_documentation_fee);
        }
      });
  }
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
    frm.set_value('total_contract_value',
      value + (frm.doc.developmental_fee || 0) + (frm.doc.legal_documentation_fee || 0));
  });
}
