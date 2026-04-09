// Copyright (c) 2026, Balamurugan and contributors — Book My Room
// Front Desk Dashboard — premium redesign v5

// Module-level state objects (survive re-renders)
const _drag   = { active: false, room: null, startDay: 0, endDay: 0, hotel: null, calMonth: null };
const _move   = { active: false, resName: null, room: null, targetRoom: null };
const _resize = { active: false, resName: null, room: null, ciDay: 1, coDay: 1, newCoDay: null };
const _tipData = {}; // keyed by "roomName_day"
let _bmr_refresh = null; // set on page load for callbacks

frappe.pages["room-status-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Front Desk",
		single_column: true,
	});

	const hotelField = page.add_field({
		fieldtype: "Link",
		options: "Hotel",
		label: "Hotel",
		fieldname: "hotel",
		default: "",
		change() {
			if (_skipHotelChange) return;
			dash.hotel = hotelField.get_value() || null;
			dash.refresh();
		},
	});
	let _skipHotelChange = false;

	let calMonth = frappe.datetime.get_today().slice(0, 7);

	$(page.main).append(`
		<div id="bmr-cal-nav" class="bmr-cal-nav">
			<button class="bmr-nav-btn" id="bmr-prev">&#8592;</button>
			<span class="bmr-cal-label" id="bmr-cal-label"></span>
			<button class="bmr-nav-btn" id="bmr-next">&#8594;</button>
		</div>
		<div id="bmr-dash" class="bmr-dash"></div>
	`);

	const $root = $(page.main).find("#bmr-dash");

	$(page.main).on("click", "#bmr-prev", function () {
		const [y, m] = calMonth.split("-").map(Number);
		const d = new Date(y, m - 2, 1);
		calMonth = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
		dash.refresh();
	});
	$(page.main).on("click", "#bmr-next", function () {
		const [y, m] = calMonth.split("-").map(Number);
		const d = new Date(y, m, 1);
		calMonth = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
		dash.refresh();
	});

	const dash = {
		hotel: null,

		refresh() {
			_inject_styles();
			const [y, m] = calMonth.split("-").map(Number);
			const from = calMonth + "-01";
			const lastDay = new Date(y, m, 0).getDate();
			const to = calMonth + "-" + String(lastDay).padStart(2, "0");

			$(page.main).find("#bmr-cal-label").text(_month_name(m) + " " + y);
			$root.html(_skeleton_html());

			_drag.hotel = this.hotel;
			_drag.calMonth = calMonth;

			const hotel = this.hotel || "";
			const collected = {};
			let pending = 6;

			function done(key, data) {
				collected[key] = data;
				if (--pending === 0) {
					try {
						$root.empty();
						_render_quick_actions($root, hotel);
						// KPI cards (left) + HK board (right) side-by-side
						$root.append('<div class="bmr-top-row"><div class="bmr-kpi-side"></div><div class="bmr-hk-side"></div></div>');
						_render_kpis($root.find(".bmr-kpi-side"), $root, collected.kpi || {});
						_render_hk_board($root.find(".bmr-hk-side"), collected.hk || []);
						// Today's activity above room status
						_render_arrivals_departures($root, collected.ad || {});
						_render_room_chips($root, collected.grid || []);
						_render_matrix($root, collected.cal || [], collected.grid || [], calMonth);
						_render_charts($root, collected.trend || [], collected.grid || []);
			_bmr_refresh = () => dash.refresh();
					} catch (e) {
						console.error("BMR render error", e);
						$root.html(`<div class="bmr-empty">Render error — see browser console.</div>`);
					}
				}
			}

			frappe.call({
				method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.get_dashboard_kpis",
				args: { hotel, from_date: from, to_date: to },
				callback(r) { done("kpi", r.message || {}); },
				error()    { done("kpi", {}); },
			});
			frappe.call({
				method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.get_room_status_data",
				args: { hotel },
				callback(r) { done("grid", r.message || []); },
				error()    { done("grid", []); },
			});
			frappe.call({
				method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.get_calendar_data",
				args: { hotel, from_date: from, to_date: to },
				callback(r) { done("cal", r.message || []); },
				error()    { done("cal", []); },
			});
			frappe.call({
				method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.get_revenue_trend",
				args: { hotel, days: 14 },
				callback(r) { done("trend", r.message || []); },
				error()    { done("trend", []); },
			});
			frappe.call({
				method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.get_today_arrivals_departures",
				args: { hotel },
				callback(r) { done("ad", r.message || {}); },
				error()    { done("ad", {}); },
			});
			frappe.call({
				method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.get_housekeeping_board",
				args: { hotel },
				callback(r) { done("hk", r.message || []); },
				error()    { done("hk", []); },
			});
		},
	};

	// ── Global drag/resize/move handlers ─────────────────────────────────────

	$(document).off("mouseup.bmr").on("mouseup.bmr", function () {
		// 1. Create new reservation by dragging available cells
		if (_drag.active) {
			_drag.active = false;
			const fromDay = Math.min(_drag.startDay, _drag.endDay);
			const toDay   = Math.max(_drag.startDay, _drag.endDay);
			$root.find(".bmr-drag-sel").removeClass("bmr-drag-sel");
			if (_drag.room) {
				_open_new_reservation(_drag.hotel, _drag.room, _drag.calMonth, fromDay, toDay);
			}
		}

		// 2. Move reservation to different room
		if (_move.active) {
			const resName   = _move.resName;
			const oldRoom   = _move.room;
			const targetRoom = _move.targetRoom;
			_move.active = false;
			_move.targetRoom = null;
			$root.find(".bmr-drop-target").removeClass("bmr-drop-target");
			$root.find(".bmr-dragging").removeClass("bmr-dragging");
			if (targetRoom && targetRoom !== oldRoom && resName) {
				frappe.confirm(
					__("Move reservation to room {0}?", [targetRoom]),
					function () {
						frappe.call({
							method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.quick_update_reservation",
							args: { reservation: resName, new_room: targetRoom, old_room: oldRoom },
							callback() { dash.refresh(); },
						});
					}
				);
			}
		}

		// 3. Resize (extend/shorten) reservation
		if (_resize.active) {
			const resName   = _resize.resName;
			const newCoDay  = _resize.newCoDay;
			const origCoDay = _resize.coDay;
			_resize.active = false;
			_resize.newCoDay = null;
			$root.find(".bmr-resize-preview").removeClass("bmr-resize-preview");
			if (resName && newCoDay && newCoDay !== origCoDay && newCoDay > _resize.ciDay) {
				const [y, m] = _drag.calMonth.split("-").map(Number);
				const pad = function (n) { return String(n).padStart(2, "0"); };
				const coObj = new Date(y, m - 1, newCoDay);
				const newCheckOut = coObj.getFullYear() + "-" + pad(coObj.getMonth() + 1) + "-" + pad(coObj.getDate()) + " 11:00:00";
				frappe.call({
					method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard.quick_update_reservation",
					args: { reservation: resName, check_out: newCheckOut },
					callback() { dash.refresh(); },
				});
			}
		}
	});

	$(document).off("mousemove.bmr").on("mousemove.bmr", function (e) {
		// Move-room: highlight target row
		if (_move.active) {
			const elem = document.elementFromPoint(e.clientX, e.clientY);
			if (elem) {
				const tr = $(elem).closest("tr[data-room]");
				const trRoom = tr.data("room");
				if (trRoom && trRoom !== _move.room) {
					$root.find(".bmr-drop-target").removeClass("bmr-drop-target");
					tr.find("td").addClass("bmr-drop-target");
					_move.targetRoom = trRoom;
				} else if (!trRoom) {
					$root.find(".bmr-drop-target").removeClass("bmr-drop-target");
					_move.targetRoom = null;
				}
			}
		}

		// Resize: preview new date range
		if (_resize.active) {
			const elem = document.elementFromPoint(e.clientX, e.clientY);
			if (elem) {
				const td = $(elem).closest("td[data-day][data-room]");
				if (td.length && td.data("room") === _resize.room) {
					const day = parseInt(td.data("day"), 10);
					if (day >= _resize.ciDay) {
						const newCo = day + 1;
						if (newCo !== _resize.newCoDay) {
							_resize.newCoDay = newCo;
							$root.find(`#bmr-matrix tr[data-room="${_resize.room}"] td`).removeClass("bmr-resize-preview");
							for (let d = _resize.ciDay; d < newCo; d++) {
								$root.find(`#bmr-matrix tr[data-room="${_resize.room}"] td[data-day="${d}"]`).addClass("bmr-resize-preview");
							}
						}
					}
				}
			}
		}
	});

	wrapper.dashboard = dash;

	// Respect Booking Settings default hotel on first load.
	// User can clear/change the filter afterwards.
	frappe.call({
		method: "bookmyroom.book_my_room.doctype.booking_settings.booking_settings.get_booking_settings",
		callback(r) {
			const defaultHotel = r.message?.default_hotel;
			if (defaultHotel && !hotelField.get_value()) {
				_skipHotelChange = true;
				hotelField.set_value(defaultHotel);
				_skipHotelChange = false;
				dash.hotel = defaultHotel;
			}
			dash.refresh();
		},
		error() {
			dash.refresh();
		},
	});
};

