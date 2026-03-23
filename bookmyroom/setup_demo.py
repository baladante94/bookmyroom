"""
Demo master data setup for BookMyRoom.
Run with:  bench --site bookmyroom.localhost execute setup_demo.create_all
"""

import frappe
from frappe.utils import add_days, today


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

COMPANY = "Prosper Zen"


def _insert(doc_dict):
	"""Insert a document only if it doesn't already exist (idempotent)."""
	doctype = doc_dict["doctype"]
	name_field = doc_dict.get("name") or doc_dict.get(frappe.get_meta(doctype).autoname.replace("field:", ""), "")
	# For field-autonamed docs, the name IS the field value
	meta = frappe.get_meta(doctype)
	if meta.autoname and meta.autoname.startswith("field:"):
		key_field = meta.autoname.replace("field:", "")
		name_val = doc_dict.get(key_field, "")
	else:
		name_val = doc_dict.get("name", "")

	if name_val and frappe.db.exists(doctype, name_val):
		print(f"  [skip] {doctype}: {name_val} already exists")
		return frappe.get_doc(doctype, name_val)

	doc = frappe.get_doc(doc_dict)
	doc.insert(ignore_permissions=True)
	print(f"  [ok]   {doctype}: {doc.name}")
	return doc


# ─────────────────────────────────────────────────────────────────────────────
# 1. UOM
# ─────────────────────────────────────────────────────────────────────────────

def create_uom():
	print("\n── UOM ──")
	if not frappe.db.exists("UOM", "Night"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Night"}).insert(ignore_permissions=True)
		print("  [ok]   UOM: Night")
	else:
		print("  [skip] UOM: Night already exists")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Billing Items (ERPNext Items for Room Types)
# ─────────────────────────────────────────────────────────────────────────────

BILLING_ITEMS = [
	("Standard Room Night", "Standard room accommodation per night"),
	("Deluxe Room Night", "Deluxe room accommodation per night"),
	("Executive Room Night", "Executive room accommodation per night"),
	("Suite Night", "Suite accommodation per night"),
	("Twin Room Night", "Twin room accommodation per night"),
]


def create_billing_items():
	print("\n── Billing Items ──")
	created = {}
	for item_code, desc in BILLING_ITEMS:
		if not frappe.db.exists("Item", item_code):
			item = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"description": desc,
					"item_group": "Services",
					"stock_uom": "Night",
					"is_stock_item": 0,
					"is_sales_item": 1,
					"is_purchase_item": 0,
					"include_item_in_manufacturing": 0,
				}
			)
			item.insert(ignore_permissions=True)
			print(f"  [ok]   Item: {item_code}")
		else:
			print(f"  [skip] Item: {item_code} already exists")
		created[item_code] = item_code
	return created


# ─────────────────────────────────────────────────────────────────────────────
# 3. Hotel Amenities
# ─────────────────────────────────────────────────────────────────────────────

AMENITIES = [
	("Free WiFi",           "In-Room",   "wifi"),
	("Air Conditioning",    "In-Room",   "ac"),
	("Flat Screen TV",      "In-Room",   "tv"),
	("Mini Bar",            "In-Room",   "shopping-cart"),
	("In-Room Safe",        "In-Room",   "lock"),
	("Hair Dryer",          "In-Room",   "settings"),
	("Swimming Pool",       "Property",  "swimming"),
	("Fitness Centre",      "Property",  "exercise"),
	("Free Parking",        "Property",  "car"),
	("24Hr Room Service",   "Services",  "time"),
	("Airport Transfer",    "Services",  "truck"),
	("Spa & Wellness",      "Services",  "heart"),
	("The Residency Restaurant", "Dining", "food"),
	("Rooftop Bar",         "Dining",    "glass"),
]


def create_amenities():
	print("\n── Hotel Amenities ──")
	for name, category, icon in AMENITIES:
		_insert(
			{
				"doctype": "Hotel Amenity",
				"amenity_name": name,
				"category": category,
				"icon": icon,
			}
		)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Meal Plans
# ─────────────────────────────────────────────────────────────────────────────

MEAL_PLANS = [
	{
		"plan_name": "Room Only (EP)",
		"description": "European Plan — accommodation only, no meals included.",
		"breakfast_included": 0,
		"lunch_included": 0,
		"dinner_included": 0,
		"extra_rate_per_person": 0,
	},
	{
		"plan_name": "Breakfast Included (CP)",
		"description": "Continental Plan — room + daily breakfast.",
		"breakfast_included": 1,
		"lunch_included": 0,
		"dinner_included": 0,
		"extra_rate_per_person": 400,
	},
	{
		"plan_name": "Half Board (MAP)",
		"description": "Modified American Plan — room + breakfast + dinner.",
		"breakfast_included": 1,
		"lunch_included": 0,
		"dinner_included": 1,
		"extra_rate_per_person": 800,
	},
	{
		"plan_name": "Full Board (AP)",
		"description": "American Plan — room + all three meals daily.",
		"breakfast_included": 1,
		"lunch_included": 1,
		"dinner_included": 1,
		"extra_rate_per_person": 1200,
	},
]


