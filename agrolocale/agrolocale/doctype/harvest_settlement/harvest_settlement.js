frappe.ui.form.on('Harvest Settlement', {
  refresh(frm) {
    if (frm.doc.docstatus === 0) {
      frm.add_custom_button('Get Qualified Subscribers', () => pull_subscribers(frm));
      frm.add_custom_button('Distribute Yield by Entitlement', () => {
        frm.call('distribute_yield').then(() => frm.refresh());
      });
    }
    if (frm.doc.docstatus === 1) {
      const pending = (frm.doc.allocations || []).some(a => a.payout_status !== 'Settled');
      if (pending) {
        frm.add_custom_button('Settle Payouts', () => open_settle_dialog(frm)).addClass('btn-primary');
      }
    }
  },
  cultivation_cycle(frm) {
    if (frm.doc.cultivation_cycle && !(frm.doc.allocations || []).length) pull_subscribers(frm);
  },
});

function open_settle_dialog(frm) {
  frm.call('get_pending_allocations').then((r) => {
    const rows = r.message || [];
    if (!rows.length) { frappe.msgprint('All subscribers on this settlement are fully settled.'); return; }
    const d = new frappe.ui.Dialog({
      title: 'Settle Payouts',
      size: 'large',
      fields: [
        { fieldtype: 'HTML', fieldname: 'intro',
          options: '<p>For each subscriber, enter how much to <b>pay now</b> (cash) and/or ' +
                   '<b>roll over</b> as credit toward a future cultivation cycle. ' +
                   'Leave both at 0 to settle that subscriber later.</p>' },
        { fieldtype: 'Table', fieldname: 'rows', cannot_add_rows: true, cannot_delete_rows: true,
          in_place_edit: true, data: rows.map(x => ({
            name: x.name, subscriber: x.subscriber, outstanding: x.outstanding,
            pay_now: 0, rollover: 0 })),
          fields: [
            { fieldtype: 'Data', fieldname: 'name', hidden: 1 },
            { fieldtype: 'Data', fieldname: 'subscriber', label: 'Subscriber',
              in_list_view: 1, read_only: 1, columns: 3 },
            { fieldtype: 'Currency', fieldname: 'outstanding', label: 'Outstanding',
              in_list_view: 1, read_only: 1, columns: 2 },
            { fieldtype: 'Currency', fieldname: 'pay_now', label: 'Pay Now',
              in_list_view: 1, columns: 2 },
            { fieldtype: 'Currency', fieldname: 'rollover', label: 'Rollover',
              in_list_view: 1, columns: 2 },
          ] },
      ],
      primary_action_label: 'Settle',
      primary_action(values) {
        const data = (values.rows || []).filter(x => (x.pay_now || 0) + (x.rollover || 0) > 0);
        if (!data.length) { frappe.msgprint('Enter a pay-now or rollover amount for at least one subscriber.'); return; }
        const bad = (values.rows || []).find(x => (x.pay_now || 0) + (x.rollover || 0) > (x.outstanding || 0) + 0.005);
        if (bad) { frappe.msgprint(`${bad.subscriber}: total exceeds the outstanding amount.`); return; }
        d.hide();
        frm.call('settle_payouts', { settlements: data.map(x => ({
          name: x.name, pay_now: x.pay_now || 0, rollover: x.rollover || 0 })) })
          .then(() => frm.refresh());
      },
    });
    d.show();
  });
}

function pull_subscribers(frm) {
  if (!frm.doc.cultivation_cycle) { frappe.msgprint('Select a Cultivation Cycle first.'); return; }
  frappe.call({
    method: 'agrolocale.agrolocale.doctype.harvest_settlement.harvest_settlement.get_cycle_subscribers',
    args: { cultivation_cycle: frm.doc.cultivation_cycle,
            actual_total_yield_kg: frm.doc.actual_total_yield_kg || 0 },
    callback: (r) => {
      if (!r.message || !r.message.length) { frappe.msgprint('No qualified subscribers found.'); return; }
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
