"""v1.9.0 (prototype C11): Construction (India) — the rules behind the Construction pages.

One place for
  · the tender register: bid / no-bid, submission, evaluation, award (which makes the project) or loss, EMD,
  · the measurement book: dimensions → quantity, the QS check and the client's check, the BOQ measured % it moves,
  · the running account (RA) bill: measured quantities this bill and to date, extra items, the client's certified amount,
    GST, and the deductions an Indian client makes — retention, mobilisation advance recovery, TDS u/s 194C, GST-TDS
    (sec. 51, government clients) and BOCW labour cess (government clients),
  · extra items and deviations (they raise the revised contract), hindrances (days lost, extension of time) and the DPR,
  · the figures and red flags every Construction page shows.

Built on ERPNext + India Compliance: Project, Project BOQ (shared with the Projects pages), Sales Invoice (GST through the
India Compliance "Output GST In-state / Out-state" templates, SAC of the works), Payment Entry, Bank Guarantee, GL Entry
(cost by project, api.projects.cost_of). The app adds Tender, Measurement Book, RA Bill, Extra Item, Hindrance and Daily
Progress Report.

Posting
  RA bill → tax invoice   Dr Client (certified + GST) · Cr Contract Revenue (certified) · Cr Output CGST + SGST (or IGST)
  receipt                 Dr Bank (net) · Dr TDS Receivable (194C) · Dr GST-TDS Receivable · Dr Retention Receivable
                          · Dr Mobilisation Advance Received (recovery) · Dr BOCW Labour Cess · Cr Client
  mobilisation advance    Dr Bank · Cr Mobilisation Advance Received (recovered from each RA bill)
The client deducts retention, TDS, cess and the advance when it pays, so the tax invoice carries the full value and GST
(as Indian contractors invoice), and the deductions are the receipt's deduction rows.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from hipersign_trading.api import projects as P

MD, PM, PMS, QS, SE, AM, AU = ("Managing Director", "Project Manager", "Projects Manager", "Quantity Surveyor", "Site Engineer",
	"Accounts Manager", "Accounts User")
CERTIFIED = ("Certified", "Invoiced", "Part paid", "Paid")
LIVE_BILL = ("Submitted to client",) + CERTIFIED
OPEN_TENDER = ("Bid / no-bid", "Being priced", "Submitted", "Technical evaluation", "Financial evaluation", "L1 — LOA awaited")
EVAL_NEXT = {"Submitted": "Technical evaluation", "Technical evaluation": "Financial evaluation", "Financial evaluation": "L1 — LOA awaited"}
# SAC of the works by project category (India Compliance checks the code)
SAC = {"Apartment complexes": "995412", "Villas & individual houses": "995411", "Industrial buildings": "995413", "Commercial buildings": "995414",
	"Hospitals": "995415", "Institutional buildings": "995415", "Interior fit-out": "995469", "MEP projects": "995463", "Roads and highways": "995421",
	"Infrastructure": "995429"}

# The process on the "How it works" tab: (stage, what happens, who, documents, approval)
STAGES = [
	("Tender", "Tender found on the e-procurement portal or a private enquiry; bid / no-bid; site visit, estimate and EMD; bid submitted; technical and financial evaluation.",
		"Estimator · Quantity Surveyor", "Tender, EMD (online or bank guarantee), priced BOQ", "Managing Director — bid / no-bid and the quoted price"),
	("Award & agreement", "Letter of acceptance, agreement, performance bank guarantee; the tender becomes a project with its contract value and BOQ.",
		"Managing Director · Finance", "LOA, agreement, performance BG, Project, Project BOQ", "Managing Director"),
	("Mobilisation", "Mobilisation advance against an advance bank guarantee; site handed over; labour, plant and stores set up.",
		"Project Manager · Finance", "Advance BG, advance receipt (journal)", "Finance Manager"),
	("Measure", "The site engineer records work in the measurement book (dimensions or BBS); the QS checks it, then the client's engineer.",
		"Site Engineer · Quantity Surveyor · Engineer-in-charge", "Measurement Book", "QS check, then the client's check"),
	("RA bill", "Checked measurements become the next running account bill — this bill and up to date, extra items, GST and the client's deductions.",
		"Quantity Surveyor", "RA Bill", "Project Manager submits; the client certifies (and may cut)"),
	("Invoice & collect", "The certified bill becomes the GST tax invoice from the branch GSTIN; the client pays the net after retention, advance recovery, TDS, GST-TDS and cess.",
		"Accountant", "Sales Invoice, Payment Entry with deductions", "Accounts Manager"),
	("Reconcile tax", "TDS (194C) is matched with Form 26AS and GST-TDS with GSTR-2X; missing credits are chased with the client.",
		"Accountant", "Form 26AS, GSTR-2X", "None"),
	("Complete & DLP", "Final bill, completion certificate, half the retention at completion and half after the defects liability period; BGs released.",
		"Project Manager · Finance", "Final RA bill, completion certificate, retention release", "Managing Director"),
]


def _has(*roles):
	return P._has(*roles)


def _need(roles, what):
	P._need(roles, what)


def is_cn(project):
	return bool(project) and cint(frappe.get_cached_value("Project", project, "hs_cn")) == 1


def project_names(cos=None, include_closed=True):
	"""The Construction (India) projects of the scope's companies; when the scope has none, every one the user may read."""
	if not frappe.get_meta("Project").has_field("hs_cn"):
		return []
	f = {"hs_cn": 1}
	if not include_closed:
		f["hs_step"] = ["<", 26]
	fields = ["name", "hs_step", "hs_contract_value"]
	rows = frappe.get_list("Project", filters=dict(f, company=["in", cos]) if cos else f, fields=fields, limit_page_length=0)
	if not rows and cos:
		rows = frappe.get_list("Project", filters=f, fields=fields, limit_page_length=0)
	rank = {"Execution": 0, "Mobilising": 1, "Handover": 2, "Tender": 3, "Closed": 4}
	rows.sort(key=lambda r: (rank[P.status_of(r.hs_step)], -flt(r.hs_contract_value), r.name))
	return [r.name for r in rows]


def inr(v, cur="INR"):
	"""₹1.86 Cr · ₹45.2 L · ₹12,500 — Indian compact amounts."""
	v = flt(v)
	sym = "₹" if cur == "INR" else (cur + " ")
	a = abs(v)
	if a >= 1e7:
		return f"{sym}{v / 1e7:.2f} Cr".replace(".00 Cr", " Cr")
	if a >= 1e5:
		return f"{sym}{v / 1e5:.1f} L".replace(".0 L", " L")
	return f"{sym}{frappe.utils.fmt_money(v, 0, 'INR').replace('₹', '').strip()}" if cur == "INR" else f"{sym}{v:,.0f}"


