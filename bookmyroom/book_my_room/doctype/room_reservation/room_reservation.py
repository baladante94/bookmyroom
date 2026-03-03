# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, format_datetime, getdate, nowdate


class RoomReservation(Document):
	# ------------------------------------------------------------------ #
	# Frappe lifecycle hooks
	# ------------------------------------------------------------------ #

	def before_save(self):
		self.validate_dates()
		self.validate_backdated_booking()
		self.validate_capacity()
		self.calculate_totals()
		self.validate_overlapping_bookings()

	def on_submit(self):
		self._update_room_status("Occupied")

	def on_cancel(self):
		self._update_room_status("Available")
		if self.status not in ("Checked Out",):
			self.db_set("cancellation_date", nowdate())

	# ------------------------------------------------------------------ #
	# Validation helpers
	# ------------------------------------------------------------------ #

	def validate_dates(self):
		if self.check_in and self.check_out and self.check_in >= self.check_out:
			frappe.throw(
				_("Check Out date must be after Check In date."),
				title=_("Invalid Dates"),
			)

	def validate_backdated_booking(self):
		"""Block backdated bookings when enabled in Booking Settings."""
		if not self.check_in:
			return
		block = frappe.db.get_single_value("Booking Settings", "block_backdated_booking")
		if block and getdate(self.check_in) < getdate(nowdate()):
			frappe.throw(
				_(
					"Backdated bookings are not allowed. Check-in date cannot be earlier than today ({0})."
					"<br>To allow backdated bookings, disable <b>Block Backdated Booking</b> in Booking Settings."
				).format(frappe.bold(nowdate())),
				title=_("Backdated Booking Blocked"),
			)

	def validate_capacity(self):
		"""Warn (non-blocking) if guest count exceeds room capacity."""
		total_guests = (self.num_adults or 0) + (self.num_children or 0)
		if not total_guests:
			return
		for row in self.get("items"):
			if not row.room:
				continue
			capacity = frappe.db.get_value("Room", row.room, "capacity") or 0
			if capacity and total_guests > capacity:
				frappe.msgprint(
					_("Room {0} has a capacity of {1} guest(s), but {2} guest(s) are booked.").format(
						frappe.bold(row.room),
						frappe.bold(capacity),
						frappe.bold(total_guests),
					),
					indicator="orange",
					alert=True,
				)

	def calculate_totals(self):
		"""
		Recalculate:
		  total_nights → room amounts → total_amount (room charges)
		  → meal_plan_amount → subtotal
		  → discount_amount → tax_amount → grand_total → balance_due
		"""
		# --- Nights ---
		self.total_nights = 0
		if self.check_in and self.check_out:
			seconds = frappe.utils.time_diff_in_seconds(self.check_out, self.check_in)
			self.total_nights = max(int(round(seconds / 86400)), 1)

		# --- Room charges ---
		self.total_amount = 0.0
		for row in self.get("items"):
			row.amount = flt(row.rate) * self.total_nights
			self.total_amount += row.amount

		# --- Meal plan charges ---
		self.meal_plan_amount = 0.0
		if self.meal_plan and self.total_nights:
			meal_rate = (
				frappe.db.get_value("Meal Plan", self.meal_plan, "extra_rate_per_person") or 0
			)
			total_persons = (self.num_adults or 1) + (self.num_children or 0)
			self.meal_plan_amount = flt(meal_rate) * total_persons * self.total_nights

		# --- Discount ---
		subtotal = self.total_amount + self.meal_plan_amount
		self.discount_amount = flt(subtotal * flt(self.discount_percentage) / 100)
		after_discount = subtotal - self.discount_amount

		# --- Tax (fetched from Hotel) ---
		tax_rate = 0.0
		if self.hotel:
			tax_rate = frappe.db.get_value("Hotel", self.hotel, "tax_rate") or 0
		self.tax_amount = flt(after_discount * flt(tax_rate) / 100)

		# --- Grand total & balance ---
		self.grand_total = after_discount + self.tax_amount
		self.balance_due = flt(self.grand_total) - flt(self.advance_amount or 0)

	def validate_overlapping_bookings(self):
		"""
		Uses frappe.qb to detect bookings that overlap the requested window for
		any room listed in the child table. Only active reservations are checked
		(docstatus < 2 and status not in ['Cancelled', 'Checked Out', 'No Show']).
		"""
		if not (self.check_in and self.check_out):
			return

		room_names = [row.room for row in self.get("items") if row.room]
		if not room_names:
			return

		rr = frappe.qb.DocType("Room Reservation")
		rri = frappe.qb.DocType("Room Reservation Item")

		query = (
			frappe.qb.from_(rr)
			.inner_join(rri)
			.on(rr.name == rri.parent)
			.select(rr.name, rr.check_in, rr.check_out, rri.room)
			.where(rri.room.isin(room_names))
			.where(rr.name != (self.name or ""))
			.where(rr.docstatus < 2)
			.where(rr.status.notin(["Cancelled", "Checked Out", "No Show"]))
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
					frappe.bold(format_datetime(c.check_in)),
					frappe.bold(format_datetime(c.check_out)),
					frappe.bold(c.name),
				),
				exc=frappe.ValidationError,
				title=_("Room Unavailable"),
			)

	# ------------------------------------------------------------------ #
	# Internal helpers
	# ------------------------------------------------------------------ #

	def _update_room_status(self, status):
		for row in self.get("items"):
			if row.room:
				frappe.db.set_value("Room", row.room, "status", status)

	def _create_housekeeping_log(self, room):
		hotel = frappe.db.get_value("Room", room, "hotel")
		log = frappe.new_doc("Housekeeping Log")
		log.room = room
		log.hotel = hotel
		log.date = nowdate()
		log.task_type = "Check-Out Clean"
		log.status = "Pending"
		log.reservation = self.name
		log.insert(ignore_permissions=True)
		return log.name

	# ------------------------------------------------------------------ #
	# Whitelisted actions (called from JS buttons)
	# ------------------------------------------------------------------ #

	@frappe.whitelist()
	def do_check_in(self):
		"""Check in the guest: update status, mark rooms Occupied."""
		if self.status != "Booked":
			frappe.throw(_("Only reservations with status 'Booked' can be checked in."))
		if self.docstatus != 1:
			frappe.throw(_("Please submit the reservation before checking in."))

		self.db_set("status", "Checked In")
		self._update_room_status("Occupied")
		frappe.msgprint(
			_("Guest checked in successfully. Rooms marked as Occupied."),
			indicator="green",
			alert=True,
		)

	@frappe.whitelist()
	def do_check_out(self):
		"""Check out the guest: update status, mark rooms Dirty, create housekeeping tasks."""
		if self.status != "Checked In":
			frappe.throw(_("Only reservations with status 'Checked In' can be checked out."))

		self.db_set("status", "Checked Out")
		self._update_room_status("Vacant")

		hk_tasks = []
		for row in self.get("items"):
			if row.room:
				frappe.db.set_value("Room", row.room, "housekeeping_status", "Dirty")
				task_name = self._create_housekeeping_log(row.room)
				hk_tasks.append(task_name)

		frappe.msgprint(
			_("Guest checked out. {0} housekeeping task(s) created.").format(len(hk_tasks)),
			indicator="green",
			alert=True,
		)

	@frappe.whitelist()
	def mark_no_show(self):
		"""Mark the reservation as a No Show and free the rooms."""
		if self.status != "Booked":
			frappe.throw(_("Only 'Booked' reservations can be marked as No Show."))

		self.db_set("status", "No Show")
		self.db_set("cancellation_date", nowdate())
		self._update_room_status("Available")
		frappe.msgprint(_("Reservation marked as No Show."), indicator="orange", alert=True)


