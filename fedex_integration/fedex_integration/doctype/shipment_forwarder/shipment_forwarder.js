// Copyright (c) 2016, fedex_integration and contributors
// For license information, please see license.txt

frappe.ui.form.on('Shipment Forwarder', {
	is_fedex_account: function(frm){
		frm.toggle_reqd("account_no", frm.doc.is_fedex_account);
		frm.toggle_reqd("fedex_meter_no", frm.doc.is_fedex_account);
		frm.toggle_reqd("fedex_key", frm.doc.is_fedex_account);
		frm.toggle_reqd("password", frm.doc.is_fedex_account);
	},
	shipment_forwarder: function(frm){
		frm.set_value("title", frm.doc.shipment_forwarder);
	}
});