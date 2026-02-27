// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Room Reservation", {
	refresh(frm) {
		// Show "Create > Sales Invoice" button only on submitted, active reservations
		if (frm.doc.docstatus === 1 && !["Cancelled", "Checked Out"].includes(frm.doc.status)) {
			frm.add_custom_button(
				__("Sales Invoice"),
				() => {
					frappe.model.open_mapped_doc({
						method:
							"bookmyroom.book_my_room.doctype.room_reservation.room_reservation.make_sales_invoice",
						frm,
					});
				},
				__("Create")
			);
		}
	},

	check_in(frm) {
		frm.trigger("calculate_totals");
	},

	check_out(frm) {
		frm.trigger("calculate_totals");
	},

	/**
	 * Central calculation handler.
	 * Derives total_nights from the datetime difference, then iterates
	 * every child row to recompute amount and accumulate total_amount.
	 */
	calculate_totals(frm) {
		let nights = 0;

		if (frm.doc.check_in && frm.doc.check_out) {
			const start = moment(frm.doc.check_in, frappe.defaultDatetimeFormat);
			const end = moment(frm.doc.check_out, frappe.defaultDatetimeFormat);
			nights = Math.max(Math.round(end.diff(start, "hours") / 24), 1);
		}

		frm.set_value("total_nights", nights);

		let total = 0;
		(frm.doc.items || []).forEach((row) => {
			const amount = flt(row.rate) * nights;
			frappe.model.set_value(row.doctype, row.name, "amount", amount);
			total += amount;
		});

		frm.set_value("total_amount", total);
	},
});

frappe.ui.form.on("Room Reservation Item", {
	/**
	 * On room selection: fetch room_type via the Room doc, then fetch
	 * the default_rate from Room Type and set it on the child row.
	 * rate's change handler then fires calculate_totals.
	 */
	room(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.room) return;

		frappe.db
			.get_value("Room", row.room, "room_type")
			.then(({ message }) => {
				if (!message?.room_type) return;

				frappe.model.set_value(cdt, cdn, "room_type", message.room_type);

				return frappe.db.get_value("Room Type", message.room_type, "default_rate");
			})
			.then((result) => {
				if (result?.message?.default_rate != null) {
					// Triggers the rate handler below, which calls calculate_totals
					frappe.model.set_value(cdt, cdn, "rate", result.message.default_rate);
				}
			});
	},

	rate(frm) {
		frm.trigger("calculate_totals");
	},

	items_remove(frm) {
		frm.trigger("calculate_totals");
	},
});