# ---------------------------------------------------------------- accounts, items
def accounts(company):
	cache = P._local("hs_cn_acc")
	if company in cache:
		return cache[company]
	base = P.accounts(company)
	cur_assets = P._group(company, "Asset", ("Tax Assets", "Current Assets"))
	cur_liab = P._group(company, "Liability", ("Current Liabilities",))
	exp = P._group(company, "Expense", ("Direct Expenses", "Expenses"))
	a = frappe._dict(
		revenue=base.revenue,
		retention=base.retention,
		tds=P._account(company, "TDS Receivable - 194C", "Asset", cur_assets),
		gst_tds=P._account(company, "GST-TDS Receivable", "Asset", cur_assets),
		advance=P._account(company, "Mobilisation Advance Received", "Liability", cur_liab),
		cess=P._account(company, "BOCW Labour Cess", "Expense", exp, "Expense Account"),
		heads=base.heads,
	)
	cache[company] = a
	return a


def bank_account(company):
	co = frappe.get_cached_doc("Company", company)
	return co.default_bank_account or frappe.db.get_value("Account", {"company": company, "account_type": "Bank", "is_group": 0}, "name", order_by="lft asc") \
		or co.default_cash_account


def works_item(category):
	"""The non-stock service item an RA bill invoices, one per SAC (works contract services)."""
	sac = SAC.get(category or "", "995414")
	if not frappe.db.exists("GST HSN Code", sac):
		sac = "995411" if frappe.db.exists("GST HSN Code", "995411") else None
	code = f"CN-WORKS-{sac or 'GEN'}"
	if frappe.db.exists("Item", code):
		return code
	grp = "Services" if frappe.db.exists("Item Group", "Services") else frappe.db.get_value("Item Group", {"is_group": 0}, "name")
	it = frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": _("Works contract services") + (f" (SAC {sac})" if sac else ""), "item_group": grp,
		"stock_uom": "Nos", "is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 0, "include_item_in_manufacturing": 0,
		"description": _("Construction works — running account bills")})
	if sac and frappe.get_meta("Item").has_field("gst_hsn_code"):
		it.gst_hsn_code = sac
	it.flags.ignore_permissions = True
	it.insert()
	return code


def _tax_template(company, company_address=None, customer=None):
	"""India Compliance's output GST template: in-state when the client's billing state is the branch's state."""
	inn = frappe.db.get_value("Sales Taxes and Charges Template", {"company": company, "title": ["like", "Output GST In-state%"], "disabled": 0}, "name") \
		or frappe.db.get_value("Sales Taxes and Charges Template", {"company": company, "name": ["like", "Output GST In-state%"]}, "name")
	out = frappe.db.get_value("Sales Taxes and Charges Template", {"company": company, "name": ["like", "Output GST Out-state%"]}, "name")
	if not (company_address and customer and out):
		return inn
	cs = frappe.db.get_value("Address", company_address, "gst_state") if frappe.get_meta("Address").has_field("gst_state") else None
	ca = _customer_address(customer)
	ps = frappe.db.get_value("Address", ca, "gst_state") if ca and cs else None
	return out if cs and ps and cs != ps else inn


def branch_address(company, customer=None):
	"""The company's GST registration (company address) in the client's state, else its first one — where a quotation or
	invoice to that client is issued from."""
	rows = frappe.db.sql("""select a.name, a.gst_state from `tabAddress` a join `tabDynamic Link` l on l.parent = a.name and l.parenttype = 'Address'
		where l.link_doctype = 'Company' and l.link_name = %s and a.is_your_company_address = 1 and a.disabled = 0 order by a.creation asc""", company, as_dict=True) \
		if frappe.get_meta("Address").has_field("gst_state") else []
	if not rows:
		return None
	ca = _customer_address(customer) if customer else None
	st = frappe.db.get_value("Address", ca, "gst_state") if ca else None
	return next((r.name for r in rows if st and r.gst_state == st), rows[0].name)


def _customer_address(customer):
	return frappe.db.get_value("Dynamic Link", {"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"}, "parent")


# ---------------------------------------------------------------- the BOQ (Project BOQ, shared with the Projects pages)
def boq(project):
	n = frappe.db.get_value("Project BOQ", {"project": project, "status": ["!=", "Superseded"]}, "name", order_by="revision desc, creation desc") \
		if frappe.get_meta("Project BOQ").has_field("revision") else frappe.db.get_value("Project BOQ", {"project": project}, "name")
	return frappe.get_doc("Project BOQ", n) if n else None


def boq_line(project, item_no):
	b = boq(project)
	if not b:
		return None, None
	for r in b.items:
		if r.item_no == item_no:
			return b, r
	return b, None


def billed_qty(project, item_no):
	"""Quantity up to date on the latest certified RA bill of the item."""
	r = frappe.db.sql("""select i.cum_qty from `tabRA Bill Item` i join `tabRA Bill` b on b.name = i.parent
		where b.project = %s and i.item_no = %s and b.status in %s order by b.bill_no desc limit 1""", (project, item_no, CERTIFIED))
	return flt(r[0][0]) if r else 0.0


def measured_qty(project, item_no, statuses=("Client checked",), exclude=None):
	"""Work measured to date: what the certified bills hold, plus the measurements not on a certified bill yet."""
	mb = flt(frappe.db.sql("""select sum(m.qty) from `tabMeasurement Book` m left join `tabRA Bill` b on b.name = m.ra_bill
		where m.project = %s and m.item_no = %s and m.status in %s and m.name != %s and (m.ra_bill is null or m.ra_bill = '' or b.status not in %s)""",
		(project, item_no, tuple(statuses), exclude or "", CERTIFIED))[0][0])
	return billed_qty(project, item_no) + mb


def sync_boq(project, item_nos=None):
	"""BOQ measured % from the client-checked measurements (lump-sum lines keep the % typed on the BOQ)."""
	b = boq(project)
	if not b:
		return
	changed = False
	for r in b.items:
		if item_nos and r.item_no not in item_nos:
			continue
		if (r.unit or "").upper() == "LS" or not flt(r.qty):
			continue
		if not frappe.db.exists("Measurement Book", {"project": project, "item_no": r.item_no}):
			continue
		m = measured_qty(project, r.item_no)
		pct = flt(m / flt(r.qty) * 100, 2)
		if abs(flt(r.measured_pct) - pct) > 0.005:
			r.measured_pct, changed = pct, True
	if changed:
		b.flags.ignore_permissions = True
		b.save()


