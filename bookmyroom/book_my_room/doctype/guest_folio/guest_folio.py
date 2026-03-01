# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class GuestFolio(Document):
	def before_save(self):
		self._calculate_total()

	def on_cancel(self):
		self.db_set("status", "Open")

	def _calculate_total(self):
		total = 0.0
		for row in self.get("items"):
			row.amount = flt(row.quantity) * flt(row.rate)
			total += row.amount
		self.total_amount = total


@frappe.whitelist()
def make_sales_invoice_from_folio(source_name):
	"""Create a draft Sales Invoice from a single Guest Folio's charges."""
	folio = frappe.get_doc("Guest Folio", source_name)

	if folio.status == "Settled":
		frappe.throw(
			_(
				"Guest Folio {0} is already Settled — its charges have been billed. "
				"Cancel the related Sales Invoice to rebill."
			).format(frappe.bold(source_name))
		)

	si = frappe.new_doc("Sales Invoice")
	si.customer = folio.customer
	si.company = folio.company
	si.due_date = frappe.utils.getdate()

	for item in folio.get("items"):
		billing_item = _get_billing_item_for_service(item.service)
		si.append(
			"items",
			{
				"item_code": billing_item,
				"description": item.description or (item.service or "Hotel Service"),
				"qty": flt(item.quantity),
				"rate": flt(item.rate),
				"bmr_guest_folio": source_name,
			},
		)

	si.bmr_guest_folio = source_name
	si.bmr_reservation = folio.reservation
	si.run_method("set_missing_values")
	si.run_method("calculate_taxes_and_totals")
	si.insert(ignore_permissions=True)
	return si.name


def on_sales_invoice_submit(doc, method):
	"""When a Sales Invoice is submitted, settle all linked Guest Folios."""
	folio_names = {row.bmr_guest_folio for row in doc.get("items") if row.get("bmr_guest_folio")}
	if doc.get("bmr_guest_folio"):
		folio_names.add(doc.bmr_guest_folio)
	for folio_name in folio_names:
		frappe.db.set_value("Guest Folio", folio_name, "status", "Settled")


def on_sales_invoice_cancel(doc, method):
	"""When a Sales Invoice is cancelled, reopen all linked Guest Folios."""
	folio_names = {row.bmr_guest_folio for row in doc.get("items") if row.get("bmr_guest_folio")}
	if doc.get("bmr_guest_folio"):
		folio_names.add(doc.bmr_guest_folio)
	for folio_name in folio_names:
		frappe.db.set_value("Guest Folio", folio_name, "status", "Open")


def _get_billing_item_for_service(service_name):
	"""
	Return the billing Item linked to a Hotel Service.
	Throws a clear error if the service or its billing item is not configured.
	"""
	if not service_name:
		frappe.throw(
			_(
				"A folio charge has no Hotel Service selected. "
				"Please edit the folio and set a Service on each charge row before billing."
			)
		)

	billing_item = frappe.db.get_value("Hotel Service", service_name, "billing_item")
	if not billing_item:
		frappe.throw(
			_(
				"Hotel Service <b>{0}</b> has no Billing Item configured. "
				"Go to Hotel Service → {0} and set a Billing Item, then try again."
			).format(service_name)
		)
	return billing_item
