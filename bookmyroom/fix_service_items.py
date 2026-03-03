"""
Fix all billing Items linked to Hotel Services and Room Types:
- Set is_stock_item = 0  (service items never carry inventory)
- Set item_group = "Services" if currently "All Item Groups"
Run: bench --site bookmyroom.localhost execute bookmyroom.fix_service_items.run
"""
import frappe


def run():
	frappe.set_user("Administrator")
	fixed = []

	# Collect billing items from Hotel Services
	hs_items = frappe.db.get_all("Hotel Service", filters={"billing_item": ["!=", ""]}, pluck="billing_item")

	# Collect billing items from Room Types
	rt_items = frappe.db.get_all("Room Type", filters={"billing_item": ["!=", ""]}, pluck="billing_item")

	all_items = list(set(filter(None, hs_items + rt_items)))

	for item_code in all_items:
		if not frappe.db.exists("Item", item_code):
			print(f"  [skip] Item not found: {item_code}")
			continue
		item = frappe.get_doc("Item", item_code)
		changed = False
		if item.is_stock_item:
			item.is_stock_item = 0
			changed = True
		if item.item_group in ("All Item Groups", None, ""):
			item.item_group = "Services"
			changed = True
		if changed:
			item.save(ignore_permissions=True)
			fixed.append(item_code)
			print(f"  [ok]  Fixed: {item_code}")
		else:
			print(f"  [--]  Already correct: {item_code}")

	frappe.db.commit()
	print(f"\nDone — {len(fixed)} item(s) updated.")
