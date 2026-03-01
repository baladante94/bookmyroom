# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt


class GuestFolio(Document):
	def before_save(self):
		self._calculate_total()

	def on_submit(self):
		self.db_set("status", "Settled")

	def on_cancel(self):
		self.db_set("status", "Open")

	def _calculate_total(self):
		total = 0.0
		for row in self.get("items"):
			row.amount = flt(row.quantity) * flt(row.rate)
			total += row.amount
		self.total_amount = total


@frappe.whitelist()
def make_sales_invoice_from_folio(source_name, target_doc=None):
	"""Create a Sales Invoice from a settled Guest Folio."""
	from frappe.utils import getdate

	def set_missing_values(source, target):
		target.customer = source.customer
		target.company = source.company
		target.due_date = getdate()
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(source_row, target_row, source_parent):
		service = frappe.db.get_value(
			"Hotel Service", source_row.service, ["billing_item", "service_name"], as_dict=True
		)
		if service and service.billing_item:
			target_row.item_code = service.billing_item
			target_row.item_name = service.service_name or source_row.description
		target_row.description = source_row.description
		target_row.qty = flt(source_row.quantity)
		target_row.rate = flt(source_row.rate)
		target_row.amount = flt(source_row.amount)

	return get_mapped_doc(
		"Guest Folio",
		source_name,
		{
			"Guest Folio": {
				"doctype": "Sales Invoice",
				"field_map": {
					"company": "company",
					"customer": "customer",
				},
				"field_no_map": ["status"],
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"Guest Folio Item": {
				"doctype": "Sales Invoice Item",
				"postprocess": update_item,
			},
		},
		target_doc,
		set_missing_values,
	)
