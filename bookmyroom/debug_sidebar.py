import frappe


def run():
	from frappe.boot import get_allowed_pages
	from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import auto_generate_sidebar_from_module

	# Check what auto_generate returns for Book My Room
	auto_sidebars = auto_generate_sidebar_from_module()
	bmr_auto = [s for s in auto_sidebars if s.title == "Book My Room"]
	print(f"[auto_generate] Book My Room entries: {len(bmr_auto)}")
	if bmr_auto:
		print(f"  Items count: {len(bmr_auto[0].items)}")
		for item in bmr_auto[0].items:
			print(f"    {item.type}: {item.label} -> {item.link_to}")

	# Check the full sidebar for book my room
	from frappe.boot import get_sidebar_items
	allowed_pages = get_allowed_pages(cache=False)
	sidebar = get_sidebar_items(allowed_pages)
	bmr_sidebar = sidebar.get("book my room")
	if bmr_sidebar:
		print(f"\n[get_sidebar_items] Book My Room items: {len(bmr_sidebar['items'])}")
		for item in bmr_sidebar["items"]:
			print(f"  {item.get('type')}: {item.get('label')} -> {item.get('link_to')}")
	else:
		print("\n[get_sidebar_items] 'book my room' NOT FOUND in sidebar dict")
		print("Available keys:", list(sidebar.keys()))
