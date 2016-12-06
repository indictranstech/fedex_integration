frappe.ui.form.on("Sales Order", {
	onload: function(frm) {
		cur_frm.set_query('warehouse', 'items', function(doc, cdt, cdn) {
			var row = locals[cdt][cdn];
			return {
				query:"fedex_integration.fedex_integration.custom_packing_slip.custom_packing_slip.warehouse_query",
				filters:{"item":row.item_code, "company":cstr(doc.company)}
			}
		});
	}
});

cur_frm.add_fetch("item_code", "country_of_manufacture", "country_of_manufacture");
cur_frm.add_fetch("item_code", "country_code", "country_code");