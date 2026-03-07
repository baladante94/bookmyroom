app_name = "bookmyroom"
app_title = "Book My Room"
app_publisher = "Balamurugan"
app_description = "Room Booking"
app_email = "baladede@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "bookmyroom",
# 		"logo": "/assets/bookmyroom/images/logo.png",
# 		"title": "Book My Room Hook",
# 		"route": "/desk/bookmyroom",
# 		"has_permission": "erpnext.check_app_permission",

# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/bookmyroom/css/bookmyroom.css"
# app_include_js = "/assets/bookmyroom/js/bookmyroom.js"

# include js, css files in header of web template
# web_include_css = "/assets/bookmyroom/css/bookmyroom.css"
# web_include_js = "/assets/bookmyroom/js/bookmyroom.js"

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "bookmyroom/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "bookmyroom.utils.jinja_methods",
# 	"filters": "bookmyroom.utils.jinja_filters"
# }

# Installation
# ------------

after_install = "bookmyroom.install.after_install"
after_migrate = "bookmyroom.install.after_migrate"

fixtures = [
	{"dt": "Custom HTML Block", "filters": [["name", "=", "BMR Room Status Grid"]]},
	{"dt": "Number Card", "filters": [["name", "like", "BMR %"]]},
	{"dt": "Dashboard Chart", "filters": [["name", "like", "BMR %"]]},
]

# Uninstallation
# ------------

# before_uninstall = "bookmyroom.uninstall.before_uninstall"
# after_uninstall = "bookmyroom.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bookmyroom.notifications.get_notification_config"

# Permissions
# -----------

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

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# Custom Fields
# -------------
# Adds Book My Room reference fields to ERPNext's Sales Invoice so that
# invoices generated from a Room Reservation or Guest Folio are traceable
# in both directions via the Connections panel.

custom_fields = {
	"Sales Invoice": [
		{
			"fieldname": "bmr_section",
			"fieldtype": "Section Break",
			"label": "Book My Room",
			"insert_after": "remarks",
			"collapsible": 1,
		},
		{
			"fieldname": "bmr_reservation",
			"fieldtype": "Link",
			"label": "Room Reservation",
			"options": "Room Reservation",
			"insert_after": "bmr_section",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "bmr_guest_folio",
			"fieldtype": "Link",
			"label": "Guest Folio",
			"options": "Guest Folio",
			"insert_after": "bmr_reservation",
			"read_only": 1,
			"no_copy": 1,
		},
	],
	"Sales Invoice Item": [
		{
			"fieldname": "bmr_guest_folio",
			"fieldtype": "Link",
			"label": "Guest Folio",
			"options": "Guest Folio",
			"insert_after": "sales_invoice_item",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "bmr_reservation",
			"fieldtype": "Link",
			"label": "Room Reservation",
			"options": "Room Reservation",
			"insert_after": "bmr_guest_folio",
			"read_only": 1,
			"no_copy": 1,
		},
	],
}

# Document Events
# ---------------
# Settle / reopen Guest Folios when a linked Sales Invoice is submitted or cancelled.

doc_events = {
	"Sales Invoice": {
		"on_submit": "bookmyroom.book_my_room.doctype.guest_folio.guest_folio.on_sales_invoice_submit",
		"on_cancel": "bookmyroom.book_my_room.doctype.guest_folio.guest_folio.on_sales_invoice_cancel",
	},
}

scheduler_events = {
	"daily": [
		"bookmyroom.tasks.send_checkin_reminders",
		"bookmyroom.tasks.auto_generate_housekeeping_tasks",
	],
}

# Testing
# -------

# before_tests = "bookmyroom.install.before_tests"

# Overriding Methods
# ------------------------------

# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bookmyroom.event.get_events"
# }

# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "bookmyroom.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"bookmyroom.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
