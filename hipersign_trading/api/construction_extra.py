"""v1.9.1 stage B4 (prototype C12): the last gaps against the prototype —
- site workers: the pay-day sheet, contractor pay proof (CLRA: our gate muster against what the labour contractor paid;
  the shortfall paid by us to the workers and recovered from the contractor's next bill), wage ledgers;
- portals: messages from clients and subcontractors with our reply, and what each subcontractor may do on its portal;
- unit sales of our own development: units, booking, a construction-linked payment plan, demand invoices with GST 5%
  and receipts;
- cost control: the S-curve (planned, earned, actual by month);
- the approval matrix with editable limits and the notification rules;
- controlled documents (revision and review), safety audits and PPE compliance.

Money:
- direct payment of a contractor's wage shortfall → Dr Subcontract Costs (project), Cr Bank; the same amount goes on the
  contractor's next draft running bill as a recovery;
- unit demand → Sales Invoice to the buyer (Residential unit — construction-linked, item tax GST 5%); receipt → Payment Entry."""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, get_first_day, get_last_day, getdate, now_datetime, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_site as S
from hipersign_trading.api import projects as P

MD, PM, PMS, QS, SE, SK, HR, PLANT, AM, AU = S.MD, S.PM, S.PMS, S.QS, S.SE, S.SK, S.HR, S.PLANT, S.AM, S.AU
SO, QA, DC, BD = "Safety Officer", "QA/QC Engineer", "Document Controller", "BD Manager"
UNIT_PLAN = [("Booking", 10), ("Agreement", 10), ("Foundation", 15), ("Ground-floor slab", 10), ("First-floor slab", 10), ("Roof slab", 10), ("Brickwork & plaster", 10),
	("Flooring & finishes", 10), ("Handover", 15)]
UNIT_ITEM = "HS-UNIT-SALE"


def _has(dt):
	return frappe.db.exists("DocType", dt)


def _who():
	return S._who()


# ================================================================ site workers: pay day, wage ledger, contractor pay proof
def pay_day(names):
	"""The musters waiting to be approved or paid on the sites: one line per worker."""
	M = frappe.get_list("Weekly Muster", filters={"project": ["in", names or [""]], "status": ["in", ["Draft", "Approved"]]}, fields=["name", "project", "week_start", "week_end",
		"status", "net", "workers"], order_by="week_start asc, project asc", limit_page_length=0) if frappe.has_permission("Weekly Muster", "read") else []
	out = []
	for m in M:
		for r in frappe.get_all("Weekly Muster Row", filters={"parent": m.name, "parenttype": "Weekly Muster"}, fields=["worker", "worker_name", "trade", "days", "ot_hours", "earned", "pf",
				"esi", "advance_recovery", "net"], order_by="idx asc"):
			r.update(muster=m.name, project=m.project, week_start=m.week_start, status=m.status, upi=frappe.get_cached_value("Site Worker", r.worker, "upi_id"))
			out.append(r)
	return M, out


def wage_ledger(names, weeks=4):
	"""Own workers: net pay of the last weeks (from the musters) and the advance still owed."""
	start = add_days(S.week_start(), -7 * weeks)
	W = frappe.get_all("Site Worker", filters={"project": ["in", names or [""]], "contractor": ["is", "not set"], "status": "Active"}, fields=["name", "worker_name", "project", "trade",
		"daily_rate", "upi_id"], order_by="project asc, worker_name asc")
	R = frappe.db.sql("""select r.worker, m.week_start, m.status, r.days, r.earned, r.advance_recovery, r.net from `tabWeekly Muster Row` r join `tabWeekly Muster` m on m.name = r.parent
		where m.week_start >= %s and m.project in %s""", (start, tuple(names or [""])), as_dict=True)
	wk = [add_days(S.week_start(), -7 * k) for k in range(weeks, -1, -1)]
	out = []
	for w in W:
		rows = {str(getdate(r.week_start)): r for r in R if r.worker == w.name}
		adv = sum(flt(a.amount) - flt(a.recovered) for a in frappe.get_all("Worker Advance", filters={"worker": w.name, "status": "Paid"}, fields=["amount", "recovered"]))
		out.append(frappe._dict(w, weeks=[rows.get(str(getdate(d))) for d in wk], advance=adv, paid=sum(flt(r.net) for r in rows.values() if r.status == "Paid")))
	return wk, out


