frappe.ui.form.on('Cultivation Programme', {
  refresh(frm) {
    if (frm.doc.docstatus !== 1) return;

    frm.add_custom_button('Refresh Crop Status', () => {
      frm.call('refresh_status').then((r) => {
        frm.reload_doc();
        frappe.show_alert({
          message: r.message ? __('All crops settled \u2014 batch ready to pay out')
                             : __('Some crops are still outstanding'),
          indicator: r.message ? 'green' : 'orange' }, 5);
      });
    });

    if (frm.doc.all_cycles_settled && frm.doc.status !== 'Settled') {
      frm.add_custom_button('Settle Batch Payouts', () => open_settle(frm)).addClass('btn-primary');
    } else if (!frm.doc.all_cycles_settled) {
      frm.set_intro('Subscribers are paid once, when every crop in this batch has been ' +
        'settled. Use Refresh Crop Status to check progress.', 'blue');
    }

    frm.add_custom_button('Batch Profitability', () =>
      frappe.set_route('query-report', 'Programme Profitability',
        { cultivation_programme: frm.doc.name }));
  },
});

function open_settle(frm) {
  frm.call('get_pending_payouts').then((r) => {
    const rows = r.message || [];
    if (!rows.length) { frappe.msgprint('Every subscriber in this batch has been settled.'); return; }
    const d = new frappe.ui.Dialog({
      title: 'Settle Batch Payouts',
      size: 'large',
      fields: [
        { fieldtype: 'Link', fieldname: 'mode_of_payment', label: 'Mode of Payment',
          options: 'Mode of Payment', description: 'Required if any cash is paid now.' },
        { fieldtype: 'Date', fieldname: 'posting_date', label: 'Payment Date',
          default: frappe.datetime.get_today(), reqd: 1 },
        { fieldtype: 'Data', fieldname: 'narration', label: 'Narration / Reference',
          description: 'Recorded as the Reference No on the posting.' },
        { fieldtype: 'Section Break' },
        { fieldtype: 'HTML', fieldname: 'intro',
          options: '<p>Each subscriber is shown <b>one consolidated amount</b> for the whole ' +
                   'batch, across every crop. Enter how much to pay now and how much to roll ' +
                   'over as credit toward a future batch.</p>' },
        { fieldtype: 'Table', fieldname: 'rows', cannot_add_rows: true, cannot_delete_rows: true,
          in_place_edit: true,
          data: rows.map(x => ({ subscriber: x.subscriber, outstanding: x.outstanding,
                                 crops: x.crops, pay_now: 0, rollover: 0 })),
          fields: [
            { fieldtype: 'Data', fieldname: 'subscriber', label: 'Subscriber',
              in_list_view: 1, read_only: 1, columns: 3 },
            { fieldtype: 'Int', fieldname: 'crops', label: 'Crops',
              in_list_view: 1, read_only: 1, columns: 1 },
            { fieldtype: 'Currency', fieldname: 'outstanding', label: 'Total Due',
              in_list_view: 1, read_only: 1, columns: 2 },
            { fieldtype: 'Currency', fieldname: 'pay_now', label: 'Pay Now',
              in_list_view: 1, columns: 2 },
            { fieldtype: 'Currency', fieldname: 'rollover', label: 'Rollover',
              in_list_view: 1, columns: 2 },
          ] },
      ],
      primary_action_label: 'Settle',
      primary_action(v) {
        const data = (v.rows || []).filter(x => (x.pay_now || 0) + (x.rollover || 0) > 0);
        if (!data.length) { frappe.msgprint('Enter an amount for at least one subscriber.'); return; }
        const bad = data.find(x => (x.pay_now || 0) + (x.rollover || 0) > (x.outstanding || 0) + 0.005);
        if (bad) { frappe.msgprint(`${bad.subscriber}: total exceeds the amount due.`); return; }
        if (data.some(x => (x.pay_now || 0) > 0) && !v.mode_of_payment) {
          frappe.msgprint('Choose a Mode of Payment for the cash portion.'); return;
        }
        d.hide();
        frm.call('settle_programme_payouts', {
          settlements: data.map(x => ({ subscriber: x.subscriber,
            pay_now: x.pay_now || 0, rollover: x.rollover || 0 })),
          mode_of_payment: v.mode_of_payment, posting_date: v.posting_date,
          narration: v.narration,
        }).then(() => frm.reload_doc());
      },
    });
    d.show();
  });
}
