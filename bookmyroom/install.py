# Copyright (c) 2026, Balamurugan and contributors

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


BMR_CUSTOM_FIELDS = {
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
			"in_standard_filter": 1,
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
	# Row-level references: folio items carry the originating Guest Folio name;
	# room charge items carry the originating Room Reservation name.
	# Both fields are placed inside the standard "References" section of SI Item.
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


def after_install():
	setup_custom_fields()


def after_migrate():
	setup_custom_fields()


def setup_custom_fields():
	"""Create or update the Book My Room custom fields on Sales Invoice."""
	create_custom_fields(BMR_CUSTOM_FIELDS, ignore_validate=True, update=True)
	frappe.db.commit()
	print("  [ok]  Book My Room custom fields applied to Sales Invoice.")