def _labour_wo(name):
	w = frappe.db.get_value("Subcontractor Work Order", name, ["name", "project", "supplier", "kind", "status"], as_dict=True)
	if not w or not (w.kind or "").startswith("Labour"):
		frappe.throw(_("{0} is not a labour-only work order.").format(name))
	return w


def cpp_validate(doc):
	"""Our gate attendance of the contractor's workers for the week, what is due at their rates (never below the minimum
	wage), what they paid as per the proof, the gap."""
	w = _labour_wo(doc.work_order)
	doc.project, doc.supplier = w.project, w.supplier
	doc.company = frappe.get_cached_value("Project", w.project, "company")
	doc.week_start = S.week_start(doc.week_start)
	doc.week_end = add_days(doc.week_start, 6)
	if frappe.db.exists("Contractor Pay Proof", {"work_order": doc.work_order, "week_start": doc.week_start, "name": ["!=", doc.name or ""]}):
		frappe.throw(_("{0} already has its pay proof for the week of {1}.").format(doc.work_order, frappe.format(doc.week_start, {"fieldtype": "Date"})))
	ws = {x.name: x for x in frappe.get_all("Site Worker", filters={"contractor": w.supplier, "project": w.project}, fields=["name", "daily_rate", "min_wage"])}
	att = frappe.db.sql("""select worker, count(distinct attendance_date) d from `tabSite Attendance` where project = %s and attendance_date between %s and %s and worker in %s
		group by worker""", (w.project, doc.week_start, doc.week_end, tuple(ws) or ("",)), as_dict=True) if ws else []
	if att:
		doc.workers = len(att)
		doc.mandays = sum(flt(a.d) for a in att)
		doc.due = flt(sum(flt(a.d) * max(flt(ws[a.worker].daily_rate), flt(ws[a.worker].min_wage)) for a in att), 0)
	if doc.status != "Paid direct":
		doc.gap = max(0, flt(doc.due) - flt(doc.paid)) if doc.proof else flt(doc.due)
		doc.status = "Missing proof" if not doc.proof else "Gap" if doc.gap > max(100, flt(doc.due) * .01) else "Verified"
		if doc.status == "Verified":
			doc.gap = 0


def _a_cpp_pay_direct(name, a):
	"""CLRA section 21: as principal employer we pay the shortfall to the workers and recover it from the contractor."""
	CN._need([PM, MD, HR], _("Paying a contractor's workers directly"))
	d = S._doc("Contractor Pay Proof", name, "read")
	if d.status != "Gap" or flt(d.gap) <= 0:
		frappe.throw(_("{0} has no wage gap to pay ({1}).").format(name, _(d.status)))
	p = frappe.get_cached_doc("Project", d.project)
	cc = p.cost_center or frappe.get_cached_value("Company", p.company, "cost_center")
	dt = a.get("date") or today()
	je = frappe.get_doc({"doctype": "Journal Entry", "company": p.company, "posting_date": dt, "voucher_type": "Bank Entry", "cheque_no": a.get("ref") or f"CLRA/{name}", "cheque_date": dt,
		"user_remark": _("Wage shortfall of {0}'s workers, week of {1}, paid direct by the principal employer — recovered from the contractor").format(d.supplier,
			frappe.format(d.week_start, {"fieldtype": "Date"})),
		"accounts": [{"account": P.accounts(p.company).heads["Subcontract"], "debit_in_account_currency": flt(d.gap), "project": d.project, "cost_center": cc},
			{"account": CN.bank_account(p.company), "credit_in_account_currency": flt(d.gap), "project": d.project, "cost_center": cc}]})
	je.flags.hs_system_entry = True
	with CN._elevated():
		je.insert()
		je.submit()
	sb = frappe.db.get_value("Subcontractor Bill", {"work_order": d.work_order, "status": "Draft"}, "name", order_by="bill_no desc")
	if sb:
		b = frappe.get_doc("Subcontractor Bill", sb)
		b.other_recovery = flt(b.other_recovery) + flt(d.gap)
		b.flags.ignore_permissions = True
		b.save()
	frappe.db.set_value("Contractor Pay Proof", name, {"status": "Paid direct", "paid_direct": flt(d.gap), "journal_entry": je.name, "recovered_in": sb})
	return {"message": _("{0} paid to the workers of {1} — {2}; {3}").format(CN.inr(d.gap), d.supplier, je.name,
		_("recovered on bill {0}").format(sb) if sb else _("recover it on the next running bill")), "open": ["Journal Entry", je.name]}


