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

// cur_frm.set_query('package_id', 'items', function(doc, cdt, cdn) {
//   	var d  = locals[cdt][cdn];
//   	var package_ids = get_package_list();
//   	return {
//   		filters:{
//   			"name":["in", package_ids]
//   		}
//   	}
// });

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
		cur_frm.cscript.enable_fedex_fields(frm);	
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
					cur_frm.set_value("fedex_package_details", []);
					cur_frm.set_value("item_packing_details", []);
					$.each(package_array, function(i, d) {
						var row = frappe.model.add_child(frm.doc, "FedEx Package Details", "fedex_package_details");
						row.fedex_package = r.message[i].name;
					});
					cur_frm.refresh_field("fedex_package_details");
				}
			});
			
		}
	},
	refresh:function(frm){
		if(frm.doc.is_fedex_account){
			if(frm.doc.docstatus == 1){
				$(frm.fields_dict.master_tracking_id.wrapper).html(repl("<button class='btn btn-secondary btn-default btn-sm'>\
					<a  target='_blank' href='https://www.fedex.com/apps/fedextrack/?tracknumbers=%(fedex_id)s&language=en&cntry_code=in'>\
					Track Shipment</a></button>",{"fedex_id":frm.doc.fedex_tracking_id}));
				if(!frm.doc.is_pickup_scheduled){
					cur_frm.add_custom_button(__('Schedule Pickup'),
						function() { cur_frm.cscript.schedule_pickup(); }, 'icon-retweet', 'btn-default');	
				}
			}
			else{
				// cur_frm.cscript.convert_shipment_amount(frm);
			}

		}else{
			$(frm.fields_dict.master_tracking_id.wrapper).html("");
		}
		cur_frm.cscript.enable_fedex_fields(frm);

	}
});

get_entity_list = function(child_table, field_name){
	var entity_ids = [];
	$.each(cur_frm.doc[child_table], function(i, pkg){
		entity_ids.push(pkg[field_name]);
	})
	return entity_ids
}

cur_frm.cscript.schedule_pickup = function(){
	frappe.prompt(
			[
				{fieldtype:'Datetime', fieldname:'ready_time', label: __('Package Ready Time'), 'reqd':1},
			],
			function(data){
				frappe.call({
					freeze:true,
					freeze_message: __("Scheduling pickup................."),
					method:"fedex_integration.fedex_integration.custom_packing_slip.custom_packing_slip.schedule_pickup",
					args:{"request_data":{"fedex_account":cur_frm.doc.shipment_forwarder, "gross_weight":cur_frm.doc.gross_weight_pkg, 
											"uom":cur_frm.doc.gross_weight_uom, "package_count":cur_frm.doc.no_of_packages,
											"shipper_id":cur_frm.doc.company_address_name, "ready_time":data.ready_time}},
					callback:function(r){
					if(r.message == "SUCCESS"){
							cur_frm.set_value("is_pickup_scheduled", true);
							cur_frm.save_or_update();
							frappe.msgprint(__("Pickup service scheduled successfully."));
						}
					}
				})
			},
			__("Schedule pickup ?"), __("Yes"));
}

cur_frm.cscript.convert_shipment_amount = function(frm){
	frappe.call({
		method: "erpnext.setup.utils.get_exchange_rate",
		args: {
			from_currency: frm.doc.shipment_currency,
			to_currency: frm.doc.currency 
		},
		callback: function(r, rt) {
			cur_frm.set_value("base_shipment_amount", flt(frm.doc.shipment_amount * r.message));
		}
	})
	
}

cur_frm.cscript.enable_fedex_fields = function(frm){
	var fields = ["drop_off_type", "service_type", "packaging_type", "total_handling_units",
			"shipping_payment_by", "duties_payment_by", "no_of_packages", "shipment_purpose",
			"shipment_type", "octroi_payment_by"];
	$.each(fields, function(i, field){
		frm.toggle_reqd(field, frm.doc.is_fedex_account);	
	});
	frm.toggle_enable("fedex_tracking_id", !frm.doc.is_fedex_account);
	// frm.fields_dict.items.grid.toggle_reqd("package_id", frm.doc.is_fedex_account);
	// frm.fields_dict.items.grid.set_column_disp("package_id", frm.doc.is_fedex_account);
	// frm.fields_dict.items.grid.toggle_reqd("no_of_pieces", frm.doc.is_fedex_account);
}


cur_frm.set_query('weight_uom', 'items', function(doc, cdt, cdn) {
	var d  = locals[cdt][cdn];
	var filter_value = doc.is_fedex_account ? ["in", ["LB", "Kg"]] : ["not in", [""]];
	return {
		filters:{
			"name": filter_value
		}
	}
});


cur_frm.set_query('fedex_package', 'item_packing_details', function(doc, cdt, cdn) {
	var d  = locals[cdt][cdn];
	var package_ids = get_entity_list("fedex_package_details", "fedex_package");
	return {
		filters:{
			"name":["in", package_ids]
		}
	}
});

cur_frm.set_query('item_code', 'item_packing_details', function(doc, cdt, cdn) {
	var d  = locals[cdt][cdn];
	var items = get_entity_list("items", "item_code");
	return {
		filters:{
			"name":["in", items]
		}
	}
});

frappe.ui.form.on("Packing Slip Item", "rate", function(frm, cdt, cdn){
	var row = locals[cdt][cdn];
	frappe.model.set_value(row.doctype, row.name, "amount", flt(row.rate) * flt(row.qty));
})

frappe.ui.form.on("Packing Slip Item", "qty", function(frm, cdt, cdn){
	var row = locals[cdt][cdn];
	frappe.model.set_value(row.doctype, row.name, "amount", flt(row.rate) * flt(row.qty));
})

cur_frm.cscript.get_items = function(doc, cdt, cdn) {
	this.frm.call({
		doc: this.frm.doc,
		method: "get_items",
		callback: function(r) {
			if(!r.exc){
				cur_frm.set_value("fedex_package_details", []);
				cur_frm.set_value("item_packing_details", []);
				cur_frm.set_value("no_of_packages", "");
				cur_frm.refresh_fields();
			}
		}
	});
}