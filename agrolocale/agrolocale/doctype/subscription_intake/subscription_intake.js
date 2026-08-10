frappe.ui.form.on('Subscription Intake', {
  refresh(frm) {
    if (frm.is_new()) return;
    const s = frm.doc.status;
    frm.set_intro(intro_for(s), intro_colour(s));

    if (s === 'Draft' || s === 'Returned to Sales') {
      frm.add_custom_button('Start Customer Care Review', () =>
        frm.call('start_review').then(() => frm.reload_doc())).addClass('btn-primary');
    }
    if (s === 'With Customer Care') {
      frm.add_custom_button('Verify & Send to Accounts', () => {
        frappe.confirm('Confirm the form, FAQ, ID and receipts have been checked?', () => {
          frm.call('send_to_accounts').then(() => frm.reload_doc());
        });
      }).addClass('btn-primary');
      frm.add_custom_button('Return to Sales', () => {
        frappe.prompt({ fieldtype: 'Small Text', fieldname: 'reason', label: 'What needs correcting?', reqd: 1 },
          (v) => frm.call('return_to_sales', { reason: v.reason }).then(() => frm.reload_doc()),
          'Return to Sales');
      });
    }
    if (s === 'With Accounts') {
      frm.add_custom_button('Process (create subscription)', () => {
        frm.call('process').then((r) => { if (r.message) frm.reload_doc(); });
      }).addClass('btn-primary');
      frm.add_custom_button('Return to Customer Care', () => {
        frappe.prompt({ fieldtype: 'Small Text', fieldname: 'reason', label: 'What is missing?', reqd: 1 },
          (v) => frm.call('return_to_sales', { reason: v.reason }).then(() => frm.reload_doc()),
          'Return');
      });
    }
    if (s === 'Processed') {
      frm.add_custom_button('Open Plot Subscription', () =>
        frappe.set_route('Form', 'Plot Subscription', frm.doc.plot_subscription));
      frm.add_custom_button('Record Receipts as Payments', () =>
        frm.call('record_receipts').then(() => frm.reload_doc())).addClass('btn-primary');
    }
  },
});

function intro_for(s) {
  return {
    'Draft': 'Sales stage \u2014 capture the subscriber and what they are buying, then hand to Customer Care.',
    'With Customer Care': 'Customer Care \u2014 attach the form, signed FAQ and ID, log and verify the receipts, then send to Accounts.',
    'With Accounts': 'Accounts \u2014 verified by Customer Care. Process to create the customer and subscription.',
    'Processed': 'Processed \u2014 subscription created. Record the receipts as payments if not yet done.',
    'Returned to Sales': 'Returned \u2014 see the Return Reason, correct it, then restart the review.',
  }[s] || '';
}
function intro_colour(s) {
  return s === 'Processed' ? 'green' : s === 'Returned to Sales' ? 'red' : 'blue';
}

// Pricing is fetched from the Estate Price Band, never typed.
// Changing the estate, plan or units re-prices the whole file on save.
frappe.ui.form.on('Subscription Intake', {
  estate(frm) { reprice_hint(frm); },
  payment_plan(frm) { reprice_hint(frm); },
});

frappe.ui.form.on('Sold Units', {
  unit_type(frm) { reprice_hint(frm); },
  qty(frm) { reprice_hint(frm); },
  is_corner_piece(frm) { reprice_hint(frm); },
  sold_units_remove(frm) { reprice_hint(frm); },
});

function reprice_hint(frm) {
  if (!frm.doc.estate || !frm.doc.payment_plan) return;
  frm.dirty();
  frappe.show_alert({ message: __('Save to apply Estate Price Band rates and fees.'),
                      indicator: 'blue' }, 4);
}
