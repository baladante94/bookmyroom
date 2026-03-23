# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt

import calendar

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, date_diff, flt, get_first_day, getdate, today


@frappe.whitelist()
def get_room_status_data(hotel=None):
	"""Return all rooms with current status, housekeeping status and active reservation info."""
	filters = {}
	if hotel:
		filters["hotel"] = hotel

	rooms = frappe.get_all(
		"Rooms",
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


# ── New KPI + chart endpoints ─────────────────────────────────────────────── #

@frappe.whitelist()
def get_dashboard_kpis(hotel=None, from_date=None, to_date=None):
	"""Return all KPI numbers for the dashboard header cards in one request.
	from_date / to_date define the period (defaults to current month up to today)."""
	t = today()

	# Resolve period
	period_start = from_date or get_first_day(t).strftime("%Y-%m-%d")
	period_end   = to_date   or t

	# Is the selected period the current month?
	is_current_month = (period_start[:7] == t[:7])

	base = {"docstatus": 1}
	if hotel:
		base["hotel"] = hotel

	# Check-ins/outs for the period
	checkins = frappe.db.count("Room Reservation", {
		**base,
		"check_in": ["between", [period_start + " 00:00:00", period_end + " 23:59:59"]],
		"status": ["in", ["Booked", "Checked In"]],
	})
	checkouts = frappe.db.count("Room Reservation", {
		**base,
		"check_out": ["between", [period_start + " 00:00:00", period_end + " 23:59:59"]],
		"status": ["in", ["Checked In", "Checked Out"]],
	})

	# Today-specific (only meaningful on current month view)
	checkins_today  = frappe.db.count("Room Reservation", {
		**base,
		"check_in": ["between", [t + " 00:00:00", t + " 23:59:59"]],
		"status": ["in", ["Booked", "Checked In"]],
	}) if is_current_month else None
	checkouts_today = frappe.db.count("Room Reservation", {
		**base,
		"check_out": ["between", [t + " 00:00:00", t + " 23:59:59"]],
		"status": ["in", ["Checked In", "Checked Out"]],
	}) if is_current_month else None

	# Real-time room state (always current, not period-scoped)
	occupied = frappe.db.count("Room Reservation", {**base, "status": "Checked In"})
	booked   = frappe.db.count("Room Reservation", {**base, "status": "Booked"})

	room_f = {"hotel": hotel} if hotel else {}
	total_rooms     = frappe.db.count("Rooms", room_f)
	available_rooms = frappe.db.count("Rooms", {**room_f, "status": "Available"})
	occupied_rooms  = frappe.db.count("Rooms", {**room_f, "status": "Occupied"})
	vacant_clean    = frappe.db.count("Rooms", {**room_f, "status": "Vacant", "housekeeping_status": "Clean"})
	vacant_dirty    = frappe.db.count("Rooms", {**room_f, "status": "Vacant", "housekeeping_status": "Dirty"})
	out_of_order    = frappe.db.count("Rooms", {**room_f, "status": "Out of Order"})
	in_maintenance  = frappe.db.count("Rooms", {**room_f, "status": "Maintenance"})

	si = frappe.qb.DocType("Sales Invoice")

	# Revenue collected (paid) for the period
	rev_period_row = (
		frappe.qb.from_(si)
		.select(Sum(si.grand_total))
		.where(si.docstatus == 1)
		.where(si.status == "Paid")
		.where(si.posting_date >= period_start)
		.where(si.posting_date <= period_end)
		.run()
	)
	revenue_month = flt((rev_period_row or [[0]])[0][0])

	# Revenue today (only on current-month view)
	if is_current_month:
		rev_today_row = (
			frappe.qb.from_(si)
			.select(Sum(si.grand_total))
			.where(si.docstatus == 1)
			.where(si.status == "Paid")
			.where(si.posting_date == t)
			.run()
		)
		revenue_today = flt((rev_today_row or [[0]])[0][0])
	else:
		revenue_today = None

	# Outstanding for the period
	outstanding_row = (
		frappe.qb.from_(si)
		.select(Sum(si.outstanding_amount))
		.where(si.docstatus == 1)
		.where(si.status.isin(["Unpaid", "Overdue", "Partly Paid"]))
		.where(si.posting_date >= period_start)
		.where(si.posting_date <= period_end)
		.run()
	)
	outstanding_month = flt((outstanding_row or [[0]])[0][0])

	# Overdue = past due_date anywhere (not period-scoped — always relevant)
	overdue_row = (
		frappe.qb.from_(si)
		.select(Sum(si.outstanding_amount))
		.where(si.docstatus == 1)
		.where(si.outstanding_amount > 0)
		.where(si.due_date < t)
		.run()
	)
	overdue_amount = flt((overdue_row or [[0]])[0][0])

	return {
		"checkins":          checkins or 0,
		"checkouts":         checkouts or 0,
		"checkins_today":    checkins_today,   # None when viewing other months
		"checkouts_today":   checkouts_today,  # None when viewing other months
		"occupied":          occupied or 0,
		"booked":            booked or 0,
		"available_rooms":   available_rooms or 0,
		"total_rooms":       total_rooms or 0,
		"occupied_rooms":    occupied_rooms or 0,
		"occupancy_pct":     round(occupied_rooms / total_rooms * 100) if total_rooms else 0,
		"revenue_today":     revenue_today,    # None when viewing other months
		"revenue_month":     revenue_month,
		"outstanding_month": outstanding_month,
		"overdue_amount":    overdue_amount,
		"period_start":      period_start,
		"period_end":        period_end,
		"is_current_month":  is_current_month,
		"vacant_clean":      vacant_clean or 0,
		"vacant_dirty":      vacant_dirty or 0,
		"out_of_order":      out_of_order or 0,
		"in_maintenance":    in_maintenance or 0,
	}


@frappe.whitelist()
def get_revenue_trend(hotel=None, days=14):
	"""Return daily revenue (sum of SI grand_total) for the last N days."""
	days = int(days)
	t = today()
	start = add_days(t, -(days - 1))

	si = frappe.qb.DocType("Sales Invoice")
	rows = (
		frappe.qb.from_(si)
		.select(si.posting_date, Sum(si.grand_total).as_("revenue"))
		.where(si.docstatus == 1)
		.where(si.posting_date >= start)
		.groupby(si.posting_date)
		.orderby(si.posting_date)
		.run(as_dict=True)
	)
	by_date = {str(r.posting_date): flt(r.revenue) for r in rows}
	return [{"date": add_days(start, i), "revenue": by_date.get(add_days(start, i), 0)}
			for i in range(days)]


@frappe.whitelist()
def get_today_arrivals_departures(hotel=None):
	"""Return today's check-in list and check-out list with room numbers."""
	t = today()
	base = {"docstatus": 1}
	if hotel:
		base["hotel"] = hotel

	arrivals_res = frappe.get_all(
		"Room Reservation",
		filters={**base, "check_in": ["between", [t + " 00:00:00", t + " 23:59:59"]],
				 "status": ["in", ["Booked", "Checked In"]]},
		fields=["name", "customer", "status", "check_in", "check_out"],
	)
	departures_res = frappe.get_all(
		"Room Reservation",
		filters={**base, "check_out": ["between", [t + " 00:00:00", t + " 23:59:59"]],
				 "status": ["in", ["Checked In", "Checked Out"]]},
		fields=["name", "customer", "status", "check_in", "check_out"],
	)

	def _enrich(res_list):
		if not res_list:
			return []
		names = [r.name for r in res_list]
		items = frappe.get_all(
			"Room Reservation Item",
			filters={"parent": ["in", names]},
			fields=["parent", "room"],
		)
		by_parent = {}
		for item in items:
			by_parent.setdefault(item.parent, []).append(item.room)
		return [
			{"name": r.name, "customer": r.customer, "status": r.status,
			 "rooms": by_parent.get(r.name, [])}
			for r in res_list
		]

	return {"arrivals": _enrich(arrivals_res), "departures": _enrich(departures_res)}


# ── Custom Number Card methods (called by workspace cards) ────────────────── #

@frappe.whitelist()
def nc_checkins_today(**kwargs):
	t = today()
	return frappe.db.count("Room Reservation", {
		"docstatus": 1,
		"check_in": ["between", [t + " 00:00:00", t + " 23:59:59"]],
		"status": ["in", ["Booked", "Checked In"]],
	}) or 0


@frappe.whitelist()
def nc_checkouts_today(**kwargs):
	t = today()
	return frappe.db.count("Room Reservation", {
		"docstatus": 1,
		"check_out": ["between", [t + " 00:00:00", t + " 23:59:59"]],
		"status": ["in", ["Checked In", "Checked Out"]],
	}) or 0


@frappe.whitelist()
def nc_revenue_this_month(**kwargs):
	t = today()
	month_start = get_first_day(t).strftime("%Y-%m-%d")
	si = frappe.qb.DocType("Sales Invoice")
	result = (
		frappe.qb.from_(si)
		.select(Sum(si.grand_total))
		.where(si.docstatus == 1)
		.where(si.status == "Paid")
		.where(si.posting_date >= month_start)
		.run()
	)
	return flt((result or [[0]])[0][0])


@frappe.whitelist()
def get_housekeeping_board(hotel=None):
	"""Return all rooms with housekeeping status and today's assignment from Housekeeping Log."""
	t = today()
	room_f = {"hotel": hotel} if hotel else {}
	rooms = frappe.get_all(
		"Rooms",
		filters=room_f,
		fields=["name", "room_name", "floor", "status", "housekeeping_status"],
		order_by="floor asc, room_name asc",
	)
	if not rooms:
		return []

	hk_filters = {"date": t}
	if hotel:
		hk_filters["hotel"] = hotel
	try:
		hk_logs = frappe.get_all(
			"Housekeeping Log",
			filters=hk_filters,
			fields=["room", "assigned_to", "status"],
			order_by="creation desc",
		)
	except Exception:
		hk_logs = []

	hk_by_room = {}
	for log in hk_logs:
		if log.room not in hk_by_room:
			hk_by_room[log.room] = log

	result = []
	for r in rooms:
		log = hk_by_room.get(r.name)
		result.append({
			"name": r.name,
			"room_name": r.room_name or r.name,
			"floor": r.floor or "",
			"room_status": r.status,
			"hk_status": r.housekeeping_status or "Clean",
			"assigned_to": log.assigned_to if log else None,
		})
	return result


@frappe.whitelist()
def quick_update_reservation(reservation, check_out=None, new_room=None, old_room=None):
	"""Quick update reservation dates or room from the dashboard."""
	if check_out:
		doc = frappe.get_doc("Room Reservation", reservation)
		doc.check_out = check_out
		doc.calculate_totals()

		# Persist recalculated child-row amounts
		for row in doc.get("items"):
			frappe.db.set_value("Room Reservation Item", row.name, "amount", row.amount)

		# Persist all recalculated header fields
		frappe.db.set_value("Room Reservation", reservation, {
			"check_out": check_out,
			"total_nights": doc.total_nights,
			"total_amount": doc.total_amount,
			"meal_plan_amount": doc.meal_plan_amount,
			"discount_amount": doc.discount_amount,
			"tax_amount": doc.tax_amount,
			"grand_total": doc.grand_total,
			"balance_due": doc.balance_due,
		})

	if new_room and old_room and new_room != old_room:
		items = frappe.get_all(
			"Room Reservation Item",
			filters={"parent": reservation, "room": old_room},
			fields=["name"],
			limit=1,
		)
		if items:
			frappe.db.set_value("Room Reservation Item", items[0].name, "room", new_room)

		res = frappe.get_doc("Room Reservation", reservation)
		if res.status == "Checked In":
			frappe.db.set_value("Rooms", old_room, "status", "Vacant")
			frappe.db.set_value("Rooms", new_room, "status", "Occupied")

	frappe.db.commit()
	frappe.publish_realtime(
		"doc_update",
		{"doctype": "Room Reservation", "name": reservation},
		doctype="Room Reservation",
		docname=reservation,
	)
	return True


@frappe.whitelist()
def quick_checkin(reservation):
	"""Quick check-in from the dashboard without opening the form."""
	res = frappe.get_doc("Room Reservation", reservation)
	if res.status != "Booked":
		return {"error": "Cannot check in: status is {}".format(res.status)}
	frappe.db.set_value("Room Reservation", reservation, "status", "Checked In")
	items = frappe.get_all("Room Reservation Item",
		filters={"parent": reservation}, fields=["room"])
	for item in items:
		if item.room:
			frappe.db.set_value("Rooms", item.room, "status", "Occupied")
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
def quick_checkout(reservation):
	"""Quick checkout from the dashboard without opening the form."""
	res = frappe.get_doc("Room Reservation", reservation)
	if res.status != "Checked In":
		return {"error": "Cannot check out: status is {}".format(res.status)}
	frappe.db.set_value("Room Reservation", reservation, "status", "Checked Out")
	items = frappe.get_all("Room Reservation Item",
		filters={"parent": reservation}, fields=["room"])
	for item in items:
		if item.room:
			frappe.db.set_value("Rooms", item.room, {
				"status": "Vacant",
				"housekeeping_status": "Dirty",
			})
	frappe.db.commit()
	return {"ok": True}
