// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Guest Folio", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Sales Invoice"),
				() => {
					frappe.model.open_mapped_doc({
						method: "bookmyroom.book_my_room.doctype.guest_folio.guest_folio.make_sales_invoice_from_folio",
						frm,
					});
				},
				__("Create")
			);
		}
	},

	reservation(frm) {
		if (!frm.doc.reservation) return;
		// Auto-fill room from reservation items if only one room
		frappe.db
			.get_list("Room Reservation Item", {
				filters: { parent: frm.doc.reservation },
				fields: ["room"],
				limit: 2,
			})
			.then((rows) => {
				if (rows.length === 1) {
					frm.set_value("room", rows[0].room);
				}
			});
	},
});

frappe.ui.form.on("Guest Folio Item", {
	service(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.service) return;
		frappe.db.get_value("Hotel Service", row.service, ["rate", "service_name"]).then(({ message }) => {
			if (message) {
				frappe.model.set_value(cdt, cdn, "rate", message.rate || 0);
				if (!row.description) {
					frappe.model.set_value(cdt, cdn, "description", message.service_name);
				}
			}
		});
	},

	quantity(frm, cdt, cdn) {
		_recalculate_row(cdt, cdn);
		frm.trigger("_update_total");
	},

	rate(frm, cdt, cdn) {
		_recalculate_row(cdt, cdn);
		frm.trigger("_update_total");
	},

	items_remove(frm) {
		frm.trigger("_update_total");
	},

	_update_total(frm) {
		let total = 0;
		(frm.doc.items || []).forEach((row) => {
			total += flt(row.amount);
		});
		frm.set_value("total_amount", total);
	},
});

function _recalculate_row(cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.quantity) * flt(row.rate));
}
