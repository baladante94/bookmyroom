# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class Room(Document):
	def validate(self):
		if self.capacity and self.capacity < 1:
			frappe.throw(_("Room capacity must be at least 1."), title=_("Invalid Capacity"))


@frappe.whitelist()
def get_room_calendar_events(start, end, filters=None):
	"""Return Room Reservation events for the Room calendar view.
	Frappe calls this with the visible date range (start/end) of the calendar."""
	if isinstance(filters, str):
		filters = json.loads(filters)
	filters = filters or {}

	# Status → colour mapping
	color_map = {
		"Booked": "#2196F3",      # blue
		"Checked In": "#f44336",  # red
		"Checked Out": "#9e9e9e", # grey
	}

	rr = frappe.qb.DocType("Room Reservation")
	rri = frappe.qb.DocType("Room Reservation Item")

	q = (
		frappe.qb.from_(rr)
		.inner_join(rri)
		.on(rr.name == rri.parent)
		.select(rr.name, rr.customer, rr.check_in, rr.check_out, rr.status, rri.room)
		.where(rr.docstatus == 1)
		.where(rr.status.notin(["Cancelled", "No Show"]))
		.where(rr.check_in < end)
		.where(rr.check_out > start)
	)
	if filters.get("hotel"):
		q = q.where(rr.hotel == filters["hotel"])

	rows = q.run(as_dict=True)

	events = []
	for r in rows:
		events.append(
			{
				"name": r.name,
				"start": str(r.check_in),
				"end": str(r.check_out),
				"title": f"{r.room} — {r.customer}",
				"color": color_map.get(r.status, "#607d8b"),
				"all_day": 0,
			}
		)
	return events


@frappe.whitelist()
def get_room_reservations(room, from_date, to_date):
	"""Return active reservations for a room that overlap the given date range.
	Used by the 30-day availability calendar in the Room form."""
	rr = frappe.qb.DocType("Room Reservation")
	rri = frappe.qb.DocType("Room Reservation Item")

	rows = (
		frappe.qb.from_(rr)
		.inner_join(rri)
		.on(rr.name == rri.parent)
		.select(rr.name, rr.customer, rr.check_in, rr.check_out, rr.status)
		.where(rri.room == room)
		.where(rr.docstatus == 1)
		.where(rr.status.isin(["Booked", "Checked In"]))
		.where(rr.check_in <= to_date + " 23:59:59")
		.where(rr.check_out >= from_date + " 00:00:00")
		.orderby(rr.check_in)
	).run(as_dict=True)

	return [
		{
			"name": r.name,
			"customer": r.customer,
			"check_in": str(r.check_in),
			"check_out": str(r.check_out),
			"status": r.status,
		}
		for r in rows
	]