# ------------------------------------------------------------------ #
# Whitelisted API functions
# ------------------------------------------------------------------ #


def _check_no_submitted_invoice(reservation_name):
	"""Raise ValidationError if a submitted Sales Invoice already exists for this reservation."""
	existing = frappe.get_all(
		"Sales Invoice",
		filters={"bmr_reservation": reservation_name, "docstatus": 1},
		fields=["name"],
		limit=1,
	)
	if existing:
		frappe.throw(
			_(
				"Submitted Sales Invoice {0} already exists for this reservation. "
				"Cancel it before generating a new one."
			).format(frappe.bold(existing[0].name)),
			exc=frappe.ValidationError,
			title=_("Duplicate Invoice"),
		)


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None):
	"""Map a submitted Room Reservation to a draft Sales Invoice."""
	from frappe.utils import getdate as _getdate

	_check_no_submitted_invoice(source_name)

	def set_missing_values(source, target):
		target.customer = source.customer
		target.company = source.company
		target.due_date = _getdate(source.check_out)
		target.bmr_reservation = source.name
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
		target_row.description = _("Room {0} — {1} night(s) @ {2}/night").format(
			source_row.room,
			source_parent.total_nights,
			flt(source_row.rate),
		)
		target_row.qty = source_parent.total_nights or 1
		target_row.rate = flt(source_row.rate)
		target_row.amount = flt(source_row.amount)
		target_row.bmr_reservation = source_parent.name

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


