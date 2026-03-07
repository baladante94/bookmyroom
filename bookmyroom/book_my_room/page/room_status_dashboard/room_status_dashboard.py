# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import calendar

import frappe
from frappe import _
from frappe.utils import flt, getdate, today


@frappe.whitelist()
def get_room_status_data(hotel=None):
	"""Return all rooms with current status, housekeeping status and active reservation info."""
	filters = {}
	if hotel:
		filters["hotel"] = hotel

	rooms = frappe.get_all(
		"Room",
		filters=filters,
		fields=[
			"name",
			"room_name",
			"hotel",
			"room_type",
			"floor",
			"status",
			"housekeeping_status",
			"capacity",
			"bed_type",
		],
		order_by="hotel asc, floor asc, room_name asc",
	)

	if not rooms:
		return rooms

	# Active reservations (Booked or Checked In)
	res_filters = {
		"status": ["in", ["Booked", "Checked In"]],
		"docstatus": 1,
	}
	if hotel:
		res_filters["hotel"] = hotel

	active_res = frappe.get_all(
		"Room Reservation",
		filters=res_filters,
		fields=["name", "customer", "check_in", "check_out", "status"],
	)

	if active_res:
		res_names = [r.name for r in active_res]
		items = frappe.get_all(
			"Room Reservation Item",
			filters={"parent": ["in", res_names]},
			fields=["parent", "room"],
		)
		# Build room → reservation map (first active match wins)
		res_by_name = {r.name: r for r in active_res}
		room_to_res = {}
		for item in items:
			if item.room not in room_to_res and item.parent in res_by_name:
				room_to_res[item.room] = res_by_name[item.parent]

		for room in rooms:
			res = room_to_res.get(room.name)
			room["reservation"] = {
				"name": res.name,
				"customer": res.customer,
				"check_in": str(res.check_in),
				"check_out": str(res.check_out),
				"status": res.status,
			} if res else None
	else:
		for room in rooms:
			room["reservation"] = None

	return rooms


@frappe.whitelist()
def get_calendar_data(hotel=None, from_date=None, to_date=None):
	"""Return submitted reservations that overlap the given date range, for calendar rendering."""
	if not from_date:
		from_date = today()
	if not to_date:
		d = getdate(from_date)
		last_day = calendar.monthrange(d.year, d.month)[1]
		to_date = d.replace(day=last_day).strftime("%Y-%m-%d")

	filters = {
		"docstatus": 1,
		"status": ["in", ["Booked", "Checked In"]],
		"check_in": ["<=", to_date + " 23:59:59"],
		"check_out": [">=", from_date + " 00:00:00"],
	}
	if hotel:
		filters["hotel"] = hotel

	reservations = frappe.get_all(
		"Room Reservation",
		filters=filters,
		fields=[
			"name",
			"customer",
			"check_in",
			"check_out",
			"status",
			"advance_amount",
			"balance_due",
			"grand_total",
			"total_nights",
		],
	)

	if not reservations:
		return []

	res_names = [r.name for r in reservations]
	items = frappe.get_all(
		"Room Reservation Item",
		filters={"parent": ["in", res_names]},
		fields=["parent", "room"],
	)

	res_by_name = {r.name: r for r in reservations}
	result = []
	for item in items:
		res = res_by_name.get(item.parent)
		if res:
			result.append(
				{
					"room": item.room,
					"reservation": res.name,
					"customer": res.customer,
					"check_in": str(res.check_in),
					"check_out": str(res.check_out),
					"status": res.status,
					"advance_amount": flt(res.advance_amount),
					"balance_due": flt(res.balance_due),
					"grand_total": flt(res.grand_total),
					"total_nights": res.total_nights or 0,
				}
			)

	return result
