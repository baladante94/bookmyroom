// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

// ─────────────────────────────────────────────────────────────────────────────
// State cached per-form to avoid redundant server fetches
// ─────────────────────────────────────────────────────────────────────────────
let _mealPlanRate = 0; // extra rate per person per night
let _defaultHotel = null;
let _defaultHotelLoaded = false;

frappe.ui.form.on("Room Reservation", {
	// ── Setup ──────────────────────────────────────────────────────────────── //

	setup(frm) {
		_set_room_query(frm);
	},

	// ── Lifecycle ──────────────────────────────────────────────────────────── //

	refresh(frm) {
		_refreshActionButtons(frm);
		_updateBalanceColor(frm);
		_loadTaxSlabs(frm);
		_apply_default_hotel(frm);

		// Pre-fill room from dashboard click (window._bmr_prefill_room set by workspace grid)
		if (frm.is_new() && window._bmr_prefill_room) {
			const room_name = window._bmr_prefill_room;
			window._bmr_prefill_room = null;
			// Frappe auto-adds one empty row; reuse it instead of adding a second
			const existing = frm.doc.items || [];
			const row =
				existing.length === 1 && !existing[0].room
					? existing[0]
					: frappe.model.add_child(frm.doc, "Room Reservation Item", "items");
			frm.refresh_field("items");
			frappe.model
				.set_value(row.doctype, row.name, "room", room_name)
				.then(() => frm.refresh_field("items"));
		}
	},

	// ── Field change handlers ──────────────────────────────────────────────── //

	hotel(frm) {
		_set_room_query(frm);
		if (!frm.doc.hotel) {
			frm.trigger("calculate_totals");
			return;
		}
		// Fetch default check-in/out times from Hotel
		frappe.db
			.get_value("Hotel", frm.doc.hotel, ["checkin_time", "checkout_time"])
			.then(({ message }) => {
				const cin_time = message?.checkin_time;
				const cout_time = message?.checkout_time;

				if (cin_time) {
					const cin_date = frm.doc.check_in
						? frm.doc.check_in.split(" ")[0]
						: frappe.datetime.get_today();
					_set_datetime_with_picker(frm, "check_in", cin_date + " " + cin_time);
				}

				if (cout_time) {
					const cout_date = frm.doc.check_out
						? frm.doc.check_out.split(" ")[0]
						: frappe.datetime.add_days(frappe.datetime.get_today(), 1);
					_set_datetime_with_picker(frm, "check_out", cout_date + " " + cout_time);
				}

				frm.trigger("calculate_totals");
			});
	},

	meal_plan(frm) {
		if (!frm.doc.meal_plan) {
			_mealPlanRate = 0;
			frm.trigger("calculate_totals");
			return;
		}
		frappe.db
			.get_value("Meal Plan", frm.doc.meal_plan, "extra_rate_per_person")
			.then(({ message }) => {
				_mealPlanRate = flt(message?.extra_rate_per_person);
				frm.trigger("calculate_totals");
			});
	},

	check_in(frm) {
		_set_room_query(frm);
		_check_backdated(frm);
		frm.trigger("calculate_totals");
		frm.trigger("_apply_rate_plan");
	},

	check_out(frm) {
		_set_room_query(frm);
		frm.trigger("calculate_totals");
	},

	num_adults(frm) {
		frm.trigger("calculate_totals");
	},

	num_children(frm) {
		frm.trigger("calculate_totals");
	},

	discount_type(frm) {
		frm.trigger("calculate_totals");
	},

	discount_percentage(frm) {
		frm.trigger("calculate_totals");
	},

	discount_value(frm) {
		frm.trigger("calculate_totals");
	},

	advance_amount(frm) {
		frm.trigger("calculate_totals");
	},

	// ── Core calculation ───────────────────────────────────────────────────── //

	/**
	 * Central recalculation handler.
	 * Mirrors the server-side calculate_totals() method for real-time feedback.
	 */
	calculate_totals(frm) {
		// Nights
		let nights = 0;
		if (frm.doc.check_in && frm.doc.check_out) {
			const start = moment(frm.doc.check_in, frappe.defaultDatetimeFormat);
			const end = moment(frm.doc.check_out, frappe.defaultDatetimeFormat);
			nights = Math.max(Math.round(end.diff(start, "hours") / 24), 1);
		}
		frm.set_value("total_nights", nights);

		// Room charges
		let room_total = 0;
		(frm.doc.items || []).forEach((row) => {
			const amount = flt(row.rate) * nights;
			frappe.model.set_value(row.doctype, row.name, "amount", amount);
			room_total += amount;
		});
		frm.set_value("total_amount", room_total);

		// Meal plan charges
		const total_persons = (frm.doc.num_adults || 1) + (frm.doc.num_children || 0);
		const meal_plan_amount = _mealPlanRate * total_persons * nights;
		frm.set_value("meal_plan_amount", meal_plan_amount);

		// Discount
		const subtotal = room_total + meal_plan_amount;
		let discount_amount = 0;
		if (frm.doc.discount_type === "Fixed Amount") {
			discount_amount = Math.min(flt(frm.doc.discount_value || 0), subtotal);
		} else {
			discount_amount = flt((subtotal * flt(frm.doc.discount_percentage || 0)) / 100);
		}
		frm.set_value("discount_amount", discount_amount);
		const after_discount = subtotal - discount_amount;

		// Tax — look up configured slab from Booking Settings (cached in frm._taxSlabs)
		let tax_rate = 0;
		let tax_desc = "";
		const rates = (frm.doc.items || []).map((r) => flt(r.rate)).filter((r) => r > 0);
		if (rates.length) {
			const avg = rates.reduce((a, b) => a + b, 0) / rates.length;
			const slabs = frm._taxSlabs || [];
			const match = slabs.find((s) => {
				const min = flt(s.min_tariff);
				const max = flt(s.max_tariff);
				return avg >= min && (max === 0 || avg <= max);
			});
			if (match) {
				tax_rate = flt(match.tax_rate);
				tax_desc = tax_rate === 0
					? __("GST Exempt")
					: match.item_tax_template
						? __("GST {0}% ({1})", [tax_rate, match.item_tax_template])
						: __("Tax {0}%", [tax_rate]);
			} else if (!slabs.length) {
				// Fallback if slabs not yet configured
				if (avg <= 1000) { tax_rate = 0; tax_desc = __("GST Exempt"); }
				else if (avg <= 7500) { tax_rate = 12; tax_desc = __("GST 12%"); }
				else { tax_rate = 18; tax_desc = __("GST 18%"); }
			}
		}
		const tax_amount = flt((after_discount * tax_rate) / 100);
		frm.set_value("tax_amount", tax_amount);
		frm.set_value("tax_description", tax_desc);

		// Grand total & balance
		const grand_total = after_discount + tax_amount;
		frm.set_value("grand_total", grand_total);
		frm.set_value("balance_due", grand_total - flt(frm.doc.advance_amount));

		_updateBalanceColor(frm);
	},

	// ── Rate plan helper ───────────────────────────────────────────────────── //

	/**
	 * When check_in changes, look for an active Rate Plan for each room's
	 * room_type and apply it automatically.
	 */
	_apply_rate_plan(frm) {
		if (!frm.doc.check_in || !frm.doc.hotel) return;
		const check_in_date = frm.doc.check_in.split(" ")[0];

		(frm.doc.items || []).forEach((row) => {
			if (!row.room_type) return;
			frappe
				.call({
					method: "bookmyroom.book_my_room.doctype.room_reservation.room_reservation.get_applicable_rate",
					args: {
						room_type: row.room_type,
						hotel: frm.doc.hotel,
						check_in_date,
					},
				})
				.then(({ message }) => {
					if (message != null) {
						frappe.model.set_value(row.doctype, row.name, "rate", message);
					}
				});
		});
	},
});