@frappe.whitelist()
def make_combined_invoice(source_name):
	"""
	Create a draft Sales Invoice containing:
	  • Room charges from the Room Reservation
	  • All Open (unsettled) Guest Folio charges linked to this reservation

	Folios are NOT settled at this point — they will be settled automatically
	when the Sales Invoice is submitted (via the on_submit doc_event hook).
	Returns the new Sales Invoice name so JS can open it.
	"""
	_check_no_submitted_invoice(source_name)

	reservation = frappe.get_doc("Room Reservation", source_name)

	if reservation.docstatus != 1:
		frappe.throw(_("Please submit the reservation before billing."))

	si = frappe.new_doc("Sales Invoice")
	si.customer = reservation.customer
	si.company = reservation.company
	si.due_date = frappe.utils.getdate(reservation.check_out or frappe.utils.nowdate())

	# ── Room charges ─────────────────────────────────────────────────────── #
	for row in reservation.get("items"):
		if not row.room_type:
			continue
		billing_item = frappe.db.get_value("Room Type", row.room_type, "billing_item")
		if not billing_item:
			frappe.throw(
				_(
					"Room Type <b>{0}</b> has no Billing Item configured. "
					"Please set one before generating an invoice."
				).format(row.room_type)
			)
		si.append(
			"items",
			{
				"item_code": billing_item,
				"description": _("Room {0} — {1} night(s) @ {2}/night").format(
					row.room, reservation.total_nights, flt(row.rate)
				),
				"qty": reservation.total_nights or 1,
				"rate": flt(row.rate),
				"bmr_reservation": source_name,
			},
		)

	# ── Open (unsettled) folio charges only ──────────────────────────────── #
	open_folios = frappe.get_all(
		"Guest Folio",
		filters={"reservation": source_name, "status": "Open"},
		fields=["name"],
	)

	for folio_info in open_folios:
		folio = frappe.get_doc("Guest Folio", folio_info["name"])
		for item in folio.get("items"):
			billing_item = None
			if item.service:
				billing_item = frappe.db.get_value("Hotel Service", item.service, "billing_item")
			if not billing_item:
				frappe.throw(
					_(
						"Hotel Service <b>{0}</b> has no Billing Item set. "
						"Please configure it before billing."
					).format(item.service or _("Unknown"))
				)
			si.append(
				"items",
				{
					"item_code": billing_item,
					"description": item.description or item.service,
					"qty": flt(item.quantity),
					"rate": flt(item.rate),
					"bmr_guest_folio": folio.name,
				},
			)

	if not si.get("items"):
		frappe.throw(_("No billable charges found for this reservation."))

	si.bmr_reservation = source_name
	si.run_method("set_missing_values")
	si.run_method("calculate_taxes_and_totals")
	si.insert(ignore_permissions=True)
	return si.name


