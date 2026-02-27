# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class RoomReservation(Document):
	def before_save(self):
		self.validate_dates()
		self.calculate_totals()
		self.validate_overlapping_bookings()

	def validate_dates(self):
		if self.check_in and self.check_out and self.check_in >= self.check_out:
			frappe.throw(
				_("Check Out date must be after Check In date."),
				title=_("Invalid Dates"),
			)

	def calculate_totals(self):
		"""Calculate total nights and amount for every child row."""
		self.total_nights = 0

		if self.check_in and self.check_out:
			seconds = frappe.utils.time_diff_in_seconds(self.check_out, self.check_in)
			self.total_nights = max(int(round(seconds / 86400)), 1)

		self.total_amount = 0.0
		for row in self.get("items"):
			row.amount = flt(row.rate) * self.total_nights
			self.total_amount += row.amount

	def validate_overlapping_bookings(self):
		"""
		Uses frappe.qb to detect bookings that overlap the requested window for
		any room listed in the child table.  Only active reservations are checked
		(docstatus < 2 and status not in ['Cancelled', 'Checked Out']).
		"""
		if not (self.check_in and self.check_out):
			return

		room_names = [row.room for row in self.get("items") if row.room]
		if not room_names:
			return

		rr = frappe.qb.DocType("Room Reservation")
		rri = frappe.qb.DocType("Room Reservation Item")

		# Overlap condition: existing.check_in < new.check_out AND existing.check_out > new.check_in
		query = (
			frappe.qb.from_(rr)
			.inner_join(rri)
			.on(rr.name == rri.parent)
			.select(rr.name, rr.check_in, rr.check_out, rri.room)
			.where(rri.room.isin(room_names))
			.where(rr.name != (self.name or ""))
			.where(rr.docstatus < 2)
			.where(rr.status.notin(["Cancelled", "Checked Out"]))
			.where(rr.check_in < self.check_out)
			.where(rr.check_out > self.check_in)
		)

		conflicts = query.run(as_dict=True)

		if conflicts:
			c = conflicts[0]
			frappe.throw(
				_(
					"Room {0} is already reserved from {1} to {2} in Reservation {3}."
					" Please choose different dates or a different room."
				).format(
					frappe.bold(c.room),
					frappe.bold(frappe.format_datetime(c.check_in)),
					frappe.bold(frappe.format_datetime(c.check_out)),
					frappe.bold(c.name),
				),
				exc=frappe.ValidationError,
				title=_("Room Unavailable"),
			)


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None):
	"""Map a submitted Room Reservation to a draft Sales Invoice via get_mapped_doc."""
	from frappe.utils import getdate
	from frappe.model.mapper import get_mapped_doc

	def set_missing_values(source, target):
		target.customer = source.customer
		target.company = source.company
		target.due_date = getdate(source.check_out)
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(source_row, target_row, source_parent):
		room_type = frappe.get_cached_doc("Room Type", source_row.room_type)

		if not room_type.billing_item:
			frappe.throw(
				_("Please set a Billing Item on Room Type {0} before generating an invoice.").format(
					frappe.bold(source_row.room_type)
				)
			)

		target_row.item_code = room_type.billing_item
		target_row.item_name = room_type.billing_item
		target_row.description = _(
			"Room {0} — {1} night(s) @ {2}/night"
		).format(source_row.room, source_parent.total_nights, flt(source_row.rate))
		target_row.qty = source_parent.total_nights or 1
		target_row.rate = flt(source_row.rate)
		target_row.amount = flt(source_row.amount)

	return get_mapped_doc(
		"Room Reservation",
		source_name,
		{
			"Room Reservation": {
				"doctype": "Sales Invoice",
				"field_map": {
					"company": "company",
					"customer": "customer",
					"name": "room_reservation",
				},
				"field_no_map": ["status"],
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"Room Reservation Item": {
				"doctype": "Sales Invoice Item",
				"postprocess": update_item,
			},
		},
		target_doc,
		set_missing_values,
	)
