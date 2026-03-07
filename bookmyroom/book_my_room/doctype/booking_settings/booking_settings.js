// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Booking Settings", {
	setup_billing_items_btn(frm) {
		const items = [
			"Room Charge (12% GST), Room Charge – Luxury (18% GST), Early Check-in, Late Check-out, Extra Bed",
			"Breakfast (CP), Half Board (MAP), Full Board (AP), Room Service, Minibar",
			"Laundry, Telephone, Parking, Airport Transfer",
			"Spa & Wellness, Gym / Fitness, Swimming Pool Access",
		];

		frappe.confirm(
			`<p>This will create <strong>standard hotel billing items</strong> in your system:</p>
			<ul>
				<li><strong>Accommodation:</strong> ${items[0]}</li>
				<li><strong>Food & Beverage:</strong> ${items[1]}</li>
				<li><strong>Guest Services:</strong> ${items[2]}</li>
				<li><strong>Recreation & Wellness:</strong> ${items[3]}</li>
			</ul>
			<p>Each item will have the appropriate SAC code and GST rate assigned.</p>
			<p class="text-muted"><strong>Note:</strong> This action cannot be undone. Items must be deleted manually if no longer needed.</p>`,
			() => {
				frappe.call({
					method: "bookmyroom.book_my_room.doctype.booking_settings.booking_settings.setup_standard_billing_items",
					freeze: true,
					freeze_message: __("Importing standard billing items..."),
					callback(r) {
						if (!r.exc) {
							const count = r.message?.created ?? 0;
							frappe.msgprint({
								title: __("Done"),
								message: __("{0} billing item(s) imported successfully.", [count]),
								indicator: "green",
							});
							frm.reload_doc();
						}
					},
				});
			}
		);
	},
});

// Auto-fill tax_rate when an Item Tax Template is selected in the Tax Slabs table
frappe.ui.form.on("Room Tax Slab", {
	item_tax_template(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_tax_template) {
			frappe.model.set_value(cdt, cdn, "tax_rate", 0);
			return;
		}
		frappe.db
			.get_value("Item Tax Template", row.item_tax_template, "gst_rate")
			.then(({ message }) => {
				if (message?.gst_rate != null) {
					frappe.model.set_value(cdt, cdn, "tax_rate", flt(message.gst_rate));
				}
			});
	},
});