def create_meal_plans():
	print("\n── Meal Plans ──")
	for mp in MEAL_PLANS:
		_insert({"doctype": "Meal Plan", **mp})


# ─────────────────────────────────────────────────────────────────────────────
# 5. Room Types
# ─────────────────────────────────────────────────────────────────────────────

ROOM_TYPES = [
	{
		"room_type_name": "Standard Room",
		"billing_item": "Standard Room Night",
		"default_rate": 2500,
		"bed_type": "Double",
		"max_adults": 2,
		"max_children": 1,
		"description": "<p>Comfortable standard room with all essential amenities. Ideal for solo travellers and couples.</p>",
	},
	{
		"room_type_name": "Deluxe Room",
		"billing_item": "Deluxe Room Night",
		"default_rate": 4000,
		"bed_type": "Queen",
		"max_adults": 2,
		"max_children": 1,
		"description": "<p>Spacious deluxe room featuring premium furnishings, city views, and enhanced amenities.</p>",
	},
	{
		"room_type_name": "Twin Room",
		"billing_item": "Twin Room Night",
		"default_rate": 3000,
		"bed_type": "Twin",
		"max_adults": 2,
		"max_children": 0,
		"description": "<p>Comfortable twin room with two single beds. Perfect for friends or colleagues travelling together.</p>",
	},
	{
		"room_type_name": "Executive Room",
		"billing_item": "Executive Room Night",
		"default_rate": 6000,
		"bed_type": "King",
		"max_adults": 2,
		"max_children": 1,
		"description": "<p>Executive room with access to the Executive Lounge. Includes complimentary breakfast and evening cocktails.</p>",
	},
	{
		"room_type_name": "Suite",
		"billing_item": "Suite Night",
		"default_rate": 10000,
		"bed_type": "King",
		"max_adults": 3,
		"max_children": 2,
		"description": "<p>Luxurious suite with a separate living area, panoramic views, and personalised butler service.</p>",
	},
]


def create_room_types():
	print("\n── Room Types ──")
	for rt in ROOM_TYPES:
		_insert({"doctype": "Room Type", **rt})


# ─────────────────────────────────────────────────────────────────────────────
# 6. Hotels
# ─────────────────────────────────────────────────────────────────────────────

HOTELS = [
	{
		"hotel_name": "Residency Hotel",
		"star_rating": 4,
		"website": "https://www.residencyhotel.com",
		"checkin_time": "14:00:00",
		"checkout_time": "12:00:00",
		"tax_rate": 12,
		"address": "49, GN Chetty Road, T. Nagar",
		"city": "Chennai",
		"phone": "+91-44-28155000",
		"email": "reservations@residencyhotel.com",
		"cancellation_policy": (
			"Free cancellation up to 48 hours before check-in. "
			"Cancellations within 48 hours will be charged one night's room rate. "
			"No-shows will be charged the full reservation amount."
		),
		"description": (
			"<p>The Residency Hotel Chennai is a landmark business hotel in the heart of T. Nagar. "
			"With 112 elegantly designed rooms, award-winning dining, and state-of-the-art conference facilities, "
			"it is the preferred choice for business and leisure travellers alike.</p>"
		),
	},
	{
		"hotel_name": "Residency Tower 2",
		"star_rating": 5,
		"website": "https://www.residencytower.com",
		"checkin_time": "15:00:00",
		"checkout_time": "11:00:00",
		"tax_rate": 18,
		"address": "115, Sir Thyagaraya Road, T. Nagar",
		"city": "Chennai",
		"phone": "+91-44-28150000",
		"email": "reservations@residencytower.com",
		"cancellation_policy": (
			"Free cancellation up to 72 hours before check-in. "
			"Cancellations within 72 hours will be charged two nights' room rate. "
			"No-shows will be charged the full reservation amount."
		),
		"description": (
			"<p>Residency Tower 2 is our flagship five-star property offering unrivalled luxury in Chennai's most "
			"vibrant neighbourhood. The hotel features panoramic rooftop views, a full-service spa, infinity pool, "
			"and Michelin-inspired dining experiences.</p>"
		),
	},
]


def create_hotels():
	print("\n── Hotels ──")
	for h in HOTELS:
		_insert({"doctype": "Hotel", **h})


# ─────────────────────────────────────────────────────────────────────────────
# 7. Rooms
# ─────────────────────────────────────────────────────────────────────────────

