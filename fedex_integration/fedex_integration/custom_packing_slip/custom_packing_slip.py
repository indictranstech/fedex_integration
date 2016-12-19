from __future__ import unicode_literals
import frappe
from frappe.utils import flt, cint, cstr
from frappe import _
import logging
import sys
import binascii
import json
from fedex.config import FedexConfig
from fedex.services.ship_service import FedexProcessShipmentRequest
from frappe.utils.file_manager import save_file
from fedex.services.track_service import FedexTrackRequest
from fedex_integration.fedex_integration.fedex_controller import FedexController
from collections import defaultdict
from erpnext.setup.utils import get_exchange_rate


uom_mapper = {"Kg":"KG", "LB":"LB"}

def validate_for_package_count(doc, method):
	if doc.no_of_packages != len(doc.fedex_package_details):
		frappe.throw(_("No of Packages must be equal to PACKAGE DETAILS table"))


def validate_package_details(doc, method):
	item_packing_dict, item_package_ids, package_wt, no_of_pieces, total_qty = get_item_packing_dict(doc)
	qty_dict = {row.item_code:row.qty for row in doc.items}
	package_ids = []
	for row in doc.fedex_package_details:
		if row.fedex_package not in item_package_ids:
			frappe.throw(_("Package {0} not linked to any item".format(row.fedex_package)))
		package_ids.append(row.fedex_package)

	packed_items = item_packing_dict.keys()
	for row in doc.items:
		if row.item_code not in packed_items:
			frappe.throw(_("Item {0} in row {1} not found in Item Packing Details \
				table".format(row.item_code, row.idx)))
		if row.qty != item_packing_dict.get(row.item_code, 0):
			frappe.throw(_("Item {0} quantity {1} is not equal to quantity {2} mentioned in\
				Item Packing Details table.".format(row.item_code, flt(row.qty), item_packing_dict.get(row.item_code, 0))))

	set_net_weight_of_package(doc)
	if doc.is_fedex_account:
		validate_for_email_notification(doc)

def init_fedex_shipment(doc, method):
	if doc.is_fedex_account and doc.no_of_packages:
		try:
			label_data = tuple()
			fedex = FedexController(doc.shipment_forwarder)
			shipment  = fedex.init_shipment(doc)
			for index, pkg in enumerate(doc.fedex_package_details):
				if index:
					shipment.RequestedShipment.MasterTrackingId.TrackingNumber = doc.fedex_tracking_id
					shipment.RequestedShipment.MasterTrackingId.TrackingIdType.value = 'EXPRESS'
					fedex.set_package_data(pkg, shipment, index + 1, doc)
				else:
					shipment.RequestedShipment.TotalWeight.Units = uom_mapper.get(doc.gross_weight_uom)
					shipment.RequestedShipment.TotalWeight.Value = doc.gross_weight_pkg
					fedex.set_package_data(pkg, shipment, index + 1, doc)
					shipment.send_validation_request()
				shipment.send_request()
				fedex.validate_fedex_shipping_response(shipment, pkg.fedex_package)
				tracking_id = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].TrackingIds[0].TrackingNumber
				if not index:
					doc.fedex_tracking_id = tracking_id
				set_package_details(pkg, cstr(shipment.response), tracking_id)
				fedex.store_label(shipment, tracking_id, doc.name)
		except Exception as e:
			fedex.delete_shipment(doc.fedex_tracking_id) if doc.fedex_tracking_id else ""
			frappe.throw(cstr(e))	
		update_shipment_rate(shipment, doc)


def update_shipment_rate(shipment, doc):
	try:
		for shipment_rate_detail in shipment.response.CompletedShipmentDetail.ShipmentRating.ShipmentRateDetails:
			if shipment_rate_detail.RateType == shipment.response.CompletedShipmentDetail.ShipmentRating.ActualRateType:
				doc.update({
				    "shipment_amount": flt(shipment_rate_detail.TotalNetCharge.Amount),
				    "shipment_currency": cstr(shipment_rate_detail.TotalNetCharge.Currency)
				})
				break
		set_base_shipment_amount(doc)
	except Exception as ex:
		frappe.msgprint('Cannot update Total Amount: %s' % cstr(ex))

def update_package_details(doc, method):
	item_packing_dict, item_package_ids, package_wt, no_of_pieces, total_qty = get_item_packing_dict(doc)
	doc.total_handling_units = cint(total_qty)
	for row in doc.items:
		row.no_of_pieces = len(no_of_pieces.get(row.item_code))

	for row in doc.fedex_package_details:
		row.package_weight = package_wt.get(row.fedex_package, 0)
		row.uom = doc.gross_weight_uom


def set_package_details(pkg, shipment_response, tracking_id):
	pkg.shipment_response = shipment_response
	pkg.fedex_tracking_id = tracking_id

