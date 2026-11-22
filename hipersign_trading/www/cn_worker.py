"""v1.9.0 A6 (prototype C9): the worker app — no Frappe login: the worker signs in with the mobile number and the
four-digit PIN the site engineer set (Site & Worker App → Worker app). English, Malayalam, Tamil and Hindi; the wording
should be checked by native speakers before going live. v1.9.2 U1: on the Hipersign app shell, installable."""

from hipersign_trading import apps_web

no_cache = 1


def get_context(context):
	apps_web.context(context, "worker")
	context.title = "Hipersign Worker"
	return context
