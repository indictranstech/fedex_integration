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
	if doc.is_fedex_account:
		if doc.no_of_packages:
			try:
				fedex = FedexController()
				shipment  = fedex.init_shipment(doc)
				for index, pkg in enumerate(doc.fedex_package_details):
					tracking_id = ""
					if index == 0:
						shipment.RequestedShipment.TotalWeight.Units = uom_mapper.get(doc.gross_weight_uom)
						shipment.RequestedShipment.TotalWeight.Value = doc.gross_weight_pkg
						fedex.set_package_data(pkg, shipment, index + 1)
						shipment.send_validation_request()
					else:
						shipment.RequestedShipment.MasterTrackingId.TrackingNumber = doc.fedex_tracking_id
						shipment.RequestedShipment.MasterTrackingId.TrackingIdType.value = 'EXPRESS'
						fedex.set_package_data(pkg, shipment, index + 1)		
					shipment.send_request()
					FedexController.validate_fedex_shipping_response(shipment, pkg.fedex_package)
					tracking_id = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].TrackingIds[0].TrackingNumber
					if index == 0:
						doc.fedex_tracking_id = tracking_id
					set_package_details(pkg, shipment_response, tracking_id)
					fedex.store_label(shipment, tracking_id, doc.name)
			except Exception as e:
				FedexController.delete_shipment(doc.fedex_tracking_id) if doc.fedex_tracking_id else ""
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
	pkg_wt = defaultdict(float)
	for row in doc.items:
		pkg_wt[row.package_id] += row.qty * row.net_weight
	for row in doc.fedex_package_details:
		row.package_weight = pkg_wt.get(row.fedex_package, 0)
		row.uom = doc.gross_weight_uom


def set_package_details(pkg, shipment_response, tracking_id, ps_name):
	pkg.shipment_response = shipment_response
	pkg.package_weight = tracking_id			