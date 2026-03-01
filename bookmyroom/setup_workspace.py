"""
Creates the 'Book My Room' Workspace with shortcuts, number cards, and charts.
Run with:  bench --site bookmyroom.localhost execute bookmyroom.setup_workspace.create_all
"""

import json
import random
import string

import frappe


WORKSPACE_NAME = "Book My Room"


def _uid():
	"""Generate a short random ID like Frappe uses for content block IDs."""
	return "".join(random.choices(string.ascii_letters + string.digits, k=10))


# ─────────────────────────────────────────────────────────────────────────────
# Number Cards
# ─────────────────────────────────────────────────────────────────────────────

NUMBER_CARDS = [
	{
		"label": "Bookings Today",
		"document_type": "Room Reservation",
		"function": "Count",
		"filters_json": json.dumps([
			["Room Reservation", "status", "=", "Booked"],
			["Room Reservation", "docstatus", "=", 1],
		]),
		"color": "#2490EF",
		"is_public": 1,
	},
	{
		"label": "Guests Checked In",
		"document_type": "Room Reservation",
		"function": "Count",
		"filters_json": json.dumps([
			["Room Reservation", "status", "=", "Checked In"],
			["Room Reservation", "docstatus", "=", 1],
		]),
		"color": "#36B37E",
		"is_public": 1,
	},
	{
		"label": "Available Rooms",
		"document_type": "Room",
		"function": "Count",
		"filters_json": json.dumps([
			["Room", "status", "=", "Available"],
		]),
		"color": "#00B8D9",
		"is_public": 1,
	},
	{
		"label": "Pending Housekeeping",
		"document_type": "Housekeeping Log",
		"function": "Count",
		"filters_json": json.dumps([
			["Housekeeping Log", "status", "in", ["Pending", "In Progress"]],
			["Housekeeping Log", "date", "=", "Today"],
		]),
		"color": "#FF991F",
		"is_public": 1,
	},
	{
		"label": "Check-outs Today",
		"document_type": "Room Reservation",
		"function": "Count",
		"filters_json": json.dumps([
			["Room Reservation", "status", "=", "Checked Out"],
			["Room Reservation", "docstatus", "=", 1],
		]),
		"color": "#6554C0",
		"is_public": 1,
	},
]


def create_number_cards():
	print("\n── Number Cards ──")
	for nc in NUMBER_CARDS:
		# Number Card is autonamed by label — label IS the document name
		doc_name = nc["label"]
		if frappe.db.exists("Number Card", doc_name):
			frappe.delete_doc("Number Card", doc_name, ignore_permissions=True, force=True)
		doc = frappe.get_doc({"doctype": "Number Card", **nc})
		doc.insert(ignore_permissions=True)
		print(f"  [ok]   Number Card: {doc_name}")


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Charts
# ─────────────────────────────────────────────────────────────────────────────

CHARTS = [
	{
		"name": "BMR - Reservations by Month",
		"chart_name": "Reservations by Month",
		"chart_type": "Count",
		"document_type": "Room Reservation",
		"based_on": "check_in",
		"timespan": "Last Year",
		"time_interval": "Monthly",
		"filters_json": json.dumps([["Room Reservation", "docstatus", "=", 1]]),
		"type": "Bar",
		"color": "#2490EF",
		"is_public": 1,
	},
	{
		"name": "BMR - Revenue by Month",
		"chart_name": "Revenue by Month",
		"chart_type": "Sum",
		"document_type": "Room Reservation",
		"based_on": "check_in",
		"value_based_on": "grand_total",
		"timespan": "Last Year",
		"time_interval": "Monthly",
		"filters_json": json.dumps([["Room Reservation", "docstatus", "=", 1]]),
		"type": "Line",
		"color": "#36B37E",
		"is_public": 1,
	},
	{
		"name": "BMR - Reservations by Status",
		"chart_name": "Reservations by Status",
		"chart_type": "Group By",
		"document_type": "Room Reservation",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"filters_json": json.dumps([["Room Reservation", "docstatus", "=", 1]]),
		"type": "Donut",
		"color": "#2490EF",
		"is_public": 1,
	},
	{
		"name": "BMR - Reservations by Source",
		"chart_name": "Bookings by Source",
		"chart_type": "Group By",
		"document_type": "Room Reservation",
		"group_by_type": "Count",
		"group_by_based_on": "booking_source",
		"filters_json": json.dumps([
			["Room Reservation", "docstatus", "=", 1],
			["Room Reservation", "booking_source", "!=", ""],
		]),
		"type": "Pie",
		"color": "#FF991F",
		"is_public": 1,
	},
	{
		"name": "BMR - Room Type Revenue",
		"chart_name": "Revenue by Room Type",
		"chart_type": "Group By",
		"document_type": "Room Reservation Item",
		"parent_document_type": "Room Reservation",
		"group_by_type": "Sum",
		"group_by_based_on": "room_type",
		"aggregate_function_based_on": "amount",
		"filters_json": json.dumps([["Room Reservation Item", "docstatus", "=", 1]]),
		"type": "Bar",
		"color": "#6554C0",
		"is_public": 1,
	},
]


