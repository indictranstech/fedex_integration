from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, flt
import logging
import sys
from fedex.config import FedexConfig
from fedex.services.ship_service import FedexProcessShipmentRequest
from frappe.utils.file_manager import save_file
import binascii
import json
from fedex.services.track_service import FedexTrackRequest
from fedex_controller import FedexController



uom_mapper = {"Kg":"KG", "LB":"LB"}

def init_fedex_shipment(doc, method):
	packing_slips = frappe.get_all("Packing Slip", fields=["*"], filters={"delivery_note":doc.name, "docstatus":0}, 
					order_by="creation asc")
	pkg_count = len(packing_slips)
	if pkg_count:
		try:
			fedex = FedexController()
			shipment  = fedex.init_shipment(doc, packing_slips, pkg_count)
			fedex.set_package_data(packing_slips[0], shipment, 1)
			shipment.RequestedShipment.TotalWeight.Units = uom_mapper.get(packing_slips[0].get("gross_weight_uom"))
			shipment.RequestedShipment.TotalWeight.Value = sum(flt(ps.get("gross_weight_pkg")) for ps in packing_slips)
			shipment.send_validation_request()
			shipment.send_request()
			doc.fedex_tracking_id = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].TrackingIds[0].TrackingNumber
			FedexController.validate_fedex_shipping_response(shipment, packing_slips[0].get("name"))
			fedex.store_label(shipment, doc.fedex_tracking_id, packing_slips[0].get("name"))
		except Exception as e:
			FedexController.delete_shipment(doc.fedex_tracking_id) if doc.fedex_tracking_id else ""
			frappe.throw('Fedex API: ' + cstr(e))

		update_packing_slip(cstr(shipment.response), doc.fedex_tracking_id, packing_slips[0].get("name"))
		try:
			if pkg_count > 1:
				shipment.RequestedShipment.MasterTrackingId.TrackingNumber = doc.fedex_tracking_id
				shipment.RequestedShipment.MasterTrackingId.TrackingIdType.value = 'EXPRESS'
				for i, ps in enumerate(packing_slips[1:]):
					fedex.set_package_data(ps, shipment, i + 2)
					shipment.send_request()
					FedexController.validate_fedex_shipping_response(shipment, ps.get("name"))
					tracking_id = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].TrackingIds[0].TrackingNumber
					fedex.store_label(shipment, tracking_id, ps.get("name"))
					update_packing_slip(cstr(shipment.response), tracking_id, ps.get("name"))
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
		frappe.msgprint('Cannot update Total Amounts: %s' % cstr(ex))



def update_packing_slip(shipment_response, tracking_id, ps_name):
	frappe.db.sql(""" update `tabPacking Slip`
						set shipment_response = %s, fedex_tracking_id = %s 
						where name = %s """,(shipment_response, tracking_id, ps_name))
	frappe.db.commit()



def track_shipment():
	CONFIG_OBJ = FedexConfig(key= "u32EgTaZL7QV3MrW",
                     password= "Ax4y0Van5vDer3xJPSrTujdGZ",
                     account_number= "510087925",
                     meter_number= "118755658",
                     freight_account_number= "510087020",
                     use_test_server=True)
	track = FedexTrackRequest(CONFIG_OBJ)

	# Track by Tracking Number
	track.SelectionDetails.PackageIdentifier.Type = 'TRACKING_NUMBER_OR_DOORTAG'
	track.SelectionDetails.PackageIdentifier.Value = "1993156690"

	# FedEx operating company or delete
	del track.SelectionDetails.OperatingCompany

	# Can optionally set the TrackingNumberUniqueIdentifier
	# del track.SelectionDetails.TrackingNumberUniqueIdentifier

	# If you'd like to see some documentation on the ship service WSDL, un-comment
	# this line. (Spammy).
	# print(track.client)

	# Un-comment this to see your complete, ready-to-send request as it stands
	# before it is actually sent. This is useful for seeing what values you can
	# change.
	# print(track.SelectionDetails)
	# print(track.ClientDetail)
	# print(track.TransactionDetail)


	# Fires off the request, sets the 'response' attribute on the object.
	track.send_request()

	# This will show the reply to your track request being sent. You can access the
	# attributes through the response attribute on the request object. This is
	# good to un-comment to see the variables returned by the FedEx reply.
	print(track.response)

	# This will convert the response to a python dict object. To
	# make it easier to work with.
	# from fedex.tools.conversion import basic_sobject_to_dict
	# print(basic_sobject_to_dict(track.response))

	# This will dump the response data dict to json.
	# from fedex.tools.conversion import sobject_to_json
	# print(basic_sobject_to_dict(track.response))

	# Look through the matches (there should only be one for a tracking number
	# query), and show a few details about each shipment.
	print("== Results ==")
	for match in track.response.CompletedTrackDetails[0].TrackDetails:
	    print("Tracking #: {}".format(match.TrackingNumber))
	    if hasattr(match, 'TrackingNumberUniqueIdentifier'):
	        print("Tracking # UniqueID: {}".format(match.TrackingNumberUniqueIdentifier))
	    if hasattr(match, 'StatusDetail.Description'):
	        print("Status Description: {}".format(match.StatusDetail.Description))
	    if hasattr(match, 'StatusDetail.AncillaryDetails'):
	        print("Status AncillaryDetails Reason: {}".format(match.StatusDetail.AncillaryDetails[-1].Reason))
	        print("Status AncillaryDetails Description: {}"
	              "".format(match.StatusDetail.AncillaryDetails[-1].ReasonDescription))
	    if hasattr(match, 'ServiceCommitMessage'):
	        print("Commit Message: {}".format(match.ServiceCommitMessage))
	    if hasattr(match, 'Notification'):
	        print("Notification Severity: {}".format(match.Notification.Severity))
	        print("Notification Code: {}".format(match.Notification.Code))
	        print("Notification Message: {}".format(match.Notification.Message))
	    print("")

	    event_details = []
	    if hasattr(match, 'Events'):
	        for j in range(len(match.Events)):
	            event_match = match.Events[j]
	            event_details.append({'created': event_match.Timestamp, 'type': event_match.EventType,
	                                  'description': event_match.EventDescription})

	            if hasattr(event_match, 'StatusExceptionDescription'):
	                event_details[j]['exception_description'] = event_match.StatusExceptionDescription

	            print("Event {}: {}".format(j + 1, event_details[j]))

