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
add_to_apps_screen = [
	{
		"name": "bookmyroom",
		"logo": "/assets/bookmyroom/images/logo.png",
		"title": "Book My Room",
		"route": "/desk/bookmyroom",
	}
]

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

# before_install = "bookmyroom.install.before_install"
# after_install = "bookmyroom.install.after_install"

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
