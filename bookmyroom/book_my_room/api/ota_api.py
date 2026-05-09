# Copyright (c) 2026, Balamurugan and contributors
# OTA Integration API — public endpoints called by the mock Booking.com / OTA demo page

import frappe
from frappe.utils import flt


@frappe.whitelist(allow_guest=True)
def get_hotels():
	"""Return all hotels available for OTA booking."""
	return frappe.get_all(
		"Hotel",
		fields=[
			"name", "hotel_name", "hotel_code", "city", "country",
			"star_rating", "checkin_time", "checkout_time",
			"description", "phone", "email", "address",
		],
		order_by="hotel_name asc",
		ignore_permissions=True,
	)


@frappe.whitelist(allow_guest=True)
def search_rooms_ota(hotel, check_in, check_out, num_adults=1, num_children=0):
	"""
	Return available rooms with rates for the given hotel and dates.
	Called by the OTA booking page search.
	"""
	from bookmyroom.book_my_room.doctype.room_reservation.room_reservation import (
		get_available_rooms,
		get_applicable_rate,
	)

	rooms = get_available_rooms(hotel, check_in, check_out)
	if not rooms:
		return []

	# Enrich with room type details and applicable rates
	rt_cache = {}
	results = []

	for room in rooms:
		rt = room.room_type
		if rt not in rt_cache:
			rt_cache[rt] = frappe.db.get_value(
				"Room Type", rt,
				["name", "default_rate", "bed_type", "max_adults", "max_children", "description"],
				as_dict=True,
			) or {}

		rt_data = rt_cache[rt]

		# Rate Plan rate takes priority; fall back to Room Type default_rate
		rate = get_applicable_rate(rt, hotel, check_in) or flt(rt_data.get("default_rate") or 0)

		# Check guest capacity
		max_adults = int(rt_data.get("max_adults") or room.get("capacity") or 2)
		if int(num_adults) > max_adults:
			continue  # Skip rooms that can't fit the party

		results.append({
			"room": room.name,
			"room_type": rt,
			"floor": room.floor,
			"capacity": room.capacity,
			"bed_type": room.get("bed_type") or rt_data.get("bed_type") or "Standard",
			"view_type": room.get("view_type") or "",
			"smoking": room.get("smoking") or 0,
			"rate": flt(rate),
			"description": rt_data.get("description") or "",
			"max_adults": max_adults,
			"max_children": int(rt_data.get("max_children") or 0),
		})

	return results


@frappe.whitelist(allow_guest=True)
def create_ota_booking(
	hotel, check_in, check_out, room, room_type, rate,
	guest_name, guest_email, guest_phone=None,
	num_adults=1, num_children=0,
	source="Booking.com", special_requests=None,
):
	"""
	Create a Room Reservation from an OTA booking.
	Auto-creates a Customer record if the email is not already registered.
	Returns reservation ID and totals.
	"""
	frappe.flags.in_test = True  # suppress some UI-only popups

	customer = _get_or_create_customer(guest_name, guest_email, guest_phone)
	company = _get_default_company()

	res = frappe.new_doc("Room Reservation")
	res.customer = customer
	res.company = company
	res.hotel = hotel
	res.check_in = check_in
	res.check_out = check_out
	res.num_adults = int(num_adults or 1)
	res.num_children = int(num_children or 0)
	res.booking_source = "OTA"
	res.notes = "OTA Channel: " + source
	res.special_requests = special_requests or ""

	res.append("items", {
		"room": room,
		"room_type": room_type,
		"rate": flt(rate),
	})

	# Mark as OTA booking so backdated-check is skipped
	res.flags.from_ota = True
	res.insert(ignore_permissions=True)
	frappe.db.commit()

	# Notify ERPNext users watching the reservation list in real-time
	frappe.publish_realtime(
		"ota_booking_received",
		{
			"reservation": res.name,
			"source": source,
			"guest": guest_name,
			"hotel": hotel,
			"check_in": check_in,
			"check_out": check_out,
			"grand_total": flt(res.grand_total),
		},
	)

	return {
		"reservation_id": res.name,
		"status": "confirmed",
		"ota_channel": source,
		"grand_total": flt(res.grand_total),
		"balance_due": flt(res.balance_due),
		"tax_amount": flt(res.tax_amount),
		"total_nights": res.total_nights,
	}


# ------------------------------------------------------------------ #
# Internal helpers
# ------------------------------------------------------------------ #

def _get_or_create_customer(guest_name, guest_email, guest_phone=None):
	"""Find existing Customer by email or create a new Individual customer."""
	if guest_email:
		existing = frappe.db.get_value("Customer", {"email_id": guest_email}, "name")
		if existing:
			return existing

	customer = frappe.new_doc("Customer")
	customer.customer_name = guest_name
	customer.customer_type = "Individual"
	customer.customer_group = (
		frappe.db.get_single_value("Selling Settings", "customer_group")
		or frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		or "All Customer Groups"
	)
	customer.territory = (
		frappe.db.get_single_value("Selling Settings", "territory")
		or frappe.db.get_value("Territory", {"is_group": 0}, "name")
		or "All Territories"
	)
	if guest_email:
		customer.email_id = guest_email
	if guest_phone:
		customer.mobile_no = guest_phone

	customer.insert(ignore_permissions=True)
	return customer.name


def _get_default_company():
	"""Return the default company from system defaults or first company."""
	company = frappe.defaults.get_defaults().get("company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name")
	return company
