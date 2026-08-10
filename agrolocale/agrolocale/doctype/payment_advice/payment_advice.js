frappe.ui.form.on('Payment Advice', {
  refresh(frm) {
    if (frm.is_new() || frm.doc.status !== 'Awaiting Verification') return;
    frm.add_custom_button('Verify & Record Payment', () => {
      frappe.confirm('Record this as a payment against the subscription?', () => {
        frm.call('record_payment').then(() => frm.reload_doc());
      });
    }).addClass('btn-primary');
    frm.add_custom_button('Reject', () => {
      frappe.prompt({ fieldtype: 'Small Text', fieldname: 'reason', label: 'Reason', reqd: 1 },
        (v) => frm.call('reject', { reason: v.reason }).then(() => frm.reload_doc()),
        'Reject Advice');
    });
  },
});