@frappe.whitelist()
def get_folios_for_reservation(reservation):
	"""Return Open (unsettled) Guest Folios linked to a reservation."""
	return frappe.get_all(
		"Guest Folio",
		filters={"reservation": reservation, "status": "Open"},
		fields=["name", "total_amount", "status", "docstatus"],
	)


@frappe.whitelist()
def get_available_rooms(hotel, check_in, check_out, room_type=None):
	"""
	Return a list of rooms that are Available and not already booked
	for the requested date window.

	Used by the room selector on the reservation form.
	"""
	# Rooms already booked for overlapping period
	rr = frappe.qb.DocType("Room Reservation")
	rri = frappe.qb.DocType("Room Reservation Item")

	booked_query = (
		frappe.qb.from_(rr)
		.inner_join(rri)
		.on(rr.name == rri.parent)
		.select(rri.room)
		.where(rr.hotel == hotel)
		.where(rr.docstatus < 2)
		.where(rr.status.notin(["Cancelled", "Checked Out", "No Show"]))
		.where(rr.check_in < check_out)
		.where(rr.check_out > check_in)
	)
	booked_rooms = {r.room for r in booked_query.run(as_dict=True)}

	# Filter available rooms
	filters = {
		"hotel": hotel,
		"status": "Available",
	}
	if room_type:
		filters["room_type"] = room_type

	rooms = frappe.get_all(
		"Room",
		filters=filters,
		fields=["name", "room_type", "floor", "capacity", "bed_type", "view_type", "smoking"],
		order_by="name asc",
	)

	return [r for r in rooms if r.name not in booked_rooms]


@frappe.whitelist()
def get_applicable_rate(room_type, hotel, check_in_date):
	"""
	Return the rate from the first active Rate Plan that covers check_in_date,
	or None if no plan matches (caller uses the Room Type default_rate).
	"""
	plans = frappe.get_all(
		"Rate Plan",
		filters={
			"hotel": hotel,
			"room_type": room_type,
			"is_active": 1,
			"valid_from": ["<=", check_in_date],
			"valid_to": [">=", check_in_date],
		},
		fields=["rate_per_night"],
		limit=1,
		order_by="valid_from desc",
	)
	return plans[0].rate_per_night if plans else None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_rooms_for_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	"""
	Server-side search function for the room picker in the reservation child table.
	Filters by hotel, status=Available, and excludes rooms booked for the given dates.
	"""
	import json

	if isinstance(filters, str):
		filters = json.loads(filters)

	hotel = filters.get("hotel") or ""
	check_in = filters.get("check_in") or ""
	check_out = filters.get("check_out") or ""
	current_reservation = filters.get("current_reservation") or ""

	r = frappe.qb.DocType("Room")

	# Hotel rooms that are bookable (exclude permanently unavailable statuses only)
	query = (
		frappe.qb.from_(r)
		.select(r.name, r.room_type, r.floor, r.bed_type, r.status)
		.where(r.hotel == hotel)
		.where(r.status.notin(["Out of Order", "Maintenance"]))
		.where(r[searchfield].like(f"%{txt}%"))
		.offset(start)
		.limit(page_len)
	)

	# Exclude rooms with overlapping active reservations
	if check_in and check_out:
		rr = frappe.qb.DocType("Room Reservation")
		rri = frappe.qb.DocType("Room Reservation Item")
		booked_query = (
			frappe.qb.from_(rr)
			.inner_join(rri)
			.on(rr.name == rri.parent)
			.select(rri.room)
			.where(rr.hotel == hotel)
			.where(rr.docstatus < 2)
			.where(rr.status.notin(["Cancelled", "Checked Out", "No Show"]))
			.where(rr.check_in < check_out)
			.where(rr.check_out > check_in)
		)
		if current_reservation:
			booked_query = booked_query.where(rr.name != current_reservation)

		booked_rooms = [row.room for row in booked_query.run(as_dict=True)]
		if booked_rooms:
			query = query.where(r.name.notin(booked_rooms))

	return query.run()
