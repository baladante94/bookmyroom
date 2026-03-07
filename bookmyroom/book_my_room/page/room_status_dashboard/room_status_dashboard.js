// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

frappe.pages["room-status-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Room Status Dashboard"),
		single_column: true,
	});

	// ── Toolbar: hotel filter ──────────────────────────────────────────────── //
	const hotel_field = page.add_field({
		fieldtype: "Link",
		options: "Hotel",
		fieldname: "hotel",
		label: __("Hotel"),
		change() {
			dashboard.hotel = this.get_value() || null;
			dashboard.refresh();
		},
	});

	// ── Toolbar: month navigation ──────────────────────────────────────────── //
	page.add_button(__("◀"), () => dashboard.prev_month(), { btn_class: "btn-default btn-sm" });

	const $month_label = $(`<span style="padding:0 8px;font-weight:600;line-height:30px"></span>`);
	page.menu_btn_group.before($month_label);

	page.add_button(__("▶"), () => dashboard.next_month(), { btn_class: "btn-default btn-sm" });
	page.add_button(__("Today"), () => dashboard.go_today(), { btn_class: "btn-default btn-sm" });
	page.add_button(__("⟳ Refresh"), () => dashboard.refresh(), { btn_class: "btn-default btn-sm" });

	// ── Main content area ──────────────────────────────────────────────────── //
	_inject_styles();
	const $main = $('<div class="bmr-dash"></div>').appendTo(page.main);

	// ── Dashboard controller ───────────────────────────────────────────────── //
	const dashboard = {
		hotel: null,
		current_month: moment(),

		async refresh() {
			$month_label.text(this.current_month.format("MMMM YYYY"));
			const from_date = this.current_month.clone().startOf("month").format("YYYY-MM-DD");
			const to_date = this.current_month.clone().endOf("month").format("YYYY-MM-DD");

			const [rooms_resp, cal_resp] = await Promise.all([
				frappe.call({
					method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.get_room_status_data",
					args: { hotel: this.hotel },
				}),
				frappe.call({
					method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.get_calendar_data",
					args: { hotel: this.hotel, from_date, to_date },
				}),
			]);

			this.render(rooms_resp.message || [], cal_resp.message || []);
		},

		render(rooms, cal_data) {
			$main.empty();
			_render_stats($main, rooms);
			_render_grid($main, rooms);
			_render_calendar($main, rooms, cal_data, this.current_month.clone());
		},

		prev_month() {
			this.current_month.subtract(1, "month");
			this.refresh();
		},
		next_month() {
			this.current_month.add(1, "month");
			this.refresh();
		},
		go_today() {
			this.current_month = moment();
			this.refresh();
		},
	};

	// ── Real-time updates ──────────────────────────────────────────────────── //
	const _rt_handler = (data) => {
		if (data.doctype === "Room" || data.doctype === "Room Reservation") {
			dashboard.refresh();
		}
	};
	frappe.realtime.on("doc_update", _rt_handler);

	// Auto-refresh every 60 s
	const _interval = setInterval(() => dashboard.refresh(), 60000);

	$(wrapper).on("remove", () => {
		frappe.realtime.off("doc_update", _rt_handler);
		clearInterval(_interval);
	});

	// ── Initial load ───────────────────────────────────────────────────────── //
	dashboard.refresh();
};

// ─────────────────────────────────────────────────────────────────────────────
// Renderers
// ─────────────────────────────────────────────────────────────────────────────

function _render_stats($el, rooms) {
	const counts = {
		Available: 0,
		Reserved: 0,
		"Checked In": 0,
		"Vacant": 0,
		"Out of Order": 0,
		Maintenance: 0,
	};
	rooms.forEach((r) => {
		if (r.reservation && r.reservation.status === "Booked") {
			counts["Reserved"]++;
		} else if (r.reservation && r.reservation.status === "Checked In") {
			counts["Checked In"]++;
		} else if (counts[r.status] !== undefined) {
			counts[r.status]++;
		}
	});

	$el.append(`
		<div class="bmr-stats">
			<div class="bmr-stat st-available">
				<div class="bmr-stat-count">${counts["Available"]}</div>
				<div class="bmr-stat-label">${__("Available")}</div>
			</div>
			<div class="bmr-stat st-reserved">
				<div class="bmr-stat-count">${counts["Reserved"]}</div>
				<div class="bmr-stat-label">${__("Reserved")}</div>
			</div>
			<div class="bmr-stat st-occupied">
				<div class="bmr-stat-count">${counts["Checked In"]}</div>
				<div class="bmr-stat-label">${__("Checked In")}</div>
			</div>
			<div class="bmr-stat st-vacant-dirty">
				<div class="bmr-stat-count">${counts["Vacant"]}</div>
				<div class="bmr-stat-label">${__("Vacant")}</div>
			</div>
			<div class="bmr-stat st-oor">
				<div class="bmr-stat-count">${counts["Out of Order"]}</div>
				<div class="bmr-stat-label">${__("Out of Order")}</div>
			</div>
			<div class="bmr-stat st-maintenance">
				<div class="bmr-stat-count">${counts["Maintenance"]}</div>
				<div class="bmr-stat-label">${__("Maintenance")}</div>
			</div>
			<div class="bmr-stat st-total">
				<div class="bmr-stat-count">${rooms.length}</div>
				<div class="bmr-stat-label">${__("Total Rooms")}</div>
			</div>
		</div>
	`);
}