frappe.pages["room-status-dashboard"].on_page_show = function (wrapper) {
	if (wrapper.dashboard) wrapper.dashboard.refresh();
};

// ── Skeleton ──────────────────────────────────────────────────────────────────
function _skeleton_html() {
	let s = "";
	for (let i = 0; i < 8; i++) s += `<div class="bmr-kpi-card bmr-skeleton"></div>`;
	return `<div class="bmr-kpi-row">${s}</div>`;
}

// ── Quick Action Buttons ───────────────────────────────────────────────────────
function _render_quick_actions($root, hotel) {
	const t = frappe.datetime.get_today();
	const pad = function (n) { return String(n).padStart(2, "0"); };

	$root.append(`
		<div class="bmr-actions-row">
			<button class="bmr-action-btn bmr-act-walkin" id="bmr-walkin">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>
				Walk-in
			</button>
			<button class="bmr-action-btn bmr-act-res" id="bmr-new-res">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="12" y1="14" x2="12" y2="18"/><line x1="10" y1="16" x2="14" y2="16"/></svg>
				New Reservation
			</button>
		</div>
	`);

	// Walk-in: today's dates + booking_source = Walk-in
	$root.find("#bmr-walkin").on("click", function () {
		const co = new Date();
		co.setDate(co.getDate() + 1);
		const coStr = co.getFullYear() + "-" + pad(co.getMonth() + 1) + "-" + pad(co.getDate());
		const _doWalkin = function (cin_time, cout_time) {
			window._bmr_hotel          = hotel || null;
			window._bmr_check_in       = cin_time  ? t     + " " + cin_time  : t;
			window._bmr_check_out      = cout_time ? coStr + " " + cout_time : coStr;
			window._bmr_room           = null;
			window._bmr_booking_source = "Walk-in";
			frappe.route_hooks.after_load = function (frm) {
				if (window._bmr_hotel)          frm.set_value("hotel",          window._bmr_hotel);
				if (window._bmr_check_in)       frm.set_value("check_in",       window._bmr_check_in);
				if (window._bmr_check_out)      frm.set_value("check_out",      window._bmr_check_out);
				if (window._bmr_booking_source) frm.set_value("booking_source", window._bmr_booking_source);
				delete window._bmr_hotel; delete window._bmr_check_in;
				delete window._bmr_check_out; delete window._bmr_room;
				delete window._bmr_booking_source;
				frappe.route_hooks.after_load = null;
			};
			frappe.new_doc("Room Reservation");
		};
		if (hotel) {
			frappe.db.get_value("Hotel", hotel, ["checkin_time", "checkout_time"], function (r) {
				_doWalkin(r && r.checkin_time, r && r.checkout_time);
			});
		} else {
			_doWalkin(null, null);
		}
	});

	// New Reservation: just pre-fill hotel
	$root.find("#bmr-new-res").on("click", function () {
		if (hotel) {
			window._bmr_hotel = hotel;
			frappe.route_hooks.after_load = function (frm) {
				if (window._bmr_hotel) frm.set_value("hotel", window._bmr_hotel);
				delete window._bmr_hotel;
				frappe.route_hooks.after_load = null;
			};
		}
		frappe.new_doc("Room Reservation");
	});

}

// ── KPI Cards ──────────────────────────────────────────────────────────────────
function _render_kpis($kpiSide, $fullRoot, kpi) {
	const fmt = function (n) { return frappe.format(Number(n || 0), { fieldtype: "Int" }); };
	const cur = function (n) {
		const c = (frappe.defaults && frappe.defaults.get_default("currency")) || "";
		return frappe.format(n || 0, { fieldtype: "Currency", options: c });
	};
	const shortDate = function (s) {
		if (!s) return "";
		const d = new Date(s + "T00:00:00");
		return d.getDate() + " " + d.toLocaleString("en", { month: "short" });
	};
	const periodLabel = shortDate(kpi.period_start) + " – " + shortDate(kpi.period_end);
	const isCurrent   = !!kpi.is_current_month;

	// ── 6 operational KPI cards ──────────────────────────────────────────────
	const cards = [
		{
			label: isCurrent ? "Check-ins Today" : "Check-ins",
			value: fmt(isCurrent ? kpi.checkins_today : kpi.checkins),
			sub: isCurrent ? null : periodLabel,
			color: "#4f46e5", grad: "135deg,#eef2ff,#e0e7ff",
			icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>`,
		},
		{
			label: isCurrent ? "Check-outs Today" : "Check-outs",
			value: fmt(isCurrent ? kpi.checkouts_today : kpi.checkouts),
			sub: isCurrent ? null : periodLabel,
			color: "#0ea5e9", grad: "135deg,#f0f9ff,#e0f2fe",
			icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`,
		},
		{
			label: "Guests In-House", value: fmt(kpi.occupied), sub: "current",
			color: "#10b981", grad: "135deg,#f0fdf4,#dcfce7",
			icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>`,
		},
		{
			label: "Reserved", value: fmt(kpi.booked), sub: "current",
			color: "#f59e0b", grad: "135deg,#fffbeb,#fef9c3",
			icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
		},
		{
			label: "Available Rooms", value: fmt(kpi.available_rooms),
			sub: "of " + fmt(kpi.total_rooms) + " total · current",
			color: "#6366f1", grad: "135deg,#f5f3ff,#ede9fe",
			icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
		},
		{
			label: "Occupancy", value: (kpi.occupancy_pct || 0) + "%", sub: "current",
			color: "#8b5cf6", grad: "135deg,#faf5ff,#f3e8ff",
			icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`,
		},
	];

	// 6-card operational row → left column only
	let opsHtml = `<div class="bmr-kpi-row">`;
	cards.forEach(function (c) {
		opsHtml += `<div class="bmr-kpi-card" style="--accent:${c.color};background:linear-gradient(${c.grad})">
			<div class="bmr-kpi-icon">${c.icon}</div>
			<div class="bmr-kpi-body">
				<div class="bmr-kpi-value">${c.value}</div>
				<div class="bmr-kpi-label">${c.label}</div>
				${c.sub ? `<div class="bmr-kpi-sub">${c.sub}</div>` : ""}
			</div>
		</div>`;
	});
	opsHtml += `</div>`;
	$kpiSide.append(opsHtml);

	// ── 2 financial summary cards (wider, more prominent) ────────────────────
	const currentOutstanding = Math.max(0, (kpi.outstanding_month || 0) - (kpi.overdue_amount || 0));
	const overdueChip = kpi.overdue_amount > 0
		? `<span class="bmr-fin-chip bmr-fin-chip-red"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Overdue &nbsp;<strong>${cur(kpi.overdue_amount)}</strong></span>`
		: `<span class="bmr-fin-chip bmr-fin-chip-green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11"><polyline points="20 6 9 17 4 12"/></svg> No overdue</span>`;
	const currentChip = currentOutstanding > 0
		? `<span class="bmr-fin-chip">Current &nbsp;<strong>${cur(currentOutstanding)}</strong></span>`
		: "";
	const todayChip = isCurrent && kpi.revenue_today != null
		? `<span class="bmr-fin-chip">Today &nbsp;<strong>${cur(kpi.revenue_today)}</strong></span>`
		: "";

	const finHtml = `<div class="bmr-fin-row">
		<div class="bmr-fin-card bmr-fin-paid">
			<div class="bmr-fin-left">
				<div class="bmr-fin-icon">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
				</div>
				<div>
					<div class="bmr-fin-title">Revenue Collected</div>
					<div class="bmr-fin-period">${periodLabel}</div>
				</div>
			</div>
			<div class="bmr-fin-amount">${cur(kpi.revenue_month)}</div>
			<div class="bmr-fin-footer">
				${todayChip}
			</div>
		</div>
		<div class="bmr-fin-card bmr-fin-out">
			<div class="bmr-fin-left">
				<div class="bmr-fin-icon">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
				</div>
				<div>
					<div class="bmr-fin-title">Outstanding</div>
					<div class="bmr-fin-period">${periodLabel}</div>
				</div>
			</div>
			<div class="bmr-fin-amount">${cur(kpi.outstanding_month)}</div>
			<div class="bmr-fin-footer">
				${overdueChip}${currentChip}
			</div>
		</div>
	</div>`;

	// Financial cards span full dashboard width (outside the KPI+HK top row)
	$fullRoot.find(".bmr-top-row").after(finHtml);
}

