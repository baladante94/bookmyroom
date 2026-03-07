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
	}


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
