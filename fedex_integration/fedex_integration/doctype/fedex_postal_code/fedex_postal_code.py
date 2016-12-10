# -*- coding: utf-8 -*-
# Copyright (c) 2015, fedex_integration and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class FedExPostalCode(Document):

	def validate(self):
		name = frappe.db.get_value("FedEx Postal Code", {"postal_code":self.postal_code,\
				"country_name":self.country_name, "name":["not in", [self.name]]}, "name")
		if name:
			frappe.throw(_("FedEx Postal code {0} already exists with same postal code & country".format(name)))