# ---------------------------------------------------------------- validation (called from the doctypes)
def validate_doc(doc):
	from hipersign_trading.api import construction_biz as B

	from hipersign_trading.api import construction_site as S  # v1.9.0 A3

	if doc.doctype in S.VALIDATE:
		return S.VALIDATE[doc.doctype](doc)
	from hipersign_trading.api import construction_qhse as Q  # v1.9.0 A4

	if doc.doctype in Q.VALIDATE:
		return Q.VALIDATE[doc.doctype](doc)
	from hipersign_trading.api import construction_fin as FN  # v1.9.0 A5

	if doc.doctype in FN.VALIDATE:
		return FN.VALIDATE[doc.doctype](doc)
	from hipersign_trading.api import construction_portal as PT  # v1.9.0 A6

	if doc.doctype in PT.VALIDATE:
		return PT.VALIDATE[doc.doctype](doc)
	from hipersign_trading.api import construction_est as EST  # v1.9.1 B1

	if doc.doctype in EST.VALIDATE:
		return EST.VALIDATE[doc.doctype](doc)
	from hipersign_trading.api import construction_ctl as CTL  # v1.9.1 B2

	if doc.doctype in CTL.VALIDATE:
		return CTL.VALIDATE[doc.doctype](doc)
	fn = {"Tender": _v_tender, "Measurement Book": _v_mb, "RA Bill": ra_compute, "Extra Item": _v_ei, "Hindrance": _v_hin,
		"Daily Progress Report": _v_dpr, "Construction Contract": B.contract_validate, "Contract Claim": _v_claim}.get(doc.doctype)
	if fn:
		fn(doc)


def EST_ACTIONS():
	from hipersign_trading.api import construction_est as EST  # v1.9.1 B1: estimating

	from hipersign_trading.api import construction_ctl as CTL  # v1.9.1 B2: tracker, risks, meetings, advance, final bill

	return dict(EST.ACTIONS, **CTL.ACTIONS)


def _v_tender(doc):
	if frappe.get_meta("Tender").has_field("checklist"):  # v1.9.1 B1: submission checklist and the bids opened
		from hipersign_trading.api import construction_est as EST

		EST.tender_validate(doc)
	if doc.due_date and doc.published_on and getdate(doc.due_date) < getdate(doc.published_on):
		frappe.throw(_("The bid due date is before the date the tender was published."))
	if doc.emd_mode == "Exempt (MSE)":
		doc.emd_status = "Not paid"


def _v_mb(doc):
	b, r = boq_line(doc.project, doc.item_no)
	if not r:
		frappe.throw(_("Item {0} is not in the BOQ of {1}.").format(doc.item_no, doc.project))
	doc.boq, doc.description, doc.unit, doc.rate = b.name, r.description, r.unit, r.rate
	if not cint(doc.manual_qty):
		dims = [flt(x) for x in (doc.nos, doc.length, doc.breadth, doc.depth) if flt(x)]
		if dims:
			q = 1.0
			for x in dims:
				q *= x
			doc.qty = flt(q, 3)
	if flt(doc.qty) <= 0:
		frappe.throw(_("Enter the dimensions or the quantity."))
	doc.amount = flt(flt(doc.qty) * flt(doc.rate), 2)
	others = measured_qty(doc.project, doc.item_no, ("Draft", "Checked by QS", "Client checked"), exclude=doc.name)
	doc.over_boq = 1 if flt(r.qty) and others + flt(doc.qty) > flt(r.qty) * 1.0001 and (r.unit or "").upper() != "LS" else 0
	if not doc.is_new() and doc.ra_bill and frappe.db.get_value("RA Bill", doc.ra_bill, "status") in LIVE_BILL:
		before = doc.get_doc_before_save()
		if before and flt(before.qty) != flt(doc.qty):
			frappe.throw(_("{0} is on {1}, which is with the client — the measurement cannot change.").format(doc.name, doc.ra_bill))


def _v_ei(doc):
	if flt(doc.amount) <= 0:
		frappe.throw(_("Enter the value of the extra item."))


def _v_hin(doc):
	end = doc.to_date or today()
	if getdate(end) < getdate(doc.from_date):
		frappe.throw(_("The hindrance ends before it starts."))
	doc.days = date_diff(end, doc.from_date) + 1


def _v_claim(doc):
	if cint(doc.claimed_days) < 0 or flt(doc.claimed_amount) < 0:
		frappe.throw(_("Claimed days and amount cannot be negative."))
	if not doc.contract:
		doc.contract = frappe.db.get_value("Construction Contract", {"project": doc.project, "status": ["!=", "Terminated"]})
	if doc.kind == "Extension of time" and not cint(doc.claimed_days):
		frappe.throw(_("An extension-of-time claim needs the days claimed."))


def _v_dpr(doc):
	doc.achievement_pct = flt(flt(doc.actual_qty) / flt(doc.planned_qty) * 100, 1) if flt(doc.planned_qty) else 0


def _bills(project, exclude=None):
	return frappe.get_all("RA Bill", filters={"project": project, "status": ["!=", "Cancelled"], "name": ["!=", exclude or ""]},
		fields=["name", "bill_no", "status", "claimed_amount", "certified_amount", "advance_recovery", "retention", "net_receivable", "received_amount",
			"due_date", "tds", "gst_tds", "labour_cess", "gst_amount", "certified_on", "submitted_on", "received_on", "tds_in_26as", "gst_tds_ok",
			"sales_invoice", "is_final", "bill_date"], order_by="bill_no asc")


