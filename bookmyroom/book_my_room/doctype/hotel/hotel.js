// Copyright (c) 2026, Balamurugan and contributors
// For license information, please see license.txt

frappe.listview_settings["Hotel"] = {
	formatters: {
		attach_image(value) {
			if (value) {
				return `<img src="${value}" style="height: 40px; width: auto; border-radius: 4px;" />`;
			}
			return "";
		},
	},
};