function _status_class(room) {
	// Distinguish Booked (reserved, not yet checked in) from Checked In (occupied)
	if (room.reservation) {
		if (room.reservation.status === "Booked") return "st-reserved";
		if (room.reservation.status === "Checked In") return "st-occupied";
	}
	return (
		{
			Available: "st-available",
			Occupied: "st-occupied",
			"Vacant": "st-vacant-dirty",
			"Out of Order": "st-oor",
			Maintenance: "st-maintenance",
		}[room.status] || "st-default"
	);
}

function _render_grid($el, rooms) {
	const $wrap = $('<div></div>');
	$wrap.append('<div class="bmr-section-label">Room Status Grid</div>');
	const $grid = $('<div class="bmr-grid"></div>');

	rooms.forEach((room) => {
		const cls = _status_class(room);
		const res = room.reservation;
		const hk = room.housekeeping_status ? `<div class="bmr-card-hk">${frappe.utils.escape_html(room.housekeeping_status)}</div>` : "";
		const guest = res ? `<div class="bmr-card-guest">${frappe.utils.escape_html(res.customer)}</div>` : "";

		const $card = $(`
			<div class="bmr-card ${cls}" title="${frappe.utils.escape_html(room.status)}">
				<div class="bmr-card-num">${frappe.utils.escape_html(room.room_name)}</div>
				<div class="bmr-card-type">${frappe.utils.escape_html(room.room_type || "")}</div>
				<div class="bmr-card-floor">Floor ${room.floor || "—"}</div>
				<div class="bmr-card-status">${frappe.utils.escape_html(room.status)}</div>
				${hk}
				${guest}
			</div>
		`);

		$card.on("click", () => frappe.set_route("Form", "Room", room.name));
		$grid.append($card);
	});

	$wrap.append($grid);
	$el.append($wrap);
}

