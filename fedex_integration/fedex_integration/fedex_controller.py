from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, flt, now, get_datetime, now_datetime
from frappe import _
import logging
import sys
import json
from fedex.config import FedexConfig
from fedex.services.ship_service import FedexProcessShipmentRequest, FedexDeleteShipmentRequest
from fedex.services.country_service import FedexValidatePostalRequest
from fedex.services.pickup_service import FedexCreatePickupRequest
from fedex.services.rate_service import FedexRateServiceRequest
from frappe.utils.file_manager import save_file
from fedex.services.track_service import FedexTrackRequest
import frappe.client as client
import base64
import datetime

class FedexController():
	
	""" A Higher-Level wrapper for Fedex python library 
		which handles API like Shipment, Tracking, GET Rate
		& other supplementary tasks. """

	uom_mapper = {"Kg":"KG", "LB":"LB"}

	def __init__(self, fedex_account):
		settings = frappe.db.get_value("Shipment Forwarder", fedex_account, "*")
		self.config_obj = FedexConfig(key= settings.get("fedex_key"),
								password= client.get_password("Shipment Forwarder", fedex_account, "password"),
								account_number= settings.get("account_no"),
								meter_number= settings.get("fedex_meter_no"),
								freight_account_number= "510087020",
								use_test_server=True if settings.get("is_test_account") else False)

	def init_shipment(self, doc):
		shipment = FedexProcessShipmentRequest(self.config_obj)
		self.set_shipment_details(doc, shipment)
		shipper_details = self.set_shipper_info(doc.company_address_name, shipment)
		recipient_details = self.set_recipient_info(doc, shipment)
		FedexController.set_fedex_label_info(shipment)
		FedexController.set_commodities_info(doc, shipment)
		self.set_commercial_invoice_info(shipment, doc)
		self.set_email_notification(shipment, doc, shipper_details, recipient_details)
		self.pkg_count = doc.no_of_packages
		return shipment


	
	def set_shipment_details(self, doc, shipment):
		shipment.RequestedShipment.DropoffType = doc.drop_off_type
		shipment.RequestedShipment.ServiceType = doc.service_type
		shipment.RequestedShipment.PackagingType = doc.packaging_type
		shipment.RequestedShipment.ShippingChargesPayment.PaymentType = doc.shipping_payment_by
		shipment.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = \
		    self.config_obj.account_number if doc.shipping_payment_by == "SENDER" else doc.shipping_payment_Account

		shipment.RequestedShipment.CustomsClearanceDetail.DutiesPayment.PaymentType = doc.duties_payment_by
		shipment.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor.ResponsibleParty.AccountNumber = \
			self.config_obj.account_number if doc.duties_payment_by == "SENDER" else doc.duties_payment_Account
		return shipment	
	
	

	def set_shipper_info(self, shipper_id, shipment):
		shipper_details = frappe.db.get_value("Address", shipper_id, "*", as_dict=True)
		self.validate_address(shipper_details)
		tin_no = frappe.db.get_value("Company", shipper_details.get("company"), "tin_no")
		
		shipment.RequestedShipment.Shipper.AccountNumber = self.config_obj.account_number
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
		if not tin_no:
			raise frappe.ValidationError("Please set TIN no in company {0}".format(shipper_details.get("company")))
		tin_details = shipment.create_wsdl_object_of_type('TaxpayerIdentification')
		tin_details.TinType.value = "BUSINESS_NATIONAL"
		tin_details.Number = tin_no
		shipment.RequestedShipment.Shipper.Tins = [tin_details]
		return shipper_details



	def set_recipient_info(self, doc, shipment):
		recipient_details = frappe.db.get_value("Address", doc.shipping_address_name, "*", as_dict=True)
		self.validate_address(recipient_details)
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
		return recipient_details
	    

	def set_biller_info(self, billing_address, shipment):
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
		billing_contact_address.AccountNumber = self.config_obj.account_number

	@staticmethod
	def set_fedex_label_info(shipment):
		shipment.RequestedShipment.LabelSpecification.LabelFormatType = "COMMON2D"
		shipment.RequestedShipment.LabelSpecification.ImageType = 'PDF'
		shipment.RequestedShipment.LabelSpecification.LabelStockType = 'PAPER_8.5X11_TOP_HALF_LABEL'
		shipment.RequestedShipment.LabelSpecification.LabelPrintingOrientation = 'BOTTOM_EDGE_OF_TEXT_FIRST'
		shipment.RequestedShipment.EdtRequestType = 'NONE'

		if hasattr(shipment.RequestedShipment.LabelSpecification, 'LabelOrder'):
		    del shipment.RequestedShipment.LabelSpecification.LabelOrder  # Delete, not using.

	
	@staticmethod
	def set_commodities_info(doc, shipment):
		total_value = 0.0
		for row in doc.items:
			commodity_dict = {
				"Name":row.get("item_code"),
				"Description":row.get("description"),
				"Weight": {"Units": FedexController.uom_mapper.get(row.get("weight_uom")),\
								 "Value":row.net_weight * row.get("qty")},
				"NumberOfPieces":row.get("no_of_pieces"),
				"CountryOfManufacture":row.get("country_code"),
				"Quantity":row.get("qty"),
				"QuantityUnits":"EA",
				"UnitPrice":{"Currency":doc.currency, "Amount":row.rate},
				"CustomsValue":{"Currency":doc.currency, "Amount":row.amount}
			}
			total_value += row.amount
			shipment.RequestedShipment.CustomsClearanceDetail.Commodities.append(commodity_dict)
		shipment.RequestedShipment.CustomsClearanceDetail.CustomsValue.Amount = total_value
		shipment.RequestedShipment.CustomsClearanceDetail.CustomsValue.Currency = doc.currency
		doc.total = total_value

	
	def set_package_data(self, pkg, shipment, pkg_no, doc):
		package = self.set_package_weight(shipment, pkg, doc)
		self.set_package_dimensions(shipment, pkg, package)
		package.SequenceNumber = pkg_no
		shipment.RequestedShipment.RequestedPackageLineItems = [package]
		shipment.RequestedShipment.PackageCount = self.pkg_count
		# shipment.add_package(package)

	def set_package_dimensions(self, shipment, pkg, package):
		# adding package dimensions
		dimn = shipment.create_wsdl_object_of_type('Dimensions')
		dimn.Length = pkg.length
		dimn.Width = pkg.width
		dimn.Height = pkg.height
		dimn.Units = pkg.unit
		package.Dimensions = dimn
	
	def set_package_weight(self, shipment, pkg, doc):
		package = shipment.create_wsdl_object_of_type('RequestedPackageLineItem')
		package.PhysicalPackaging = pkg.physical_packaging
		# adding package weight
		package_weight = shipment.create_wsdl_object_of_type('Weight')
		package_weight.Units = FedexController.uom_mapper.get(pkg.uom)
		package_weight.Value = pkg.package_weight
		package.Weight = package_weight
		# Adding references as required by label evaluation process
		for ref, field in {"P_O_NUMBER":"shipment_type", "DEPARTMENT_NUMBER":"octroi_payment_by"}.iteritems():
			ref_data = shipment.create_wsdl_object_of_type('CustomerReference')
			ref_data.CustomerReferenceType = ref
			ref_data.Value = doc.get(field)
			package.CustomerReferences.append(ref_data)
		return package

	
	def validate_fedex_shipping_response(self, shipment, package_id):
		msg = ''
		try:
		    msg = shipment.response.Message
		except:
		    pass
		if shipment.response.HighestSeverity == "SUCCESS":
		    frappe.msgprint('Shipment is created successfully in Fedex service for package {0}.'.format(package_id))
		elif shipment.response.HighestSeverity in ["NOTE", "WARNING"]:
		    frappe.msgprint('Shipment is created in Fedex service for package {0} with the following message:\n{1}'.format(package_id, msg))
		    self.show_notification(shipment)
		else:  # ERROR, FAILURE
		    self.show_notification(shipment)
		    frappe.throw('Creating of Shipment in Fedex service for package {0} failed.'.format(package_id))

	@staticmethod
	def store_label(shipment, tracking_id, ps_name):
		label_data = base64.b64decode(shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].Label.Parts[0].Image)
		FedexController.store_file('FEDEX-ID-{0}.pdf'.format(tracking_id), label_data, ps_name)
		if hasattr(shipment.response.CompletedShipmentDetail, 'ShipmentDocuments'):
			inovice_data = base64.b64decode(shipment.response.CompletedShipmentDetail.ShipmentDocuments[0].Parts[0].Image)
			FedexController.store_file('COMMER-INV-{0}.pdf'.format(ps_name), inovice_data, ps_name)

	@staticmethod
	def store_file(file_name, image_data, ps_name):
		save_file(file_name, image_data, "Packing Slip", ps_name)

	def delete_shipment(self, tracking_id):
		del_request = FedexDeleteShipmentRequest(self.config_obj)
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
			self.show_notification(del_request)
			frappe.throw('Canceling of Shipment in Fedex service failed.')


	def validate_postal_address(self, recipient_address):
		recipient_details = frappe.db.get_value("Address", recipient_address, "*", as_dict=True)

		inquiry = FedexValidatePostalRequest(self.config_obj)
		inquiry.Address.PostalCode = recipient_details.get("pincode")
		inquiry.Address.CountryCode = recipient_details.get("country_code")
		inquiry.Address.StreetLines = [recipient_details.get("address_line2"),\
										recipient_details.get("address_line1")]
		inquiry.Address.City = recipient_details.get("city")
		inquiry.Address.StateOrProvinceCode = recipient_details.get("state_code")
		inquiry.send_request()
		if inquiry.response.HighestSeverity not in ["SUCCESS", "NOTE", "WARNING"]:
			self.show_notification(inquiry)
			frappe.throw(_('Recipient Address verification failed.'))

	
	def schedule_pickup(self, request_data):
		shipper_details, closing_time = self.get_company_data(request_data, "closing_time")
		
		pickup_service = FedexCreatePickupRequest(self.config_obj)
		pickup_service.OriginDetail.PickupLocation.Contact.PersonName = shipper_details.get("address_title")
		pickup_service.OriginDetail.PickupLocation.Contact.EMailAddress = shipper_details.get("email_id")
		pickup_service.OriginDetail.PickupLocation.Contact.CompanyName = shipper_details.get("company")
		pickup_service.OriginDetail.PickupLocation.Contact.PhoneNumber = shipper_details.get("phone")
		pickup_service.OriginDetail.PickupLocation.Address.StateOrProvinceCode = shipper_details.get("state_code")
		pickup_service.OriginDetail.PickupLocation.Address.PostalCode = shipper_details.get("pincode")
		pickup_service.OriginDetail.PickupLocation.Address.CountryCode = shipper_details.get("country_code")
		pickup_service.OriginDetail.PickupLocation.Address.StreetLines = [shipper_details.get("address_line1"),\
																	 shipper_details.get("address_line2")]
		pickup_service.OriginDetail.PickupLocation.Address.City = shipper_details.get("city")
		pickup_service.OriginDetail.PickupLocation.Address.Residential = True if shipper_details.get("is_residential_address") \
																			else False
		pickup_service.OriginDetail.PackageLocation = 'NONE'
		pickup_service.OriginDetail.ReadyTimestamp = get_datetime(request_data.get("ready_time")).replace(microsecond=0).isoformat()
		pickup_service.OriginDetail.CompanyCloseTime = closing_time if closing_time else '20:00:00'
		pickup_service.CarrierCode = 'FDXE'
		pickup_service.PackageCount = request_data.get("package_count")

		package_weight = pickup_service.create_wsdl_object_of_type('Weight')
		package_weight.Units = FedexController.uom_mapper.get(request_data.get("uom"))
		package_weight.Value = request_data.get("gross_weight")
		pickup_service.TotalWeight = package_weight

		pickup_service.send_request()
		if pickup_service.response.HighestSeverity not in ["SUCCESS", "NOTE", "WARNING"]:
			self.show_notification(pickup_service)
			frappe.throw(_('Pickup service scheduling failed.'))
		return { "response": pickup_service.response.HighestSeverity,
				  "pickup_id": pickup_service.response.PickupConfirmationNumber,
				  "location_no": pickup_service.response.Location
				}


	def get_shipment_rate(self, doc):
		rate_request = FedexRateServiceRequest(self.config_obj)
		self.set_shipment_details(doc, rate_request)
		self.set_shipper_info(doc.company_address_name, rate_request)
		self.set_recipient_info(doc, rate_request)
		FedexController.set_commodities_info(doc, rate_request)
		rate_request.RequestedShipment.EdtRequestType = 'NONE'

		for row in doc.fedex_package_details:  
			package1 = self.set_package_weight(rate_request, row, doc)
			package1.GroupPackageCount = 1
			rate_request.add_package(package1)

		self.set_commercial_invoice_info(rate_request, doc)
		rate_request.send_request()
		if rate_request.response.HighestSeverity not in ["SUCCESS", "NOTE", "WARNING"]:
			self.show_notification(rate_request)
			frappe.throw(_("Error !!! Get shipment rate request failed."))
		return rate_request

	def show_notification(self, shipment):
		for notification in shipment.response.Notifications:
			frappe.msgprint('Code: %s, %s' % (notification.Code, notification.Message))

	
	def set_commercial_invoice_info(self, shipment, doc):
		shipment.RequestedShipment.CustomsClearanceDetail.CommercialInvoice.Purpose = doc.shipment_purpose
		shipment.RequestedShipment.ShippingDocumentSpecification.ShippingDocumentTypes = "COMMERCIAL_INVOICE"
		shipment.RequestedShipment.ShippingDocumentSpecification.CommercialInvoiceDetail.\
														Format.ImageType = "PDF"
		shipment.RequestedShipment.ShippingDocumentSpecification.CommercialInvoiceDetail.\
														Format.StockType = "PAPER_LETTER"

	@staticmethod
	def get_company_data(request_data, field_name):
		shipper_details = frappe.db.get_value("Address", request_data.get("shipper_id"), "*", as_dict=True)
		field_value = frappe.db.get_value("Company", shipper_details.get("company"), field_name)
		return shipper_details, field_value

	def set_email_notification(self, shipment, doc, shipper_details, recipient_details):
		if doc.fedex_notification:
			shipment.RequestedShipment.SpecialServicesRequested.EMailNotificationDetail.AggregationType = "PER_SHIPMENT"
			notify_mapper = {"Sender":"SHIPPER", "Recipient":"RECIPIENT", "Other-1":"OTHER", \
								"Other-2":"OTHER", "Other-3":"OTHER"}
			email_id_mapper = {"Sender":shipper_details, "Recipient":recipient_details, "Other-1":{}, \
								"Other-2":{}, "Other-3":{} }
			for row in doc.fedex_notification:
				notify_dict = {
					"EMailNotificationRecipientType":notify_mapper.get(row.notify_to, "SHIPPER"),
					"EMailAddress":email_id_mapper.get(row.notify_to, {}).get("email_id", row.email_id or ""),
					"NotificationEventsRequested":[ fedex_event for event, fedex_event in {"shipment":"ON_SHIPMENT", "delivery":"ON_DELIVERY", \
														"tendered":"ON_TENDER", "exception":"ON_EXCEPTION"}.items() if row.get(event)],
					"Format":"HTML",
					"Localization":{"LanguageCode":"EN", \
									"LocaleCode":email_id_mapper.get(row.notify_to, {}).get("country_code", "IN")}
				}
				shipment.RequestedShipment.SpecialServicesRequested.EMailNotificationDetail.Recipients.append(notify_dict)

	def validate_address(self, address):
		for field, label in {"country":"Country", "country_code":"Country Code", "pincode":"Pin Code", \
						"phone":"Phone", "email_id":"Email ID", "city":"City", "address_line1":"Address Lines"}.items():
			if not address.get(field):
				raise frappe.ValidationError("Please specify {1} in Address {0}".format(address.get("name"), label))