// ── Housekeeping Board (panel with filter buttons) ────────────────────────────
function _render_hk_board($container, hk) {
	if (!hk || !hk.length) return;

	const HK = {
		"Clean":       { bg: "#dcfce7", color: "#166534", dot: "#16a34a" },
		"Dirty":       { bg: "#fee2e2", color: "#b91c1c", dot: "#ef4444" },
		"Cleaning":    { bg: "#fef9c3", color: "#854d0e", dot: "#ca8a04" },
		"Inspected":   { bg: "#dbeafe", color: "#1d4ed8", dot: "#3b82f6" },
		"Out of Order":{ bg: "#f1f5f9", color: "#475569", dot: "#94a3b8" },
	};
	const FILTER_COLORS = {
		"Dirty": "#ef4444", "Cleaning": "#ca8a04", "Clean": "#16a34a",
		"Inspected": "#3b82f6", "Out of Order": "#94a3b8",
	};

	// Build filter list from existing statuses, in preferred order
	const PREFERRED = ["All", "Dirty", "Cleaning", "Clean", "Inspected", "Out of Order"];
	const existing = new Set(hk.map(function (r) { return r.hk_status || "Clean"; }));
	const filters = PREFERRED.filter(function (s) { return s === "All" || existing.has(s); });
	hk.forEach(function (r) {
		const s = r.hk_status || "Clean";
		if (filters.indexOf(s) === -1) filters.push(s);
	});

	const statusCounts = {};
	hk.forEach(function(r) { const s = r.hk_status || "Clean"; statusCounts[s] = (statusCounts[s] || 0) + 1; });
	const filterBtns = filters.map(function (s) {
		const fc    = FILTER_COLORS[s] || "#4f46e5";
		const count = s === "All" ? hk.length : (statusCounts[s] || 0);
		return `<button class="bmr-hkb-filter${s === "All" ? " active" : ""}" data-filter="${s}" style="--fc:${fc}">${s} <span class="bmr-hkb-fcount">(${count})</span></button>`;
	}).join("");

	const rows = hk.map(function (r) {
		const hs  = r.hk_status || "Clean";
		const col = HK[hs] || HK["Clean"];
		const badge = `<span class="bmr-hkb-badge" style="background:${col.bg};color:${col.color}"><span class="bmr-hkb-dot" style="background:${col.dot}"></span>${hs}</span>`;
		const assigned = r.assigned_to ? frappe.utils.escape_html(r.assigned_to) : `<span class="bmr-hkb-none">—</span>`;
		return `<tr data-hk-status="${hs}">
			<td class="bmr-hkb-room">${frappe.utils.escape_html(r.room_name)}</td>
			<td class="bmr-hkb-status">${badge}</td>
			<td class="bmr-hkb-person">${assigned}</td>
		</tr>`;
	}).join("");

	$container.append(`
		<div class="bmr-hkb-panel">
			<div class="bmr-hkb-header">
				<span class="bmr-hkb-title">Housekeeping</span>
				<span class="bmr-hkb-count">${hk.length} rooms</span>
			</div>
			<div class="bmr-hkb-filters">${filterBtns}</div>
			<div class="bmr-hkb-scroll">
				<table class="bmr-hkb-table">
					<thead><tr><th>Room</th><th>Status</th><th>Assigned To</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		</div>
	`);

	// Filter click handler
	$container.on("click", ".bmr-hkb-filter", function () {
		const filter = $(this).data("filter");
		$container.find(".bmr-hkb-filter").removeClass("active");
		$(this).addClass("active");
		const tbody = $container.find(".bmr-hkb-table tbody tr");
		if (filter === "All") {
			tbody.show();
		} else {
			tbody.each(function () { $(this).toggle($(this).data("hk-status") === filter); });
		}
	});
}

// ── Room Status Chips ──────────────────────────────────────────────────────────
function _room_display_status(r) {
	if (r.status === "Vacant") {
		return r.housekeeping_status === "Dirty" ? "Vacant Dirty" : "Vacant Clean";
	}
	if (r.status === "Available" && r.reservation) return "Reserved";
	return r.status || "Available";
}

function _render_room_chips($root, rooms) {
	if (!rooms || !rooms.length) return;

	const STATUS = {
		"Available":    { cls: "ch-av" },
		"Reserved":     { cls: "ch-bk" },
		"Occupied":     { cls: "ch-ci" },
		"Vacant Clean": { cls: "ch-vc" },
		"Vacant Dirty": { cls: "ch-vd" },
		"Out of Order": { cls: "ch-oo" },
		"Maintenance":  { cls: "ch-mn" },
	};

	let html = `
		<div class="bmr-section-head">Room Status
			<span class="bmr-legend-row">
				<span class="bmr-leg"><span class="ch-av bmr-leg-dot"></span>Available</span>
				<span class="bmr-leg"><span class="ch-bk bmr-leg-dot"></span>Reserved</span>
				<span class="bmr-leg"><span class="ch-ci bmr-leg-dot"></span>Occupied</span>
				<span class="bmr-leg"><span class="ch-vc bmr-leg-dot"></span>Vacant Clean</span>
				<span class="bmr-leg"><span class="ch-vd bmr-leg-dot"></span>Vacant Dirty</span>
				<span class="bmr-leg"><span class="ch-oo bmr-leg-dot"></span>Out of Order</span>
			</span>
		</div>
		<div class="bmr-room-strip">`;

	rooms.forEach(function (r) {
		const ds   = _room_display_status(r);
		const meta = STATUS[ds] || STATUS["Available"];
		const res  = r.reservation;
		const tip  = res ? `${r.room_name} · ${r.room_type || ""} · ${res.customer} (${res.status})`
		                 : `${r.room_name} · ${r.room_type || ""} · ${ds}`;
		const guestFirst = res ? res.customer.split(" ")[0] : "";
		html += `<div class="bmr-chip ${meta.cls}" data-room="${r.name}" data-res="${res ? res.name : ""}" title="${tip}">
			<span class="bmr-chip-num">${r.room_name || r.name}</span>
			${guestFirst ? `<span class="bmr-chip-guest">${guestFirst}</span>` : ""}
		</div>`;
	});
	html += `</div>`;
	$root.append(html);

	$root.find(".bmr-chip").on("click", function () {
		const res  = $(this).data("res");
		const room = $(this).data("room");
		if (res)  frappe.set_route("Form", "Room Reservation", res);
		else if (room) frappe.set_route("Form", "Rooms", room);
	});
}