def ra_compute(doc):
	"""RA bill: this bill and up to date per BOQ line → claimed → (certified) → GST → the client's deductions → net."""
	p = frappe.get_cached_doc("Project", doc.project)
	if not cint(p.get("hs_cn")):
		frappe.throw(_("{0} is not a Construction (India) project.").format(doc.project))
	doc.company, doc.customer = p.company, p.customer
	doc.government_client = cint(p.get("hs_cn_govt"))
	if doc.is_new():
		doc.retention_pct = doc.retention_pct if doc.retention_pct is not None and flt(doc.retention_pct) else flt(p.get("hs_retention_pct"))
		doc.advance_pct = doc.advance_pct if flt(doc.advance_pct) else flt(p.get("hs_advance_pct"))
		doc.tds_pct = flt(p.get("hs_cn_tds_pct")) or flt(doc.tds_pct) or 2
		if doc.government_client:
			doc.gst_tds_pct = doc.gst_tds_pct or 2
			doc.cess_pct = doc.cess_pct or 1
		if not doc.gst_rate:
			doc.gst_rate = 18
	earlier = [b for b in _bills(doc.project, doc.name) if not doc.bill_no or cint(b.bill_no) < cint(doc.bill_no)]
	if not cint(doc.bill_no):
		doc.bill_no = (max([cint(b.bill_no) for b in _bills(doc.project, doc.name)] or [0])) + 1
		earlier = [b for b in _bills(doc.project, doc.name) if cint(b.bill_no) < cint(doc.bill_no)]
	b, _r = boq_line(doc.project, None)
	lines = {r.item_no: r for r in (b.items if b else [])}
	for it in doc.items:
		r = lines.get(it.item_no)
		if r:
			it.description = it.description or r.description
			it.unit = it.unit or r.unit
			it.rate = it.rate if flt(it.rate) else r.rate
			it.boq_qty = r.qty
		it.cum_qty = flt(flt(it.prev_qty) + flt(it.this_qty), 3)
		it.this_amount = flt(flt(it.this_qty) * flt(it.rate), 2)
		it.cum_amount = flt(it.cum_qty * flt(it.rate), 2)
		it.over_boq = 1 if flt(it.boq_qty) and it.cum_qty > flt(it.boq_qty) * 1.0001 and (it.unit or "").upper() != "LS" else 0
	doc.claimed_amount = flt(sum(flt(i.this_amount) for i in doc.items) + flt(doc.extra_items_amount), 2)
	doc.previous_billed = flt(sum(flt(x.certified_amount) if x.status in CERTIFIED else flt(x.claimed_amount) for x in earlier if x.status != "Draft"), 2)
	doc.work_to_date = flt(doc.previous_billed + doc.claimed_amount, 2)
	if doc.status in CERTIFIED:
		if not flt(doc.certified_amount):
			doc.certified_amount = doc.claimed_amount
		doc.cut_amount = flt(doc.claimed_amount - flt(doc.certified_amount), 2)
		base = flt(doc.certified_amount)
	else:
		doc.certified_amount, doc.cut_amount = 0, 0
		base = flt(doc.claimed_amount)
	doc.gst_amount = flt(base * flt(doc.gst_rate) / 100, 2)
	doc.gross_with_gst = flt(base + doc.gst_amount, 2)
	doc.retention = flt(base * flt(doc.retention_pct) / 100, 2)
	# v1.9.1 B2: recover only what the client actually paid as the mobilisation advance (capped at the advance in the terms)
	from hipersign_trading.api import construction_ctl as CTL

	adv_total = min(flt(p.get("hs_contract_value")) * flt(p.get("hs_advance_pct")) / 100, CTL.adv_received(doc.project)) if flt(p.get("hs_advance_pct")) else 0
	adv_done = sum(flt(x.advance_recovery) for x in earlier)
	doc.advance_recovery = flt(max(0, min(base * flt(doc.advance_pct) / 100, adv_total - adv_done)), 2)
	if cint(doc.is_final) and adv_total:
		doc.advance_recovery = flt(max(0, adv_total - adv_done), 2)
	doc.tds = flt(base * flt(doc.tds_pct) / 100, 2)
	doc.gst_tds = flt(base * flt(doc.gst_tds_pct) / 100, 2)
	doc.labour_cess = flt(base * flt(doc.cess_pct) / 100, 2)
	doc.total_deductions = flt(doc.retention + doc.advance_recovery + doc.tds + doc.gst_tds + doc.labour_cess, 2)
	doc.net_receivable = flt(doc.gross_with_gst - doc.total_deductions, 2)
	if not doc.is_new() and doc.status in LIVE_BILL:
		before = doc.get_doc_before_save()
		if before and before.status == doc.status and flt(before.claimed_amount) != flt(doc.claimed_amount):
			frappe.throw(_("{0} is {1} — the quantities cannot change. Raise the difference on the next bill.").format(doc.name, _(doc.status)))


# ---------------------------------------------------------------- figures
def _c():
	return P._local("hs_cn_fig")


def clear_cache():
	frappe.local.hs_cn_fig = {}
	P.clear_cache()


def eis(project):
	return frappe.get_all("Extra Item", filters={"project": project}, fields=["name", "title", "kind", "amount", "status", "raised_on", "sent_on", "approved_on", "reference"],
		order_by="raised_on asc")


def fig(name):
	c = _c()
	if name in c:
		return c[name]
	p = frappe.get_cached_doc("Project", name)
	step = cint(p.get("hs_step"))
	contract = flt(p.get("hs_contract_value"))
	E = eis(name)
	ei_ok = sum(flt(e.amount) for e in E if e.status == "Approved")
	from hipersign_trading.api import construction_biz as B

	claims_ok = B.claims_awarded(name)
	revised = contract + ei_ok + claims_ok
	b = boq(name)
	work_boq = sum(flt(r.amount) * flt(r.measured_pct) / 100 for r in (b.items if b else []))
	B = _bills(name)
	cert = [x for x in B if x.status in CERTIFIED]
	billed = sum(flt(x.certified_amount) for x in cert)
	inv = [x for x in B if x.status in ("Invoiced", "Part paid", "Paid")]
	received = sum(flt(x.received_amount) for x in inv)
	out_rows = [x for x in inv if flt(x.net_receivable) - flt(x.received_amount) > 1]
	outstanding = sum(flt(x.net_receivable) - flt(x.received_amount) for x in out_rows)
	overdue = sum(flt(x.net_receivable) - flt(x.received_amount) for x in out_rows if x.due_date and getdate(x.due_date) < getdate(today()))
	pending = [x for x in B if x.status == "Submitted to client"]
	work = work_boq + (ei_ok * min(1, work_boq / contract) if contract else 0)
	work = max(work, billed + sum(flt(x.claimed_amount) for x in pending))
	pct = 100 if step >= 22 else (min(100, work / revised * 100) if revised else 0)
	cost = P.cost_of(name) if b else frappe._dict(actual=0, budget=0, fac=0)
	adv_total = contract * flt(p.get("hs_advance_pct")) / 100
	F = frappe._dict(
		step=step, status=P.status_of(step), contract=contract, ei=ei_ok, ei_pending=sum(flt(e.amount) for e in E if e.status in ("Draft", "Pending client")),
		claims=claims_ok, revised=revised, work=work, pct=pct, billed=billed, gst=sum(flt(x.gst_amount) for x in cert), received=received, outstanding=outstanding, overdue=overdue,
		pending_cert=sum(flt(x.claimed_amount) for x in pending), retention=sum(flt(x.retention) for x in cert), tds=sum(flt(x.tds) for x in cert),
		gst_tds=sum(flt(x.gst_tds) for x in cert), cess=sum(flt(x.labour_cess) for x in cert), adv_total=adv_total,
		adv_recovered=sum(flt(x.advance_recovery) for x in cert), bills=len(cert), last_bill=(B[-1] if B else None),
		tds_open=len([x for x in inv if flt(x.received_amount) > 0 and flt(x.tds) and not cint(x.tds_in_26as)]),
		cost=flt(cost.actual), budget=flt(cost.budget), fac=flt(cost.fac),
	)
	# margin on the work done (cost is booked as the work is done, the bills follow), against the estimate's margin
	F.margin = (F.work - F.cost) / F.work * 100 if F.work and F.cost else 0
	F.bud_margin = (revised - F.budget) / revised * 100 if revised and F.budget else 0
	F.fc_margin = (revised - F.fac) / revised * 100 if revised and F.fac else F.bud_margin
	c[name] = F
	return F


