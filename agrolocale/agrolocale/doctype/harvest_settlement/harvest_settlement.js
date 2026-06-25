frappe.ui.form.on('Harvest Settlement', {
  refresh(frm) {
    frm.add_custom_button('Get Qualified Subscribers', () => pull_subscribers(frm));
  },
  cultivation_cycle(frm) {
    if (frm.doc.cultivation_cycle && !(frm.doc.allocations || []).length) {
      pull_subscribers(frm);
    }
  },
});

function pull_subscribers(frm) {
  if (!frm.doc.cultivation_cycle) {
    frappe.msgprint('Select a Cultivation Cycle first.');
    return;
  }
  frappe.call({
    method: 'agrolocale.agrolocale.doctype.harvest_settlement.harvest_settlement.get_cycle_subscribers',
    args: {
      cultivation_cycle: frm.doc.cultivation_cycle,
      actual_total_yield_kg: frm.doc.actual_total_yield_kg || 0,
    },
    callback: (r) => {
      if (!r.message || !r.message.length) {
        frappe.msgprint('No qualified subscribers found for this cycle.');
        return;
      }
      frm.clear_table('allocations');
      r.message.forEach((row) => {
        const c = frm.add_child('allocations');
        c.subscriber = row.subscriber;
        c.cultivation_subscription = row.cultivation_subscription;
        c.yield_kg = row.yield_kg;
      });
      frm.refresh_field('allocations');
      frm.dirty();
    },
  });
}
