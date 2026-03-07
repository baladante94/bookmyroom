# Copyright (c) 2026, Balamurugan and contributors

import frappe
from frappe import _
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
	setup_item_groups()


def after_migrate():
	setup_custom_fields()
	setup_item_groups()


def setup_custom_fields():
	"""Create or update the Book My Room custom fields on Sales Invoice."""
	create_custom_fields(BMR_CUSTOM_FIELDS, ignore_validate=True, update=True)
	frappe.db.commit()
	print("  [ok]  Book My Room custom fields applied to Sales Invoice.")


# ---------------------------------------------------------------------------
# Item Group & Item setup
# ---------------------------------------------------------------------------

# Item group hierarchy (created automatically on install/migrate)
# All Item Groups
#   └─ Hotel Services
#        ├─ Accommodation      (SAC 996311 — room charges)
#        ├─ Food & Beverage    (SAC 996331 — meal plans, room service)
#        ├─ Guest Services     (laundry, telephone, parking)
#        └─ Recreation & Wellness (spa, gym, pool)

_ITEM_GROUPS = [
	{"name": "Hotel Services",        "parent": "All Item Groups", "is_group": 1},
	{"name": "Accommodation",         "parent": "Hotel Services",  "is_group": 0},
	{"name": "Food & Beverage",       "parent": "Hotel Services",  "is_group": 0},
	{"name": "Guest Services",        "parent": "Hotel Services",  "is_group": 0},
	{"name": "Recreation & Wellness", "parent": "Hotel Services",  "is_group": 0},
]

# Standard billing items (imported on-demand via Booking Settings)
# (item_code, item_name, item_group, uom, gst_hsn_code, gst_rate)
STANDARD_ITEMS = [
	# Accommodation — SAC 996311, 18%
	("room-charge",      "Room Charge",            "Accommodation",        "Night", "996311", 18),
	("early-checkin",    "Early Check-in Charge",  "Accommodation",        "Nos",   "996311", 18),
	("late-checkout",    "Late Check-out Charge",  "Accommodation",        "Nos",   "996311", 18),
	("extra-bed",        "Extra Bed Charge",       "Accommodation",        "Night", "996311", 18),

	# Food & Beverage — SAC 996331, 5%
	("meal-plan-cp",     "Breakfast (CP)",         "Food & Beverage",      "Nos",   "996331", 5),
	("meal-plan-map",    "Half Board (MAP)",       "Food & Beverage",      "Nos",   "996331", 5),
	("meal-plan-ap",     "Full Board (AP)",        "Food & Beverage",      "Nos",   "996331", 5),
	("room-service",     "Room Service",           "Food & Beverage",      "Nos",   "996331", 5),
	("minibar",          "Minibar Charges",        "Food & Beverage",      "Nos",   "996331", 5),

	# Guest Services — various SAC codes, 18% (airport transfer 5%)
	("laundry",          "Laundry & Dry Cleaning", "Guest Services",       "Nos",   "999712", 18),
	("telephone",        "Telephone Charges",      "Guest Services",       "Nos",   "998413", 18),
	("parking",          "Parking",                "Guest Services",       "Nos",   "996601", 18),
	("airport-transfer", "Airport Transfer",       "Guest Services",       "Nos",   "996412", 5),

	# Recreation & Wellness — SAC 999722/999723, 18%
	("spa",              "Spa & Wellness",         "Recreation & Wellness","Nos",   "999722", 18),
	("gym",              "Gym / Fitness",          "Recreation & Wellness","Nos",   "999723", 18),
	("swimming-pool",    "Swimming Pool Access",   "Recreation & Wellness","Nos",   "999723", 18),
]


def _get_tax_template_by_rate(gst_rate):
	"""Return the first Item Tax Template whose gst_rate matches, or None."""
	results = frappe.get_all(
		"Item Tax Template",
		filters={"gst_rate": gst_rate},
		fields=["name"],
		limit=1,
	)
	return results[0]["name"] if results else None


def setup_item_groups():
	"""Create Hotel Services item group hierarchy. Safe to call repeatedly — skips existing groups."""
	for grp in _ITEM_GROUPS:
		if frappe.db.exists("Item Group", grp["name"]):
			continue
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": grp["name"],
				"parent_item_group": grp["parent"],
				"is_group": grp["is_group"],
			}
		).insert(ignore_permissions=True)
		print(f"  [ok]  Created Item Group: {grp['name']}")
	frappe.db.commit()


def create_standard_billing_items():
	"""Create standard hotel billing items. Called from Booking Settings UI (one-time)."""
	created = 0
	for item_code, item_name, item_group, uom, sac, gst_rate in STANDARD_ITEMS:
		if frappe.db.exists("Item", item_code):
			continue
		template = _get_tax_template_by_rate(gst_rate)
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_name,
				"item_group": item_group,
				"stock_uom": uom,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"is_purchase_item": 0,
				"include_item_in_manufacturing": 0,
				"gst_hsn_code": sac,
				"taxes": [{"item_tax_template": template}] if template else [],
			}
		).insert(ignore_permissions=True)
		created += 1
	frappe.db.commit()
	return created
