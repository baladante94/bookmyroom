// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hotel", {
	item_tax_template(frm) {
		if (!frm.doc.item_tax_template) {
			frm.set_value("tax_rate", 0);
			return;
		}
		frappe.db
			.get_value("Item Tax Template", frm.doc.item_tax_template, "gst_rate")
			.then(({ message }) => {
				if (message && message.gst_rate != null) {
					frm.set_value("tax_rate", flt(message.gst_rate));
				}
			});
	},
});

frappe.listview_settings['Hotel'] = {
    formatters: {
        attach_image(value) {
            if (value) {
                return `<img src="${value}" style="height: 40px; width: auto; border-radius: 4px;" />`;
            }
            return '';
        }
    }
};