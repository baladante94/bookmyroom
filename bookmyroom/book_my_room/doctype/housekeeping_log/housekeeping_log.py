# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class HousekeepingLog(Document):
	def before_save(self):
		if self.status == "In Progress" and not self.start_time:
			self.start_time = now_datetime().strftime("%H:%M:%S")

		if self.status == "Completed" and not self.end_time:
			self.end_time = now_datetime().strftime("%H:%M:%S")

	def on_update(self):
		self._sync_room_housekeeping_status()

	def _sync_room_housekeeping_status(self):
		"""Keep the Room's housekeeping_status in sync with the latest log entry.
		When Completed, also mark the room Available so it is ready for new guests."""
		hk_status_map = {
			"Completed": "Clean",
			"In Progress": "In Progress",
			"Pending": "Dirty",
			"Skipped": "Dirty",
		}
		hk_status = hk_status_map.get(self.status)
		if hk_status and self.room:
			frappe.db.set_value("Room", self.room, "housekeeping_status", hk_status)
			if self.status == "Completed":
				# Room is clean — mark Available so it shows as ready for reservations
				frappe.db.set_value("Room", self.room, "status", "Available")