function _render_calendar($el, rooms, cal_data, m) {
	const days_in_month = m.daysInMonth();
	const month_label = m.format("MMMM YYYY");
	const today_str = frappe.datetime.get_today();

	// Build room → reservations map
	const res_by_room = {};
	cal_data.forEach((r) => {
		if (!res_by_room[r.room]) res_by_room[r.room] = [];
		res_by_room[r.room].push(r);
	});

	// Header row
	let header = `<th class="cal-room-col">Room</th>`;
	for (let d = 1; d <= days_in_month; d++) {
		const date = m.clone().date(d).format("YYYY-MM-DD");
		const is_today = date === today_str;
		const dow = m.clone().date(d).format("dd")[0];
		header += `<th class="${is_today ? "cal-today" : ""}">${d}<br><small>${dow}</small></th>`;
	}

	// Data rows
	let rows = "";
	rooms.forEach((room) => {
		let cells = `<td class="cal-room-name">${frappe.utils.escape_html(room.room_name)}</td>`;
		const reservations = res_by_room[room.name] || [];

		for (let d = 1; d <= days_in_month; d++) {
			const date = m.clone().date(d).format("YYYY-MM-DD");
			const res = reservations.find((r) => {
				return r.check_in.split(" ")[0] <= date && r.check_out.split(" ")[0] >= date;
			});

			let td_cls = "";
			let td_title = "";
			let td_content = "";

			if (res) {
				td_cls = res.status === "Checked In" ? "cal-occupied" : "cal-booked";
				td_title = `${res.customer} · ${res.reservation}`;
				if (res.check_in.split(" ")[0] === date) {
					const initials = (res.customer || "")
						.split(" ")
						.map((p) => p[0])
						.join("")
						.toUpperCase()
						.slice(0, 2);
					td_content = `<span>${initials}</span>`;
				}
			} else if (room.status === "Out of Order") {
				td_cls = "cal-oor";
			} else if (room.status === "Maintenance") {
				td_cls = "cal-maint";
			} else if (room.status === "Vacant") {
				td_cls = "cal-vacant-dirty";
			}

			cells += `<td class="${td_cls}" title="${frappe.utils.escape_html(td_title)}">${td_content}</td>`;
		}

		rows += `<tr>${cells}</tr>`;
	});

	const legend = `
		<div class="bmr-cal-legend">
			<span class="bmr-legend-dot" style="background:#4caf50"></span>${__("Available")} &nbsp;
			<span class="bmr-legend-dot" style="background:#2196F3"></span>${__("Booked / Reserved")} &nbsp;
			<span class="bmr-legend-dot" style="background:#f44336"></span>${__("Checked In")} &nbsp;
			<span class="bmr-legend-dot" style="background:#ff9800"></span>${__("Vacant (Dirty)")} &nbsp;
			<span class="bmr-legend-dot" style="background:#9e9e9e"></span>${__("Out of Order")}
		</div>`;

	$el.append(`
		<div style="margin-top:20px">
			<div class="bmr-section-label">Booking Calendar — ${month_label}</div>
			<div class="bmr-cal-scroll">
				<table class="bmr-cal-table">
					<thead><tr>${header}</tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
			${legend}
		</div>
	`);
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────

function _inject_styles() {
	if (document.getElementById("bmr-dash-css")) return;
	const style = document.createElement("style");
	style.id = "bmr-dash-css";
	style.textContent = `
		.bmr-dash { padding: 16px; }

		/* Stats strip */
		.bmr-stats { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }
		.bmr-stat { border-radius:8px; padding:14px 22px; text-align:center;
			min-width:110px; color:#fff; cursor:default; }
		.bmr-stat-count { font-size:30px; font-weight:700; line-height:1.1; }
		.bmr-stat-label { font-size:11px; text-transform:uppercase; opacity:.9; margin-top:2px; }
		.st-available  { background:#4caf50; }
		.st-reserved   { background:#2196F3; }
		.st-occupied   { background:#f44336; }
		.st-vacant-dirty { background:#ff9800; }
		.st-oor        { background:#9e9e9e; }
		.st-maintenance{ background:#9c27b0; }
		.st-total      { background:#607d8b; }
		.st-default    { background:#78909c; }

		/* Section label */
		.bmr-section-label { font-size:12px; font-weight:700; color:var(--text-muted);
			text-transform:uppercase; letter-spacing:.8px; margin:16px 0 8px; }

		/* Room grid */
		.bmr-grid { display:grid;
			grid-template-columns:repeat(auto-fill, minmax(130px,1fr));
			gap:10px; margin-bottom:4px; }
		.bmr-card { border-radius:8px; padding:10px 12px; color:#fff; cursor:pointer;
			transition:transform .12s, box-shadow .12s; }
		.bmr-card:hover { transform:translateY(-2px); box-shadow:0 4px 14px rgba(0,0,0,.22); }
		.bmr-card-num  { font-size:18px; font-weight:700; }
		.bmr-card-type { font-size:11px; opacity:.85; margin-top:1px; }
		.bmr-card-floor{ font-size:10px; opacity:.7; }
		.bmr-card-status { display:inline-block; font-size:10px; font-weight:600; margin-top:5px;
			background:rgba(0,0,0,.18); border-radius:4px; padding:2px 6px; }
		.bmr-card-hk   { font-size:10px; opacity:.8; margin-top:2px; }
		.bmr-card-guest{ font-size:11px; font-style:italic; margin-top:3px; }

		/* Calendar */
		.bmr-cal-scroll { overflow-x:auto; }
		.bmr-cal-table { border-collapse:collapse; font-size:11px; }
		.bmr-cal-table th, .bmr-cal-table td {
			border:1px solid var(--border-color); padding:3px 4px;
			text-align:center; min-width:26px; }
		.bmr-cal-table .cal-room-col { min-width:70px; }
		.bmr-cal-table .cal-room-name { font-weight:600; white-space:nowrap;
			padding:3px 8px; text-align:left; }
		.bmr-cal-table .cal-today { background:var(--yellow-tint,#fffde7); font-weight:700; }
		.bmr-cal-table td.cal-booked      { background:#2196F3; color:#fff; font-weight:600; }
		.bmr-cal-table td.cal-occupied    { background:#f44336; color:#fff; font-weight:600; }
		.bmr-cal-table td.cal-vacant-dirty{ background:#ff9800; }
		.bmr-cal-table td.cal-oor         { background:#e0e0e0; }
		.bmr-cal-table td.cal-maint       { background:#e1bee7; }

		.bmr-cal-legend { display:flex; gap:14px; flex-wrap:wrap;
			margin-top:8px; font-size:12px; color:var(--text-muted); align-items:center; }
		.bmr-legend-dot { display:inline-block; width:10px; height:10px;
			border-radius:2px; vertical-align:middle; margin-right:3px; }
	`;
	document.head.appendChild(style);
}