// ─────────────────────────────────────────────────────────────────────────────
// Child table handlers — Room Reservation Item
// ─────────────────────────────────────────────────────────────────────────────

frappe.ui.form.on("Room Reservation Item", {
	/**
	 * On room selection:
	 * 1. Fetch room_type from Room doc
	 * 2. Check for an active Rate Plan; fall back to default_rate from Room Type
	 * 3. Auto-set rate (triggers calculate_totals via rate handler)
	 */
	room(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.room) return;

		frappe.db
			.get_value("Room", row.room, ["room_type", "hotel"])
			.then(({ message }) => {
				if (!message?.room_type) return;
				frappe.model.set_value(cdt, cdn, "room_type", message.room_type);

				const check_in_date = frm.doc.check_in ? frm.doc.check_in.split(" ")[0] : null;
				const hotel = frm.doc.hotel || message.hotel;

				// Try Rate Plan first
				if (check_in_date && hotel) {
					return frappe
						.call({
							method: "bookmyroom.book_my_room.doctype.room_reservation.room_reservation.get_applicable_rate",
							args: {
								room_type: message.room_type,
								hotel,
								check_in_date,
							},
						})
						.then(({ message: planned_rate }) => {
							if (planned_rate != null) {
								frappe.model.set_value(cdt, cdn, "rate", planned_rate);
							} else {
								// Fall back to Room Type default
								return frappe.db
									.get_value("Room Type", message.room_type, "default_rate")
									.then(({ message: rt }) => {
										if (rt?.default_rate != null) {
											frappe.model.set_value(cdt, cdn, "rate", rt.default_rate);
										}
									});
							}
						});
				}

				// No check_in set yet — just use default rate
				return frappe.db
					.get_value("Room Type", message.room_type, "default_rate")
					.then(({ message: rt }) => {
						if (rt?.default_rate != null) {
							frappe.model.set_value(cdt, cdn, "rate", rt.default_rate);
						}
					});
			});
	},

	rate(frm) {
		frm.trigger("calculate_totals");
	},

	items_remove(frm) {
		frm.trigger("calculate_totals");
	},
});