ROOMS_RESIDENCY = [
	# Floor 1 — Standard
	{"room_name": "101", "room_type": "Standard Room", "floor": 1, "capacity": 2, "view_type": "Courtyard View", "smoking": 0},
	{"room_name": "102", "room_type": "Standard Room", "floor": 1, "capacity": 2, "view_type": "Courtyard View", "smoking": 0},
	{"room_name": "103", "room_type": "Twin Room",     "floor": 1, "capacity": 2, "view_type": "Courtyard View", "smoking": 0},
	# Floor 2 — Deluxe
	{"room_name": "201", "room_type": "Deluxe Room",   "floor": 2, "capacity": 2, "view_type": "City View",      "smoking": 0},
	{"room_name": "202", "room_type": "Deluxe Room",   "floor": 2, "capacity": 2, "view_type": "City View",      "smoking": 0},
	{"room_name": "203", "room_type": "Twin Room",     "floor": 2, "capacity": 2, "view_type": "City View",      "smoking": 0},
	# Floor 3 — Executive
	{"room_name": "301", "room_type": "Executive Room","floor": 3, "capacity": 2, "view_type": "City View",      "smoking": 0},
	{"room_name": "302", "room_type": "Executive Room","floor": 3, "capacity": 2, "view_type": "City View",      "smoking": 0},
	# Floor 4 — Suites
	{"room_name": "401", "room_type": "Suite",         "floor": 4, "capacity": 3, "view_type": "City View",      "smoking": 0},
	{"room_name": "402", "room_type": "Suite",         "floor": 4, "capacity": 3, "view_type": "City View",      "smoking": 0},
]

ROOMS_TOWER2 = [
	# Floor 1 — Standard
	{"room_name": "T2-101", "room_type": "Standard Room",  "floor": 1, "capacity": 2, "view_type": "Garden View",  "smoking": 0},
	{"room_name": "T2-102", "room_type": "Standard Room",  "floor": 1, "capacity": 2, "view_type": "Garden View",  "smoking": 0},
	# Floor 2 — Deluxe
	{"room_name": "T2-201", "room_type": "Deluxe Room",    "floor": 2, "capacity": 2, "view_type": "Pool View",    "smoking": 0},
	{"room_name": "T2-202", "room_type": "Deluxe Room",    "floor": 2, "capacity": 2, "view_type": "Pool View",    "smoking": 0},
	{"room_name": "T2-203", "room_type": "Twin Room",      "floor": 2, "capacity": 2, "view_type": "Pool View",    "smoking": 0},
	# Floor 3 — Executive
	{"room_name": "T2-301", "room_type": "Executive Room", "floor": 3, "capacity": 2, "view_type": "Sea View",     "smoking": 0},
	{"room_name": "T2-302", "room_type": "Executive Room", "floor": 3, "capacity": 2, "view_type": "Sea View",     "smoking": 0},
	# Floor 4 & 5 — Suites
	{"room_name": "T2-401", "room_type": "Suite",          "floor": 4, "capacity": 4, "view_type": "Sea View",     "smoking": 0},
	{"room_name": "T2-501", "room_type": "Suite",          "floor": 5, "capacity": 4, "view_type": "Sea View",     "smoking": 0},
]

# Amenities to attach to every room
ROOM_AMENITIES_STANDARD  = ["Free WiFi", "Air Conditioning", "Flat Screen TV", "In-Room Safe"]
ROOM_AMENITIES_DELUXE    = ROOM_AMENITIES_STANDARD + ["Mini Bar", "Hair Dryer"]
ROOM_AMENITIES_EXECUTIVE = ROOM_AMENITIES_DELUXE
ROOM_AMENITIES_SUITE     = ROOM_AMENITIES_EXECUTIVE

ROOM_AMENITY_MAP = {
	"Standard Room":  ROOM_AMENITIES_STANDARD,
	"Twin Room":      ROOM_AMENITIES_STANDARD,
	"Deluxe Room":    ROOM_AMENITIES_DELUXE,
	"Executive Room": ROOM_AMENITIES_EXECUTIVE,
	"Suite":          ROOM_AMENITIES_SUITE,
}


def _room_amenity_rows(room_type):
	return [{"doctype": "Room Amenity", "amenity": a} for a in ROOM_AMENITY_MAP.get(room_type, [])]


def create_rooms():
	print("\n── Rooms: Residency Hotel ──")
	for r in ROOMS_RESIDENCY:
		_insert(
			{
				"doctype": "Rooms",
				"hotel": "Residency Hotel",
				"status": "Available",
				"housekeeping_status": "Clean",
				"bed_type": frappe.db.get_value("Room Type", r["room_type"], "bed_type") or "",
				"amenities": _room_amenity_rows(r["room_type"]),
				**r,
			}
		)

	print("\n── Rooms: Residency Tower 2 ──")
	for r in ROOMS_TOWER2:
		_insert(
			{
				"doctype": "Rooms",
				"hotel": "Residency Tower 2",
				"status": "Available",
				"housekeeping_status": "Clean",
				"bed_type": frappe.db.get_value("Room Type", r["room_type"], "bed_type") or "",
				"amenities": _room_amenity_rows(r["room_type"]),
				**r,
			}
		)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Hotel Services