def flags(name):
	"""Red flags — what a project manager or the MD should act on today."""
	p = frappe.get_cached_doc("Project", name)
	F = fig(name)
	t = getdate(today())
	out = []

	def add(lvl, text, dt, dn):
		out.append({"lvl": lvl, "text": text, "open": [dt, dn]})

	for x in _bills(name):
		bal = flt(x.net_receivable) - flt(x.received_amount)
		if x.status in ("Invoiced", "Part paid") and bal > 1 and x.due_date and getdate(x.due_date) < t:
			add("High", _("RA bill {0}: {1} overdue by {2} days").format(x.bill_no, inr(bal), date_diff(t, x.due_date)), "RA Bill", x.name)
		if x.status == "Submitted to client" and x.submitted_on and date_diff(t, x.submitted_on) > 21:
			add("Medium", _("RA bill {0} with the client for {1} days — not certified").format(x.bill_no, date_diff(t, x.submitted_on)), "RA Bill", x.name)
		if x.received_on and flt(x.tds) and not cint(x.tds_in_26as) and date_diff(t, x.received_on) > 45:
			add("Medium", _("TDS {0} on RA bill {1} not in Form 26AS").format(inr(x.tds), x.bill_no), "RA Bill", x.name)
	for h in frappe.get_all("Hindrance", filters={"project": name, "to_date": ["is", "not set"]}, fields=["name", "from_date", "cause", "attributable_to", "eot_status"]):
		d = date_diff(t, h.from_date) + 1
		if d > 7 and h.eot_status == "Not applied" and h.attributable_to in ("Client", "Authority", "Weather"):
			add("High" if d > 21 else "Medium", _("Hindrance {0} days, EOT not applied — {1}").format(d, h.cause), "Hindrance", h.name)
	for e in eis(name):
		if e.status == "Pending client" and e.sent_on and date_diff(t, e.sent_on) > 30:
			add("Medium", _("Extra item {0} ({1}) with the client for {2} days").format(e.title, inr(e.amount), date_diff(t, e.sent_on)), "Extra Item", e.name)
	over = frappe.db.sql("""select item_no, count(*) from `tabMeasurement Book` where project = %s and over_boq = 1 and status != 'Rejected' group by item_no""", name)
	for item_no, n in over:
		if not frappe.db.exists("Extra Item", {"project": name, "kind": "Deviation (excess quantity)", "status": ["!=", "Rejected"]}):
			add("Medium", _("Item {0} measured beyond the BOQ — raise a deviation statement").format(item_no), "Project", name)
	bm = frappe.get_meta("Bank Guarantee")
	if bm.has_field("project"):
		fields = ["name", "end_date", "amount"] + [x for x in ("hs_bond_type", "hs_bond_status") if bm.has_field(x)]
		for g in frappe.get_all("Bank Guarantee", filters={"project": name, "docstatus": 1, "end_date": ["between", [t, add_days(t, 30)]]}, fields=fields):
			if g.get("hs_bond_status") in ("Returned",):
				continue
			add("High", _("{0} {1} expires on {2} — renew or get it released").format(_(g.get("hs_bond_type") or "Bank guarantee"), inr(g.amount),
				frappe.format(g.end_date, {"fieldtype": "Date"})), "Bank Guarantee", g.name)
	if F.cost and F.budget and F.margin < F.bud_margin - 3 and F.step < 22:
		add("Medium", _("Margin {0:.1f}% against {1:.1f}% in the estimate").format(F.margin, F.bud_margin), "Project", name)
	from hipersign_trading.api import construction_biz as B

	out += B.flags(name)
	from hipersign_trading.api import construction_site as S

	out += S.flags(name)
	from hipersign_trading.api import construction_qhse as Q

	out += Q.flags(name)
	from hipersign_trading.api import construction_fin as FN

	out += FN.flags(name)
	from hipersign_trading.api import construction_portal as PT

	out += PT.flags(name)
	from hipersign_trading.api import construction_ctl as CTL  # v1.9.1 B2

	out += CTL.flags(name)
	return out


# ---------------------------------------------------------------- documents the actions make
class _elevated(P._elevated):
	pass


def make_invoice(ra_name, posting_date=None):
	ra = frappe.get_doc("RA Bill", ra_name)
	if ra.sales_invoice and frappe.db.get_value("Sales Invoice", ra.sales_invoice, "docstatus") == 1:
		return ra.sales_invoice
	p = frappe.get_cached_doc("Project", ra.project)
	acc = accounts(p.company)
	posting_date = posting_date or today()
	addr = p.get("hs_cn_address") or branch_address(p.company, p.customer)
	tpl = _tax_template(p.company, addr, p.customer)
	si = frappe.get_doc({"doctype": "Sales Invoice", "company": p.company, "customer": p.customer, "project": p.name, "posting_date": posting_date,
		"set_posting_time": 1, "due_date": add_days(posting_date, 30), "cost_center": p.cost_center or frappe.get_cached_value("Company", p.company, "cost_center"),
		"items": [{"item_code": works_item(p.get("hs_cn_category")), "qty": 1, "rate": flt(ra.certified_amount), "income_account": acc.revenue,
			"description": _("RA bill no. {0}{1} — {2}: work certified up to {3}").format(ra.bill_no, _(" (final)") if cint(ra.is_final) else "", p.project_name,
				frappe.format(ra.period_to or ra.certified_on or posting_date, {"fieldtype": "Date"})), "project": p.name}],
		"taxes_and_charges": tpl, "remarks": _("RA bill {0} of {1}").format(ra.name, p.name)})
	if addr:
		si.company_address = addr
	ca = _customer_address(p.customer)
	if ca:
		si.customer_address = ca
	if tpl:
		for r in frappe.get_doc("Sales Taxes and Charges Template", tpl).taxes:
			si.append("taxes", {"charge_type": r.charge_type, "account_head": r.account_head, "rate": r.rate, "description": r.description, "cost_center": r.cost_center})
	si.flags.ignore_permissions = True
	si.insert()
	si.submit()
	ra.db_set({"sales_invoice": si.name, "status": "Invoiced", "due_date": si.due_date})
	if cint(p.get("hs_step")) < 15:
		frappe.db.set_value("Project", p.name, "hs_step", 15)
	return si.name


