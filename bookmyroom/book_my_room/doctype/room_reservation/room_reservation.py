# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, format_datetime, getdate, now_datetime, nowdate, time_diff_in_hours
from frappe.utils import nowdate as _nowdate


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
		# Rooms stay as-is until the guest physically arrives.
		# do_check_in() is the only place that sets rooms to Occupied.
		pass

	def on_cancel(self):
		# Only reset room status if the guest was actually checked in
		if self.status == "Checked In":
			self._update_room_status("Available")
		if self.status not in ("Checked Out",):
			self.db_set("cancellation_date", nowdate())
		self._apply_cancellation_fee()
		self._send_cancellation_email()

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
		"""Block saving if guest count exceeds any room's capacity."""
		total_guests = (self.num_adults or 0) + (self.num_children or 0)
		if not total_guests:
			return
		for row in self.get("items"):
			if not row.room:
				continue
			capacity = frappe.db.get_value("Room", row.room, "capacity") or 0
			if capacity and total_guests > capacity:
				frappe.throw(
					_("Room {0} has a maximum capacity of {1} guest(s), but {2} guest(s) are booked."
					  " Please reduce the guest count or choose a different room.").format(
						frappe.bold(row.room),
						frappe.bold(capacity),
						frappe.bold(total_guests),
					),
					title=_("Capacity Exceeded"),
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
		if self.discount_type == "Fixed Amount":
			self.discount_amount = min(flt(self.discount_value or 0), subtotal)
		else:
			self.discount_amount = flt(subtotal * flt(self.discount_percentage or 0) / 100)

		# Split discount proportionally across room and meal components
		discount_ratio = self.discount_amount / subtotal if subtotal else 0
		room_after_discount = self.total_amount * (1 - discount_ratio)
		meal_after_discount = self.meal_plan_amount * (1 - discount_ratio)

		# --- Tax: room and meal calculated at their own rates ---
		room_tax_rate, room_tax_desc = self._get_tax_rate()
		room_tax = flt(room_after_discount * room_tax_rate / 100)

		meal_tax_rate = self._get_meal_tax_rate() if meal_after_discount else 0.0
		meal_tax = flt(meal_after_discount * meal_tax_rate / 100)

		self.tax_amount = room_tax + meal_tax

		# Build a clear tax description
		if meal_tax_rate and meal_after_discount:
			self.tax_description = _("{0} on rooms; {1}% on meal plan").format(
				room_tax_desc, meal_tax_rate
			)
		else:
			self.tax_description = room_tax_desc

		# --- Grand total & balance ---
		after_discount = subtotal - self.discount_amount
		self.grand_total = after_discount + self.tax_amount
		self.balance_due = flt(self.grand_total) - flt(self.advance_amount or 0)

	def _get_tax_rate(self):
		"""Return (tax_rate_pct, description) for room charges from configured tax slabs."""
		rates = [flt(row.rate) for row in self.get("items") if flt(row.rate) > 0]
		if not rates:
			return 0.0, ""
		avg_rate = sum(rates) / len(rates)
		return _tax_rate_for_tariff(avg_rate)

	def _get_meal_tax_rate(self):
		"""Return effective tax rate (%) for the meal plan's billing item."""
		if not self.meal_plan:
			return 0.0
		billing_item = frappe.db.get_value("Meal Plan", self.meal_plan, "billing_item")
		if not billing_item:
			return 0.0
		return _effective_tax_rate_for_item(billing_item)

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

	def _apply_cancellation_fee(self):
		"""Calculate and store cancellation fee based on Booking Settings policy."""
		fee_type = frappe.db.get_single_value("Booking Settings", "cancellation_fee_type") or "None"
		if fee_type == "None":
			return

		free_hours = flt(frappe.db.get_single_value("Booking Settings", "free_cancellation_hours") or 24)
		hours_to_checkin = time_diff_in_hours(self.check_in, now_datetime())

		# Within free cancellation window — no fee
		if hours_to_checkin >= free_hours:
			return

		fee = 0.0
		if fee_type == "Fixed Amount":
			fee = flt(frappe.db.get_single_value("Booking Settings", "cancellation_fee_value") or 0)
		elif fee_type == "First Night Rate":
			fee = sum(flt(row.rate) for row in self.get("items"))

		if fee:
			frappe.db.set_value("Room Reservation", self.name, "cancellation_fee", fee)
			frappe.msgprint(
				_("Cancellation fee of {0} applied (late cancellation).").format(
					frappe.utils.fmt_money(fee)
				),
				indicator="orange",
				alert=True,
			)

	def _send_cancellation_email(self):
		"""Send cancellation confirmation email to the customer."""
		if not self.customer:
			return
		email = frappe.db.get_value("Customer", self.customer, "email_id")
		if not email:
			return
		try:
			frappe.sendmail(
				recipients=[email],
				subject=_("Reservation Cancellation — {0}").format(self.name),
				message=_(
					"Dear {0},<br><br>"
					"Your reservation <b>{1}</b> has been cancelled.<br>"
					"Check-in: {2} &nbsp;|&nbsp; Check-out: {3}<br><br>"
					"If you have any questions, please contact us.<br><br>"
					"Regards,<br>{4}"
				).format(
					self.customer,
					self.name,
					frappe.utils.format_datetime(self.check_in, "dd-MM-yyyy HH:mm"),
					frappe.utils.format_datetime(self.check_out, "dd-MM-yyyy HH:mm"),
					frappe.defaults.get_defaults().get("company") or "",
				),
			)
		except Exception:
			pass  # Email failure must never block cancellation

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
	def extend_stay(self, new_check_out):
		"""Extend the check-out date for a currently checked-in guest."""
		if self.status != "Checked In":
			frappe.throw(_("Only 'Checked In' reservations can be extended."))

		new_co = getdate(str(new_check_out).split(" ")[0])
		cur_co = getdate(str(self.check_out).split(" ")[0])
		if new_co <= cur_co:
			frappe.throw(_("New check-out must be later than the current check-out ({0}).").format(
				frappe.utils.formatdate(cur_co)
			))

		# Check for overlapping bookings in the extension window
		room_names = [row.room for row in self.get("items") if row.room]
		if room_names:
			rr = frappe.qb.DocType("Room Reservation")
			rri = frappe.qb.DocType("Room Reservation Item")
			conflicts = (
				frappe.qb.from_(rr)
				.inner_join(rri).on(rr.name == rri.parent)
				.select(rr.name, rri.room)
				.where(rri.room.isin(room_names))
				.where(rr.name != self.name)
				.where(rr.docstatus < 2)
				.where(rr.status.notin(["Cancelled", "Checked Out", "No Show"]))
				.where(rr.check_in < new_check_out)
				.where(rr.check_out > self.check_out)
			).run(as_dict=True)
			if conflicts:
				c = conflicts[0]
				frappe.throw(
					_("Cannot extend: Room {0} is already reserved in {1} during the extension period.").format(
						frappe.bold(c.room), frappe.bold(c.name)
					)
				)

		# Recalculate totals with new check-out
		self.check_out = new_check_out
		self.calculate_totals()

		for row in self.get("items"):
			frappe.db.set_value("Room Reservation Item", row.name, "amount", row.amount)

		frappe.db.set_value("Room Reservation", self.name, {
			"check_out": new_check_out,
			"total_nights": self.total_nights,
			"total_amount": self.total_amount,
			"meal_plan_amount": self.meal_plan_amount,
			"discount_amount": self.discount_amount,
			"tax_amount": self.tax_amount,
			"grand_total": self.grand_total,
			"balance_due": self.balance_due,
		})
		frappe.db.commit()
		frappe.publish_realtime(
			"doc_update",
			{"doctype": "Room Reservation", "name": self.name},
			doctype="Room Reservation",
			docname=self.name,
		)
		frappe.msgprint(
			_("Stay extended to {0}. New total: {1}.").format(
				frappe.utils.formatdate(new_co),
				frappe.utils.fmt_money(self.grand_total),
			),
			indicator="green",
			alert=True,
		)

	@frappe.whitelist()
	def make_advance_payment_entry(self):
		"""Create a draft Payment Entry for the advance amount."""
		if not flt(self.advance_amount):
			frappe.throw(_("Please set an Advance Amount before creating a payment entry."))
		if self.advance_payment_entry and frappe.db.exists("Payment Entry", self.advance_payment_entry):
			frappe.throw(
				_("A payment entry {0} already exists for this reservation.").format(
					frappe.bold(self.advance_payment_entry)
				)
			)

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Receive"
		pe.party_type = "Customer"
		pe.party = self.customer
		pe.company = self.company
		pe.paid_amount = flt(self.advance_amount)
		pe.received_amount = flt(self.advance_amount)
		pe.posting_date = self.advance_payment_date or nowdate()
		pe.reference_date = self.advance_payment_date or nowdate()
		if self.advance_payment_mode:
			pe.mode_of_payment = self.advance_payment_mode
		pe.remarks = _("Advance payment for Room Reservation {0}").format(self.name)
		pe.insert(ignore_permissions=True)

		frappe.db.set_value("Room Reservation", self.name, "advance_payment_entry", pe.name)
		frappe.db.commit()
		return pe.name

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


def _get_item_tax_template(item_code):
	"""Return the first Item Tax Template assigned to an Item (via its Item Tax child table)."""
	if not item_code:
		return None
	return frappe.db.get_value(
		"Item Tax",
		{"parent": item_code, "parenttype": "Item"},
		"item_tax_template",
	)


def _effective_tax_rate_for_item(item_code):
	"""Return the effective GST rate (%) for an item by reading gst_rate
	directly from its Item Tax Template — the canonical single source of truth."""
	if not item_code:
		return 0.0

	template_name = frappe.db.get_value(
		"Item Tax",
		{"parent": item_code, "parenttype": "Item"},
		"item_tax_template",
		order_by="idx asc",
	)
	if not template_name:
		return 0.0

	return flt(frappe.db.get_value("Item Tax Template", template_name, "gst_rate") or 0)


def _get_tax_slabs():
	"""Return configured room tax slabs from Booking Settings, ordered by min_tariff."""
	return frappe.get_all(
		"Room Tax Slab",
		filters={"parent": "Booking Settings"},
		fields=["min_tariff", "max_tariff", "item_tax_template", "tax_rate"],
		order_by="min_tariff asc",
	)


def _tax_rate_for_tariff(rate_per_night):
	"""Return (tax_rate_pct, description) for a given room tariff using configured slabs.

	Falls back to Indian GST accommodation slabs (0%/12%/18%) if no slabs are configured.
	"""
	slabs = _get_tax_slabs()
	rate = flt(rate_per_night)

	if slabs:
		for slab in slabs:
			min_t = flt(slab.min_tariff)
			max_t = flt(slab.max_tariff)
			if rate >= min_t and (max_t == 0 or rate <= max_t):
				tax_rate = flt(slab.tax_rate)
				template = slab.item_tax_template
				if tax_rate == 0:
					return 0.0, _("GST Exempt")
				if template:
					return tax_rate, _("GST {0}% ({1})").format(tax_rate, template)
				return tax_rate, _("Tax {0}%").format(tax_rate)
		return 0.0, ""

	# Hardcoded Indian hotel GST fallback when no slabs configured
	if rate <= 1000:
		return 0.0, _("GST Exempt (tariff ≤ ₹1,000/night)")
	elif rate <= 7500:
		return 12.0, _("GST 12% (tariff ₹1,001–₹7,500/night)")
	else:
		return 18.0, _("GST 18% (tariff > ₹7,500/night)")


def _get_room_tax_template_for_rate(rate_per_night):
	"""Return the item_tax_template for a given room rate from configured tax slabs."""
	slabs = _get_tax_slabs()
	rate = flt(rate_per_night)
	for slab in slabs:
		min_t = flt(slab.min_tariff)
		max_t = flt(slab.max_tariff)
		if rate >= min_t and (max_t == 0 or rate <= max_t):
			return slab.item_tax_template or None
	return None


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
		target.due_date = max(_getdate(source.check_out), _getdate(_nowdate()))
		target.bmr_reservation = source.name

		# Add meal plan charges as a separate line item if applicable
		if flt(source.meal_plan_amount) > 0 and source.meal_plan:
			meal_billing_item = frappe.db.get_value("Meal Plan", source.meal_plan, "billing_item")
			if meal_billing_item:
				meal_tax_template = _get_item_tax_template(meal_billing_item)
				target.append("items", {
					"item_code": meal_billing_item,
					"description": _("Meal Plan: {0} — {1} person(s) × {2} night(s)").format(
						source.meal_plan,
						(source.num_adults or 1) + (source.num_children or 0),
						source.total_nights,
					),
					"qty": 1,
					"rate": flt(source.meal_plan_amount),
					"bmr_reservation": source.name,
					"item_tax_template": meal_tax_template or None,
				})

		# Transfer reservation-level discount so SI total matches
		if flt(source.discount_amount) > 0:
			target.additional_discount_amount = flt(source.discount_amount)

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

		# Apply Item Tax Template per room rate from configured tax slabs
		tax_template = _get_room_tax_template_for_rate(source_row.rate)
		if tax_template:
			target_row.item_tax_template = tax_template

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

	# ── Pre-validate ALL billing items before building the document ───────── #
	errors = []
	for row in reservation.get("items"):
		if row.room_type and not frappe.db.get_value("Room Type", row.room_type, "billing_item"):
			errors.append(_("Room Type <b>{0}</b> has no Billing Item configured.").format(row.room_type))

	open_folios_for_validation = frappe.get_all(
		"Guest Folio",
		filters={"reservation": source_name, "status": "Open"},
		fields=["name"],
	)
	for folio_info in open_folios_for_validation:
		folio_doc = frappe.get_doc("Guest Folio", folio_info["name"])
		for item in folio_doc.get("items"):
			if item.service:
				billing_item = frappe.db.get_value("Hotel Service", item.service, "billing_item")
				if not billing_item:
					errors.append(
						_("Hotel Service <b>{0}</b> (Folio {1}) has no Billing Item set.").format(
							item.service, folio_info["name"]
						)
					)
	if errors:
		frappe.throw(
			_("Cannot create invoice. Fix the following issues first:<br>") + "<br>".join(errors),
			title=_("Missing Billing Items"),
		)

	si = frappe.new_doc("Sales Invoice")
	si.customer = reservation.customer
	si.company = reservation.company
	si.due_date = max(
		frappe.utils.getdate(reservation.check_out or frappe.utils.nowdate()),
		frappe.utils.getdate(frappe.utils.nowdate()),
	)

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
				"item_tax_template": _get_room_tax_template_for_rate(flt(row.rate)),
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
			# Fetch tax template from the Item master (service items have their own rate)
			svc_tax_template = _get_item_tax_template(billing_item)
			si.append(
				"items",
				{
					"item_code": billing_item,
					"description": item.description or item.service,
					"qty": flt(item.quantity),
					"rate": flt(item.rate),
					"bmr_guest_folio": folio.name,
					"item_tax_template": svc_tax_template or None,
				},
			)

	# ── Meal plan charges ─────────────────────────────────────────────────── #
	if flt(reservation.meal_plan_amount) > 0 and reservation.meal_plan:
		meal_billing_item = frappe.db.get_value("Meal Plan", reservation.meal_plan, "billing_item")
		if meal_billing_item:
			# Food/restaurant services carry their own GST rate (typically 5%)
			# — fetched from the Item Tax child table, NOT the hotel room template
			meal_tax_template = _get_item_tax_template(meal_billing_item)
			si.append(
				"items",
				{
					"item_code": meal_billing_item,
					"description": _("Meal Plan: {0} — {1} person(s) × {2} night(s)").format(
						reservation.meal_plan,
						(reservation.num_adults or 1) + (reservation.num_children or 0),
						reservation.total_nights,
					),
					"qty": 1,
					"rate": flt(reservation.meal_plan_amount),
					"bmr_reservation": source_name,
					"item_tax_template": meal_tax_template or None,
				},
			)

	if not si.get("items"):
		frappe.throw(_("No billable charges found for this reservation."))

	# Transfer reservation-level discount so SI total matches
	if flt(reservation.discount_amount) > 0:
		si.additional_discount_amount = flt(reservation.discount_amount)

	si.bmr_reservation = source_name
	si.run_method("set_missing_values")
	si.run_method("calculate_taxes_and_totals")
	try:
		si.insert(ignore_permissions=True)
	except Exception as e:
		frappe.db.rollback()
		frappe.throw(_("Failed to create Sales Invoice: {0}").format(str(e)))
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
