# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class RatePlan(Document):
	def validate(self):
		if self.valid_from and self.valid_to and getdate(self.valid_from) >= getdate(self.valid_to):
			frappe.throw(_("Valid To date must be after Valid From date."), title=_("Invalid Date Range"))
		self._check_overlapping_plans()

	def _check_overlapping_plans(self):
		if not (self.hotel and self.room_type and self.valid_from and self.valid_to):
			return
		overlap = frappe.db.sql("""
			SELECT name FROM `tabRate Plan`
			WHERE hotel = %(hotel)s
			  AND room_type = %(room_type)s
			  AND name != %(name)s
			  AND is_active = 1
			  AND valid_from < %(valid_to)s
			  AND valid_to > %(valid_from)s
			LIMIT 1
		""", {
			"hotel": self.hotel,
			"room_type": self.room_type,
			"name": self.name or "",
			"valid_from": self.valid_from,
			"valid_to": self.valid_to,
		})
		if overlap:
			frappe.throw(
				_("Rate Plan {0} already covers an overlapping date range for {1} — {2}. "
				  "Please adjust the dates to avoid conflicts.").format(
					frappe.bold(overlap[0][0]),
					frappe.bold(self.hotel),
					frappe.bold(self.room_type),
				),
				title=_("Overlapping Rate Plan"),
			)