# ================================================================ portals: messages and partner features
SP_FEATURES = {"bills": "Submit running bills", "photos": "Upload progress photos", "labour": "Upload labour documents", "payments": "See payments",
	"retention": "See retention", "messages": "Send messages"}

SP_SHORT = {"bills": "Bills", "photos": "Photos", "labour": "Labour docs", "payments": "Payments", "retention": "Retention", "messages": "Messages"}


def partner_features(supplier):
	f = [f"hs_spp_{k}" for k in SP_FEATURES]
	if not frappe.get_meta("Supplier").has_field("hs_spp_bills"):
		return frappe._dict({k: 1 for k in SP_FEATURES})
	v = frappe.db.get_value("Supplier", supplier, f, as_dict=True) or {}
	return frappe._dict({k: cint(v.get(f"hs_spp_{k}")) for k in SP_FEATURES})


def _a_sp_features(name, a):
	CN._need([PM, MD, PMS], _("Changing what a subcontractor can do"))
	frappe.db.set_value("Supplier", name, {f"hs_spp_{k}": cint(a.get(k)) for k in SP_FEATURES if k in a})
	return {"message": _("{0}: portal updated").format(name)}


def _message(kind, party, message, subject=None, project=None):
	if not (message or "").strip():
		frappe.throw(_("Write the message."))
	m = frappe.get_doc({"doctype": "Portal Message", "party_type": kind, "party": party, "project": project, "from_user": frappe.session.user,
		"from_name": frappe.utils.get_fullname(frappe.session.user), "sent_on": now_datetime(), "subject": (subject or message.split("\n")[0])[:120], "message": message[:2000],
		"company": frappe.get_cached_value("Project", project, "company") if project else frappe.defaults.get_global_default("company"), "status": "Open"})
	with CN._elevated():
		m.insert(ignore_permissions=True)
	return {"message": _("Message sent — we reply here and by e-mail.")}


@frappe.whitelist()
def cp_message(project, message, subject=None):
	from hipersign_trading.api import construction_portal as PT

	pj = PT._client_check(project, "messages")
	return _message("Customer", pj.customer, message, subject, project)


@frappe.whitelist()
def sp_message(message, subject=None, project=None):
	from hipersign_trading.api import construction_portal as PT

	supplier, _w = PT._partner_check(project=project, feature="messages") if project else PT._partner_check(feature="messages")
	return _message("Supplier", supplier, message, subject, project)


def messages(kind, party=None, status=None):
	f = {"party_type": kind}
	if party:
		f["party"] = party
	if status:
		f["status"] = status
	return frappe.get_all("Portal Message", filters=f, fields=["name", "party", "project", "from_name", "from_user", "sent_on", "subject", "message", "status", "reply", "replied_by",
		"replied_on"], order_by="sent_on desc", limit=200) if _has("Portal Message") else []


def _a_msg_reply(name, a):
	CN._need([PM, MD, PMS, QS, AM, AU, BD], _("Replying to a portal message"))
	d = frappe.get_doc("Portal Message", name)
	if not (a.get("reply") or "").strip():
		frappe.throw(_("Write the reply."))
	d.reply = (f"{d.reply}\n\n" if d.reply else "") + a.get("reply")
	d.status, d.replied_by, d.replied_on = "Replied", _who(), now_datetime()
	d.flags.ignore_permissions = True
	d.save()
	email = frappe.db.get_value("User", d.from_user, "email") if d.from_user else None
	mailed = False
	if email and email != "admin@example.com":
		try:  # the reply is on the portal in any case; the e-mail needs an outgoing e-mail account
			frappe.sendmail(recipients=[email], subject=_("Re: {0}").format(d.subject), message=frappe.utils.escape_html(a.get("reply")).replace("\n", "<br>"),
				reference_doctype="Portal Message", reference_name=d.name, now=False)
			mailed = True
		except frappe.OutgoingEmailError:
			frappe.clear_last_message()
	return {"message": _("Reply sent to {0}").format(d.from_name or d.party) + ("" if mailed or not email else _(" — on the portal (no outgoing e-mail account to e-mail it)"))}


