import json
import frappe


NEW_CONTENT = [
	{"id": "j75L4AgQME", "type": "shortcut", "data": {"shortcut_name": "Room Reservation", "col": 2}},
	{"id": "kzAfoTwGyg", "type": "shortcut", "data": {"shortcut_name": "Rooms", "col": 2}},
	{"id": "7pxXXnOe2T", "type": "shortcut", "data": {"shortcut_name": "Housekeeping", "col": 2}},
	{"id": "DKNt3iyhOl", "type": "shortcut", "data": {"shortcut_name": "Guest Folio", "col": 2}},
	{"id": "Pl9WChBP4i", "type": "shortcut", "data": {"shortcut_name": "Hotels", "col": 2}},
	{"id": "nuorP7C6W4", "type": "shortcut", "data": {"shortcut_name": "Rate Plans", "col": 2}},
	{"id": "IJY5brB7mM", "type": "spacer", "data": {"col": 12}},
	{"id": "RSzqVniZwW", "type": "number_card", "data": {"number_card_name": "BMR Check-ins Today", "col": 4}},
	{"id": "hKgtzCVH1S", "type": "number_card", "data": {"number_card_name": "BMR Guests Checked In", "col": 4}},
	{"id": "dEFyw5N3DH", "type": "number_card", "data": {"number_card_name": "BMR Available Rooms", "col": 4}},
	{"id": "8BeXeSlw1n", "type": "number_card", "data": {"number_card_name": "BMR Check-outs Today", "col": 4}},
	{"id": "UCUCG38gFI", "type": "number_card", "data": {"number_card_name": "BMR Revenue This Month", "col": 4}},
	{"id": "jey7xEWmH7", "type": "spacer", "data": {"col": 12}},
	{"id": "82eSg5N8Q1", "type": "chart", "data": {"chart_name": "BMR Reservations by Month", "col": 12}},
	{"id": "LVp6YJu3tC", "type": "chart", "data": {"chart_name": "BMR Revenue by Month", "col": 6}},
	{"id": "q3QFjuBFe2", "type": "chart", "data": {"chart_name": "BMR Reservations by Status", "col": 6}},
	{"id": "PLAAZ1gQty", "type": "chart", "data": {"chart_name": "BMR Bookings by Source", "col": 6}},
	{"id": "TbtQzCh54W", "type": "spacer", "data": {"col": 12}},
]


def execute():
	frappe.db.set_value("Workspace", "Book My Room", "content", json.dumps(NEW_CONTENT))
	frappe.db.commit()
	print("  [ok]  Workspace content updated.")
