from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Freight"),
			"icon": "icon-star",
			"items": [
				{
					"type": "doctype",
					"name": "Shipment Forwarder",
					"description": _("Master containing various shipment forwarder.")
				}

			]
		},
		{
			"label": _("Transactions"),
			"icon": "icon-star",
			"items": [
				{
					"type": "doctype",
					"name": "Packing Slip",
					"description": _("Packing slips against delivery notes."),
				},
				{
					"type": "doctype",
					"name": "Delivery Note",
					"description": _("Delivered orders to Customers."),
				},
				{
					"type": "doctype",
					"name": "Sales Order",
					"description": _("Confirmed orders from Customers")
				},
			]
		},
		{
			"label": _("FedEx"),
			"icon": "icon-star",
			"items": [
				{
					"type": "doctype",
					"name": "FedEx Postal Code",
					"description": _("Master containing postal codes allowed by FedEx for delivery.")
				},
				{
					"type": "doctype",
					"name": "FedEx Package",
					"description": _("Master of FedEx packages.")
				}

			]	
		}

	]
