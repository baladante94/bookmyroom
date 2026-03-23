// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

// ─────────────────────────────────────────────────────────────────────────────
// List view: color indicators per room status
// ─────────────────────────────────────────────────────────────────────────────

frappe.listview_settings["Rooms"] = {
	get_indicator: function (doc) {
		const map = {
			Available: "green",
			Occupied: "red",
			"Vacant": "orange",
			"Out of Order": "grey",
			Maintenance: "purple",
		};
		return [__(doc.status), map[doc.status] || "grey", "status,=," + doc.status];
	},
};

// ─────────────────────────────────────────────────────────────────────────────
// Form view: booking calendar section
// ─────────────────────────────────────────────────────────────────────────────

frappe.ui.form.on("Rooms", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("View Reservations"), () => {
				frappe.set_route("List", "Room Reservation", {
					items: frm.doc.name,
				});
			});

			_render_booking_calendar(frm);
		}
	},
});

/**
 * Fetch upcoming reservations for this room and render a compact
 * 30-day availability strip appended to the form body.
 */
function _render_booking_calendar(frm) {
	const today = frappe.datetime.get_today();
	const to_date = frappe.datetime.add_days(today, 29);

	// Use a dedicated Python method to avoid client-side filter complexity
	frappe.call({
		method: "bookmyroom.book_my_room.doctype.rooms.rooms.get_room_reservations",
		args: {
			room: frm.doc.name,
			from_date: today,
			to_date: to_date,
		},
		callback({ message: reservations }) {
			_draw_calendar_strip(frm, today, reservations || []);
		},
	});
}

function _draw_calendar_strip(frm, today, reservations) {
	// Remove any previously rendered strip to avoid duplicates on re-refresh
	frm.$wrapper.find(".bmr-room-cal-wrap").remove();

	const days = 30;
	let header_cells = "";
	let body_cells = "";

	for (let i = 0; i < days; i++) {
		const date = frappe.datetime.add_days(today, i);
		const d = moment(date);
		const isToday = i === 0;
		const dow = d.format("ddd").slice(0, 1);
		const dom = d.date();

		const res = reservations.find(
			(r) => r.check_in.split(" ")[0] <= date && r.check_out.split(" ")[0] > date
		);

		header_cells += `<th class="${isToday ? "bmr-cal-today" : ""}" title="${date}">${dom}<br><small>${dow}</small></th>`;

		let td_cls = "";
		let td_title = "";
		let td_content = "";
		if (res) {
			td_cls = res.status === "Checked In" ? "bmr-cal-occupied" : "bmr-cal-booked";
			td_title = `${res.customer} · ${res.name}`;
			if (res.check_in.split(" ")[0] === date) {
				const initials = (res.customer || "")
					.split(" ")
					.map((p) => p[0])
					.join("")
					.toUpperCase()
					.slice(0, 2);
				td_content = `<span>${initials}</span>`;
			}
		}
		body_cells += `<td class="${td_cls}" title="${frappe.utils.escape_html(td_title)}">${td_content}</td>`;
	}

	const legend = `
		<div class="bmr-cal-legend">
			<span class="bmr-cal-dot bmr-cal-booked-dot"></span>${__("Booked")} &nbsp;
			<span class="bmr-cal-dot bmr-cal-occupied-dot"></span>${__("Checked In")} &nbsp;
			<span class="bmr-cal-dot bmr-cal-free-dot"></span>${__("Available")}
		</div>`;

	const $cal = $(`
		<div class="bmr-room-cal-wrap">
			<div class="bmr-cal-title">${__("30-Day Availability")}</div>
			<div class="bmr-cal-scroll">
				<table class="bmr-room-cal">
					<thead><tr><th class="bmr-cal-room-col">${__("Room")}</th>${header_cells}</tr></thead>
					<tbody><tr>
						<td class="bmr-cal-room-name">${frappe.utils.escape_html(frm.doc.room_name)}</td>
						${body_cells}
					</tr></tbody>
				</table>
			</div>
			${legend}
		</div>`);

	// Append below all form fields — frm.fields_dict.notes.$wrapper is the
	// Notes field's own container; we insert the calendar after it.
	const $notes = frm.fields_dict.notes && frm.fields_dict.notes.$wrapper;
	if ($notes && $notes.length) {
		$cal.insertAfter($notes);
	} else {
		$cal.appendTo(frm.body || frm.$wrapper.find(".page-form"));
	}

	_inject_cal_styles();
}

function _inject_cal_styles() {
	if (document.getElementById("bmr-room-cal-css")) return;
	const style = document.createElement("style");
	style.id = "bmr-room-cal-css";
	style.textContent = `
		.bmr-room-cal-wrap { margin: 16px 15px; }
		.bmr-cal-title { font-size:12px; font-weight:700; color:var(--text-muted);
			text-transform:uppercase; letter-spacing:1px; margin-bottom:6px; }
		.bmr-cal-scroll { overflow-x:auto; }
		.bmr-room-cal { border-collapse:collapse; font-size:12px; }
		.bmr-room-cal th, .bmr-room-cal td { border:1px solid var(--border-color);
			padding:3px 4px; text-align:center; min-width:28px; }
		.bmr-room-cal .bmr-cal-room-col { min-width:70px; }
		.bmr-room-cal .bmr-cal-room-name { font-weight:600; white-space:nowrap;
			padding:3px 10px; text-align:left; }
		.bmr-room-cal .bmr-cal-today { background:#fffde7; font-weight:700; }
		.bmr-room-cal td.bmr-cal-booked   { background:#2196F3; color:#fff; }
		.bmr-room-cal td.bmr-cal-occupied { background:#f44336; color:#fff; }
		.bmr-cal-legend { margin-top:6px; font-size:12px; color:var(--text-muted); display:flex; gap:12px; }
		.bmr-cal-dot { display:inline-block; width:10px; height:10px;
			border-radius:2px; vertical-align:middle; margin-right:3px; }
		.bmr-cal-dot.bmr-cal-booked-dot   { background:#2196F3; }
		.bmr-cal-dot.bmr-cal-occupied-dot { background:#f44336; }
		.bmr-cal-dot.bmr-cal-free-dot     { background:var(--border-color); }
	`;
	document.head.appendChild(style);
}
