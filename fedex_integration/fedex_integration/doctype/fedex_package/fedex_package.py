# -*- coding: utf-8 -*-
# Copyright (c) 2015, fedex_integration and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.controllers.queries import get_filters_cond

class FedExPackage(Document):
	pass


 # searches for fedex packages
def package_query(doctype, txt, searchfield, start, page_len, filters):
	conditions = []
	cond = ",".join(["'{0}'".format(pkg) for pkg in filters.get("name")])
	return frappe.db.sql("""select name from `tabFedEx Package`
		where name in ({cond})
		and {key} like %(txt)s
		order by creation asc
		limit %(start)s, %(page_len)s""".format(**{'key': searchfield,
			'cond': cond if cond else "''"}
			), {
			'txt': "%%%s%%" % txt,
			'start': start,
			'page_len': page_len})