// ── Matrix Calendar — tape view with drag/resize/move ────────────────────────
function _render_matrix($root, reservations, rooms, calMonth) {
	if (!rooms || !rooms.length) return;

	// Reset tip data
	Object.keys(_tipData).forEach(function (k) { delete _tipData[k]; });

	const parts       = calMonth.split("-");
	const y           = parseInt(parts[0], 10);
	const m           = parseInt(parts[1], 10);
	const daysInMonth = new Date(y, m, 0).getDate();
	const todayStr    = frappe.datetime.get_today();
	const todayMonth  = todayStr.slice(0, 7);
	const todayDay    = parseInt(todayStr.slice(8, 10), 10);
	const DAYS        = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

	// Build cell map
	const cellMap = {};
	rooms.forEach(function (r) { cellMap[r.name] = {}; });

	(reservations || []).forEach(function (r) {
		if (!cellMap[r.room]) return;
		const ci  = new Date(r.check_in);
		const co  = new Date(r.check_out);
		const ciD = new Date(ci.getFullYear(), ci.getMonth(), ci.getDate());
		const coD = new Date(co.getFullYear(), co.getMonth(), co.getDate());

		for (let d = 1; d <= daysInMonth; d++) {
			const date  = new Date(y, m - 1, d);
			if (date < ciD || date >= coD) continue;

			const next    = new Date(y, m - 1, d + 1);
			const isStart = date.getTime() === ciD.getTime();
			const isEnd   = next.getTime() === coD.getTime() || (d === daysInMonth && coD > new Date(y, m, 0));
			let type = "mid";
			if (isStart && isEnd)  type = "only";
			else if (isStart)      type = "start";
			else if (isEnd)        type = "end";

			// ciDay in this matrix (1 if starts in a previous month)
			const ciInMonth = ciD.getFullYear() === y && ciD.getMonth() === m - 1;
			const ciDayMatrix = ciInMonth ? ciD.getDate() : 1;
			// coDay = day after the last night (could exceed daysInMonth)
			const coDayMatrix = (coD.getFullYear() === y && coD.getMonth() === m - 1)
				? coD.getDate()
				: daysInMonth + 1;

			cellMap[r.room][d] = {
				type,
				customer:      r.customer,
				resName:       r.reservation,
				status:        r.status,
				checkIn:       String(r.check_in).slice(0, 10),
				checkOut:      String(r.check_out).slice(0, 10),
				totalNights:   r.total_nights || 0,
				grandTotal:    r.grand_total  || 0,
				balanceDue:    r.balance_due  || 0,
				ciDayMatrix,
				coDayMatrix,
			};
		}
	});

	// Header
	let hdr = `<th class="bmr-m-room-th">Room</th>`;
	for (let d = 1; d <= daysInMonth; d++) {
		const dow = new Date(y, m - 1, d).getDay();
		const wk  = (dow === 0 || dow === 6) ? " bmr-wkend" : "";
		const td  = (calMonth === todayMonth && d === todayDay) ? " bmr-today-col" : "";
		hdr += `<th class="${wk}${td}">
			<span class="bmr-day-num">${d}</span>
			<span class="bmr-day-name">${DAYS[dow]}</span>
		</th>`;
	}

	// Rows (tape view)
	let body = "";
	rooms.forEach(function (room) {
		let row = `<td class="bmr-m-room-cell" data-room="${room.name}">${room.room_name || room.name}</td>`;
		for (let d = 1; d <= daysInMonth; d++) {
			const dow  = new Date(y, m - 1, d).getDay();
			const wk   = (dow === 0 || dow === 6) ? " bmr-wkend" : "";
			const tdCls = (calMonth === todayMonth && d === todayDay) ? " bmr-today-col" : "";
			const cell  = cellMap[room.name][d];

			if (cell) {
				const barCls = cell.status === "Checked In" ? "bmr-bar-ci" : "bmr-bar-bk";
				const label  = (cell.type === "start" || cell.type === "only")
					? `<span class="bmr-bar-lbl">${frappe.utils.escape_html(cell.customer)}</span>` : "";
				// Resize handle only on end/only cells
				const resizeHandle = (cell.type === "end" || cell.type === "only")
					? `<div class="bmr-resize-right" title="Drag to resize"></div>` : "";
				// Store tooltip data
				_tipData[room.name + "_" + d] = cell;
				row += `<td class="bmr-res-td bmr-bar-${cell.type}${wk}${tdCls}" data-room="${room.name}" data-day="${d}" data-res="${cell.resName}">
					<div class="bmr-bar ${barCls} bmr-bar-movable">${label}${resizeHandle}</div>
				</td>`;
			} else {
				// Tape for available cells (vs dot)
				const isToday = (calMonth === todayMonth && d === todayDay);
				const ds = isToday ? _room_display_status(room) : "Available";
				const tapeCls = ds === "Vacant Dirty"  ? "bmr-tape-vd"
					: ds === "Vacant Clean"            ? "bmr-tape-vc"
					: ds === "Out of Order"            ? "bmr-tape-oo"
					: ds === "Maintenance"             ? "bmr-tape-mn"
					: "bmr-tape-av";
				const notBookable = isToday && (ds === "Out of Order" || ds === "Maintenance");
				row += `<td class="${notBookable ? "bmr-cell-na" : "bmr-cell-av"}${wk}${tdCls}" data-room="${room.name}" data-day="${d}">
					<div class="${tapeCls}"></div>
				</td>`;
			}
		}
		body += `<tr data-room="${room.name}">${row}</tr>`;
	});

	$root.append(`
		<div class="bmr-section-head">Reservation Matrix — ${_month_name(m)} ${y}
			<span class="bmr-matrix-hints">
				<span>✦ Drag empty cells to create</span>
				<span>⟺ Drag bar to move room</span>
				<span>⇤ Drag edge to resize</span>
			</span>
		</div>
		<div class="bmr-m-wrap">
			<table id="bmr-matrix" class="bmr-matrix" cellspacing="0">
				<thead><tr>${hdr}</tr></thead>
				<tbody>${body}</tbody>
			</table>
		</div>`);

	// Click on reservation → open (only if not dragging)
	$root.find(".bmr-res-td").on("click", function () {
		if (_move.active || _resize.active) return;
		const res = $(this).data("res");
		if (res) frappe.set_route("Form", "Room Reservation", res);
	});

	// Drag to create on available cells
	$root.find("#bmr-matrix").on("mousedown", ".bmr-cell-av", function (e) {
		e.preventDefault();
		_drag.active   = true;
		_drag.room     = $(this).data("room");
		_drag.startDay = parseInt($(this).data("day"), 10);
		_drag.endDay   = _drag.startDay;
		$(this).addClass("bmr-drag-sel");
	});

	$root.find("#bmr-matrix").on("mouseover", ".bmr-cell-av", function () {
		if (!_drag.active || $(this).data("room") !== _drag.room) return;
		_drag.endDay = parseInt($(this).data("day"), 10);
		const lo = Math.min(_drag.startDay, _drag.endDay);
		const hi = Math.max(_drag.startDay, _drag.endDay);
		$root.find(`#bmr-matrix .bmr-cell-av[data-room="${_drag.room}"]`).each(function () {
			const d = parseInt($(this).data("day"), 10);
			$(this).toggleClass("bmr-drag-sel", d >= lo && d <= hi);
		});
	});

	// Resize handle mousedown
	$root.find("#bmr-matrix").on("mousedown", ".bmr-resize-right", function (e) {
		e.preventDefault();
		e.stopPropagation();
		const td  = $(this).closest("td");
		const key = td.data("room") + "_" + td.data("day");
		const tip = _tipData[key];
		if (!tip) return;
		const ciInMonth = tip.checkIn.slice(0, 7) === _drag.calMonth;
		_resize.active  = true;
		_resize.resName = td.data("res");
		_resize.room    = td.data("room");
		_resize.ciDay   = ciInMonth ? parseInt(tip.checkIn.slice(8, 10), 10) : 1;
		_resize.coDay   = tip.coDayMatrix || (parseInt(td.data("day"), 10) + 1);
		_resize.newCoDay = _resize.coDay;
	});

	// Move bar mousedown (not on resize handle)
	$root.find("#bmr-matrix").on("mousedown", ".bmr-bar-movable", function (e) {
		if ($(e.target).hasClass("bmr-resize-right")) return;
		e.preventDefault();
		const td = $(this).closest("td");
		_move.active    = true;
		_move.resName   = td.data("res");
		_move.room      = td.data("room");
		_move.targetRoom = td.data("room");
		$(this).addClass("bmr-dragging");
	});

	// Tooltip on reservation cells
	if (!document.getElementById("bmr-tooltip")) {
		$("body").append(`<div id="bmr-tooltip" class="bmr-tooltip"></div>`);
	}
	$root.find(".bmr-res-td")
		.on("mouseenter", function (e) {
			if (_move.active || _resize.active) return;
			const key = $(this).data("room") + "_" + $(this).data("day");
			const tip = _tipData[key];
			if (!tip) return;
			const crf = frappe.format(tip.grandTotal || 0, { fieldtype: "Currency" });
			const bal = frappe.format(tip.balanceDue  || 0, { fieldtype: "Currency" });
			const stCls = tip.status === "Checked In" ? "bmr-tip-ci" : "bmr-tip-bk";
			$("#bmr-tooltip").html(`
				<div class="bmr-tip-guest">${frappe.utils.escape_html(tip.customer)}</div>
				<div class="bmr-tip-row"><b>Check-in:</b> ${tip.checkIn}</div>
				<div class="bmr-tip-row"><b>Check-out:</b> ${tip.checkOut}</div>
				<div class="bmr-tip-row"><b>Nights:</b> ${tip.totalNights}</div>
				<div class="bmr-tip-row"><b>Total:</b> ${crf}</div>
				<div class="bmr-tip-row"><b>Balance:</b> ${bal}</div>
				<div class="bmr-tip-badge ${stCls}">${tip.status}</div>
			`).css({ display: "block", top: e.pageY + 14, left: e.pageX + 14 });
		})
		.on("mousemove", function (e) {
			if (_move.active || _resize.active) return;
			$("#bmr-tooltip").css({ top: e.pageY + 14, left: e.pageX + 14 });
		})
		.on("mouseleave", function () {
			$("#bmr-tooltip").hide();
		});
}