def validate_postal_code(doc, method):
	if doc.is_fedex_account:
		fedex = FedexController(doc.shipment_forwarder)
		try:
			fedex.validate_postal_address(doc.shipping_address_name)
		except Exception,e:
			frappe.throw(cstr(e))


@frappe.whitelist()
def schedule_pickup(request_data):
	request_data = json.loads(request_data)
	fedex = FedexController(request_data.get("fedex_account"))
	try:
		response = fedex.schedule_pickup(request_data)
		return response
	except Exception,e:
		frappe.throw(cstr(e))


def get_fedex_shipment_rate(doc, method):
	if doc.is_fedex_account:
		fedex = FedexController(doc.shipment_forwarder)
		try:
			rate_request = fedex.get_shipment_rate(doc)
			set_shipment_rate(doc, rate_request)
		except Exception,e:
			print "traceback__________", frappe.get_traceback()
			frappe.throw(cstr(e))

def set_shipment_rate(doc, rate_request):
	for service in rate_request.response.RateReplyDetails:
		for rate_detail in service.RatedShipmentDetails:
			doc.shipment_currency = rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Currency
			doc.shipment_amount = rate_detail.ShipmentRateDetail.TotalNetFedExCharge.Amount
	set_base_shipment_amount(doc)


def set_base_shipment_amount(doc):
	exchange_rate = get_exchange_rate(doc.shipment_currency, doc.currency)
	doc.base_shipment_amount = flt(doc.shipment_amount) * flt(exchange_rate)


def validate_for_existing_packing_slip(doc, method):
	ps = frappe.db.get_value("Packing Slip", {"name":["not in", [doc.name]],\
											"delivery_note":doc.delivery_note, "docstatus":["in", ["0"]]}, "name")
	if ps:
		frappe.throw(_("Packing Slip {0} already created against delivery note {1}."\
							.format(ps, doc.delivery_note)))


@frappe.whitelist()
def warehouse_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select distinct wr.name, CONCAT_WS(" : ", "Actual Qty", ifnull(bin.actual_qty, 0))
							from `tabWarehouse` wr
							left join `tabBin` bin
							on wr.name = bin.warehouse
							where wr.is_group = 0
							and wr.company in ("", %(company)s)
							and bin.item_code = %(item)s
							and wr.`{key}` like %(txt)s
							order by name desc
							limit %(start)s, %(page_len)s """.format(key=frappe.db.escape(searchfield)),
							{
							 	"txt": "%%%s%%" % frappe.db.escape(txt),
								"start": start,
								"page_len": page_len,
								"item":filters.get("item"),
								"company":filters.get("company", "")
							})

def write_response_to_file(file_name, response):
	with open(file_name, "w") as fi:
		fi.write(response)


def verify_postal_code(doc, method):
	if doc.is_fedex_account:
		address = frappe.db.get_value("Address", {"name":doc.get("shipping_address_name")}, "*", as_dict=True)
		if not frappe.db.get_value("FedEx Postal Code", {"postal_code":address.get("pincode"), \
			"country_name":address.get("country")}, "name"):
			frappe.throw(_("FedEx shipment delivery is not allowed at Recipient postal pode {0}".format(address.get("pincode"))))


def get_item_packing_dict(doc):
	item_packing_dict = defaultdict(float)
	package_wt = defaultdict(float)
	no_of_pieces = defaultdict(set)
	item_package_ids = set()
	total_qty = 0
	for row in doc.item_packing_details:
		item_packing_dict[row.item_code] += row.qty
		package_wt[row.fedex_package] += flt(row.qty) * flt(row.net_weight)
		no_of_pieces[row.item_code].add(row.fedex_package)
		item_package_ids.add(row.fedex_package)
		total_qty += row.qty
	return item_packing_dict, item_package_ids, package_wt, no_of_pieces, total_qty


def set_net_weight_of_package(doc):
	item_wt = {row.item_code:row.net_weight for row in doc.items}
	for row in doc.item_packing_details:
		row.net_weight = item_wt.get(row.item_code, 0)

def validate_for_email_notification(doc):
	notify_list = []
	for row in doc.fedex_notification:
		if row.notify_to in notify_list:
			frappe.throw(_("In FedEx Notification table, duplicate entry of {0} not allowed.".format(row.notify_to)))
		notify_list.append(row.notify_to)
		if not any([row.shipment, row.delivery, row.tendered, row.exception]):
			frappe.throw(_("Please check any one notification type \
							in FedEx Notification table in row {0}".format(row.idx)))
		if row.notify_to in ["Other-1", "Other-2", "Other-3"] and not row.email_id:
			frappe.throw(_("For FedEx Notification table, Please enter email id in row {0}.".format(row.idx)))


