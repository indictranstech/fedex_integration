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


def get_fedex_account_details():
	return frappe.db.get_singles_dict("Fedex Settings")


def init_fedex_shipment(doc, method):
	fedex = FedexController()
	shipment  = fedex.make_shipment(doc)
	shipment.send_validation_request()
	frappe.errprint(shipment.RequestedShipment)
	print "shipement response_____________________", shipment.response.HighestSeverity
	jkjkjjjjkj
	# Fires off the request, sets the 'response' attribute on the object.
	shipment.send_request()

	print "HighestSeverity: {}".format(shipment.response.HighestSeverity)

	# Getting the tracking number from the new shipment.
	print "Master Tracking ID___________#: {}".format(shipment.response.CompletedShipmentDetail.MasterTrackingId.TrackingNumber)

	print "Check Child tracking IDS________", shipment.response.CompletedShipmentDetail
	doc.fedex_tracking_id = shipment.response.CompletedShipmentDetail.MasterTrackingId.TrackingNumber
	
	# # Net shipping costs.
	amount = shipment.response.CompletedShipmentDetail.ShipmentRating.\
									ShipmentRateDetails[0].TotalNetCharge.Amount
	print "Net Shipping Cost (US$): {}".format(amount)

	doc.shipment_amount = amount

	
	from fedex.tools.conversion import sobject_to_dict, sobject_to_json
	response_dict = sobject_to_json(shipment.response)
	file = open(r"normal_shipment", "w")
	file.write(response_dict)
	file.close()
	# # # Get the label image in ASCII format from the reply. Note the list indices
	# # we're using. You'll need to adjust or iterate through these if your shipment
	# # has multiple packages.

	ascii_label_data = shipment.response.CompletedShipmentDetail.ShipmentDocuments[0].Parts[0].Image
	# doc.fedex_label_data = ascii_label_data
	label_binary_data = binascii.a2b_base64(ascii_label_data)
	save_file('FedxTrackID{0}.pdf'.format(doc.fedex_tracking_id), label_binary_data, doc.doctype, doc.name)


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

