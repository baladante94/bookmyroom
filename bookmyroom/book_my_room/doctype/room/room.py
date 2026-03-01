# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Room(Document):
	def validate(self):
		if self.capacity and self.capacity < 1:
			frappe.throw(_("Room capacity must be at least 1."), title=_("Invalid Capacity"))
