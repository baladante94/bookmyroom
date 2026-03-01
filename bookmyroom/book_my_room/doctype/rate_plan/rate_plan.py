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