// ── Today's Arrivals & Departures ─────────────────────────────────────────────
function _render_arrivals_departures($root, data) {
	const arrivals   = (data && data.arrivals)   || [];
	const departures = (data && data.departures) || [];

	function _list_html(items, emptyMsg, isArrival) {
		if (!items.length) return `<div class="bmr-ad-empty">${emptyMsg}</div>`;
		return items.map(function (r) {
			const rooms  = r.rooms && r.rooms.length ? r.rooms.join(", ") : "—";
				const stCls  = r.status === "Checked In" ? "bmr-ad-st-ci" : r.status === "Checked Out" ? "bmr-ad-st-co" : "bmr-ad-st-bk";
				let actionBtn = "";
				if (isArrival && r.status === "Booked") {
					actionBtn = `<button class="bmr-ad-pill bmr-ad-action-btn bmr-ad-checkin" data-res="${r.name}">Check-in</button>`;
				} else if (r.status === "Checked In") {
					actionBtn = `<button class="bmr-ad-pill bmr-ad-action-btn bmr-ad-checkout" data-res="${r.name}">Checkout</button>`;
				}
				return `<div class="bmr-ad-row" data-res="${r.name}">
					<div class="bmr-ad-rooms">${frappe.utils.escape_html(rooms)}</div>
					<div class="bmr-ad-customer">${frappe.utils.escape_html(r.customer)}</div>
					<span class="bmr-ad-pill bmr-ad-status ${stCls}">${r.status}</span>
					${actionBtn}
				</div>`;
			}).join("");
	}

	$root.append(`
		<div class="bmr-section-head">Today's Activity</div>
		<div class="bmr-ad-panels">
			<div class="bmr-ad-panel">
				<div class="bmr-ad-title">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>
					Arrivals (${arrivals.length})
				</div>
				<div class="bmr-ad-list">${_list_html(arrivals, "No arrivals today", true)}</div>
			</div>
			<div class="bmr-ad-panel">
				<div class="bmr-ad-title">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
					Departures (${departures.length})
				</div>
				<div class="bmr-ad-list">${_list_html(departures, "No departures today", false)}</div>
			</div>
		</div>
	`);

	$root.find(".bmr-ad-row").on("click", function (e) {
		if ($(e.target).closest(".bmr-ad-action-btn").length) return;
		const res = $(this).data("res");
		if (res) frappe.set_route("Form", "Room Reservation", res);
	});

	function _do_quick_action(method, reservation, $btn, label) {
		$btn.prop("disabled", true).text("...");
		frappe.call({
			method: "bookmyroom.book_my_room.page.room_status_dashboard.room_status_dashboard." + method,
			args: { reservation },
			callback: function(r) {
				if (r.message && r.message.ok) {
					frappe.show_alert({ message: label + " successful", indicator: "green" });
					_bmr_refresh && _bmr_refresh();
				} else {
					frappe.show_alert({ message: (r.message && r.message.error) || "Action failed", indicator: "red" });
					$btn.prop("disabled", false).text(label);
				}
			},
		});
	}

	$root.find(".bmr-ad-checkin").on("click", function (e) {
		e.stopPropagation();
		_do_quick_action("quick_checkin", $(this).data("res"), $(this), "Check-in");
	});
	$root.find(".bmr-ad-checkout").on("click", function (e) {
		e.stopPropagation();
		_do_quick_action("quick_checkout", $(this).data("res"), $(this), "Checkout");
	});
}

// ── Charts ────────────────────────────────────────────────────────────────────
function _render_charts($root, trend, rooms) {
	const trendLabels = (trend || []).map(function (r) { return String(r.date); });
	const trendData   = (trend || []).map(function (r) { return r.revenue || 0; });

	const statusCount = {};
	(rooms || []).forEach(function (r) {
		statusCount[r.status] = (statusCount[r.status] || 0) + 1;
	});
	const donutLabels = Object.keys(statusCount);
	const donutData   = donutLabels.map(function (k) { return statusCount[k]; });

	$root.append(`
		<div class="bmr-section-head">Analytics</div>
		<div class="bmr-charts-row">
			<div class="bmr-chart-card">
				<div class="bmr-chart-title">Revenue — Last 14 Days</div>
				<div id="bmr-trend-chart"></div>
			</div>
			<div class="bmr-chart-card">
				<div class="bmr-chart-title">Room Distribution</div>
				<div id="bmr-donut-chart"></div>
			</div>
		</div>
	`);

	if (trendData.some(function (v) { return v > 0; })) {
		new frappe.Chart("#bmr-trend-chart", {
			type: "bar",
			data: { labels: trendLabels, datasets: [{ name: "Revenue", values: trendData }] },
			colors: ["#4f46e5"],
			height: 220,
			axisOptions: { xIsSeries: true },
		});
	} else {
		$("#bmr-trend-chart").html(`<div class="bmr-chart-empty">No revenue data for this period.</div>`);
	}

	if (donutData.length) {
		new frappe.Chart("#bmr-donut-chart", {
			type: "donut",
			data: { labels: donutLabels, datasets: [{ values: donutData }] },
			colors: ["#10b981", "#f59e0b", "#4f46e5", "#0ea5e9", "#ef4444", "#6b7280", "#8b5cf6"],
			height: 220,
		});
	} else {
		$("#bmr-donut-chart").html(`<div class="bmr-chart-empty">No room data.</div>`);
	}
}

