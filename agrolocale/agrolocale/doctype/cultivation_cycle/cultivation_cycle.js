frappe.ui.form.on('Cultivation Cycle', {
  refresh(frm) {
    if (frm.doc.docstatus !== 1) return;

    frm.add_custom_button('Issue Farm Inputs', () => {
      frappe.model.open_mapped_doc({
        method: 'agrolocale.agrolocale.doctype.cultivation_cycle.cultivation_cycle.make_material_issue',
        frm: frm,
      });
    }, 'Costing').addClass('btn-primary');

    if (!frm.doc.warehouse || !frm.doc.cost_center) {
      frm.set_intro('This cycle has no warehouse or cost centre yet. Click ' +
        'Costing \u2192 Sync Costing Defaults to pull them from the farm.', 'orange');
      frm.add_custom_button('Sync Costing Defaults', () => {
        frm.call('sync_costing_defaults').then(() => frm.reload_doc());
      }, 'Costing').addClass('btn-primary');
    }

    frm.add_custom_button('Refresh Input Cost', () => {
      frm.call('refresh_input_cost').then((r) => {
        frm.reload_doc();
        frappe.show_alert({ message: __('Input cost updated'), indicator: 'green' });
      });
    }, 'Costing');

    if (frm.doc.project) {
      frm.add_custom_button('Open Project', () =>
        frappe.set_route('Form', 'Project', frm.doc.project), 'Costing');
      frm.add_custom_button('Cycle Profitability', () =>
        frappe.set_route('query-report', 'Cultivation Cycle Profitability',
          { cultivation_cycle: frm.doc.name }), 'Costing');
    }
  },
});
