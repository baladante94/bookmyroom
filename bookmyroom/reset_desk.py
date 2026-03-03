"""Remove stale Desktop Icon and Workspace Sidebar records, then re-sync."""
import frappe


def run():
	frappe.set_user("Administrator")

	# Remove all stale desktop icon records for this app
	for name in frappe.db.get_all("Desktop Icon", filters={"app": "bookmyroom"}, pluck="name"):
		frappe.delete_doc("Desktop Icon", name, ignore_permissions=True, force=True)
		print(f"  [del] Desktop Icon: {name}")

	# Remove stale workspace sidebar records
	for name in frappe.db.get_all(
		"Workspace Sidebar",
		filters=[["name", "in", ["Book My Room", "Book My Room Final", "BMR"]]],
		pluck="name",
	):
		frappe.delete_doc("Workspace Sidebar", name, ignore_permissions=True, force=True)
		print(f"  [del] Workspace Sidebar: {name}")

	frappe.db.commit()
	print("Done — now run: bench sync-desktop-icons")
