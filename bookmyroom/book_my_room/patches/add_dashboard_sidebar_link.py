import frappe


def execute():
	# Insert "Room Status Dashboard" page link into the Book My Room sidebar
	# between "Front Desk" section and "Room Reservation"
	sidebar = frappe.get_doc("Workspace Sidebar", "Book My Room")

	# Check if already exists
	for item in sidebar.items:
		if item.label == "Room Status Dashboard":
			print("  [skip] Room Status Dashboard link already in sidebar.")
			return

	# Find the idx of "Room Reservation" to insert before it
	insert_before_idx = None
	for item in sidebar.items:
		if item.label == "Room Reservation":
			insert_before_idx = item.idx
			break

	if insert_before_idx is None:
		insert_before_idx = 3  # fallback: insert at position 3 (after Front Desk section break)

	# Shift all items at or after insert_before_idx down by 1
	for item in sidebar.items:
		if item.idx >= insert_before_idx:
			item.idx += 1

	sidebar.append("items", {
		"child": 1,
		"collapsible": 1,
		"icon": "monitor",
		"indent": 0,
		"keep_closed": 0,
		"label": "Room Status Dashboard",
		"link_to": "room-status-dashboard",
		"link_type": "Page",
		"show_arrow": 0,
		"type": "Link",
		"idx": insert_before_idx,
	})

	sidebar.save(ignore_permissions=True)
	frappe.db.commit()
	print("  [ok]  Room Status Dashboard sidebar link added.")