// ─────────────────────────────────────────────────────────────────────────────
// Private helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Fetch room tax slabs from Booking Settings and cache on frm._taxSlabs.
 * Called once on refresh; slabs rarely change during a session.
 */
function _loadTaxSlabs(frm) {
	frappe.call({
		method: "bookmyroom.book_my_room.doctype.booking_settings.booking_settings.get_tax_slabs",
		callback({ message }) {
			frm._taxSlabs = message || [];
		},
	});
}

/**
 * Auto-apply Booking Settings.default_hotel on new reservations.
 * Applied only once per form load and never overrides an existing hotel.
 */
function _apply_default_hotel(frm) {
	if (!frm.is_new() || frm.doc.hotel || frm._default_hotel_applied || window._bmr_hotel) return;
	frm._default_hotel_applied = true;

	if (_defaultHotelLoaded) {
		if (_defaultHotel) {
			frm.set_value("hotel", _defaultHotel);
		}
		return;
	}

	frappe.call({
		method: "bookmyroom.book_my_room.doctype.booking_settings.booking_settings.get_booking_settings",
		callback({ message }) {
			_defaultHotelLoaded = true;
			_defaultHotel = message?.default_hotel || null;
			if (_defaultHotel && !frm.doc.hotel) {
				frm.set_value("hotel", _defaultHotel);
			}
		},
		error() {
			_defaultHotelLoaded = true;
		},
	});
}

/**
 * Set (or refresh) the room search query on the items child table.
 * Filters by hotel + status=Available and excludes rooms with overlapping bookings.
 */
function _set_room_query(frm) {
	frm.set_query("room", "items", function () {
		return {
			query: "bookmyroom.book_my_room.doctype.room_reservation.room_reservation.get_rooms_for_query",
			filters: {
				hotel: frm.doc.hotel || "",
				check_in: frm.doc.check_in || "",
				check_out: frm.doc.check_out || "",
				current_reservation: frm.doc.name || "__newdoc__",
			},
		};
	});
}