// ── Open New Reservation (drag-to-create) ─────────────────────────────────────
function _open_new_reservation(hotel, roomId, calMonth, fromDay, toDay) {
	if (!roomId || !calMonth) return;
	const [y, m] = calMonth.split("-").map(Number);
	const pad = function (n) { return String(n).padStart(2, "0"); };
	const startDate = y + "-" + pad(m) + "-" + pad(fromDay);
	const coDateObj = new Date(y, m - 1, toDay + 1);
	const endDate   = coDateObj.getFullYear() + "-" + pad(coDateObj.getMonth() + 1) + "-" + pad(coDateObj.getDate());

	const _doOpen = function (cin_time, cout_time) {
		window._bmr_room      = roomId;
		window._bmr_hotel     = hotel;
		window._bmr_check_in  = cin_time  ? startDate + " " + cin_time  : startDate;
		window._bmr_check_out = cout_time ? endDate   + " " + cout_time : endDate;

		frappe.route_hooks.after_load = function (frm) {
			if (window._bmr_hotel)     frm.set_value("hotel",     window._bmr_hotel);
			if (window._bmr_check_in)  frm.set_value("check_in",  window._bmr_check_in);
			if (window._bmr_check_out) frm.set_value("check_out", window._bmr_check_out);
			if (window._bmr_room) {
				frm.clear_table("items");
				const row = frm.add_child("items");
				frappe.model.set_value(row.doctype, row.name, "room", window._bmr_room);
				frm.refresh_field("items");
			}
			delete window._bmr_room; delete window._bmr_hotel;
			delete window._bmr_check_in; delete window._bmr_check_out;
			frappe.route_hooks.after_load = null;
		};
		frappe.new_doc("Room Reservation");
	};

	if (hotel) {
		frappe.db.get_value("Hotel", hotel, ["checkin_time", "checkout_time"], function (r) {
			_doOpen(r && r.checkin_time, r && r.checkout_time);
		});
	} else {
		_doOpen(null, null);
	}
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function _month_name(m) {
	return ["", "January", "February", "March", "April", "May", "June",
		"July", "August", "September", "October", "November", "December"][m] || "";
}

// ── Styles ────────────────────────────────────────────────────────────────────
function _inject_styles() {
	if (document.getElementById("bmr-dash-style")) return;
	const s = document.createElement("style");
	s.id = "bmr-dash-style";
	s.textContent = `
/* Nav */
.bmr-cal-nav{
	display:flex;align-items:center;gap:12px;padding:10px 12px 8px;
	background:linear-gradient(135deg,#f8fafc,#eef2ff);
	border:1px solid #e2e8f0;border-radius:12px;
	box-shadow:0 4px 18px rgba(15,23,42,.05),inset 0 1px 0 rgba(255,255,255,.8);
}
.bmr-nav-btn{
	background:linear-gradient(180deg,#ffffff,#f1f5f9);
	border:1px solid #dbe4ef;border-radius:10px;padding:4px 14px;cursor:pointer;font-size:16px;line-height:1.5;
	transition:all .18s;box-shadow:0 2px 8px rgba(15,23,42,.08);
}
.bmr-nav-btn:hover{background:linear-gradient(180deg,#ffffff,#e9eef6);transform:translateY(-1px)}
.bmr-cal-label{font-weight:700;font-size:14px;color:#0f172a;min-width:120px;text-align:center;letter-spacing:.02em}

/* Dashboard */
.bmr-dash{
	padding:14px 12px 48px;margin-top:10px;border-radius:16px;
	background:
		radial-gradient(circle at 0% 0%,rgba(79,70,229,.08) 0%,rgba(79,70,229,0) 45%),
		radial-gradient(circle at 100% 0%,rgba(14,165,233,.08) 0%,rgba(14,165,233,0) 40%),
		linear-gradient(180deg,#ffffff 0%,#f8fafc 100%);
	border:1px solid #e5eaf2;
}

/* Quick Actions */
.bmr-actions-row{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap}

/* Top row: KPI grid (left) + HK board (right) — stretch so board matches KPI height */
.bmr-top-row{display:grid;grid-template-columns:1fr 290px;gap:14px;align-items:stretch;margin-bottom:22px}
.bmr-kpi-side .bmr-kpi-row{margin-bottom:0}
.bmr-hk-side{display:flex;flex-direction:column}
.bmr-action-btn{display:inline-flex;align-items:center;gap:7px;padding:9px 20px;border-radius:10px;border:none;cursor:pointer;font-size:13px;font-weight:700;letter-spacing:.01em;transition:all .15s;box-shadow:0 2px 6px rgba(0,0,0,.08)}
.bmr-action-btn svg{width:15px;height:15px;flex-shrink:0}
.bmr-act-walkin{background:linear-gradient(135deg,#4f46e5,#6366f1);color:#fff}
.bmr-act-walkin:hover{background:linear-gradient(135deg,#4338ca,#4f46e5);box-shadow:0 4px 14px rgba(79,70,229,.35);transform:translateY(-1px)}
.bmr-act-res{background:linear-gradient(135deg,#0ea5e9,#38bdf8);color:#fff}
.bmr-act-res:hover{background:linear-gradient(135deg,#0284c7,#0ea5e9);box-shadow:0 4px 14px rgba(14,165,233,.35);transform:translateY(-1px)}

/* KPI Row — 6 cards, 3 per row (2 rows) */
.bmr-kpi-row{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:0}
.bmr-kpi-card{
	position:relative;border-radius:14px;
	background:linear-gradient(180deg,#ffffff 0%,#f9fbff 100%);
	box-shadow:0 2px 8px rgba(15,23,42,.06),0 12px 26px rgba(15,23,42,.05);
	padding:16px 14px 14px;display:flex;align-items:flex-start;gap:10px;
	border:1px solid rgba(148,163,184,.25);
	transition:box-shadow .2s,transform .2s,border-color .2s;cursor:default;min-height:90px;
	animation:bmr-rise .28s ease-out both;
}
.bmr-kpi-card::after{
	content:"";position:absolute;left:0;right:0;top:0;height:3px;border-radius:14px 14px 0 0;
	background:linear-gradient(90deg,var(--accent,#4f46e5),color-mix(in srgb,var(--accent,#4f46e5) 45%,#fff));
	opacity:.8;
}
.bmr-kpi-card:hover{box-shadow:0 8px 24px rgba(15,23,42,.14);transform:translateY(-3px);border-color:rgba(99,102,241,.35)}
.bmr-kpi-icon{width:36px;height:36px;min-width:36px;border-radius:9px;background:color-mix(in srgb,var(--accent,#4f46e5) 15%,white);display:flex;align-items:center;justify-content:center;color:var(--accent,#4f46e5);margin-top:2px}
.bmr-kpi-icon svg{width:17px;height:17px}
.bmr-kpi-body{flex:1;min-width:0}
.bmr-kpi-value{font-size:20px;font-weight:800;color:#0f172a;line-height:1.15;letter-spacing:-.5px}
.bmr-kpi-cur{font-size:16px;letter-spacing:-.2px;word-break:break-all}
.bmr-kpi-label{font-size:10px;color:#64748b;margin-top:3px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;line-height:1.3}
.bmr-kpi-sub{font-size:10px;color:#94a3b8;margin-top:2px;font-weight:500}

/* Skeleton */
.bmr-skeleton{height:90px;border:none!important;background:linear-gradient(90deg,#e2e8f0 25%,#f8fafc 50%,#e2e8f0 75%);background-size:200% 100%;animation:bmr-shimmer 1.4s infinite}
@keyframes bmr-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* Financial Summary Cards */
.bmr-fin-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:22px}
.bmr-fin-card{
	border-radius:16px;padding:20px 24px;display:flex;flex-direction:column;gap:12px;
	border:1px solid rgba(0,0,0,.07);
	box-shadow:0 2px 10px rgba(15,23,42,.07),0 1px 3px rgba(15,23,42,.05);
	transition:box-shadow .2s,transform .2s;
}
.bmr-fin-card:hover{box-shadow:0 8px 28px rgba(15,23,42,.12);transform:translateY(-2px)}
.bmr-fin-paid{background:linear-gradient(135deg,#f0fdf4 0%,#dcfce7 100%)}
.bmr-fin-out{background:linear-gradient(135deg,#fef2f2 0%,#fee2e2 100%)}
.bmr-fin-left{display:flex;align-items:center;gap:14px}
.bmr-fin-icon{
	width:48px;height:48px;flex-shrink:0;border-radius:14px;
	display:flex;align-items:center;justify-content:center;
}
.bmr-fin-icon svg{width:22px;height:22px}
.bmr-fin-paid .bmr-fin-icon{background:rgba(16,185,129,.18);color:#059669}
.bmr-fin-out  .bmr-fin-icon{background:rgba(239,68,68,.15);color:#dc2626}
.bmr-fin-title{font-size:14px;font-weight:700;color:#0f172a;letter-spacing:-.01em}
.bmr-fin-period{font-size:11px;color:#64748b;margin-top:3px;font-weight:500;letter-spacing:.01em}
.bmr-fin-amount{font-size:32px;font-weight:800;letter-spacing:-.06em;line-height:1}
.bmr-fin-paid .bmr-fin-amount{color:#065f46}
.bmr-fin-out  .bmr-fin-amount{color:#991b1b}
.bmr-fin-footer{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.bmr-fin-chip{
	display:inline-flex;align-items:center;gap:5px;
	font-size:11.5px;font-weight:500;color:#475569;
	padding:4px 12px;border-radius:20px;
	background:rgba(255,255,255,.7);border:1px solid rgba(0,0,0,.08);
	white-space:nowrap;
}
.bmr-fin-chip strong{font-weight:700;color:#0f172a}
.bmr-fin-chip-red{background:rgba(239,68,68,.1);border-color:rgba(239,68,68,.25);color:#b91c1c}
.bmr-fin-chip-red strong{color:#7f1d1d}
.bmr-fin-chip-green{background:rgba(16,185,129,.1);border-color:rgba(16,185,129,.25);color:#065f46}
@media(max-width:768px){.bmr-fin-row{grid-template-columns:1fr}.bmr-fin-amount{font-size:26px}}

/* Housekeeping Board panel */
.bmr-hkb-panel{
	background:linear-gradient(180deg,#ffffff,#f8fafc);
	border-radius:14px;border:1px solid #e2e8f0;
	box-shadow:0 2px 10px rgba(15,23,42,.08),0 14px 24px rgba(15,23,42,.04);
	overflow:hidden;display:flex;flex-direction:column;max-height:230px;
}
.bmr-hkb-header{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:linear-gradient(135deg,#f8fafc,#f1f5f9);border-bottom:1px solid #e2e8f0;flex-shrink:0}
.bmr-hkb-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#64748b}
.bmr-hkb-count{font-size:10px;color:#94a3b8;font-weight:500}
.bmr-hkb-filters{display:flex;gap:5px;flex-wrap:wrap;padding:8px 12px;border-bottom:1px solid #f1f5f9;background:#fafafa;flex-shrink:0}
.bmr-hkb-filter{padding:3px 10px;border-radius:20px;border:1px solid #e2e8f0;background:#fff;cursor:pointer;font-size:10px;font-weight:600;color:#64748b;transition:all .12s;outline:none;line-height:1.5}
.bmr-hkb-filter:hover{background:#f1f5f9;border-color:#cbd5e1}
.bmr-hkb-filter.active{background:var(--fc,#4f46e5);color:#fff;border-color:var(--fc,#4f46e5)}
.bmr-hkb-scroll{overflow-y:auto;flex:1;min-height:0}
.bmr-hkb-table{width:100%;border-collapse:collapse;font-size:12px}
.bmr-hkb-table thead tr{background:#f8fafc;border-bottom:2px solid #e2e8f0;position:sticky;top:0;z-index:1}
.bmr-hkb-table th{padding:7px 12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#64748b;text-align:left;background:#f8fafc}
.bmr-hkb-table tbody tr{border-bottom:1px solid #f1f5f9;transition:background .12s}
.bmr-hkb-table tbody tr:last-child{border-bottom:none}
.bmr-hkb-table tbody tr:hover{background:#f8fafc}
.bmr-hkb-room{padding:7px 12px;font-weight:700;color:#1e293b;white-space:nowrap}
.bmr-hkb-status{padding:5px 12px}
.bmr-hkb-person{padding:7px 12px;color:#475569;font-size:11px}
.bmr-hkb-badge{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap}
.bmr-hkb-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.bmr-hkb-none{color:#cbd5e1}

/* Sections */
.bmr-section-head{
	font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.09em;color:#475569;
	margin:28px 0 10px;padding:2px 0 8px;border-bottom:1px solid #dbe4ef;
	display:flex;align-items:center;gap:10px;flex-wrap:wrap;position:relative;
}
.bmr-section-head::before{
	content:"";width:22px;height:3px;border-radius:3px;
	background:linear-gradient(90deg,#4f46e5,#0ea5e9);
}
.bmr-legend-row{display:flex;gap:10px;flex-wrap:wrap;margin-left:auto}
.bmr-leg{display:flex;align-items:center;gap:4px;font-size:10px;color:#64748b;font-weight:500}
.bmr-leg-dot{display:inline-block;width:8px;height:8px;border-radius:50%}
.bmr-matrix-hints{display:flex;gap:12px;margin-left:auto;font-size:10px;color:#a855f7;font-weight:500;flex-wrap:wrap}

/* Room Chips */
.bmr-room-strip{display:flex;flex-wrap:wrap;gap:6px;padding:10px 0 16px}
.bmr-chip{display:inline-flex;flex-direction:column;align-items:center;justify-content:center;min-width:52px;padding:5px 8px;border-radius:9px;cursor:pointer;border:1px solid;transition:transform .16s,box-shadow .16s,filter .16s;line-height:1.2;box-shadow:0 2px 8px rgba(15,23,42,.09)}
.bmr-chip:hover{transform:translateY(-2px) scale(1.03);box-shadow:0 8px 16px rgba(15,23,42,.15);filter:saturate(1.08)}
.bmr-chip-num{font-size:12px;font-weight:700;color:inherit}
.bmr-chip-guest{font-size:9px;font-weight:500;color:inherit;opacity:.7;max-width:50px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ch-av{background:#dcfce7;color:#166534;border-color:#86efac}
.ch-bk{background:#fef08a;color:#713f12;border-color:#ca8a04}
.ch-ci{background:#4f46e5;color:#fff;border-color:#3730a3}
.ch-vc{background:#0ea5e9;color:#fff;border-color:#0284c7}
.ch-vd{background:#ef4444;color:#fff;border-color:#b91c1c}
.ch-oo{background:#64748b;color:#fff;border-color:#475569}
.ch-mn{background:#7c3aed;color:#fff;border-color:#6d28d9}
.ch-av.bmr-leg-dot{background:#16a34a}
.ch-bk.bmr-leg-dot{background:#ca8a04}
.ch-ci.bmr-leg-dot{background:#4f46e5}
.ch-vc.bmr-leg-dot{background:#0ea5e9}
.ch-vd.bmr-leg-dot{background:#ef4444}
.ch-oo.bmr-leg-dot{background:#64748b}
.ch-mn.bmr-leg-dot{background:#7c3aed}

/* Matrix Calendar */
.bmr-m-wrap{
	overflow:auto;max-height:520px;border-radius:12px;border:1px solid #dbe4ef;
	box-shadow:0 2px 10px rgba(15,23,42,.08),0 16px 26px rgba(15,23,42,.05);
	background:#fff;
}
.bmr-matrix{border-collapse:separate;border-spacing:0;font-size:11px;background:#fff;width:max-content;min-width:100%}
.bmr-matrix th{background:#f1f5f9;border-bottom:2px solid #dde4f0;border-right:1px solid #e8edf4;padding:6px 2px 4px;text-align:center;min-width:32px;height:40px;font-weight:600;color:#64748b;position:sticky;top:0;z-index:2}
.bmr-matrix td{border-bottom:1px solid #f0f4fa;border-right:1px solid #f0f4fa;padding:0;text-align:center;min-width:32px;height:34px;position:relative}
.bmr-m-room-th{min-width:96px!important;text-align:left!important;padding:0 10px!important;position:sticky!important;top:0!important;left:0!important;z-index:5!important;background:#f1f5f9!important}
.bmr-m-room-cell{min-width:96px!important;text-align:left!important;padding:0 10px!important;font-weight:700!important;font-size:11px!important;color:#1e293b!important;background:#f8fafc!important;position:sticky!important;left:0!important;z-index:1!important;white-space:nowrap!important;border-right:2px solid #dde4f0!important}
.bmr-matrix tbody tr:hover .bmr-m-room-cell{background:#eef2ff!important}
.bmr-wkend{background:#f5f5f7!important}
.bmr-today-col{background:#eff6ff!important}
th.bmr-today-col{background:linear-gradient(180deg,#dbeafe,#eff6ff)!important;color:#1d4ed8!important;font-weight:800!important;border-top:3px solid #3b82f6!important}
.bmr-day-num{display:block;font-size:12px;font-weight:700;line-height:1.1}
.bmr-day-name{display:block;font-size:9px;opacity:.7}

/* Tape view — available cells */
.bmr-cell-av{cursor:crosshair}
.bmr-cell-na{cursor:default}
.bmr-tape-av{height:8px;background:#bbf7d0;border-radius:3px;margin:13px 3px;opacity:.55;transition:all .12s}
.bmr-cell-av:hover .bmr-tape-av{opacity:1;background:#4ade80;height:10px;margin:12px 3px}
.bmr-tape-vd{height:8px;background:#fca5a5;border-radius:3px;margin:13px 3px;opacity:.7}
.bmr-tape-vc{height:8px;background:#7dd3fc;border-radius:3px;margin:13px 3px;opacity:.6}
.bmr-tape-oo{height:8px;background:#cbd5e1;border-radius:3px;margin:13px 3px;opacity:.5}
.bmr-tape-mn{height:8px;background:#c4b5fd;border-radius:3px;margin:13px 3px;opacity:.6}

/* Drag to create: highlight */
.bmr-drag-sel{background:#f0f0ff!important;cursor:crosshair}
.bmr-drag-sel .bmr-tape-av{opacity:1;background:linear-gradient(90deg,#818cf8,#4f46e5);height:10px;margin:12px 3px}

/* Reservation bar */
.bmr-res-td{cursor:pointer;padding:0;user-select:none}
.bmr-bar{height:22px;display:flex;align-items:center;margin:6px 0;position:relative;overflow:visible;transition:filter .12s}
.bmr-bar-movable{cursor:grab}
.bmr-bar-movable:active{cursor:grabbing}
.bmr-bar-ci{background:linear-gradient(90deg,#4f46e5,#6366f1);box-shadow:0 1px 4px rgba(79,70,229,.3)}
.bmr-bar-bk{background:linear-gradient(90deg,#f59e0b,#fbbf24);box-shadow:0 1px 4px rgba(245,158,11,.3)}
.bmr-bar-start .bmr-bar{border-radius:11px 0 0 11px;margin-left:4px}
.bmr-bar-end   .bmr-bar{border-radius:0 11px 11px 0;margin-right:4px}
.bmr-bar-only  .bmr-bar{border-radius:11px;margin-left:4px;margin-right:4px}
.bmr-bar-mid   .bmr-bar{border-radius:0;margin:6px -1px}
.bmr-bar-lbl{font-size:10px;font-weight:700;color:#fff;padding:0 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:88px;text-shadow:0 1px 2px rgba(0,0,0,.2)}
.bmr-res-td:hover .bmr-bar{filter:brightness(1.08)}

/* Resize handle */
.bmr-resize-right{position:absolute;right:0;top:0;bottom:0;width:7px;cursor:ew-resize;background:rgba(255,255,255,.25);border-radius:0 11px 11px 0;opacity:0;transition:opacity .12s;z-index:2}
.bmr-res-td:hover .bmr-resize-right{opacity:1}
.bmr-resize-preview{background:#fef9c3!important}
.bmr-resize-preview .bmr-tape-av,.bmr-resize-preview .bmr-bar{background:#fde68a!important}

/* Move drag feedback */
.bmr-dragging{opacity:.6}
.bmr-drop-target{background:#f0fdf4!important}

/* Tooltip */
.bmr-tooltip{position:fixed;z-index:9999;display:none;background:#1e293b;color:#f1f5f9;border-radius:10px;padding:12px 14px;min-width:190px;max-width:240px;box-shadow:0 8px 28px rgba(0,0,0,.35);pointer-events:none;font-size:12px;line-height:1.5}
.bmr-tip-guest{font-weight:800;font-size:13px;color:#fff;margin-bottom:7px;border-bottom:1px solid rgba(255,255,255,.1);padding-bottom:6px}
.bmr-tip-row{color:#cbd5e1;margin-bottom:2px}
.bmr-tip-row b{color:#e2e8f0;font-weight:600}
.bmr-tip-badge{display:inline-block;margin-top:7px;padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.bmr-tip-ci{background:#4f46e5;color:#fff}
.bmr-tip-bk{background:#f59e0b;color:#fff}
.bmr-tip-co{background:#10b981;color:#fff}

/* Arrivals / Departures */
.bmr-ad-panels{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:28px}
.bmr-ad-panel{
	background:linear-gradient(180deg,#ffffff,#f8fafc);
	border-radius:14px;border:1px solid #dbe4ef;
	box-shadow:0 2px 10px rgba(15,23,42,.08),0 12px 22px rgba(15,23,42,.04);
	overflow:hidden;
}
.bmr-ad-title{display:flex;align-items:center;gap:7px;padding:11px 16px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.06em}
.bmr-ad-list{padding:4px 0;max-height:220px;overflow-y:auto}
.bmr-ad-row{display:flex;align-items:center;gap:10px;padding:8px 16px;cursor:pointer;border-bottom:1px solid #f1f5f9;transition:background .12s}
.bmr-ad-row:last-child{border-bottom:none}
.bmr-ad-row:hover{background:#f8fafc}
.bmr-ad-rooms{font-size:11px;font-weight:700;color:#1e293b;min-width:55px;white-space:nowrap}
.bmr-ad-customer{flex:1;font-size:12px;color:#475569;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bmr-ad-empty{padding:28px 16px;text-align:center;color:#94a3b8;font-size:12px}
	.bmr-ad-pill{display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;min-width:88px;height:24px;padding:0 12px;border-radius:20px;font-size:11px;font-weight:700;line-height:1;white-space:nowrap}
	.bmr-ad-status{text-transform:uppercase;letter-spacing:.03em;cursor:default}
	.bmr-ad-action-btn{border:none;cursor:pointer;transition:all .12s}
	.bmr-ad-st-bk{background:#f59e0b;color:#fff}
	.bmr-ad-st-ci{background:#4f46e5;color:#fff}
	.bmr-ad-st-co{background:#10b981;color:#fff}
	.bmr-ad-checkin{background:#4f46e5;color:#fff}
	.bmr-ad-checkin:hover{background:#3730a3}
	.bmr-ad-checkout{background:#10b981;color:#fff}
.bmr-ad-checkout:hover{background:#059669}
.bmr-ad-action-btn:disabled{opacity:.5;cursor:default}
.bmr-hkb-fcount{font-weight:500;opacity:.75}

/* Charts */
.bmr-charts-row{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:28px}
.bmr-chart-card{
	background:linear-gradient(180deg,#ffffff,#f9fbff);
	border-radius:14px;box-shadow:0 2px 10px rgba(15,23,42,.08),0 12px 24px rgba(15,23,42,.04);
	padding:20px 20px 12px;border:1px solid #dbe4ef;
}
.bmr-chart-title{font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px}
.bmr-chart-empty{height:180px;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:13px}

/* Empty */
.bmr-empty{text-align:center;padding:60px 0;color:#64748b;font-size:14px}

@keyframes bmr-rise{
	from{opacity:0;transform:translateY(6px)}
	to{opacity:1;transform:translateY(0)}
}

@media(max-width:1100px){
  .bmr-top-row{grid-template-columns:1fr 260px}
}
@media(max-width:900px){
  .bmr-top-row{grid-template-columns:1fr}
  .bmr-hkb-panel{max-height:260px}
  .bmr-kpi-row{grid-template-columns:repeat(3,1fr)}
  .bmr-fin-row{grid-template-columns:1fr}
  .bmr-ad-panels,.bmr-charts-row{grid-template-columns:1fr}
}
@media(max-width:600px){
  .bmr-kpi-row{grid-template-columns:repeat(2,1fr)}
  .bmr-fin-amount{font-size:22px}
}
	`;
	document.head.appendChild(s);
}
