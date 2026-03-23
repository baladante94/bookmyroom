// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

// Calendar view for Room: shows Room Reservation events
// Each bar represents a guest stay on a particular room.

frappe.views.calendar["Rooms"] = {
	field_map: {
		start: "start",
		end: "end",
		id: "name",
		title: "title",
		color: "color",
		allDay: "all_day",
	},
	gantt: false,
	get_events_method:
		"bookmyroom.book_my_room.doctype.rooms.rooms.get_room_calendar_events",
	doctype: "Room Reservation",
};
