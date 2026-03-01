"""Refresh Installed Applications and clear cache."""
import frappe


def run():
	frappe.get_doc("Installed Applications", "Installed Applications").update_versions()
	frappe.db.commit()
	print("Installed Applications updated.")
