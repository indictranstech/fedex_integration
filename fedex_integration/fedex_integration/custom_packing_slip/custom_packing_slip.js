cur_frm.add_fetch("delivery_note", "customer", "customer");
cur_frm.add_fetch("delivery_note", "customer_name", "customer_name");

frappe.ui.form.on("Packing Slip", "shipping_address_name", function(frm, cdt, cdn){
	erpnext.utils.get_address_display(frm, 'shipping_address_name', 'shipping_address', true);
})

frappe.ui.form.on("Packing Slip", "company_address_name", function(frm, cdt, cdn){
	erpnext.utils.get_address_display(frm, 'company_address_name', 'company_address', true);
})

cur_frm.set_query('company_address_name', function(){
	return {
		"filters": {
			"is_your_company_address": 1
		}
	};
});

cur_frm.set_query('shipping_address_name', function(doc){
	return {
		"filters": {
			"customer": doc.customer
		}
	};
});

cur_frm.set_query('package_id', 'items', function(doc, cdt, cdn) {
  	var d  = locals[cdt][cdn];
  	var package_ids = get_package_list();
  	return {
  		filters:{
  			"name":["in", package_ids]
  		}
  	}
});

cur_frm.set_query('weight_uom', 'items', function(doc, cdt, cdn) {
  	var d  = locals[cdt][cdn];
  	var filter_value = doc.is_fedex_account ? ["in", ["LB", "Kg"]] : ["not in", [""]];
  	return {
  		filters:{
  			"name": filter_value
  		}
  	}
});

frappe.ui.form.on('Packing Slip', {
	is_fedex_account: function(frm){
		frm.toggle_reqd("drop_off_type", frm.doc.is_fedex_account);
		frm.toggle_reqd("service_type", frm.doc.is_fedex_account);
		frm.toggle_reqd("packaging_type", frm.doc.is_fedex_account);
		frm.toggle_reqd("total_handling_units", frm.doc.is_fedex_account);
		frm.toggle_reqd("shipping_payment_by", frm.doc.is_fedex_account);
		frm.toggle_reqd("duties_payment_by", frm.doc.is_fedex_account);
		frm.toggle_reqd("no_of_packages", frm.doc.is_fedex_account);
		frm.fields_dict.items.grid.toggle_reqd("package_id", frm.doc.is_fedex_account);
		frm.fields_dict.items.grid.set_column_disp("package_id", frm.doc.is_fedex_account);
	},
	shipment_forwarder:function(frm){
		if (frm.doc.shipment_forwarder == ""){
			cur_frm.set_value("is_fedex_account", 0);
		}
	},
	shipping_payment_by:function(frm){
		frm.toggle_reqd("shipping_payment_account", inList(["RECIPIENT", "THIRD_PARTY"], frm.doc.shipping_payment_by));
	},
	duties_payment_by:function(frm){
		frm.toggle_reqd("duties_payment_account", inList(["RECIPIENT", "THIRD_PARTY"], frm.doc.duties_payment_by));
	},
	no_of_packages:function(frm){
		frm.toggle_display("fedex_package_details", frm.doc.no_of_packages);
		if(frm.doc.no_of_packages){
			var package_array = new Array(frm.doc.no_of_packages)
			frappe.call({
				method:"frappe.client.get_list",
				args:{
					doctype:"FedEx Package",
					fields: ["name"],
					order_by: "name asc",
					limit_page_length : frm.doc.no_of_packages
				},
				callback: function(r) {
					cur_frm.set_value("fedex_package_details", [])
					$.each(package_array, function(i, d) {
						var row = frappe.model.add_child(frm.doc, "FedEx Package Details", "fedex_package_details");
						row.fedex_package = r.message[i].name;
					});
					refresh_field("fedex_package_details");	
				}
			});
			
		}
	},
});

get_package_list = function(){
	var package_ids = [];
	$.each(cur_frm.doc.fedex_package_details, function(i, pkg){
		package_ids.push(pkg.fedex_package);
	})
	return package_ids
}

