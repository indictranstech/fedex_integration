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
					if (r.message.length == frm.doc.no_of_packages){
						$.each(package_array, function(i, d) {
							var row = frappe.model.add_child(frm.doc, "FedEx Package Details", "fedex_package_details");
							row.fedex_package = r.message[i].name;
						});
						cur_frm.refresh_field("fedex_package_details");
						cur_frm.cscript.set_package_uom(frm);
					}else{
						frappe.msgprint(__(repl("%(pkg_no)s Packages not found in FedEx Package master.\
												Please add packages in master & try again.", {"pkg_no":frm.doc.no_of_packages})));
					}
				}
			});
			
		}
	},
	refresh:function(frm){
		if(frm.doc.is_fedex_account){
			if(frm.doc.docstatus == 1){
				$(frm.fields_dict.master_tracking_id.wrapper).html(
					frappe.render_template("fedex_tracking",{"tracking_ids":frm.doc.fedex_package_details}));
				if(!frm.doc.is_pickup_scheduled){
					cur_frm.add_custom_button(__('Schedule Pickup'),
						function() { cur_frm.cscript.schedule_pickup(); }, 'icon-retweet', 'btn-default');	
				}
			}

		}else{
			$(frm.fields_dict.master_tracking_id.wrapper).html("");
		}
		cur_frm.cscript.enable_fedex_fields(frm);

	},
	set_kg:function(frm){
		if (frm.doc.set_kg){
			cur_frm.events.init_weight_uom_change_process(frm, "Kg", "CM", "set_lb");
		}
	},
	set_lb:function(frm){
		if (frm.doc.set_lb){
			cur_frm.events.init_weight_uom_change_process(frm, "LB", "IN", "set_kg");
		}
	},
	onload:function(frm){
		cur_frm.cscript.set_weight_uom_formatter();
	},
	init_weight_uom_change_process:function(frm, wt_uom, pkg_uom, field){
		cur_frm.cscript.set_box_uom(frm, pkg_uom);
		cur_frm.cscript.set_item_weight_uom(wt_uom);
		cur_frm.set_value(field, 0);
		cur_frm.cscript.set_gross_wt_uom(frm, wt_uom);
		cur_frm.refresh_field("items");
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
					if(r.message.response == "SUCCESS"){
							cur_frm.set_value("is_pickup_scheduled", true);
							cur_frm.set_value("pickup_no", r.message.pickup_id);
							cur_frm.set_value("pickup_location", r.message.location_no);
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
		query:"fedex_integration.fedex_integration.doctype.fedex_package.fedex_package.package_query",
		filters:{
			"name":package_ids
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
	frappe.model.set_value(row.doctype, row.name, "total_weight", flt(row.net_weight) * flt(row.qty));
	cur_frm.cscript.set_total_handling_units(frm);
	cur_frm.cscript.calculate_total_pkg_wt(frm);
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
				cur_frm.cscript.set_total_handling_units(cur_frm);
				cur_frm.cscript.calculate_total_pkg_wt(cur_frm);
				cur_frm.refresh_fields();
			}
		}
	});
}

frappe.ui.form.on("FedEx Notification",{
	select_all:function(frm ,cdt,cdn){
		var row = locals[cdt][cdn];
		$.each(["shipment", "tendered", "exception", "delivery"], function(index, field) {
			frappe.model.set_value(row.doctype, row.name, field, row.select_all);
		})
	}
})

cur_frm.cscript.set_box_uom = function(frm, uom){
	$.each(frm.doc.fedex_package_details || [], function(i, row) {
		frappe.model.set_value(row.doctype, row.name, "unit", uom || "");
	});
}

frappe.ui.form.on("FedEx Notification",{
	select_all:function(frm ,cdt,cdn){
		var row = locals[cdt][cdn];
		$.each(["shipment", "tendered", "exception", "delivery"], function(index, field) {
			frappe.model.set_value(row.doctype, row.name, field, row.select_all);
		})
	}
})

frappe.ui.form.on("Packing Slip Item", "net_weight", function(frm, cdt, cdn){
	var row = locals[cdt][cdn];
	frappe.model.set_value(row.doctype, row.name, "total_weight", flt(row.net_weight) * flt(row.qty));
	cur_frm.cscript.calculate_total_pkg_wt(frm);
})

cur_frm.cscript.set_item_weight_uom = function(uom){
	$.each(cur_frm.doc.items || [], function(i, row) {
		frappe.model.set_value(row.doctype, row.name, "weight_uom", uom);
	});
}

cur_frm.cscript.set_package_uom = function(frm){
	var pkg_uom = "";
	if(frm.doc.set_kg){
		pkg_uom = "CM";
	}else if(frm.doc.set_lb){
		pkg_uom = "IN";
	}
	cur_frm.cscript.set_box_uom(frm, pkg_uom);
}

cur_frm.cscript.set_total_handling_units = function(frm){
	var total_qty = 0;
	$.each(frm.doc.items || [], function(i, row) {
		total_qty += row.qty;
	});
	cur_frm.set_value("total_handling_units", total_qty);	
}


frappe.ui.form.on("Packing Slip Item", "items_remove", function(frm) {
	cur_frm.cscript.set_total_handling_units(frm);
	cur_frm.cscript.calculate_total_pkg_wt(frm);
});

cur_frm.cscript.calculate_total_pkg_wt = function(frm){
	var ps_detail = frm.doc.items || [];
	cur_frm.cscript.calc_net_total_pkg(frm.doc, ps_detail);
}


// Calculate Net Weight of Package according to clients requirement
cur_frm.cscript.calc_net_total_pkg = function(doc, ps_detail) {
	var net_weight_pkg = 0;
	doc.net_weight_uom = (ps_detail && ps_detail.length) ? ps_detail[0].weight_uom : '';
	doc.gross_weight_uom = doc.net_weight_uom;

	for(var i=0; i<ps_detail.length; i++) {
		var item = ps_detail[i];
		if(item.weight_uom != doc.net_weight_uom) {
			msgprint(__("Different UOM for items will lead to incorrect (Total) Net Weight value. Make sure that Net Weight of each item is in the same UOM."));
			validated = false;
		}
		net_weight_pkg += flt(item.total_weight);
	}

	doc.net_weight_pkg = _round(net_weight_pkg, 2);
	doc.gross_weight_pkg = doc.net_weight_pkg
	refresh_many(['net_weight_pkg', 'net_weight_uom', 'gross_weight_uom', 'gross_weight_pkg']);
}


cur_frm.cscript.set_gross_wt_uom = function(frm, uom){
	frm.doc.gross_weight_uom = uom;
	frm.doc.net_weight_uom = uom;
	refresh_many(['net_weight_uom', 'gross_weight_uom']);
}

cur_frm.cscript.change_grid_labels = function(label, wt_uom){
	var df = frappe.meta.get_docfield("Packing Slip Item", "net_weight", cur_frm.doc.name);
	if(df) df.label = label;
	cur_frm.refresh_fields();
}

frappe.ui.form.on("Packing Slip Item", "total_weight", function(frm, cdt, cdn){
	cur_frm.cscript.calculate_total_pkg_wt(frm);
})

cur_frm.cscript.set_weight_uom_formatter = function(){
	$.each(["net_weight", "total_weight"], function(i, field){
		var df = frappe.meta.get_docfield("Packing Slip Item", field, cur_frm.doc.name);
		df.formatter = function(value, df, options, doc) {
			var uom = doc.weight_uom ? doc.weight_uom : ""
			return frappe.form.formatters._right( (value==null || value==="") ? "" : value + "  " + uom , options)
		}
	});
}