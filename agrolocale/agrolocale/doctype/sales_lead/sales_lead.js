frappe.ui.form.on('Sales Lead', {
  refresh(frm) {
    if (!frm.is_new() && !frm.doc.subscription_intake) {
      frm.add_custom_button('Create Subscription Intake', () => {
        frm.call('create_intake').then((r) => {
          if (r.message) frappe.set_route('Form', 'Subscription Intake', r.message);
        });
      }).addClass('btn-primary');
    }
    if (frm.doc.subscription_intake) {
      frm.add_custom_button('Open Intake', () =>
        frappe.set_route('Form', 'Subscription Intake', frm.doc.subscription_intake));
    }
  },
});