# ─────────────────────────────────────────────────────────────────────────────

SERVICES = [
	{"service_name": "Room Service Delivery",  "service_type": "Room Service",    "rate": 150},
	{"service_name": "Express Laundry",        "service_type": "Laundry",         "rate": 250},
	{"service_name": "Standard Laundry",       "service_type": "Laundry",         "rate": 150},
	{"service_name": "Minibar Restock",        "service_type": "Minibar",         "rate": 600},
	{"service_name": "Spa - Full Body Massage","service_type": "Spa",             "rate": 2500},
	{"service_name": "Spa - Head Massage",     "service_type": "Spa",             "rate": 1200},
	{"service_name": "Airport Transfer (1-Way)","service_type": "Transportation", "rate": 1500},
	{"service_name": "Extra Bed",              "service_type": "Other",           "rate": 800},
	{"service_name": "Baby Cot",              "service_type": "Other",           "rate": 300},
	{"service_name": "Bottled Water (1L)",     "service_type": "Minibar",         "rate": 80},
]


def create_hotel_services():
	print("\n── Hotel Services ──")
	for svc in SERVICES:
		_insert({"doctype": "Hotel Service", "is_active": 1, **svc})


# ─────────────────────────────────────────────────────────────────────────────
# 9. Rate Plans (seasonal overrides)
# ─────────────────────────────────────────────────────────────────────────────

def create_rate_plans():
	print("\n── Rate Plans ──")
	plans = [
		# Residency Hotel
		{
			"rate_plan_name": "RH - Weekend Special (Standard)",
			"hotel": "Residency Hotel",
			"room_type": "Standard Room",
			"valid_from": "2026-03-07",
			"valid_to": "2026-06-30",
			"rate_per_night": 3200,
			"is_active": 1,
			"description": "Weekend and summer promotional rate for Standard rooms",
		},
		{
			"rate_plan_name": "RH - Peak Season (Suite)",
			"hotel": "Residency Hotel",
			"room_type": "Suite",
			"valid_from": "2026-04-01",
			"valid_to": "2026-06-30",
			"rate_per_night": 13000,
			"is_active": 1,
			"description": "Peak summer season rate for Suites",
		},
		# Tower 2
		{
			"rate_plan_name": "T2 - Early Bird (Deluxe)",
			"hotel": "Residency Tower 2",
			"room_type": "Deluxe Room",
			"valid_from": "2026-03-01",
			"valid_to": "2026-03-31",
			"rate_per_night": 3500,
			"is_active": 1,
			"description": "March early-bird discount on Deluxe rooms",
		},
		{
			"rate_plan_name": "T2 - Peak Season (Suite)",
			"hotel": "Residency Tower 2",
			"room_type": "Suite",
			"valid_from": "2026-04-01",
			"valid_to": "2026-06-30",
			"rate_per_night": 18000,
			"is_active": 1,
			"description": "Peak summer season rate for Tower 2 Suites",
		},
	]
	for p in plans:
		_insert({"doctype": "Rate Plan", **p})


# ─────────────────────────────────────────────────────────────────────────────
# 10. Test Customer
# ─────────────────────────────────────────────────────────────────────────────

def create_test_customer():
	print("\n── Test Customer ──")
	customers = [
		{"customer_name": "Arjun Mehta",   "email_id": "arjun.mehta@example.com",  "mobile_no": "9876543210"},
		{"customer_name": "Priya Sharma",   "email_id": "priya.sharma@example.com", "mobile_no": "9876543211"},
	]
	for c in customers:
		if not frappe.db.exists("Customer", c["customer_name"]):
			cust = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": c["customer_name"],
					"customer_type": "Individual",
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
					"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories",
					"email_id": c["email_id"],
					"mobile_no": c["mobile_no"],
				}
			)
			cust.insert(ignore_permissions=True)
			print(f"  [ok]   Customer: {c['customer_name']}")
		else:
			print(f"  [skip] Customer: {c['customer_name']} already exists")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def create_all():
	frappe.set_user("Administrator")
	print("\n========================================")
	print(" BookMyRoom — Demo Master Data Setup")
	print("========================================")

	create_uom()
	create_billing_items()
	create_amenities()
	create_meal_plans()
	create_room_types()
	create_hotels()
	create_rooms()
	create_hotel_services()
	create_rate_plans()
	create_test_customer()

	frappe.db.commit()
	print("\n========================================")
	print(" ✅  All demo masters created!")
	print("========================================\n")
