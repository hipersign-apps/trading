"""v1.9.0 A6 (prototype C9): the construction client portal — the client's projects: progress and milestones, published
photos, RA bills (certified online by private clients), documents and weekly reports, variations, snags. Staff open it as a
preview of any client (Client Portal page → Preview)."""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_portal as PT

no_cache = 1
TABS = [("progress", "Progress", "progress"), ("bills", "RA bills", "bills"), ("documents", "Documents", "documents"), ("variations", "Variations", "vo"),
	("snags", "Snags", "snags"), ("cost", "Cost & margin", "cost")]


def get_context(context):
	customer, customers, preview = PT.portal_party("Customer")
	context.no_header = 1
	context.no_breadcrumbs = 1
	context.preview = preview
	context.parties = customers
	context.customer = customer
	context.feat = f = PT.client_features(customer)
	projects = frappe.get_all("Project", filters={"customer": customer, "hs_cn": 1}, fields=["name", "project_name", "hs_cn_govt", "expected_end_date", "hs_step"],
		order_by="expected_start_date desc")
	context.projects = projects
	pid = frappe.form_dict.get("project")
	p = next((x for x in projects if x.name == pid), projects[0] if projects else None)
	if not p:
		frappe.throw(_("No projects yet."))
	context.p = p
	context.govt = cint(p.hs_cn_govt)
	context.title = _("{0} — client portal").format(p.project_name)
	tabs = [(k, _(l)) for k, l, feat in TABS if f.get(feat) or (k == "progress" and (f.progress or f.photos))]
	context.tabs = tabs
	tab = frappe.form_dict.get("tab")
	context.tab = tab if tab in [k for k, _l in tabs] else (tabs[0][0] if tabs else None)
	F = CN.fig(p.name)
	context.F = F
	context.kpis = [(_("Contract (revised)"), CN.inr(F.revised), _("incl. approved variations")), (_("Work done"), f"{F.pct:.1f}%", CN.inr(F.work)),
		(_("Certified"), CN.inr(F.billed), _("{0} bills").format(F.bills)), (_("Paid"), CN.inr(F.received), ""),
		(_("Due to us"), CN.inr(F.outstanding), _("{0} overdue").format(CN.inr(F.overdue)) if F.overdue > 1 else "")]
	t = context.tab
	if t == "progress":
		context.milestones = frappe.get_all("Construction Milestone", filters={"project": p.name, "client_visible": 1},
			fields=["title", "planned", "forecast", "actual", "status"], order_by="planned asc") if f.progress else []
		context.photos = frappe.db.sql("""select c.name as pub, s.caption, s.location, s.taken_on from `tabClient Publication` c join `tabSite Photo` s on s.name = c.photo
			where c.project = %s and c.status = 'Published' order by s.taken_on desc limit 24""", p.name, as_dict=True) if f.photos else []
	elif t == "bills":
		context.bills = frappe.get_all("RA Bill", filters={"project": p.name, "status": ["!=", "Draft"]}, fields=["name", "bill_no", "period_to", "status", "claimed_amount",
			"certified_amount", "gst_amount", "net_receivable", "received_amount", "due_date", "sales_invoice", "submitted_on"], order_by="bill_no desc")
		context.can_certify = f.certify and not context.govt and not preview
	elif t == "documents":
		context.drawings = frappe.db.sql("""select c.name as pub, d.drawing_no, d.revision, d.title, d.discipline, d.gfc_on, d.file, c.published_on from `tabClient Publication` c
			join `tabConstruction Drawing` d on d.name = c.drawing where c.project = %s and c.status = 'Published' and d.status = 'GFC' order by d.drawing_no""", p.name, as_dict=True)
		context.reports = frappe.get_all("Client Publication", filters={"project": p.name, "kind": "Weekly report", "status": "Published"}, fields=["title", "content", "published_on"],
			order_by="week_start desc", limit=12)
	elif t == "variations":
		context.eis = frappe.get_all("Extra Item", filters={"project": p.name, "status": ["!=", "Draft"]}, fields=["name", "title", "kind", "amount", "status", "sent_on", "approved_on",
			"approved_by", "notes", "reference"], order_by="sent_on desc")
	elif t == "snags":
		context.snags = frappe.get_all("Snag", filters={"project": p.name}, fields=["name", "location", "trade", "description", "status", "raised_on", "target", "fixed_on"],
			order_by="raised_on desc", limit=100)
		context.trades = (frappe.get_meta("Snag").get_field("trade").options or "").split("\n")
	elif t == "cost":
		context.cost = F
	context.today = today()
	return context
