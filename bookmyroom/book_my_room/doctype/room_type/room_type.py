# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RoomType(Document):
	def before_save(self):
		self.total_rooms = frappe.db.count("Room", {"room_type": self.name})
