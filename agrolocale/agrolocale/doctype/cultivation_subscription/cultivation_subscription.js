frappe.ui.form.on('Cultivation Subscription', {
  refresh(frm) {
    if (frm.doc.docstatus === 1 && frm.doc.setup_invoice) {
      frm.call('get_available_credit').then((r) => {
        const total = (r.message && r.message.total) || 0;
        if (total > 0) {
          frm.add_custom_button(`Apply Harvest Credit (${format_currency(total)})`, () => {
            const d = new frappe.ui.Dialog({
              title: 'Apply Harvest Credit',
              fields: [
                { fieldtype: 'Currency', fieldname: 'amount', label: 'Amount to apply',
                  default: total,
                  description: 'Capped at the invoice outstanding and the available credit. Oldest credits are used first.' },
              ],
              primary_action_label: 'Apply',
              primary_action(v) {
                d.hide();
                frm.call('apply_harvest_credit', { amount: v.amount }).then(() => frm.refresh());
              },
            });
            d.show();
          }).addClass('btn-primary');
        }
      });
    }
  },
  subscriber(frm) {
    frm.set_query('eligibility_subscription', () => ({
      filters: { subscriber: frm.doc.subscriber, subscription_status: 'Allocated' }
    }));
  },
  cultivation_cycle: project,
  number_of_plots: project,
  number_of_acres: project,
});

function project(frm) {
  if (!frm.doc.cultivation_cycle) return;
  frappe.db.get_value('Cultivation Cycle', frm.doc.cultivation_cycle, 'crop').then(r => {
    const crop = r.message && r.message.crop;
    if (!crop) return;
    frappe.db.get_doc('Crop', crop).then(c => {
      const p = frm.doc.number_of_plots || 0, a = frm.doc.number_of_acres || 0;
      const share = (c.subscriber_share_pct || 80) / 100;
      const yld = p * (c.expected_yield_per_plot_kg || 0) + a * (c.expected_yield_per_acre_kg || 0);
      frm.set_value('crop', crop);
      frm.set_value('setup_fee', p * (c.setup_fee_per_plot || 0) + a * (c.setup_fee_per_acre || 0));
      frm.set_value('expected_yield_kg', yld);
      frm.set_value('projected_revenue_min', yld * (c.min_price_per_kg || 0) * share);
      frm.set_value('projected_revenue_max', yld * (c.max_price_per_kg || 0) * share);
    });
  });
}
