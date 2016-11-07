from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, flt
import logging
import sys
import json
from fedex.config import FedexConfig
from fedex.services.ship_service import FedexProcessShipmentRequest
from frappe.utils.file_manager import save_file
from fedex.services.track_service import FedexTrackRequest
import frappe.client as client


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


	def make_shipment(self, doc):
		shipment = FedexController.set_shipment_details(doc)
		FedexController.set_shipper_info(doc.company_address_name, shipment)
		FedexController.set_recipient_info(doc, shipment)
		FedexController.set_biller_info(doc.customer_address, shipment)
		FedexController.set_fedex_label_info(shipment)
		FedexController.set_package_details(doc, shipment)
		FedexController.set_commodities_info(doc, shipment)
		return shipment


	@classmethod
	def set_shipment_details(cls_obj, doc):
		shipment = FedexProcessShipmentRequest(cls_obj.CONFIG_OBJ)
		shipment.RequestedShipment.DropoffType = doc.drop_off_type
		shipment.RequestedShipment.ServiceType = doc.service_type
		shipment.RequestedShipment.PackagingType = doc.packaging_type
		# shipment.RequestedShipment.FreightShipmentDetail.FedExFreightAccountNumber \
		# 											= cls_obj.CONFIG_OBJ.freight_account_number
		
		shipment.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = cls_obj.CONFIG_OBJ.account_number
		shipment.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER'

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
		shipment.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = \
		    cls_obj.CONFIG_OBJ.freight_account_number

	    
	@staticmethod
	def set_biller_info(billing_address, shipment):
		biller_details = frappe.db.get_value("Address", billing_address, "*", as_dict=True)
		
		billing_contact_address = shipment.RequestedShipment.FreightShipmentDetail.FedExFreightBillingContactAndAddress
		billing_contact_address.Contact.PersonName = biller_details.get("address_title")
		billing_contact_address.Contact.CompanyName = biller_details.get("company")
		billing_contact_address.Contact.PhoneNumber = biller_details.get("phone")
		billing_contact_address.Address.StreetLines = [biller_details.get("address_line1"), biller_details.get("address_line2")]
		billing_contact_address.Address.City = biller_details.get("city")
		billing_contact_address.Address.StateOrProvinceCode = biller_details.get("state_code")
		billing_contact_address.Address.PostalCode = biller_details.get("pincode")
		billing_contact_address.Address.CountryCode = biller_details.get("country_code")
		billing_contact_address.Address.Residential = True if biller_details.get("is_residential_address") else False	    
	

	@staticmethod
	def set_fedex_label_info(shipment):
		shipment.RequestedShipment.LabelSpecification.LabelFormatType = "FEDEX_FREIGHT_STRAIGHT_BILL_OF_LADING"
		shipment.RequestedShipment.LabelSpecification.ImageType = 'PDF'
		shipment.RequestedShipment.LabelSpecification.LabelStockType = 'PAPER_LETTER'
		shipment.RequestedShipment.LabelSpecification.LabelPrintingOrientation = 'BOTTOM_EDGE_OF_TEXT_FIRST'
		shipment.RequestedShipment.EdtRequestType = 'NONE'

		if hasattr(shipment.RequestedShipment.LabelSpecification, 'LabelOrder'):
		    del shipment.RequestedShipment.LabelSpecification.LabelOrder  # Delete, not using.

	
	@staticmethod
	def set_commodities_info(doc, shipment):
		packing_slip_items = frappe.db.sql("""  select psi.* from  
								`tabPacking Slip Item` as psi 
								 join `tabPacking Slip` as ps
								 on psi.parent = ps.name 
								 where ps.delivery_note = '{0}' """.format(doc.name), as_dict=1)
		print "checking packing slip items_________", packing_slip_items
		# for row in packing_slip_items:
		# 	commodity = shipment.create_wsdl_object_of_type('Commodities')
		# 	commodity.Name = row.get("item_code")
		# 	commodity.Description = row.get("description")
		# 	commodity_weight = shipment.create_wsdl_object_of_type('Weight')
		# 	commodity_weight.Value = row.get("net_weight")
		# 	commodity_weight.Units = row.get("weight_uom")
		# 	commodity.Weight = commodity_weight
		# 	commodity.NumberOfPieces = row.get("no_of_pieces")
		# 	commodity.Quantity = row.get("quantity")
		# 	commodity.QuantityUnits = "EA"
		# 	shipment.RequestedShipment.CustomsClearanceDetail.Commodities.append(commodity_dict)
		shipment.RequestedShipment.CustomsClearanceDetail.CustomsValue.Amount = doc.grand_total
		shipment.RequestedShipment.CustomsClearanceDetail.CustomsValue.Currency = doc.currency


	@classmethod
	def set_package_details(cls_obj, doc, shipment):
		packing_slips = frappe.get_all("Packing Slip", fields=["*"], filters={"delivery_note":doc.name, "docstatus":1}, 
					order_by="creation asc")
		total_weight = 0.0
		print "packing slips____________", packing_slips
		for ps in packing_slips:	
			package1_weight = shipment.create_wsdl_object_of_type('Weight')
			package1_weight.Value = ps.get("gross_weight_pkg")
			package1_weight.Units = cls_obj.uom_mapper.get(ps.get("gross_weight_uom"))

			# package1 = shipment.create_wsdl_object_of_type('FreightShipmentLineItem')
			# package1.Weight = package1_weight
			# package1.Packaging = ps.get("commodity_packaging")
			# package1.Description = ps.get("commodity_description")
			# package1.FreightClass = 'CLASS_500'
			# package1.HazardousMaterials = None
			# package1.Pieces = ps.get("no_of_pieces")

			# shipment.RequestedShipment.FreightShipmentDetail.LineItems.append(package1)

			# total_weight += ps.get("gross_weight_pkg")
			package1 = shipment.create_wsdl_object_of_type('RequestedPackageLineItem')
			package1.PhysicalPackaging = 'ENVELOPE'
			package1.Weight = package1_weight
			package1.SpecialServicesRequested.SpecialServiceTypes = 'SIGNATURE_OPTION'
			package1.SpecialServicesRequested.SignatureOptionDetail.OptionType = 'SERVICE_DEFAULT'
			shipment.add_package(package1)

		# pallet_weight = shipment.create_wsdl_object_of_type('Weight')
		# pallet_weight.Value = total_weight
		# pallet_weight.Units = "KG"
		# shipment.RequestedShipment.FreightShipmentDetail.PalletWeight = pallet_weight


