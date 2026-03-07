// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Booking Settings", {
	setup_billing_items_btn(frm) {
		const items = [
			"Room Charge, Early Check-in, Late Check-out, Extra Bed",
			"Breakfast (CP), Half Board (MAP), Full Board (AP), Room Service, Minibar",
			"Laundry, Telephone, Parking, Airport Transfer",
			"Spa & Wellness, Gym / Fitness, Swimming Pool Access",
		];

		frappe.confirm(
			`<p>This will create <strong>16 standard hotel billing items</strong> in your system:</p>
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
