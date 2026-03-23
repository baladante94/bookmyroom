# Copyright (c) 2026, Balamurugan and contributors
# For license information, please see license.txt
"""
Scheduled background tasks for Book My Room.
Registered in hooks.py → scheduler_events.
"""

import frappe
from frappe import _
from frappe.utils import add_days, nowdate


def send_checkin_reminders():
	"""
	Daily task: send an email reminder to customers whose check-in is tomorrow.
	Runs once per day via the Frappe scheduler.
	"""
	tomorrow = add_days(nowdate(), 1)

	reservations = frappe.get_all(
		"Room Reservation",
		filters={
			"docstatus": 1,
			"status": "Booked",
			"check_in": ["between", [f"{tomorrow} 00:00:00", f"{tomorrow} 23:59:59"]],
		},
		fields=["name", "customer", "hotel", "check_in", "check_out", "total_nights", "grand_total"],
	)

	for res in reservations:
		_send_reminder_email(res)


def _send_reminder_email(res):
	"""Send a check-in reminder email for one reservation."""
	customer_email = frappe.db.get_value("Customer", res.customer, "email_id")
	if not customer_email:
		return

	subject = _("Reminder: Your stay at {0} starts tomorrow").format(res.hotel)
	message = _(
		"""
		<p>Dear {customer},</p>
		<p>This is a friendly reminder that your reservation <strong>{name}</strong>
		at <strong>{hotel}</strong> begins tomorrow.</p>
		<ul>
			<li><strong>Check-in:</strong> {check_in}</li>
			<li><strong>Check-out:</strong> {check_out}</li>
			<li><strong>Nights:</strong> {nights}</li>
			<li><strong>Grand Total:</strong> {total}</li>
		</ul>
		<p>We look forward to welcoming you!</p>
		"""
	).format(
		customer=res.customer,
		name=res.name,
		hotel=res.hotel,
		check_in=frappe.format_datetime(res.check_in),
		check_out=frappe.format_datetime(res.check_out),
		nights=res.total_nights,
		total=frappe.format_value(res.grand_total, {"fieldtype": "Currency"}),
	)

	frappe.sendmail(
		recipients=[customer_email],
		subject=subject,
		message=message,
		now=True,
	)


def auto_generate_housekeeping_tasks():
	"""
	Daily task: generate Daily Service housekeeping logs for all currently
	Occupied rooms that do not already have a Pending/In-Progress task today.
	"""
	today = nowdate()

	occupied_rooms = frappe.get_all(
		"Rooms",
		filters={"status": "Occupied"},
		fields=["name", "hotel"],
	)

	for room in occupied_rooms:
		# Skip if a task already exists for today
		existing = frappe.db.exists(
			"Housekeeping Log",
			{
				"room": room.name,
				"date": today,
				"status": ["in", ["Pending", "In Progress"]],
			},
		)
		if existing:
			continue

		log = frappe.new_doc("Housekeeping Log")
		log.room = room.name
		log.hotel = room.hotel
		log.date = today
		log.task_type = "Daily Service"
		log.status = "Pending"
		log.insert(ignore_permissions=True)

	if occupied_rooms:
		frappe.db.commit()
