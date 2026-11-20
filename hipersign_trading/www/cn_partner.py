"""v1.9.0 A6 (prototype C9): the subcontractor portal — the partner's work orders, running bills (submitted here), payments
with TDS and retention, labour documents and progress photos. Staff open it as a preview (Subcontractor Portal → Preview)."""

import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_portal as PT

no_cache = 1
TABS = [("orders", "Work orders"), ("bills", "Running bills"), ("payments", "Payments"), ("labour", "Labour documents"), ("photos", "Photos"), ("messages", "Messages")]


def get_context(context):
	supplier, suppliers, preview = PT.portal_party("Supplier")
	context.no_header = 1
	context.no_breadcrumbs = 1
	context.preview, context.parties, context.supplier = preview, suppliers, supplier
	context.title = _("{0} — partner portal").format(supplier)
	from hipersign_trading.api import construction_extra as X  # v1.9.1 B4: what this subcontractor may see and do

	context.feat = feat = X.partner_features(supplier)
	context.tabs = [(k, _(l)) for k, l in TABS if k == "orders" or feat.get(k)]
	tab = frappe.form_dict.get("tab")
	context.tab = tab if tab in dict(context.tabs) else "orders"
	context.today = today()
	wos = frappe.get_all("Subcontractor Work Order", filters={"supplier": supplier, "status": ["!=", "Draft"]}, fields=["name", "project", "scope", "kind", "status", "value",
		"retention_pct", "tds_pct", "start_date", "end_date"], order_by="wo_date desc")
	for w in wos:
		w.project_name = frappe.get_cached_value("Project", w.project, "project_name")
	context.wos = wos
	bills = frappe.get_all("Subcontractor Bill", filters={"supplier": supplier, "status": ["!=", "Cancelled"]}, fields=["name", "work_order", "project", "bill_no", "bill_date",
		"status", "gross", "taxable", "gst_amount", "tds", "retention", "net_payable", "compliance_hold", "partner_submitted", "partner_verified", "purchase_invoice",
		"payment_entry", "supplier_invoice_no"], order_by="bill_date desc")
	context.bills = bills
	paid = [b for b in bills if b.status == "Paid"]
	context.kpis = [(_("Work orders"), CN.inr(sum(flt(w.value) for w in wos)), _("{0} active").format(len([w for w in wos if w.status == "Active"]))),
		(_("Billed (net)"), CN.inr(sum(flt(b.net_payable) for b in bills)), _("{0} bills").format(len(bills))),
		(_("Paid"), CN.inr(sum(flt(b.net_payable) for b in paid)), ""),
		(_("Retention held"), CN.inr(sum(flt(b.retention) for b in bills if b.status in ("Approved", "Paid"))), _("released after the defects period")),
		(_("TDS deducted"), CN.inr(sum(flt(b.tds) for b in bills if b.status in ("Approved", "Paid"))), _("sec. 194C — in your Form 26AS"))]
	if not feat.retention:
		context.kpis = [k for k in context.kpis if k[0] != _("Retention held")]
	if not feat.payments:
		context.kpis = [k for k in context.kpis if k[0] != _("Paid")]
	context.held = [b for b in bills if b.compliance_hold]
	t = context.tab
	if t == "bills":
		wo = frappe.form_dict.get("wo")
		active = [w for w in wos if w.status == "Active"]
		context.active = active
		w = next((x for x in active if x.name == wo), None)
		if w:
			doc = frappe.get_doc("Subcontractor Work Order", w.name)
			prev = {}
			for b in frappe.get_all("Subcontractor Bill", filters={"work_order": w.name, "status": ["!=", "Cancelled"]}, pluck="name"):
				for i in frappe.get_doc("Subcontractor Bill", b).items:
					prev[i.item_no] = max(prev.get(i.item_no, 0), flt(i.cum_qty))
			context.form_wo = w
			context.form_items = [frappe._dict(item_no=i.item_no, description=i.description, unit=i.unit, rate=i.rate, qty=i.qty, prev=prev.get(i.item_no, 0),
				left=flt(i.qty) * 1.1 - prev.get(i.item_no, 0)) for i in doc.items]
	elif t == "payments":
		context.payments = frappe.get_all("Payment Entry", filters={"party_type": "Supplier", "party": supplier, "docstatus": 1}, fields=["name", "posting_date", "paid_amount",
			"reference_no", "mode_of_payment"], order_by="posting_date desc", limit=50)
	elif t == "labour":
		projects = sorted({w.project for w in wos if w.status == "Active"})
		context.lab_projects = [(p, frappe.get_cached_value("Project", p, "project_name")) for p in projects]
		context.months = [get_first_day(add_months(today(), -k)) for k in (1, 2, 3)]
		context.lcs = frappe.get_all("Labour Compliance", filters={"supplier": supplier}, fields=["name", "project", "month", "workers", "status", "partner_submitted",
			"wage_register_file", "pf_ecr_file", "esi_file", "verified_by"], order_by="month desc", limit=24)
	elif t == "photos":
		context.lab_projects = [(p, frappe.get_cached_value("Project", p, "project_name")) for p in sorted({w.project for w in wos if w.status == "Active"})]
		context.photos = frappe.get_all("Site Photo", filters={"supplier": supplier, "source": "Subcontractor portal"}, fields=["name", "caption", "project", "status", "taken_on"],
			order_by="taken_on desc", limit=40)
	elif t == "messages":
		context.msgs = X.messages("Supplier", supplier)
		context.lab_projects = [(p, frappe.get_cached_value("Project", p, "project_name")) for p in sorted({w.project for w in wos})]
	return context
