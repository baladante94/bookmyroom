import frappe

no_cache = 1
allow_guest = True

def get_context(context):
	context.no_cache = 1
	context.hotels = frappe.get_all(
		"Hotel",
		fields=["name", "hotel_name", "city", "country", "star_rating"],
		order_by="hotel_name asc",
		ignore_permissions=True,
	)
