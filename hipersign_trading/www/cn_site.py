"""v1.9.0 A6 (prototype C9): the site app for site engineers, project managers and storekeepers — check-in with GPS, gang
check-in of workers, DPR from today's check-ins, geo-tagged photos, site cash, deliveries (the driver's OTP) and site chat.
Data comes from hipersign_trading.api.construction_portal.sa_*. v1.9.2 U1: on the Hipersign app shell, installable."""

import frappe
from frappe import _

from hipersign_trading import apps_web

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/cn-site"
		raise frappe.Redirect
	from hipersign_trading.api import construction_portal as PT

	PT._site_user()
	apps_web.context(context, "site")
	context.title = _("Hipersign Site")
	return context
