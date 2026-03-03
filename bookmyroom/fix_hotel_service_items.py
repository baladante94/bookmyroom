"""
Create billing Items for all Hotel Services that don't have one,
and link them back to the Hotel Service record.
Run: bench --site bookmyroom.localhost execute bookmyroom.fix_hotel_service_items.run
"""
import frappe


def _ensure_item(item_code, item_name, uom="Nos"):
	"""Create an Item if it doesn't exist; always returns item_code."""
	if frappe.db.exists("Item", item_code):
		# Ensure it's not a stock item
		frappe.db.set_value("Item", item_code, "is_stock_item", 0)
		return item_code

	# Ensure "Services" item group exists
	if not frappe.db.exists("Item Group", "Services"):
		ig = frappe.get_doc({"doctype": "Item Group", "item_group_name": "Services", "parent_item_group": "All Item Groups"})
		ig.insert(ignore_permissions=True)

	# Ensure UOM exists
	if not frappe.db.exists("UOM", uom):
		frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)

	item = frappe.get_doc({
		"doctype": "Item",
		"item_code": item_code,
		"item_name": item_name,
		"item_group": "Services",
		"stock_uom": uom,
		"is_stock_item": 0,
		"is_sales_item": 1,
	})
	item.insert(ignore_permissions=True)
	return item_code


def run():
	frappe.set_user("Administrator")

	services = frappe.get_all(
		"Hotel Service",
		fields=["name", "service_name", "service_type", "billing_item"],
	)

	for svc in services:
		if svc.billing_item:
			print(f"  [--]  Already linked: {svc.name} → {svc.billing_item}")
			continue

		# Derive item_code from service name (max 140 chars)
		item_code = svc.service_name[:140]
		_ensure_item(item_code, svc.service_name)

		frappe.db.set_value("Hotel Service", svc.name, "billing_item", item_code)
		print(f"  [ok]  {svc.name} → {item_code}")

	frappe.db.commit()
	print("\nDone.")