def _a_msg_close(name, a):
	d = frappe.get_doc("Portal Message", name)
	d.status = "Closed"
	d.flags.ignore_permissions = True
	d.save()
	return {"message": _("{0} closed").format(name)}


# ================================================================ unit sales (own development)
def developments():
	if not frappe.get_meta("Project").has_field("hs_own_dev"):
		return []
	return frappe.get_all("Project", filters={"hs_own_dev": 1, "status": ["!=", "Cancelled"]}, fields=["name", "project_name", "hs_rera_no", "hs_dev_stage", "company"],
		order_by="creation asc")


def _unit_item(company):
	if not frappe.db.exists("Item", UNIT_ITEM):
		grp = "Services" if frappe.db.exists("Item Group", "Services") else frappe.db.get_value("Item Group", {"is_group": 0})
		it = frappe.get_doc({"doctype": "Item", "item_code": UNIT_ITEM, "item_name": _("Residential unit — construction-linked instalment"), "item_group": grp, "stock_uom": "Nos",
			"is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 0})
		if it.meta.has_field("gst_hsn_code") and frappe.db.exists("GST HSN Code", "995411"):
			it.gst_hsn_code = "995411"
		t5 = frappe.db.get_value("Item Tax Template", {"gst_rate": 5, "company": company}) if _has("Item Tax Template") else None
		if t5:
			it.append("taxes", {"item_tax_template": t5})
		it.flags.ignore_permissions = True
		it.insert()
	return UNIT_ITEM


def unit_refresh(unit):
	SI = frappe.get_all("Sales Invoice", filters={"hs_dev_unit": unit, "docstatus": 1}, fields=["net_total", "grand_total", "outstanding_amount", "due_date"])
	t = getdate(today())
	frappe.db.set_value("Development Unit", unit, {"demanded": sum(flt(x.net_total) for x in SI), "received": sum(flt(x.grand_total) - flt(x.outstanding_amount) for x in SI),
		"outstanding": sum(flt(x.outstanding_amount) for x in SI), "overdue": sum(flt(x.outstanding_amount) for x in SI if x.due_date and getdate(x.due_date) < t)},
		update_modified=False)


def _demand(u, stages, date):
	"""One demand invoice for a unit: the stages completed, at their % of the agreement value, GST 5%."""
	pct = sum(p for _s, p in stages)
	co = u.company or frappe.get_cached_value("Project", u.project, "company")
	addr = CN.branch_address(co, u.customer)
	tpl = CN._tax_template(co, addr, u.customer)
	si = frappe.get_doc({"doctype": "Sales Invoice", "company": co, "customer": u.customer, "posting_date": date, "set_posting_time": 1, "due_date": add_days(date, 15),
		"hs_dev_unit": u.name, "cost_center": frappe.get_cached_value("Project", u.project, "cost_center") or frappe.get_cached_value("Company", co, "cost_center"),
		"remarks": _("Demand — unit {0}: {1}").format(u.unit_no, ", ".join(s for s, _p in stages)), "taxes_and_charges": tpl,
		"items": [{"item_code": _unit_item(co), "qty": 1, "rate": flt(flt(u.agreement_value) * pct / 100, 2), "project": u.project,
			"description": _("Unit {0} ({1}) — {2}: {3:g}% of the agreement value").format(u.unit_no, _(u.unit_type), ", ".join(s for s, _p in stages), pct)}]})
	if addr:
		si.company_address = addr
	ca = CN._customer_address(u.customer)
	if ca:
		si.customer_address = ca
	if tpl:
		for r in frappe.get_doc("Sales Taxes and Charges Template", tpl).taxes:
			si.append("taxes", {"charge_type": r.charge_type, "account_head": r.account_head, "rate": r.rate, "description": r.description, "cost_center": r.cost_center})
	si.flags.ignore_permissions = True
	with CN._elevated():
		si.insert()
		si.submit()
	return si.name


def _a_unit_book(name, a):
	CN._need([MD, BD, "Sales Manager", AM], _("Booking a unit"))
	u = frappe.get_doc("Development Unit", name)
	if u.status != "Available":
		frappe.throw(_("{0} is {1}.").format(u.unit_no, _(u.status)))
	if not a.get("customer"):
		frappe.throw(_("Pick the buyer."))
	d = a.get("date") or today()
	u.db_set({"status": "Booked", "customer": a.get("customer"), "booked_on": d})
	u.reload()
	done = max(2, cint(frappe.db.get_value("Project", u.project, "hs_dev_stage")))
	si = _demand(u, UNIT_PLAN[:done], d)
	unit_refresh(name)
	return {"message": _("{0} booked to {1} — demand {2} for {3} stages").format(u.unit_no, u.customer, si, done), "open": ["Sales Invoice", si]}


def _a_dev_stage(name, a):
	"""A construction stage is completed on site: every booked unit gets its demand."""
	CN._need([MD, PM, BD, AM], _("Recording a construction stage"))
	p = frappe.get_doc("Project", name)
	if not cint(p.get("hs_own_dev")):
		frappe.throw(_("{0} is not an own development.").format(name))
	k = max(2, cint(p.hs_dev_stage))
	if k >= len(UNIT_PLAN):
		frappe.throw(_("Every stage of {0} is completed.").format(p.project_name))
	st = UNIT_PLAN[k]
	d = a.get("date") or today()
	n = 0
	for u in frappe.get_all("Development Unit", filters={"project": name, "status": "Booked"}, pluck="name"):
		_demand(frappe.get_doc("Development Unit", u), [st], d)
		unit_refresh(u)
		n += 1
	frappe.db.set_value("Project", name, "hs_dev_stage", k + 1)
	return {"message": _("{0} completed — {1} demand letters at {2}% + GST 5%").format(st[0], n, st[1])}


def _a_unit_receive(name, a):
	"""The buyer paid: against the unit's open demands, oldest first."""
	CN._need([AM, AU, MD], _("Recording a buyer's payment"))
	u = frappe.get_doc("Development Unit", name)
	SI = frappe.get_all("Sales Invoice", filters={"hs_dev_unit": name, "docstatus": 1, "outstanding_amount": [">", 0]}, fields=["name", "outstanding_amount"], order_by="posting_date asc")
	if not SI:
		frappe.throw(_("Nothing outstanding on {0}.").format(u.unit_no))
	left = flt(a.get("amount")) or sum(flt(x.outstanding_amount) for x in SI)
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	made = []
	d = a.get("date") or today()
	for x in SI:
		if left <= .5:
			break
		amt = min(left, flt(x.outstanding_amount))
		pe = get_payment_entry("Sales Invoice", x.name, party_amount=amt)
		pe.posting_date = d
		pe.reference_no, pe.reference_date = a.get("ref") or f"UNIT/{u.unit_no}", d
		pe.paid_amount = pe.received_amount = amt
		pe.references[0].allocated_amount = amt
		pe.flags.ignore_permissions = True
		with CN._elevated():
			pe.insert()
			pe.submit()
		made.append(pe.name)
		left -= amt
	unit_refresh(name)
	return {"message": _("{0}: {1} received — {2}").format(u.unit_no, CN.inr(flt(a.get("amount")) or sum(flt(x.outstanding_amount) for x in SI)), ", ".join(made))}


# ================================================================ S-curve
def s_curve(project):
	"""Month by month: planned value (an S-shaped baseline over the contract period), earned value (the measured work at
	the BOQ rates) and actual cost (the project's expense postings) — cumulative, against the budget."""
	p = frappe.get_cached_doc("Project", project)
	from hipersign_trading.api import construction_fin as FN

	E = FN.evm(project)
	bac = flt(E.bac)
	a, b = getdate(p.expected_start_date or p.creation), getdate(p.expected_end_date or add_months(today(), 6))
	months, m = [], get_first_day(a)
	while m <= get_first_day(max(b, getdate(today()))) and len(months) < 60:
		months.append(m)
		m = add_months(m, 1)
	span = max(1, date_diff(b, a))
	import math

	boq_total = sum(flt(r.amount) for r in (CN.boq(project).items if CN.boq(project) else [])) or 1
	# the work earned over time: each RA bill's work (by its bill date) and the measurements not yet billed (by their date),
	# scaled to the earned value today
	pts = [(x.bill_date, flt(x.claimed_amount)) for x in frappe.get_all("RA Bill", filters={"project": project, "status": ["!=", "Cancelled"]}, fields=["bill_date", "claimed_amount"])]
	pts += [(x.measured_on, flt(x.amount)) for x in frappe.get_all("Measurement Book", filters={"project": project, "status": ["in", ["Checked by QS", "Client checked"]],
		"ra_bill": ["is", "not set"]}, fields=["measured_on", "amount"])]
	measured = sum(v for _d, v in pts) or 1
	GL = frappe.db.sql("""select gl.posting_date d, sum(gl.debit - gl.credit) v from `tabGL Entry` gl join `tabAccount` ac on ac.name = gl.account where gl.project = %s
		and gl.is_cancelled = 0 and ac.root_type = 'Expense' group by gl.posting_date""", project, as_dict=True)
	t = getdate(today())
	out = []
	for m in months:
		e = get_last_day(m)
		x = min(1, max(0, date_diff(e, a) / span))
		pv = bac * (1 - math.cos(math.pi * x)) / 2
		ev = flt(E.ev) * sum(v for d, v in pts if d and getdate(d) <= e) / measured if m <= t else None
		ac = sum(flt(r.v) for r in GL if getdate(r.d) <= e) if m <= t else None
		out.append(frappe._dict(month=m, pv=pv, ev=ev, ac=ac))
	return frappe._dict(bac=bac, rows=out, E=E, boq=boq_total)


# ================================================================ approval matrix and notification rules
LIMITS = [  # settings field, label, kind
	("cn_quote_discount_limit", "Quotation discount above which the MD approves (%)", "Percent"),
	("cn_quote_margin_floor", "Quotation margin below which the MD approves (%)", "Percent"),
	("cn_bid_md_limit", "Tender bid above which only the MD sets the price", "Currency"),
	("cn_jv_md_limit", "Manual journal above which the MD approves", "Currency"),
	("cn_worker_advance_limit", "Worker advance above which the PM approves", "Currency"),
	("cn_site_cash_limit", "Site cash a site engineer books without approval", "Currency"),
	("cn_ld_flag_days", "Flag a project this many days behind (LD)", "Int"),
]


def matrix():
	"""(document, rule, level 1, level 2, limit field) — the live rules of the construction module."""
	s = frappe.get_cached_doc("Hipersign Settings")
	v = lambda f, kind: f"{flt(s.get(f)):g}%" if kind == "Percent" else CN.inr(s.get(f)) if kind == "Currency" else _("{0} days").format(cint(s.get(f)))
	k = dict((f, kind) for f, _l, kind in LIMITS)
	return [
		(_("Quotation"), _("Discount or margin beyond the limits"), _("BD Manager — within the limits"), _("Managing Director — discount above {0} or margin below {1}").format(
			v("cn_quote_discount_limit", "Percent"), v("cn_quote_margin_floor", "Percent")), ["cn_quote_discount_limit", "cn_quote_margin_floor"]),
		(_("Tender bid price"), _("Margin on the tender price"), _("Estimation / QS — up to {0}").format(v("cn_bid_md_limit", "Currency")),
			_("Managing Director above {0}").format(v("cn_bid_md_limit", "Currency")), ["cn_bid_md_limit"]),
		(_("Manual journal"), _("Journals the app does not post itself"), _("Accounts Manager"), _("Managing Director above {0}").format(v("cn_jv_md_limit", "Currency")), ["cn_jv_md_limit"]),
		(_("Worker advance"), _("Up to four weeks' wages"), _("Site Engineer / HR up to {0}").format(v("cn_worker_advance_limit", "Currency")), _("Project Manager above"),
			["cn_worker_advance_limit"]),
		(_("Site cash expense"), _("From the site imprest"), _("Site Engineer up to {0}").format(v("cn_site_cash_limit", "Currency")), _("Project Manager above"), ["cn_site_cash_limit"]),
		(_("Indent above the BOQ need"), _("Material beyond the BOQ quantity + wastage"), _("Site Engineer raises"), _("Project Manager / MD"), []),
		(_("Purchase order"), _("Hipersign Purchase Order Approval workflow"), _("Purchase Manager"), _("MD by value (workflow)"), []),
		(_("Subcontractor bill"), _("Running bill of a work order"), _("QS certifies"), _("Project Manager approves; accounts pay"), []),
		(_("RA bill"), _("Bill to the client from the measurement book"), _("QS prepares"), _("Project Manager submits; client certifies"), []),
		(_("Permit to work"), _("Height, hot work, lifting, confined space"), _("Site Engineer requests"), _("Safety Officer issues"), []),
		(_("Project delay"), _("LD exposure"), _("Flag at {0} behind").format(v("cn_ld_flag_days", "Int")), _("Monthly review by the MD"), ["cn_ld_flag_days"]),
	]


def limits_changed():
	return frappe.get_all("Version", filters={"ref_doctype": "Hipersign Settings"}, fields=["owner", "creation", "data"], order_by="creation desc", limit=40)


def _a_am_limits(name, a):
	if MD not in frappe.get_roles() and "System Manager" not in frappe.get_roles() and frappe.session.user != "Administrator":
		frappe.throw(_("Only the Managing Director changes the approval limits."), frappe.PermissionError)
	s = frappe.get_doc("Hipersign Settings")
	ch = []
	for f, label, kind in LIMITS:
		if f in a and a.get(f) not in (None, ""):
			v = cint(a.get(f)) if kind == "Int" else flt(a.get(f))
			if v < 0 or (kind == "Percent" and v > 100):
				frappe.throw(_("{0}: {1} is not a valid limit.").format(_(label), v))
			if flt(s.get(f)) != flt(v):
				ch.append(f"{_(label)}: {s.get(f)} → {v}")
				s.set(f, v)
	if not ch:
		frappe.throw(_("Nothing changed."))
	s.flags.ignore_permissions = True
	s.save()
	frappe.clear_document_cache("Hipersign Settings", "Hipersign Settings")
	return {"message": _("Approval limits changed — {0}").format("; ".join(ch))}


NT_DOCTYPES = ("RA Bill", "Subcontractor Bill", "Hindrance", "Work Permit", "Safety Incident", "NCR", "Extra Item", "Portal Message", "Worker Advance", "Site Diary", "Contractor Pay Proof",
	"Material Request", "Purchase Order", "Bank Guarantee")


def notifications():
	return frappe.get_all("Notification", filters={"document_type": ["in", NT_DOCTYPES]}, fields=["name", "subject", "document_type", "event", "channel", "enabled", "send_system_notification"],
		order_by="document_type asc")


def _a_nt_toggle(name, a):
	CN._need([MD], _("Changing a notification rule"))
	n = frappe.get_doc("Notification", name)
	n.enabled = 0 if n.enabled else 1
	n.flags.ignore_permissions = True
	n.save()
	return {"message": _("{0} {1}").format(name, _("switched on") if n.enabled else _("switched off"))}


# ================================================================ controlled documents
def cdoc_validate(doc):
	if doc.project:
		doc.company = frappe.get_cached_value("Project", doc.project, "company")
	doc.company = doc.company or frappe.defaults.get_user_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")
	if not doc.review_on and doc.issued_on:
		doc.review_on = add_days(doc.issued_on, 365)
	doc.owner_name = doc.owner_name or _who()
	if doc.is_new() and not doc.history:
		doc.history = f"{doc.revision or 'R0'} — {frappe.format(doc.issued_on or today(), {'fieldtype': 'Date'})} — {_('issued by')} {doc.owner_name}"


def _a_cdoc_rev(name, a):
	"""Issues the next revision — the earlier one is withdrawn (kept in the history and the file versions)."""
	CN._need([MD, PM, PMS, QA, SO, DC], _("Issuing a revision"))
	d = S._doc("Controlled Document", name)
	if d.status == "Withdrawn":
		frappe.throw(_("{0} is withdrawn.").format(d.title))
	r = (d.revision or "R0").strip()
	nxt = a.get("revision") or (f"R{cint(r[1:]) + 1}" if r[:1].upper() == "R" and r[1:].isdigit() else f"{r}.1")
	d.revision, d.issued_on, d.review_on, d.status = nxt, today(), add_days(today(), 365), "Current"
	if a.get("file"):
		d.file = a.get("file")
	d.history = (d.history or "") + f"\n{nxt} — {frappe.format(today(), {'fieldtype': 'Date'})} — {_who()}" + (f": {a.get('note')}" if a.get("note") else "")
	d.save()
	return {"message": _("{0} issued as {1} — the earlier revision is withdrawn").format(d.title, nxt)}


def _a_cdoc_status(name, a):
	CN._need([MD, PM, PMS, QA, SO, DC], _("Changing a controlled document"))
	d = S._doc("Controlled Document", name)
	st = a.get("status")
	if st not in ("Under review", "Withdrawn", "Current"):
		frappe.throw(_("Pick a status."))
	d.status = st
	d.history = (d.history or "") + f"\n{_(st)} — {frappe.format(today(), {'fieldtype': 'Date'})} — {_who()}"
	d.save()
	return {"message": _("{0}: {1}").format(d.title, _(st))}


# ================================================================ safety: audits and PPE
def _a_ppe_issue(name, a):
	CN._need([SO, SE, PM, MD, HR], _("Recording PPE issue"))
	w = frappe.get_doc("Site Worker", name)
	if cint(w.ppe_issued):
		frappe.throw(_("{0} already has PPE.").format(w.worker_name))
	w.ppe_issued = 1
	w.flags.ignore_permissions = True
	w.save()
	return {"message": _("PPE issued to {0} — helmet, shoes, vest").format(w.worker_name)}


# ================================================================ flags, validation, actions
def flags(name):
	out = []
	t = getdate(today())
	if _has("Contractor Pay Proof"):
		for c in frappe.get_all("Contractor Pay Proof", filters={"project": name, "status": ["in", ["Gap", "Missing proof"]], "week_end": ["<", add_days(t, -3)]},
				fields=["name", "supplier", "status", "gap", "week_start"]):
			out.append({"lvl": "High" if c.status == "Gap" else "Medium", "text": _("{0}: {1} for the week of {2} — {3} (CLRA: principal employer pays)").format(c.supplier,
				_("wages short") if c.status == "Gap" else _("no pay proof"), frappe.format(c.week_start, {"fieldtype": "Date"}), CN.inr(c.gap)), "open": ["Contractor Pay Proof", c.name]})
	if _has("Controlled Document"):
		for d in frappe.get_all("Controlled Document", filters={"project": name, "status": "Current", "review_on": ["<", t]}, fields=["name", "title", "review_on"]):
			out.append({"lvl": "Low", "text": _("Controlled document past its review — {0}").format(d.title), "open": ["Controlled Document", d.name]})
	n = frappe.db.count("Site Worker", {"project": name, "status": "Active", "ppe_issued": 0})
	if n:
		out.append({"lvl": "Medium", "text": (_("1 worker without PPE") if n == 1 else _("{0} workers without PPE").format(n)), "open": ["Project", name]})
	return out


VALIDATE = {"Contractor Pay Proof": cpp_validate, "Controlled Document": cdoc_validate}
ACTIONS = {"cpp_pay_direct": _a_cpp_pay_direct, "sp_features": _a_sp_features, "msg_reply": _a_msg_reply, "msg_close": _a_msg_close, "unit_book": _a_unit_book,
	"dev_stage": _a_dev_stage, "unit_receive": _a_unit_receive, "am_limits": _a_am_limits, "nt_toggle": _a_nt_toggle, "cdoc_rev": _a_cdoc_rev, "cdoc_status": _a_cdoc_status,
	"ppe_issue": _a_ppe_issue}
