# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "fedex_integration"
app_title = "fedex_integration"
app_publisher = "fedex_integration"
app_description = "fedex_integration"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "fedex_integration"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/fedex_integration/css/fedex_integration.css"
# app_include_js = "/assets/fedex_integration/js/fedex_integration.js"

# include js, css files in header of web template
# web_include_css = "/assets/fedex_integration/css/fedex_integration.css"
# web_include_js = "/assets/fedex_integration/js/fedex_integration.js"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "fedex_integration.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "fedex_integration.install.before_install"
# after_install = "fedex_integration.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "fedex_integration.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Packing Slip":{
		"validate":["fedex_integration.fedex_integration.custom_packing_slip.custom_packing_slip.validate_for_package_count",
					"fedex_integration.fedex_integration.custom_packing_slip.custom_packing_slip.validate_package_details",
					"fedex_integration.fedex_integration.custom_packing_slip.custom_packing_slip.update_package_details"],
		"before_submit": ["fedex_integration.fedex_integration.custom_packing_slip.custom_packing_slip.init_fedex_shipment"]
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"fedex_integration.tasks.all"
# 	],
# 	"daily": [
# 		"fedex_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"fedex_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"fedex_integration.tasks.weekly"
# 	]
# 	"monthly": [
# 		"fedex_integration.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "fedex_integration.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "fedex_integration.event.get_events"
# }

