import frappe

from hipersign_trading import apps_web

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/driver"
		raise frappe.Redirect
	apps_web.context(context, "driver")  # v1.9.2 U1: on the Hipersign app shell, installable
	context.title = "Hipersign Driver"
	context.full_name = frappe.utils.get_fullname()
	return context