def create_charts():
	print("\n── Dashboard Charts ──")
	for c in CHARTS:
		# Dashboard Chart is autonamed by chart_name, so that is the document name
		doc_name = c["chart_name"]
		if frappe.db.exists("Dashboard Chart", doc_name):
			frappe.delete_doc("Dashboard Chart", doc_name, ignore_permissions=True, force=True)
		# Remove the separate 'name' key so Frappe uses chart_name as autoname
		chart_data = {k: v for k, v in c.items() if k != "name"}
		doc = frappe.get_doc({"doctype": "Dashboard Chart", **chart_data})
		doc.insert(ignore_permissions=True)
		print(f"  [ok]   Chart: {doc_name}")


# ─────────────────────────────────────────────────────────────────────────────
# Workspace
# ─────────────────────────────────────────────────────────────────────────────

# Shortcuts definition — each entry must have a unique label used as shortcut_name in content
SHORTCUTS = [
	{"label": "Room Reservation", "link_to": "Room Reservation", "type": "DocType", "color": "#2490EF", "icon": "calendar"},
	{"label": "Rooms",            "link_to": "Room",             "type": "DocType", "color": "#36B37E", "icon": "home"},
	{"label": "Housekeeping",     "link_to": "Housekeeping Log", "type": "DocType", "color": "#FF991F", "icon": "cleaning"},
	{"label": "Guest Folio",      "link_to": "Guest Folio",      "type": "DocType", "color": "#6554C0", "icon": "file-text"},
	{"label": "Hotels",           "link_to": "Hotel",            "type": "DocType", "color": "#00B8D9", "icon": "building"},
	{"label": "Rate Plans",       "link_to": "Rate Plan",        "type": "DocType", "color": "#FF5630", "icon": "tag"},
]

# Link cards in the sidebar/content (Card Break = section header, Link = item)
LINKS = [
	{"type": "Card Break", "label": "Front Desk", "hidden": 0, "is_query_report": 0, "link_count": 0, "onboard": 0},
	{"type": "Link", "label": "Room Reservation", "link_to": "Room Reservation", "link_type": "DocType", "onboard": 1, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},
	{"type": "Link", "label": "Guest Folio",       "link_to": "Guest Folio",       "link_type": "DocType", "onboard": 1, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},
	{"type": "Link", "label": "Housekeeping Log",  "link_to": "Housekeeping Log",  "link_type": "DocType", "onboard": 1, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},

	{"type": "Card Break", "label": "Masters", "hidden": 0, "is_query_report": 0, "link_count": 0, "onboard": 0},
	{"type": "Link", "label": "Hotel",        "link_to": "Hotel",        "link_type": "DocType", "onboard": 1, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},
	{"type": "Link", "label": "Room",          "link_to": "Room",          "link_type": "DocType", "onboard": 1, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},
	{"type": "Link", "label": "Room Type",     "link_to": "Room Type",     "link_type": "DocType", "onboard": 1, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},
	{"type": "Link", "label": "Meal Plan",     "link_to": "Meal Plan",     "link_type": "DocType", "onboard": 0, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},
	{"type": "Link", "label": "Hotel Service", "link_to": "Hotel Service", "link_type": "DocType", "onboard": 0, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},
	{"type": "Link", "label": "Hotel Amenity", "link_to": "Hotel Amenity", "link_type": "DocType", "onboard": 0, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},

	{"type": "Card Break", "label": "Pricing", "hidden": 0, "is_query_report": 0, "link_count": 0, "onboard": 0},
	{"type": "Link", "label": "Rate Plan",     "link_to": "Rate Plan",     "link_type": "DocType", "onboard": 1, "hidden": 0, "is_query_report": 0, "link_count": 0, "dependencies": ""},
]