def receive(ra_name, posting_date=None, reference=None):
	ra = frappe.get_doc("RA Bill", ra_name)
	if not ra.sales_invoice:
		frappe.throw(_("{0} has no tax invoice yet.").format(ra.name))
	si = frappe.get_doc("Sales Invoice", ra.sales_invoice)
	if flt(si.outstanding_amount) <= 0.5:
		return None
	acc = accounts(si.company)
	posting_date = posting_date or today()
	cc = si.cost_center or frappe.get_cached_value("Company", si.company, "cost_center")
	ded = [(acc.tds, ra.tds), (acc.gst_tds, ra.gst_tds), (acc.retention, ra.retention), (acc.advance, ra.advance_recovery), (acc.cess, ra.labour_cess)]
	ded = [(a, flt(v, 2)) for a, v in ded if flt(v) > 0]
	alloc = flt(si.outstanding_amount, 2)
	net = flt(alloc - sum(v for _a, v in ded), 2)
	bank = bank_account(si.company)
	pe = frappe.get_doc({"doctype": "Payment Entry", "payment_type": "Receive", "company": si.company, "posting_date": posting_date, "party_type": "Customer",
		"party": si.customer, "paid_from": si.debit_to, "paid_to": bank, "paid_amount": net, "received_amount": net, "project": ra.project,
		"reference_no": reference or f"NEFT/{ra.name}", "reference_date": posting_date, "cost_center": cc,
		"references": [{"reference_doctype": "Sales Invoice", "reference_name": si.name, "allocated_amount": alloc}],
		"deductions": [{"account": a, "amount": v, "cost_center": cc} for a, v in ded],
		"remarks": _("RA bill {0}: received {1} after retention, advance recovery, TDS{2}").format(ra.bill_no, inr(net), _(", GST-TDS and labour cess") if ra.gst_tds else "")})
	pe.flags.ignore_permissions = True
	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.insert()
	pe.submit()
	ra.db_set({"payment_entry": pe.name, "received_amount": flt(ra.received_amount) + net, "received_on": posting_date, "status": "Paid"})
	return pe.name


def make_project(tender):
	t = frappe.get_doc("Tender", tender)
	if t.project:
		return t.project
	if not t.customer:
		frappe.throw(_("Pick the client (customer) on {0} first.").format(t.name))
	pj = frappe.get_doc({"doctype": "Project", "project_name": t.tender_name, "company": t.company, "customer": t.customer, "status": "Open",
		"hs_cn": 1, "hs_contract_value": flt(t.our_bid) or flt(t.estimated_value), "hs_revised_contract": flt(t.our_bid) or flt(t.estimated_value),
		"hs_step": 4, "hs_award_date": today(), "hs_enquiry_date": t.published_on, "hs_tender_due": t.due_date, "hs_retention_pct": 5, "hs_advance_pct": 10,
		"hs_dlp_months": 12, "hs_cn_tds_pct": 2, "hs_cn_govt": 1 if t.portal in ("Kerala e-Tenders", "CPPP", "GeM", "State e-procurement") else 0,
		"estimated_costing": flt(t.our_bid) or flt(t.estimated_value)})
	pj.flags.ignore_permissions = True
	pj.insert()
	if frappe.db.exists("DocType", "Construction Contract"):  # v1.9.0 A2: the contract (LOA) with the project
		c = frappe.get_doc({"doctype": "Construction Contract", "project": pj.name, "tender": t.name, "loa_no": f"LOA/{pj.name}", "loa_date": today(),
			"original_value": pj.hs_contract_value, "start_date": add_days(today(), 21), "completion_date": add_days(today(), 21 + 540),
			"retention_pct": 5, "advance_pct": 10, "price_escalation": "Price variation clause (indices)" if pj.hs_cn_govt else "None — firm price"})
		c.flags.ignore_permissions = True
		c.insert()
	return pj.name


# ---------------------------------------------------------------- actions (every button on the Construction pages)
@frappe.whitelist(methods=["POST"])
def act(action, name, args=None):
	args = frappe._dict(frappe.parse_json(args) if isinstance(args, str) else (args or {}))
	from hipersign_trading.api import construction_biz as B  # v1.9.0 A2: business actions

	from hipersign_trading.api import construction_site as S  # v1.9.0 A3: site-resource actions

	from hipersign_trading.api import construction_qhse as Q  # v1.9.0 A4: quality, safety, drawings, handover

	from hipersign_trading.api import construction_fin as FN  # v1.9.0 A5: finance & tax

	from hipersign_trading.api import construction_portal as PT  # v1.9.0 A6: controls, portals and apps

	fn = ACTIONS.get(action) or B.ACTIONS.get(action) or S.ACTIONS.get(action) or Q.ACTIONS.get(action) or FN.ACTIONS.get(action) or PT.ACTIONS.get(action) or EST_ACTIONS().get(action)
	if not fn:
		frappe.throw(_("Unknown action"))
	r = fn(name, args) or {}
	clear_cache()
	return r


def _doc(dt, name, perm="write"):
	d = frappe.get_doc(dt, name)
	d.check_permission(perm)
	return d


def _who():
	return frappe.utils.get_fullname(frappe.session.user)


def _a_tnd_bid(name, a):
	_need([MD], _("The bid / no-bid decision"))
	t = _doc("Tender", name)
	t.bid_decision, t.decided_by = "Bid", _who()
	if t.status == "Bid / no-bid":
		t.status = "Being priced"
	t.save()
	return {"message": _("{0}: bid — estimate and EMD next").format(t.name)}


def _a_tnd_nobid(name, a):
	_need([MD], _("The bid / no-bid decision"))
	t = _doc("Tender", name)
	t.bid_decision, t.decided_by, t.status = "No bid", _who(), "No bid"
	t.save()
	return {"message": _("{0}: no bid").format(t.name)}


def _a_tnd_submit(name, a):
	_need([MD, QS, PM], _("Submitting a tender"))
	t = _doc("Tender", name)
	if t.bid_decision != "Bid":
		frappe.throw(_("{0} has no bid decision yet.").format(t.name))
	if not flt(t.our_bid):
		frappe.throw(_("Enter our quoted value on {0} first.").format(t.name))
	if t.meta.has_field("checklist"):  # v1.9.1 B1
		from hipersign_trading.api import construction_est as EST

		EST.check_ready(t)
	if t.emd_mode != "Exempt (MSE)" and flt(t.emd_amount) and t.emd_status == "Not paid":
		t.emd_status = "Held by client"
	t.status = "Submitted"
	t.save()
	return {"message": _("{0} submitted — {1}").format(t.name, inr(t.our_bid))}


