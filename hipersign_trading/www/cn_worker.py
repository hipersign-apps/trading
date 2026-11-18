"""v1.9.0 A6 (prototype C9): the worker app — no Frappe login: the worker signs in with the mobile number and the
four-digit PIN the site engineer set (Site & Worker App → Worker app). English, Malayalam, Tamil and Hindi; the wording
should be checked by native speakers before going live."""

no_cache = 1


def get_context(context):
	context.no_header = 1
	context.no_breadcrumbs = 1
	context.title = "Hipersign Worker"
	return context
