# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BookingSettings(Document):
	pass


@frappe.whitelist()
def get_booking_settings():
	"""Return Booking Settings as dict (for client-side consumption)."""
	return {
		"block_backdated_booking": frappe.db.get_single_value(
			"Booking Settings", "block_backdated_booking"
		)
		or 0,
		"default_hotel": frappe.db.get_single_value("Booking Settings", "default_hotel"),
	}


@frappe.whitelist()
def get_tax_slabs():
	"""Return configured room tax slabs ordered by min tariff."""
	return frappe.get_all(
		"Room Tax Slab",
		filters={"parent": "Booking Settings"},
		fields=["min_tariff", "max_tariff", "item_tax_template", "tax_rate"],
		order_by="min_tariff asc",
	)


@frappe.whitelist()
def setup_standard_billing_items():
	"""Create standard hotel billing items. One-time action triggered from Booking Settings."""
	if frappe.db.get_single_value("Booking Settings", "billing_items_imported"):
		frappe.throw(_("Standard billing items have already been imported."))

	from bookmyroom.install import create_standard_billing_items

	created = create_standard_billing_items()

	frappe.db.set_single_value("Booking Settings", "billing_items_imported", 1)
	frappe.db.commit()

	return {"created": created}