def _a_tnd_next(name, a):
	_need([MD, QS, PM], _("Recording the evaluation"))
	t = _doc("Tender", name)
	nxt = EVAL_NEXT.get(t.status)
	if not nxt:
		frappe.throw(_("{0} is {1}.").format(t.name, _(t.status)))
	t.status = nxt
	if nxt == "L1 — LOA awaited":
		t.rank = "L1"
	t.save()
	return {"message": _("{0}: {1}").format(t.name, _(nxt))}


def _a_tnd_award(name, a):
	_need([MD], _("Accepting the letter of award"))
	t = _doc("Tender", name)
	if t.status not in ("L1 — LOA awaited", "Financial evaluation", "Submitted", "Technical evaluation"):
		frappe.throw(_("{0} is {1}.").format(t.name, _(t.status)))
	with _elevated():
		pj = make_project(t.name)
	t.reload()
	t.status, t.project, t.rank = "Awarded", pj, t.rank or "L1"
	if t.emd_status == "Held by client":
		t.emd_status = "Adjusted in PBG"
	t.save()
	return {"message": _("{0} awarded — project {1} created").format(t.name, pj), "open": ["Project", pj]}


def _a_tnd_lost(name, a):
	_need([MD, QS, PM], _("Recording a lost tender"))
	t = _doc("Tender", name)
	t.status, t.rank = "Lost", a.get("rank") or t.rank or "L2"
	if t.emd_status == "Held by client":
		t.emd_status = "Refund pending"
	t.save()
	return {"message": _("{0} lost ({1}) — EMD refund requested").format(t.name, t.rank)}


def _a_emd_refunded(name, a):
	_need([MD, AM, AU, QS], _("Recording the EMD refund"))
	t = _doc("Tender", name)
	t.emd_status = "Refunded"
	t.save()
	return {"message": _("EMD of {0} refunded").format(t.name)}


def _a_mb_qs(name, a):
	_need([QS, PM, MD], _("Checking a measurement"))
	m = _doc("Measurement Book", name)
	if m.status != "Draft":
		frappe.throw(_("{0} is {1}.").format(m.name, _(m.status)))
	m.status, m.qs_checked_by = "Checked by QS", _who()
	m.save()
	return {"message": _("{0} checked — send it to the client's engineer").format(m.name)}


def _a_mb_client(name, a):
	_need([QS, PM, MD], _("Recording the client's check"))
	m = _doc("Measurement Book", name)
	if m.status != "Checked by QS":
		frappe.throw(_("{0} is {1} — the QS checks it first.").format(m.name, _(m.status)))
	m.status, m.client_checked_by = "Client checked", frappe.get_cached_value("Project", m.project, "hs_cn_eic") or _("Engineer-in-charge")
	m.save()
	sync_boq(m.project, [m.item_no])
	return {"message": _("{0} checked by the client — ready for the next RA bill").format(m.name)}


def _a_mb_reject(name, a):
	_need([QS, PM, MD], _("Rejecting a measurement"))
	m = _doc("Measurement Book", name)
	if m.ra_bill:
		frappe.throw(_("{0} is on {1}.").format(m.name, m.ra_bill))
	m.status = "Rejected"
	m.save()
	sync_boq(m.project, [m.item_no])
	return {"message": _("{0} rejected").format(m.name)}


def new_ra(project):
	"""The next RA bill from the client-checked measurements not yet billed."""
	if not is_cn(project):
		frappe.throw(_("{0} is not a Construction (India) project.").format(project))
	if frappe.db.exists("RA Bill", {"project": project, "status": "Draft"}):
		frappe.throw(_("{0} already has a draft RA bill: {1}").format(project, frappe.db.get_value("RA Bill", {"project": project, "status": "Draft"})))
	mbs = frappe.get_all("Measurement Book", filters={"project": project, "status": "Client checked", "ra_bill": ["is", "not set"]},
		fields=["name", "item_no", "qty"], order_by="measured_on asc")
	if not mbs:
		frappe.throw(_("No client-checked measurements to bill on {0}.").format(project))
	b = boq(project)
	lines = {r.item_no: r for r in b.items}
	billed = {}
	for b2 in _bills(project):
		for it in frappe.get_all("RA Bill Item", filters={"parent": b2.name}, fields=["item_no", "this_qty"]):
			billed[it.item_no] = billed.get(it.item_no, 0) + flt(it.this_qty)
	this = {}
	for m in mbs:
		this[m.item_no] = this.get(m.item_no, 0) + flt(m.qty)
	ra = frappe.get_doc({"doctype": "RA Bill", "project": project, "bill_date": today(), "period_to": today(), "status": "Draft",
		"items": [{"item_no": k, "description": lines[k].description, "unit": lines[k].unit, "rate": lines[k].rate, "boq_qty": lines[k].qty,
			"prev_qty": flt(billed.get(k), 3), "this_qty": flt(v, 3)} for k, v in sorted(this.items(), key=lambda x: [cint(p) if p.isdigit() else p for p in x[0].split(".")]) if k in lines]})
	ra.flags.ignore_permissions = True
	ra.insert()
	for m in mbs:
		frappe.db.set_value("Measurement Book", m.name, "ra_bill", ra.name, update_modified=False)
	return ra.name


def _a_ra_new(name, a):
	_need([QS, PM, MD], _("Preparing an RA bill"))
	frappe.has_permission("RA Bill", "create", throw=True)
	n = new_ra(name)
	return {"message": _("{0} prepared from the checked measurements").format(n), "open": ["RA Bill", n]}


def _a_ra_submit(name, a):
	_need([PM, MD, QS], _("Submitting an RA bill to the client"))
	ra = _doc("RA Bill", name)
	if ra.status != "Draft":
		frappe.throw(_("{0} is {1}.").format(ra.name, _(ra.status)))
	if flt(ra.claimed_amount) <= 0:
		frappe.throw(_("{0} has nothing to claim.").format(ra.name))
	ra.status, ra.submitted_on = "Submitted to client", today()
	ra.save()
	return {"message": _("{0} submitted to the client — {1}").format(ra.name, inr(ra.claimed_amount))}


def _a_ra_certify(name, a):
	_need([QS, PM, MD], _("Recording the client's certification"))
	ra = _doc("RA Bill", name)
	if ra.status != "Submitted to client":
		frappe.throw(_("{0} is {1} — submit it to the client first.").format(ra.name, _(ra.status)))
	amt = flt(a.get("amount")) or flt(ra.claimed_amount)
	if amt > flt(ra.claimed_amount) + 0.5:
		frappe.throw(_("The client cannot certify more than was claimed ({0}).").format(inr(ra.claimed_amount)))
	ra.status, ra.certified_amount, ra.certified_on = "Certified", amt, a.get("date") or today()
	ra.save()
	b = boq(ra.project)
	if b:
		cum = {i.item_no: flt(i.cum_qty) for i in ra.items}
		for r in b.items:
			if r.item_no in cum and flt(r.qty):
				r.certified_pct = flt(min(100, cum[r.item_no] / flt(r.qty) * 100), 2)
		b.flags.ignore_permissions = True
		b.save()
	cut = flt(ra.claimed_amount) - amt
	return {"message": _("{0} certified {1}").format(ra.name, inr(amt)) + (_(" — {0} cut by the client").format(inr(cut)) if cut > 1 else "")}