def _build_content():
	"""Build the content JSON array with unique IDs for every block."""
	blocks = []

	# Row 1: Shortcuts (col 2 each so 6 fit in 12-col grid)
	for s in SHORTCUTS:
		blocks.append({
			"id": _uid(),
			"type": "shortcut",
			"data": {"shortcut_name": s["label"], "col": 2},
		})

	# Spacer
	blocks.append({"id": _uid(), "type": "spacer", "data": {"col": 12}})

	# Row 2: Number cards (col 4 each — 3 per row, 5 cards = 2 rows)
	for nc in NUMBER_CARDS:
		blocks.append({
			"id": _uid(),
			"type": "number_card",
			"data": {"number_card_name": nc["label"], "col": 4},
		})

	# Spacer
	blocks.append({"id": _uid(), "type": "spacer", "data": {"col": 12}})

	# Charts
	col_map = [12, 6, 6, 6, 6]  # first chart full-width, rest half
	for chart, col in zip(CHARTS, col_map):
		blocks.append({
			"id": _uid(),
			"type": "chart",
			"data": {"chart_name": chart["chart_name"], "col": col},
		})

	# Spacer
	blocks.append({"id": _uid(), "type": "spacer", "data": {"col": 12}})

	return json.dumps(blocks)


def create_workspace():
	print("\n── Workspace ──")

	if frappe.db.exists("Workspace", WORKSPACE_NAME):
		frappe.delete_doc("Workspace", WORKSPACE_NAME, ignore_permissions=True, force=True)
		print(f"  [del]  Old workspace removed, recreating...")

	workspace = frappe.get_doc({
		"doctype": "Workspace",
		"name": WORKSPACE_NAME,
		"label": WORKSPACE_NAME,
		"title": WORKSPACE_NAME,
		"module": "Book My Room",
		"is_standard": 0,
		"public": 1,
		"icon": "hotel",
		# Shortcuts child table
		"shortcuts": [
			{
				"label": s["label"],
				"link_to": s["link_to"],
				"type": s["type"],
				"icon": s.get("icon", ""),
				"color": s.get("color", ""),
				"doc_view": "",
				"format": "",
			}
			for s in SHORTCUTS
		],
		# Number cards child table — number_card_name = document name = label
		"number_cards": [
			{"number_card_name": nc["label"], "label": nc["label"]}
			for nc in NUMBER_CARDS
		],
		# Charts child table
		"charts": [
			{"chart_name": c["chart_name"], "label": c["chart_name"]}
			for c in CHARTS
		],
		# Links child table (sidebar navigation)
		"links": LINKS,
		# Content JSON (layout descriptor with block IDs)
		"content": _build_content(),
	})
	workspace.insert(ignore_permissions=True)
	print(f"  [ok]   Workspace: {WORKSPACE_NAME}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def create_all():
	frappe.set_user("Administrator")
	print("\n========================================")
	print(" BookMyRoom — Workspace Setup")
	print("========================================")

	create_number_cards()
	create_charts()
	create_workspace()

	frappe.db.commit()
	print("\n========================================")
	print(" ✅  Workspace created!")
	print("========================================\n")
