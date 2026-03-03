# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
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