def _a_ra_invoice(name, a):
	_need([AM, AU, MD, PM], _("Raising the tax invoice"))
	ra = _doc("RA Bill", name, "read")  # the role is checked above; accounts staff only read RA bills
	if ra.status != "Certified":
		frappe.throw(_("{0} is {1} — the client certifies it first.").format(ra.name, _(ra.status)))
	with _elevated():
		si = make_invoice(ra.name, a.get("date"))
	return {"message": _("Tax invoice {0} for {1} (incl. GST)").format(si, inr(ra.gross_with_gst)), "open": ["Sales Invoice", si]}


def _a_ra_receive(name, a):
	_need([AM, AU, MD], _("Recording the client's payment"))
	ra = _doc("RA Bill", name, "read")  # the role is checked above; accounts staff only read RA bills
	if ra.status not in ("Invoiced", "Part paid"):
		frappe.throw(_("{0} is {1}.").format(ra.name, _(ra.status)))
	with _elevated():
		pe = receive(ra.name, a.get("date"), a.get("reference"))
	return {"message": _("{0} received — {1} net of deductions").format(ra.name, inr(frappe.db.get_value("RA Bill", ra.name, "received_amount"))),
		"open": ["Payment Entry", pe] if pe else None}


def _a_ra_26as(name, a):
	_need([AM, AU, MD], _("Matching TDS with Form 26AS"))
	ra = _doc("RA Bill", name, "read")  # the role is checked above; accounts staff only read RA bills
	ra.db_set({"tds_in_26as": 1, "gst_tds_ok": 1 if flt(ra.gst_tds) else ra.gst_tds_ok})
	return {"message": _("TDS on {0} matched with Form 26AS").format(ra.name)}


def _a_ra_cancel(name, a):
	_need([PM, MD], _("Cancelling an RA bill"))
	ra = _doc("RA Bill", name)
	if ra.status not in ("Draft", "Submitted to client"):
		frappe.throw(_("{0} is {1} — cancel its tax invoice instead.").format(ra.name, _(ra.status)))
	for m in frappe.get_all("Measurement Book", filters={"ra_bill": ra.name}, pluck="name"):
		frappe.db.set_value("Measurement Book", m, "ra_bill", None, update_modified=False)
	ra.status = "Cancelled"
	ra.save()
	return {"message": _("{0} cancelled — its measurements are free for the next bill").format(ra.name)}


def _ei_update_project(project):
	from hipersign_trading.api import construction_biz as B

	B.sync_contract(project)  # v1.9.0 A2: the project and its contract follow extra items and awarded claims


def _a_ei_send(name, a):
	_need([QS, PM, MD], _("Sending an extra item to the client"))
	e = _doc("Extra Item", name)
	if e.status != "Draft":
		frappe.throw(_("{0} is {1}.").format(e.name, _(e.status)))
	e.status, e.sent_on = "Pending client", today()
	e.save()
	return {"message": _("{0} sent to the client").format(e.name)}


def _a_ei_approve(name, a):
	_need([PM, MD], _("Recording the client's approval"))
	e = _doc("Extra Item", name)
	if e.status != "Pending client":
		frappe.throw(_("{0} is {1} — send it to the client first.").format(e.name, _(e.status)))
	e.status, e.approved_on, e.approved_by = "Approved", a.get("date") or today(), frappe.get_cached_value("Project", e.project, "hs_cn_eic") or _("Client")
	e.save()
	_ei_update_project(e.project)
	return {"message": _("{0} approved — revised contract up by {1}").format(e.name, inr(e.amount))}


def _a_ei_reject(name, a):
	_need([PM, MD], _("Recording the client's rejection"))
	e = _doc("Extra Item", name)
	e.status = "Rejected"
	e.save()
	_ei_update_project(e.project)
	return {"message": _("{0} rejected by the client").format(e.name)}


def _a_hin_close(name, a):
	_need([SE, PM, MD, QS], _("Closing a hindrance"))
	h = _doc("Hindrance", name)
	h.to_date = a.get("date") or today()
	h.save()
	return {"message": _("{0} closed — {1} days").format(h.name, h.days)}


def _a_hin_eot(name, a):
	_need([PM, MD], _("Applying for an extension of time"))
	h = _doc("Hindrance", name)
	h.eot_status = "Applied"
	h.eot_ref = h.eot_ref or f"EOT/{h.project}/{today()}"
	h.save()
	return {"message": _("EOT applied for {0} ({1} days)").format(h.name, h.days)}


def _a_dpr_submit(name, a):
	d = _doc("Daily Progress Report", name)
	if d.status != "Draft":
		frappe.throw(_("{0} is {1}.").format(d.name, _(d.status)))
	d.status = "Submitted"
	d.save()
	return {"message": _("{0} submitted").format(d.name)}


def _a_dpr_approve(name, a):
	_need([PM, MD], _("Approving a DPR"))
	d = _doc("Daily Progress Report", name)
	if d.status != "Submitted":
		frappe.throw(_("{0} is {1}.").format(d.name, _(d.status)))
	d.status, d.approved_by = "Approved", _who()
	d.save()
	return {"message": _("{0} approved").format(d.name)}


ACTIONS = {
	"tnd_bid": _a_tnd_bid, "tnd_nobid": _a_tnd_nobid, "tnd_submit": _a_tnd_submit, "tnd_next": _a_tnd_next, "tnd_award": _a_tnd_award,
	"tnd_lost": _a_tnd_lost, "emd_refunded": _a_emd_refunded,
	"mb_qs": _a_mb_qs, "mb_client": _a_mb_client, "mb_reject": _a_mb_reject,
	"ra_new": _a_ra_new, "ra_submit": _a_ra_submit, "ra_certify": _a_ra_certify, "ra_invoice": _a_ra_invoice, "ra_receive": _a_ra_receive,
	"ra_26as": _a_ra_26as, "ra_cancel": _a_ra_cancel,
	"ei_send": _a_ei_send, "ei_approve": _a_ei_approve, "ei_reject": _a_ei_reject,
	"hin_close": _a_hin_close, "hin_eot": _a_hin_eot, "dpr_submit": _a_dpr_submit, "dpr_approve": _a_dpr_approve,
}