function _refreshActionButtons(frm) {
	const isSubmitted = frm.doc.docstatus === 1;
	const status = frm.doc.status;

	// ── Check In ─────────────────────────────────────────────────────────── //
	if (isSubmitted && status === "Booked") {
		frm
			.add_custom_button(__("Check In"), () => {
				frappe.confirm(__("Check in guest now?"), () => {
					frappe.call({ method: "do_check_in", doc: frm.doc }).then(() => frm.reload_doc());
				});
			})
			.addClass("btn-primary");

		frm.add_custom_button(__("No Show"), () => {
			frappe.confirm(
				__("Mark this reservation as No Show? Rooms will be freed."),
				() => frappe.call({ method: "mark_no_show", doc: frm.doc }).then(() => frm.reload_doc())
			);
		});

		// Record Advance Payment — only if advance amount is set and no PE linked yet
		if (flt(frm.doc.advance_amount) > 0 && !frm.doc.advance_payment_entry) {
			frm.add_custom_button(__("Record Advance"), () => {
				frappe.confirm(
					__("Create a Payment Entry for the advance amount of {0}?", [
						format_currency(frm.doc.advance_amount),
					]),
					() => {
						frappe
							.call({ method: "make_advance_payment_entry", doc: frm.doc })
							.then(({ message }) => {
								if (message) {
									frappe.set_route("Form", "Payment Entry", message);
								}
							});
					}
				);
			}, __("Create"));
		}
	}

	// ── Post Service Charge (during stay) ────────────────────────────────── //
	if (isSubmitted && status === "Checked In") {
		frm.add_custom_button(__("Post Service Charge"), () => _openFolioDialog(frm));
		frm.add_custom_button(__("Extend Stay"), () => _openExtendStayDialog(frm));
	}

	// ── Check Out ────────────────────────────────────────────────────────── //
	if (isSubmitted && status === "Checked In") {
		frm
			.add_custom_button(__("Check Out"), () => {
				frappe.confirm(
					__("Check out guest and create housekeeping tasks?"),
					() =>
						frappe
							.call({ method: "do_check_out", doc: frm.doc })
							.then(() => frm.reload_doc())
				);
			})
			.addClass("btn-warning");
	}

	// ── Billing: always show Room Invoice when submitted ──────────────────── //
	if (isSubmitted) {
		frm.add_custom_button(
			__("Room Invoice"),
			() => {
				frappe.model.open_mapped_doc({
					method: "bookmyroom.book_my_room.doctype.room_reservation.room_reservation.make_sales_invoice",
					frm,
				});
			},
			__("Create")
		);

		// Check if any folios exist for this reservation (any status)
		frappe
			.call({
				method: "bookmyroom.book_my_room.doctype.room_reservation.room_reservation.get_folios_for_reservation",
				args: { reservation: frm.doc.name },
			})
			.then(({ message: folios }) => {
				if (!folios || folios.length === 0) return;

				const folioTotal = folios.reduce((s, f) => s + (f.total_amount || 0), 0);
				const label = __("Room + Folio Invoice ({0} folio{1}, {2})", [
					folios.length,
					folios.length > 1 ? "s" : "",
					format_currency(folioTotal),
				]);

				frm.add_custom_button(label, () => _createCombinedInvoice(frm), __("Create"));
			});
	}
}

function _createCombinedInvoice(frm) {
	frappe.confirm(
		__(
			"Create one invoice with room charges + all folio service charges? " +
				"Any unsettled folios will be automatically settled."
		),
		() => {
			frappe.call({
				method: "bookmyroom.book_my_room.doctype.room_reservation.room_reservation.make_combined_invoice",
				args: { source_name: frm.doc.name },
				callback({ message }) {
					if (message) {
						frappe.set_route("Form", "Sales Invoice", message);
					}
				},
			});
		}
	);
}

/**
 * Open a quick-charge dialog to post an ad-hoc charge via a new Guest Folio.
 */
function _openFolioDialog(frm) {
	const rooms = (frm.doc.items || []).map((r) => r.room).filter(Boolean);

	const dialog = new frappe.ui.Dialog({
		title: __("Post Folio Charge"),
		fields: [
			{
				label: __("Room"),
				fieldname: "room",
				fieldtype: "Select",
				options: rooms.join("\n"),
				reqd: 1,
				default: rooms[0] || "",
			},
			{
				label: __("Service"),
				fieldname: "service",
				fieldtype: "Link",
				options: "Hotel Service",
				filters: { is_active: 1 },
			},
			{
				label: __("Quantity"),
				fieldname: "quantity",
				fieldtype: "Float",
				default: 1,
				reqd: 1,
			},
			{
				label: __("Rate"),
				fieldname: "rate",
				fieldtype: "Currency",
				reqd: 1,
			},
			{
				label: __("Amount"),
				fieldname: "amount",
				fieldtype: "Currency",
				read_only: 1,
			},
			{
				label: __("Description"),
				fieldname: "description",
				fieldtype: "Data",
				reqd: 1,
			},
		],
		primary_action_label: __("Post Charge"),
		primary_action(values) {
			frappe
				.call({
					method: "frappe.client.insert",
					args: {
						doc: {
							doctype: "Guest Folio",
							reservation: frm.doc.name,
							room: values.room,
							folio_date: frappe.datetime.get_today(),
							status: "Open",
							items: [
								{
									service: values.service || null,
									description: values.description,
									posting_date: frappe.datetime.get_today(),
									quantity: values.quantity,
									rate: values.rate,
									amount: values.quantity * values.rate,
								},
							],
						},
					},
				})
				.then(({ message }) => {
					dialog.hide();
					frappe.msgprint(
						__("Folio charge posted: {0}", [
							`<a href="/app/guest-folio/${message.name}">${message.name}</a>`,
						]),
						__("Success")
					);
					frm.reload_doc();
				});
		},
	});

	// Auto-fill rate when service is picked
	dialog.fields_dict.service.df.onchange = function () {
		const svc = dialog.get_value("service");
		if (!svc) return;
		frappe.db.get_value("Hotel Service", svc, ["rate", "service_name"]).then(({ message }) => {
			if (message) {
				dialog.set_value("rate", message.rate || 0);
				if (!dialog.get_value("description")) {
					dialog.set_value("description", message.service_name);
				}
				_recalcDialogAmount(dialog);
			}
		});
	};

	dialog.fields_dict.quantity.df.onchange = () => _recalcDialogAmount(dialog);
	dialog.fields_dict.rate.df.onchange = () => _recalcDialogAmount(dialog);

	dialog.show();
}

