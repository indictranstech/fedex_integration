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


uom_mapper = {"Kg":"KG", "LB":"LB"}

def validate_for_package_count(doc, method):
	if doc.is_fedex_account and doc.no_of_packages != len(doc.fedex_package_details):
		frappe.throw(_("No of Packages must be equal to FEDEX PACKING DETAILS table"))


def validate_package_details(doc, method):
	if doc.is_fedex_account:
		item_package_ids = [row.package_id for row in doc.items]
		package_ids = []
		for row in doc.fedex_package_details:
			if row.fedex_package not in item_package_ids:
				frappe.throw(_("Package {0} not linked to any item".format(row.fedex_package)))
			package_ids.append(row.fedex_package)
		for row in doc.items:
			if row.package_id not in package_ids:
				frappe.throw(_("Package {0} linked to item {1} in row {2} not found in \
									FEDEX PACKING DETAILS table".format(row.package_id, row.item_code, row.idx)))


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
	except Exception as ex:
		frappe.msgprint('Cannot update Total Amount: %s' % cstr(ex))

def update_package_details(doc, method):
	if doc.is_fedex_account:
		pkg_wt = defaultdict(float)
		total_qty = 0
		for row in doc.items:
			pkg_wt[row.package_id] += row.qty * row.net_weight
			total_qty += row.qty
		doc.total_handling_units = cint(total_qty)
		for row in doc.fedex_package_details:
			row.package_weight = pkg_wt.get(row.fedex_package, 0)
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
		print frappe.get_traceback()
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
