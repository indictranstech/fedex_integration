from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, flt
import logging
import sys
import json
from fedex.config import FedexConfig
from fedex.services.ship_service import FedexProcessShipmentRequest
from fedex.services.ship_service import FedexDeleteShipmentRequest
from frappe.utils.file_manager import save_file
from fedex.services.track_service import FedexTrackRequest
import frappe.client as client
import base64


class FedexController():
	
	""" A Higher-Level wrapper for Fedex python library 
		which handles API like Shipment, Tracking, GET Rate
		& other supplementary tasks. """

	uom_mapper = {"Kg":"KG", "LB":"LB"}
	settings = frappe.db.get_singles_dict("Fedex Settings")
	CONFIG_OBJ = FedexConfig(key= settings.get("fedex_key"),
	                     password= client.get_password("Fedex Settings", None, "fedex_password"),
	                     account_number= settings.get("fedex_account_no"),
	                     meter_number= settings.get("fedex_meter_number"),
	                     freight_account_number= "510087020",
	                     use_test_server=True)


	def init_shipment(self, doc):
		shipment = FedexController.set_shipment_details(doc)
		FedexController.set_shipper_info(doc.company_address_name, shipment)
		FedexController.set_recipient_info(doc, shipment)
		# FedexController.set_biller_info(doc.customer_address, shipment)
		FedexController.set_fedex_label_info(shipment)
		# FedexController.set_package_details(doc, shipment)
		FedexController.set_commodities_info(doc, shipment)
		self.pkg_count = doc.no_of_packages
		return shipment


	@classmethod
	def set_shipment_details(cls_obj, doc):
		shipment = FedexProcessShipmentRequest(cls_obj.CONFIG_OBJ)
		shipment.RequestedShipment.DropoffType = doc.drop_off_type
		shipment.RequestedShipment.ServiceType = doc.service_type
		shipment.RequestedShipment.PackagingType = doc.packaging_type
		# shipment.RequestedShipment.FreightShipmentDetail.FedExFreightAccountNumber \
		# 											= cls_obj.CONFIG_OBJ.freight_account_number
		
		# shipment.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = cls_obj.CONFIG_OBJ.account_number
		shipment.RequestedShipment.ShippingChargesPayment.PaymentType = doc.shipping_payment_by
		shipment.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = \
		    cls_obj.CONFIG_OBJ.account_number if doc.shipping_payment_by == "SENDER" else doc.shipping_payment_Account

		shipment.RequestedShipment.CustomsClearanceDetail.DutiesPayment.PaymentType = doc.duties_payment_by
		shipment.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor.ResponsibleParty.AccountNumber = \
			cls_obj.CONFIG_OBJ.account_number if doc.duties_payment_by == "SENDER" else doc.duties_payment_Account			

		# spec = shipment.create_wsdl_object_of_type('ShippingDocumentSpecification')
		# spec.ShippingDocumentTypes = [spec.CertificateOfOrigin]
		# shipment.RequestedShipment.ShippingDocumentSpecification = spec

		# role = shipment.create_wsdl_object_of_type('FreightShipmentRoleType')
		# shipment.RequestedShipment.FreightShipmentDetail.Role = role.SHIPPER
		# shipment.RequestedShipment.FreightShipmentDetail.CollectTermsType = 'STANDARD'
		return shipment	
	
	
	@classmethod
	def set_shipper_info(cls_obj, shipper_id, shipment):
		shipper_details = frappe.db.get_value("Address", shipper_id, "*", as_dict=True)
		
		shipment.RequestedShipment.Shipper.AccountNumber = cls_obj.CONFIG_OBJ.account_number
		shipment.RequestedShipment.Shipper.Contact.PersonName = shipper_details.get("address_title")
		shipment.RequestedShipment.Shipper.Contact.CompanyName = shipper_details.get("company")
		shipment.RequestedShipment.Shipper.Contact.PhoneNumber = shipper_details.get("phone")
		shipment.RequestedShipment.Shipper.Address.StreetLines = [shipper_details.get("address_line1"),\
																	 shipper_details.get("address_line2")]
		shipment.RequestedShipment.Shipper.Address.City = shipper_details.get("city")
		shipment.RequestedShipment.Shipper.Address.StateOrProvinceCode = shipper_details.get("state_code")
		shipment.RequestedShipment.Shipper.Address.PostalCode = shipper_details.get("pincode")
		shipment.RequestedShipment.Shipper.Address.CountryCode = shipper_details.get("country_code")
		shipment.RequestedShipment.Shipper.Address.Residential = True if shipper_details.get("is_residential_address") \
																else False


	@classmethod	
	def set_recipient_info(cls_obj, doc, shipment):
		recipient_details = frappe.db.get_value("Address", doc.shipping_address_name, "*", as_dict=True)
		
		shipment.RequestedShipment.Recipient.Contact.PersonName = recipient_details.get("address_title")
		shipment.RequestedShipment.Recipient.Contact.CompanyName = recipient_details.get("address_title")
		shipment.RequestedShipment.Recipient.Contact.PhoneNumber = recipient_details.get("phone")
		shipment.RequestedShipment.Recipient.Address.StreetLines = [recipient_details.get("address_line1"), \
																		recipient_details.get("address_line1")]
		shipment.RequestedShipment.Recipient.Address.City = recipient_details.get("city")
		shipment.RequestedShipment.Recipient.Address.StateOrProvinceCode = recipient_details.get("state_code")
		shipment.RequestedShipment.Recipient.Address.PostalCode = recipient_details.get("pincode")
		shipment.RequestedShipment.Recipient.Address.CountryCode = recipient_details.get("country_code")

		# This is needed to ensure an accurate rate quote with the response.
		shipment.RequestedShipment.Recipient.Address.Residential = True if recipient_details.get("is_residential_address") else False
		shipment.RequestedShipment.FreightShipmentDetail.TotalHandlingUnits = doc.total_handling_units

	    
	@classmethod
	def set_biller_info(cls_obj, billing_address, shipment):
		biller_details = frappe.db.get_value("Address", billing_address, "*", as_dict=True)
		
		billing_contact_address = shipment.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor.ResponsibleParty
		billing_contact_address.Contact.PersonName = biller_details.get("address_title")
		billing_contact_address.Contact.CompanyName = biller_details.get("company")
		billing_contact_address.Contact.PhoneNumber = biller_details.get("phone")
		billing_contact_address.Address.StreetLines = [biller_details.get("address_line1"), biller_details.get("address_line2")]
		billing_contact_address.Address.City = biller_details.get("city")
		billing_contact_address.Address.StateOrProvinceCode = biller_details.get("state_code")
		billing_contact_address.Address.PostalCode = biller_details.get("pincode")
		billing_contact_address.Address.CountryCode = biller_details.get("country_code")
		billing_contact_address.Address.Residential = True if biller_details.get("is_residential_address") else False	    
		billing_contact_address.AccountNumber = cls_obj.CONFIG_OBJ.account_number

	@staticmethod
	def set_fedex_label_info(shipment):
		shipment.RequestedShipment.LabelSpecification.LabelFormatType = "COMMON2D"
		shipment.RequestedShipment.LabelSpecification.ImageType = 'PDF'
		shipment.RequestedShipment.LabelSpecification.LabelStockType = 'PAPER_7X4.75'
		shipment.RequestedShipment.LabelSpecification.LabelPrintingOrientation = 'BOTTOM_EDGE_OF_TEXT_FIRST'
		shipment.RequestedShipment.EdtRequestType = 'NONE'

		if hasattr(shipment.RequestedShipment.LabelSpecification, 'LabelOrder'):
		    del shipment.RequestedShipment.LabelSpecification.LabelOrder  # Delete, not using.

	
	@staticmethod
	def set_commodities_info(doc, shipment):
		for row in doc.items:
			commodity_dict = {
				"Name":row.get("item_code"),
				"Description":row.get("description"),
				"Weight": {"Units": FedexController.uom_mapper.get(row.get("weight_uom")),\
								 "Value":row.net_weight},
				"NumberOfPieces":row.get("no_of_pieces"),
				"CountryOfManufacture":"IN",
				"Quantity":row.get("qty"),
				"QuantityUnits":"EA",
				"UnitPrice":{"Currency":doc.currency, "Amount":row.amount},
				"CustomsValue":{"Currency":doc.currency, "Amount":row.amount}
			}
			shipment.RequestedShipment.CustomsClearanceDetail.Commodities.append(commodity_dict)
		shipment.RequestedShipment.CustomsClearanceDetail.CustomsValue.Amount = 145715.00
		shipment.RequestedShipment.CustomsClearanceDetail.CustomsValue.Currency = doc.currency

	@classmethod
	def set_package_details(cls_obj, doc, shipment):
		packing_slips = frappe.get_all("Packing Slip", fields=["*"], filters={"delivery_note":doc.name, "docstatus":1}, 
					order_by="creation asc", debug=1)
		print "packing slips____________", packing_slips
		for ps in packing_slips:	
			FedexController.set_package_data(shipment)

		# pallet_weight = shipment.create_wsdl_object_of_type('Weight')
		# pallet_weight.Value = total_weight
		# pallet_weight.Units = "KG"
		# shipment.RequestedShipment.FreightShipmentDetail.PalletWeight = pallet_weight

	
	def set_package_data(self, pkg, shipment, pkg_no):
		package = shipment.create_wsdl_object_of_type('RequestedPackageLineItem')
		package.PhysicalPackaging = 'BOX'
		# adding weight
		print "package check uom_______", pkg.uom
		package_weight = shipment.create_wsdl_object_of_type('Weight')
		package_weight.Units = FedexController.uom_mapper.get(pkg.uom)
		package_weight.Value = pkg.package_weight
		package.Weight = package_weight

		package.SequenceNumber = pkg_no
		shipment.RequestedShipment.RequestedPackageLineItems = [package]
		shipment.RequestedShipment.PackageCount = self.pkg_count
		
	@staticmethod	
	def validate_fedex_shipping_response(shipment, package_id):
		msg = ''
		try:
		    msg = shipment.response.Message
		except:
		    pass
		if shipment.response.HighestSeverity == "SUCCESS":
		    frappe.msgprint('Shipment is created successfully in Fedex service for package {0}.'.format(package_id))
		elif shipment.response.HighestSeverity == "NOTE":
		    frappe.msgprint('Shipment is created in Fedex service with the following note:\n%s' % msg)
		    for notification in shipment.response.Notifications:
		        frappe.msgprint('Code: %s, %s' % (notification.Code, notification.Message))
		elif shipment.response.HighestSeverity == "WARNING":
		    frappe.msgprint('Shipment is created in Fedex service with the following warning:\n%s' % msg)
		    for notification in shipment.response.Notifications:
		        frappe.msgprint('Code: %s, %s' % (notification.Code, notification.Message))
		else:  # ERROR, FAILURE
		    frappe.throw('Creating of Shipment in Fedex service failed.')
		    for notification in shipment.response.Notifications:
		        frappe.msgprint('Code: %s, %s' % (notification.Code, notification.Message))

	@staticmethod
	def store_label(shipment, tracking_id, ps_name):
		label_image_data = base64.b64decode(shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].Label.Parts[0].Image)
		save_file('FEDEX-ID-{0}.pdf'.format(tracking_id), label_image_data, "Packing Slip", ps_name) 


	@classmethod	
	def delete_shipment(cls_obj, tracking_id):
		del_request = FedexDeleteShipmentRequest(cls_obj.CONFIG_OBJ)
		del_request.DeletionControlType = "DELETE_ALL_PACKAGES"
		del_request.TrackingId.TrackingNumber = tracking_id
		del_request.TrackingId.TrackingIdType = 'EXPRESS'
		try:
			del_request.send_request()
		except Exception as ex:
			frappe.throw('Fedex API: ' + cstr(ex))

		if del_request.response.HighestSeverity == "SUCCESS":
			frappe.msgprint('Shipment with tracking number %s is deleted successfully.' % tracking_id)
		else:
			for notification in del_request.response.Notifications:
				frappe.msgprint('Code: %s, %s' % (notification.Code, notification.Message))
				frappe.throw('Canceling of Shipment in Fedex service failed.')