function _recalcDialogAmount(dialog) {
	const qty = flt(dialog.get_value("quantity"));
	const rate = flt(dialog.get_value("rate"));
	dialog.set_value("amount", qty * rate);
}

/**
 * Client-side guard: warn + clear check_in if backdated booking is blocked.
 * The server re-validates on save; this gives instant feedback.
 */
function _check_backdated(frm) {
	if (!frm.doc.check_in) return;
	const check_in_date = frm.doc.check_in.split(" ")[0];
	const today = frappe.datetime.get_today();
	if (check_in_date >= today) return; // not backdated
	frappe.db
		.get_single_value("Booking Settings", "block_backdated_booking")
		.then((blocked) => {
			if (blocked) {
				frappe.msgprint({
					title: __("Backdated Booking Blocked"),
					message: __(
						"Check-in date cannot be earlier than today. Backdated bookings are disabled in <b>Booking Settings</b>."
					),
					indicator: "red",
				});
				frm.set_value("check_in", "");
			}
		});
}

/** Highlight balance_due in red when the guest still owes money. */
function _updateBalanceColor(frm) {
	const balance = flt(frm.doc.balance_due);
	if (!frm.fields_dict.balance_due) return;
	const $field = frm.fields_dict.balance_due.$wrapper;
	$field.find(".control-value").css("color", balance > 0 ? "var(--red-600)" : "var(--green-600)");
}

function _openExtendStayDialog(frm) {
	const currentCheckOut = frm.doc.check_out ? frm.doc.check_out.split(" ")[0] : "";
	const currentTime = frm.doc.check_out ? frm.doc.check_out.split(" ")[1] || "11:00:00" : "11:00:00";

	const dialog = new frappe.ui.Dialog({
		title: __("Extend Stay"),
		fields: [
			{
				label: __("Current Check-Out"),
				fieldname: "current_check_out",
				fieldtype: "Data",
				read_only: 1,
				default: frm.doc.check_out || "",
			},
			{
				label: __("New Check-Out Date"),
				fieldname: "new_check_out_date",
				fieldtype: "Date",
				reqd: 1,
				default: frappe.datetime.add_days(currentCheckOut, 1),
			},
		],
		primary_action_label: __("Extend"),
		primary_action(values) {
			const newCheckOut = values.new_check_out_date + " " + currentTime;
			frappe
				.call({
					method: "extend_stay",
					doc: frm.doc,
					args: { new_check_out: newCheckOut },
				})
				.then(() => {
					dialog.hide();
					frm.reload_doc();
				});
		},
	});
	dialog.show();
}

function _set_datetime_with_picker(frm, fieldname, value) {
	// set doc value normally
	frm.doc[fieldname] = value;

	// update control UI
	const field = frm.fields_dict[fieldname];
	if (!field || !field.datepicker) return;

	// convert to JS Date
	const dt = frappe.datetime.str_to_obj(value);

	// sync Air Datepicker internal state
	field.datepicker.selectDate(dt);

	field.refresh();
}
