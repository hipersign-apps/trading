"""v1.9.0 stage A2 (prototype C5): Construction (India) — business & commercial (feature cn_biz).

  · CRM: ERPNext Opportunities marked "Construction enquiry" (category, location, competition, next follow-up), the client
    master, site visits & meetings (Client Visit) and the lost analysis,
  · quotations: ERPNext Quotation marked Construction — estimated cost and margin, discount against the value before
    discount; the MD approves when the discount is above the limit or the margin below the floor (Hipersign Settings); a sent
    quotation is revised (new revision with a reason, the old one cancelled), never overwritten; accepted → project, BOQ from
    the quotation lines and the contract (LOA); lost → reason,
  · contracts: Construction Contract (LOA, agreement, value, retention, advance, time, LD, DLP) kept in step with approved extra
    items, awarded claims and granted EOT; Contract Claim (EOT, cost, prolongation, escalation: submit → negotiate → award);
    liquidated-damages exposure from the programme slip less the EOT granted,
  · collections: the ladder on overdue RA bills (L1 e-mail → L2 PM call → L3 MD letter → L4 legal notice) and its log.
"""

import math

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from hipersign_trading.api import construction as CN

MD, BD, PM, PMS, QS, AM, AU = "Managing Director", "BD Manager", "Project Manager", "Projects Manager", "Quantity Surveyor", "Accounts Manager", "Accounts User"
STAGES = ["Lead", "Qualified", "Site visit", "Estimating", "Proposal sent", "Negotiation"]
STAGE_PROB = {"Lead": 10, "Qualified": 25, "Site visit": 35, "Estimating": 45, "Proposal sent": 60, "Negotiation": 75}
LEVELS = ["L1 — e-mail reminder", "L2 — PM call", "L3 — MD letter", "L4 — legal notice"]
APPROVING = ("Pending", "Rejected")


def limits():
	s = frappe.get_cached_doc("Hipersign Settings")
	return frappe._dict(disc=flt(s.get("cn_quote_discount_limit")) or 5, margin=flt(s.get("cn_quote_margin_floor")) or 10,
		ld_days=cint(s.get("cn_ld_flag_days")) or 21)


def level_for(days_overdue):
	d = cint(days_overdue)
	return None if d <= 0 else LEVELS[0] if d <= 15 else LEVELS[1] if d <= 30 else LEVELS[2] if d <= 60 else LEVELS[3]


# ---------------------------------------------------------------- quotations (doc events)
def quotation_validate(doc, method=None):
	if not cint(doc.get("hs_cn")):
		return
	net = flt(doc.base_net_total)
	cost = flt(doc.get("hs_cn_cost"))
	if cost:
		doc.hs_estimated_gross_profit = net - cost
		doc.hs_estimated_margin = (net - cost) / net * 100 if net else 0
	lst = flt(doc.get("hs_cn_list_value")) or sum(flt(i.price_list_rate) * flt(i.qty) for i in doc.items)
	doc.hs_cn_discount_pct = flt((lst - net) / lst * 100, 2) if lst and lst > net else 0
	L = limits()
	needs = doc.hs_cn_discount_pct > L.disc or (cost and flt(doc.hs_estimated_margin) < L.margin)
	if not needs:
		doc.hs_cn_approval = "Not needed"
	elif doc.hs_cn_approval == "Approved" and abs(flt(doc.get("hs_cn_approved_value")) - net) < 1:
		pass
	elif doc.hs_cn_approval != "Rejected" or abs(flt(doc.get("hs_cn_approved_value")) - net) >= 1:
		doc.hs_cn_approval = "Pending"
	if doc.is_new() and not cint(doc.get("hs_cn_revision")) and not doc.get("hs_cn_revision_of"):
		doc.hs_cn_revision = 0
	if not doc.get("hs_cn_outcome"):
		doc.hs_cn_outcome = "Open"


def quotation_before_submit(doc, method=None):
	if cint(doc.get("hs_cn")) and doc.get("hs_cn_approval") in APPROVING:
		L = limits()
		frappe.throw(_("{0} needs the Managing Director's approval first — discount {1:.1f}% (limit {2:g}%), margin {3:.1f}% (floor {4:g}%).").format(
			doc.name, flt(doc.hs_cn_discount_pct), L.disc, flt(doc.hs_estimated_margin), L.margin))


# ---------------------------------------------------------------- contracts, claims, LD
def contract_of(project):
	n = frappe.db.get_value("Construction Contract", {"project": project, "status": ["!=", "Terminated"]}, "name") if frappe.db.exists("DocType", "Construction Contract") else None
	return frappe.get_doc("Construction Contract", n) if n else None


def claims(project):
	if not frappe.db.exists("DocType", "Contract Claim"):
		return []
	return frappe.get_all("Contract Claim", filters={"project": project}, fields=["name", "title", "kind", "status", "claimed_days", "claimed_amount", "awarded_days",
		"awarded_amount", "submitted_on", "decided_on", "hindrance"], order_by="creation asc")


def claims_awarded(project):
	return sum(flt(c.awarded_amount) for c in claims(project) if c.status == "Awarded")


def eot_granted(project):
	days = sum(cint(c.awarded_days) for c in claims(project) if c.status == "Awarded" and c.kind == "Extension of time")
	days += cint(frappe.db.sql("""select sum(eot_days) from `tabHindrance` where project = %s and eot_status = 'Granted'
		and name not in (select ifnull(hindrance, '') from `tabContract Claim` where project = %s and status = 'Awarded')""", (project, project))[0][0]) \
		if frappe.db.exists("DocType", "Contract Claim") else 0
	return days


def sync_contract(project):
	"""The contract and the project's revised value follow the approved extra items, the awarded claims and the granted EOT."""
	ei = sum(flt(e.amount) for e in CN.eis(project) if e.status == "Approved")
	cl = claims_awarded(project)
	cv = flt(frappe.db.get_value("Project", project, "hs_contract_value"))
	frappe.db.set_value("Project", project, {"hs_variations": ei + cl, "hs_revised_contract": cv + ei + cl})
	c = contract_of(project)
	if c:
		eot = eot_granted(project)
		c.db_set({"variations": ei, "claims_awarded": cl, "revised_value": flt(c.original_value) + ei + cl, "eot_days": eot,
			"extended_completion": add_days(c.completion_date, eot) if c.completion_date else None})


def contract_validate(doc):
	ei = sum(flt(e.amount) for e in CN.eis(doc.project) if e.status == "Approved")
	cl = claims_awarded(doc.project)
	doc.variations, doc.claims_awarded = ei, cl
	doc.revised_value = flt(doc.original_value) + ei + cl
	doc.eot_days = eot_granted(doc.project)
	if doc.completion_date:
		if doc.start_date and getdate(doc.completion_date) <= getdate(doc.start_date):
			frappe.throw(_("Completion is on or before the start."))
		doc.extended_completion = add_days(doc.completion_date, doc.eot_days)
	if frappe.db.exists("Construction Contract", {"project": doc.project, "name": ["!=", doc.name or ""], "status": ["!=", "Terminated"]}):
		frappe.throw(_("{0} already has a contract.").format(doc.project))


def ld(project):
	"""Liquidated-damages exposure: the programme slip (planned % − actual % of the duration) beyond the completion date
	extended by the EOT granted, charged per week at the contract's LD rate, up to its cap. Hindrance days attributable to the
	client, authorities or weather that have no EOT yet are what can still be claimed against it."""
	c = contract_of(project)
	F = CN.fig(project)
	p = frappe.get_cached_doc("Project", project)
	out = frappe._dict(contract=c, planned=flt(p.get("hs_cn_planned_pct")), actual=F.pct, slip=0, forecast=None, delay=0, weeks=0, amount=0, cap=0, claimable=0)
	hin = frappe.get_all("Hindrance", filters={"project": project, "attributable_to": ["in", ["Client", "Authority", "Weather"]], "eot_status": ["in", ["Not applied", "Applied"]]},
		fields=["from_date", "to_date"])
	out.claimable = sum(date_diff(h.to_date or today(), h.from_date) + 1 for h in hin)
	if not c or not c.start_date or not c.completion_date:
		return out
	dur = date_diff(c.completion_date, c.start_date)
	end = c.extended_completion or c.completion_date
	if F.step >= 22:
		out.forecast = c.completion_date
	else:
		out.slip = max(0, round((out.planned - out.actual) / 100 * dur)) if out.planned else 0
		out.forecast = add_days(c.completion_date, out.slip)
	out.delay = max(0, date_diff(out.forecast, end))
	out.weeks = math.ceil(out.delay / 7) if out.delay else 0
	rev = flt(c.revised_value) or F.revised
	out.cap = rev * flt(c.ld_cap_pct) / 100
	out.amount = min(out.cap, rev * flt(c.ld_rate_pct) / 100 * out.weeks)
	return out


def flags(name):
	"""Business red flags added to the Construction project flags."""
	out = []
	if not frappe.db.exists("DocType", "Construction Contract"):
		return out
	x = ld(name)
	if x.delay > limits().ld_days and x.amount:
		out.append({"lvl": "High", "text": _("{0} days behind the extended completion — LD exposure {1}{2}").format(x.delay, CN.inr(x.amount),
			_(" ({0} hindrance days still claimable)").format(x.claimable) if x.claimable else ""), "open": ["Construction Contract", x.contract.name]})
	t = getdate(today())
	for r in frappe.get_all("RA Bill", filters={"project": name, "status": ["in", ["Invoiced", "Part paid"]], "due_date": ["<", add_days(t, -30)]},
			fields=["name", "bill_no", "due_date"]):
		last = frappe.db.get_value("Collection Follow-up", {"ra_bill": r.name}, "followed_on", order_by="followed_on desc")
		if not last or date_diff(t, last) > 14:
			out.append({"lvl": "Medium", "text": _("RA bill {0} overdue {1} days — no follow-up for two weeks").format(r.bill_no, date_diff(t, r.due_date)),
				"open": ["RA Bill", r.name]})
	return out


# ---------------------------------------------------------------- actions
def _who():
	return frappe.utils.get_fullname(frappe.session.user)


def _doc(dt, name, perm="write"):
	d = frappe.get_doc(dt, name)
	d.check_permission(perm)
	return d


def _sales_stage(stage):
	if stage and not frappe.db.exists("Sales Stage", stage):
		frappe.get_doc({"doctype": "Sales Stage", "stage_name": stage}).insert(ignore_permissions=True)
	return stage


def _a_opp_stage(name, a):
	CN._need([BD, MD, PM], _("Moving an enquiry"))
	o = _doc("Opportunity", name)
	st = a.get("stage")
	if st not in STAGES:
		i = STAGES.index(o.sales_stage) if o.sales_stage in STAGES else -1
		st = STAGES[min(len(STAGES) - 1, i + 1)]
	o.sales_stage = _sales_stage(st)
	o.probability = max(cint(o.probability), STAGE_PROB[st])
	o.save()
	return {"message": _("{0} moved to {1}").format(o.title or o.name, _(st))}


def _a_opp_followed(name, a):
	CN._need([BD, MD, PM], _("Recording a follow-up"))
	o = _doc("Opportunity", name)
	o.hs_cn_next_date = a.get("date") or add_days(today(), 7)
	o.save()
	if a.get("note"):
		o.add_comment("Comment", a.get("note"))
	return {"message": _("Next follow-up on {0}").format(frappe.format(o.hs_cn_next_date, {"fieldtype": "Date"}))}


def _lost_reason(r):
	r = (r or "Other").strip()
	if not frappe.db.exists("Opportunity Lost Reason", r):
		frappe.get_doc({"doctype": "Opportunity Lost Reason", "lost_reason": r}).insert(ignore_permissions=True)
	if frappe.db.exists("DocType", "Quotation Lost Reason") and not frappe.db.exists("Quotation Lost Reason", r):
		frappe.get_doc({"doctype": "Quotation Lost Reason", "order_lost_reason": r}).insert(ignore_permissions=True)
	return r


def _a_opp_lost(name, a):
	CN._need([BD, MD], _("Closing an enquiry as lost"))
	o = _doc("Opportunity", name)
	r = _lost_reason(a.get("reason"))
	comp = []
	if a.get("competitor"):
		if not frappe.db.exists("Competitor", a.competitor):
			frappe.get_doc({"doctype": "Competitor", "competitor_name": a.competitor}).insert(ignore_permissions=True)
		comp = [{"competitor": a.competitor}]
	for q in frappe.get_all("Quotation", filters={"opportunity": o.name, "docstatus": 1, "status": ["not in", ["Lost", "Ordered"]]}, pluck="name"):
		qd = frappe.get_doc("Quotation", q)
		qd.flags.ignore_permissions = True
		qd.declare_enquiry_lost([{"lost_reason": r}], comp, a.get("note"))
		frappe.db.set_value("Quotation", q, "hs_cn_outcome", "Lost")
	o.reload()
	if o.status != "Lost":
		o.flags.ignore_permissions = True
		o.declare_enquiry_lost([{"lost_reason": r}], comp, a.get("note"))
	return {"message": _("{0} lost — {1}").format(o.title or o.name, _(r))}


def _a_opp_quote(name, a):
	CN._need([BD, MD, QS, PM], _("Preparing a quotation"))
	o = _doc("Opportunity", name, "read")
	frappe.has_permission("Quotation", "create", throw=True)
	if o.opportunity_from not in ("Customer", "Lead", "Prospect"):
		frappe.throw(_("Pick the client on {0} first.").format(o.name))
	from erpnext.crm.doctype.opportunity.opportunity import make_quotation

	q = make_quotation(o.name)
	q.hs_cn, q.hs_cn_outcome = 1, "Open"
	if not q.items:
		q.append("items", {"item_code": CN.works_item(o.get("hs_cn_category")), "qty": 1, "rate": flt(o.opportunity_amount) or 1,
			"description": _("{0} — construction works as per the scope, drawings and specifications").format(o.title or o.party_name)})
	amt = flt(o.opportunity_amount)
	q.hs_cn_list_value = amt
	q.hs_cn_cost = flt(amt * .86, 0)
	q.valid_till = add_days(today(), 45)
	q.hs_subject = o.title
	if q.quotation_to == "Customer":
		q.company_address = CN.branch_address(q.company, q.party_name) or q.get("company_address")
		tpl = CN._tax_template(q.company, q.company_address, q.party_name)
		if tpl:
			q.taxes_and_charges = tpl
			q.set("taxes", [])
			for r in frappe.get_doc("Sales Taxes and Charges Template", tpl).taxes:
				q.append("taxes", {"charge_type": r.charge_type, "account_head": r.account_head, "rate": r.rate, "description": r.description})
	q.flags.ignore_permissions = True
	q.run_method("set_missing_values")
	q.run_method("calculate_taxes_and_totals")
	q.insert()
	frappe.db.set_value("Opportunity", o.name, {"sales_stage": _sales_stage("Estimating"), "probability": max(cint(o.probability), 45)})
	return {"message": _("Quotation {0} drafted — check the cost and the lines").format(q.name), "open": ["Quotation", q.name]}


def _a_qt_approve(name, a):
	CN._need([MD], _("Approving a quotation"))
	q = _doc("Quotation", name, "read")
	if q.hs_cn_approval != "Pending":
		frappe.throw(_("{0} does not need approval.").format(q.name))
	q.db_set({"hs_cn_approval": "Approved", "hs_cn_approved_by": _who(), "hs_cn_approved_value": q.base_net_total})
	q.add_comment("Comment", _("Approved by {0}: discount {1:.1f}%, margin {2:.1f}%").format(_who(), flt(q.hs_cn_discount_pct), flt(q.hs_estimated_margin)))
	return {"message": _("{0} approved — it can be sent").format(q.name)}


def _a_qt_reject(name, a):
	CN._need([MD], _("Rejecting a quotation"))
	q = _doc("Quotation", name, "read")
	q.db_set({"hs_cn_approval": "Rejected", "hs_cn_approved_by": _who(), "hs_cn_approved_value": q.base_net_total})
	q.add_comment("Comment", _("Sent back by {0}: {1}").format(_who(), a.get("note") or _("rework the price")))
	return {"message": _("{0} sent back for rework").format(q.name)}


def _a_qt_send(name, a):
	CN._need([BD, MD, PM, QS], _("Sending a quotation"))
	q = _doc("Quotation", name)
	if q.docstatus != 0:
		frappe.throw(_("{0} is already sent.").format(q.name))
	q.submit()
	if q.opportunity:
		frappe.db.set_value("Opportunity", q.opportunity, {"sales_stage": _sales_stage("Proposal sent"), "probability": 60})
	return {"message": _("{0} sent to the client — {1}").format(q.name, CN.inr(q.base_net_total))}


def _a_qt_revise(name, a):
	CN._need([BD, MD, PM, QS], _("Revising a quotation"))
	reason = (a.get("reason") or "").strip()
	if not reason:
		frappe.throw(_("Give the reason for the revision."))
	q = _doc("Quotation", name)
	if q.docstatus != 1 or q.hs_cn_outcome not in ("Open", None, ""):
		frappe.throw(_("Only a sent, open quotation is revised — {0} is {1}.").format(q.name, _(q.hs_cn_outcome or q.status)))
	n = frappe.copy_doc(q)
	n.hs_cn_revision = cint(q.hs_cn_revision) + 1
	n.hs_cn_revision_of, n.hs_cn_revision_reason, n.hs_cn_outcome = q.name, reason, "Open"
	n.hs_cn_approval, n.hs_cn_approved_by, n.hs_cn_approved_value = "Not needed", None, 0
	n.transaction_date, n.valid_till = today(), add_days(today(), 45)
	n.insert()
	with CN._elevated():
		old = frappe.get_doc("Quotation", q.name)
		old.flags.ignore_links = True
		old.cancel()
		frappe.db.set_value("Quotation", q.name, "hs_cn_outcome", "Revised")
	return {"message": _("Revision {0} drafted as {1}; {2} is withdrawn").format(n.hs_cn_revision, n.name, q.name), "open": ["Quotation", n.name]}


def _customer_of(q):
	if q.quotation_to == "Customer":
		return q.party_name
	if q.quotation_to == "Lead":
		c = frappe.db.get_value("Customer", {"lead_name": q.party_name})
		if c:
			return c
		from erpnext.crm.doctype.lead.lead import make_customer

		cu = make_customer(q.party_name)
		cu.flags.ignore_permissions = True
		cu.insert()
		return cu.name
	frappe.throw(_("Make {0} a customer before accepting the quotation.").format(q.party_name))


def _a_qt_accept(name, a):
	CN._need([MD, BD], _("Recording the client's acceptance"))
	q = _doc("Quotation", name, "read")
	if q.docstatus != 1 or q.hs_cn_outcome not in ("Open", None, ""):
		frappe.throw(_("{0} is {1}.").format(q.name, _(q.hs_cn_outcome or q.status)))
	start = a.get("start") or add_days(today(), 21)
	months = cint(a.get("months")) or 18
	with CN._elevated():
		customer = _customer_of(q)
		opp = frappe.get_doc("Opportunity", q.opportunity) if q.opportunity else None
		cat = (opp and opp.get("hs_cn_category")) or None
		pj = frappe.get_doc({"doctype": "Project", "project_name": q.get("hs_subject") or (opp and opp.title) or q.customer_name, "company": q.company, "customer": customer,
			"status": "Open", "expected_start_date": start, "expected_end_date": add_days(start, months * 30), "percent_complete_method": "Manual",
			"hs_cn": 1, "hs_cn_category": cat, "hs_cn_address": q.get("company_address") or CN.branch_address(q.company, customer), "hs_contract_value": q.base_net_total, "hs_revised_contract": q.base_net_total, "hs_step": 5, "hs_award_date": today(),
			"hs_retention_pct": 5, "hs_advance_pct": 10, "hs_dlp_months": 12, "hs_cn_tds_pct": 2, "hs_cn_planned_pct": 0, "estimated_costing": flt(q.get("hs_cn_cost")),
			"hs_location": opp and opp.get("hs_cn_location"), "hs_payment_terms": q.get("terms") and frappe.utils.strip_html(q.terms)[:500]})
		pj.flags.ignore_permissions = True
		pj.insert()
		b = frappe.get_doc({"doctype": "Project BOQ", "title": pj.project_name, "project": pj.name, "customer": customer, "client_name": q.customer_name, "company": q.company,
			"status": "Awarded", "revision": 1, "tender_value": q.base_net_total, "margin_pct": flt(q.hs_estimated_margin, 1), "target_margin": limits().margin,
			"items": [{"section": "A", "section_name": _("Contract works"), "item_no": f"{i + 1}", "description": r.description or r.item_name, "unit": r.uom, "qty": r.qty,
				"rate": r.base_net_rate, "measured_pct": 0, "certified_pct": 0, "mat_share": 55, "lab_share": 25, "plant_share": 5, "ovh_share": 5} for i, r in enumerate(q.items)]})
		b.flags.ignore_permissions = True
		b.insert()
		c = frappe.get_doc({"doctype": "Construction Contract", "project": pj.name, "quotation": q.name, "loa_no": a.get("loa_no") or f"LOA/{pj.name}", "loa_date": a.get("loa_date") or today(),
			"original_value": q.base_net_total, "start_date": start, "completion_date": add_days(start, months * 30), "retention_pct": 5, "advance_pct": 10,
			"payment_terms": pj.hs_payment_terms})
		c.flags.ignore_permissions = True
		c.insert()
		frappe.db.set_value("Quotation", q.name, {"hs_cn_outcome": "Accepted", "hs_cn_project": pj.name})
		if opp:
			frappe.db.set_value("Opportunity", opp.name, {"status": "Converted", "hs_cn_project": pj.name, "probability": 100})
	return {"message": _("{0} accepted — project {1} and contract {2} created").format(q.name, pj.name, c.name), "open": ["Project", pj.name]}


def _a_qt_lost(name, a):
	CN._need([BD, MD], _("Recording a lost quotation"))
	q = _doc("Quotation", name, "read")
	r = _lost_reason(a.get("reason"))
	with CN._elevated():
		qd = frappe.get_doc("Quotation", q.name)
		qd.declare_enquiry_lost([{"lost_reason": r}], [], a.get("note"))
		frappe.db.set_value("Quotation", q.name, "hs_cn_outcome", "Lost")
		if q.opportunity and frappe.db.get_value("Opportunity", q.opportunity, "status") not in ("Lost", "Converted"):
			frappe.db.set_value("Opportunity", q.opportunity, "status", "Lost")
	return {"message": _("{0} lost — {1}").format(q.name, _(r))}


def _a_clm_submit(name, a):
	CN._need([PM, MD, QS, BD], _("Submitting a claim"))
	c = _doc("Contract Claim", name)
	if c.status != "Draft":
		frappe.throw(_("{0} is {1}.").format(c.name, _(c.status)))
	if not (cint(c.claimed_days) or flt(c.claimed_amount)):
		frappe.throw(_("Enter the days or the amount claimed."))
	c.status, c.submitted_on = "Submitted", today()
	c.save()
	if c.hindrance and c.kind == "Extension of time":
		frappe.db.set_value("Hindrance", c.hindrance, {"eot_status": "Applied", "eot_ref": c.name})
	return {"message": _("{0} submitted to the client").format(c.name)}


def _a_clm_negotiate(name, a):
	CN._need([PM, MD, BD], _("Recording the negotiation"))
	c = _doc("Contract Claim", name)
	if c.status != "Submitted":
		frappe.throw(_("{0} is {1}.").format(c.name, _(c.status)))
	c.status = "Under negotiation"
	c.save()
	return {"message": _("{0} under negotiation").format(c.name)}


def _a_clm_award(name, a):
	CN._need([MD, PM], _("Recording the award"))
	c = _doc("Contract Claim", name)
	if c.status not in ("Submitted", "Under negotiation"):
		frappe.throw(_("{0} is {1}.").format(c.name, _(c.status)))
	days = cint(a.get("days")) if a.get("days") is not None else cint(c.claimed_days)
	amt = flt(a.get("amount")) if a.get("amount") is not None else flt(c.claimed_amount)
	if days > cint(c.claimed_days) or amt > flt(c.claimed_amount) + 0.5:
		frappe.throw(_("The award cannot be more than the claim."))
	c.status, c.decided_on, c.awarded_days, c.awarded_amount = "Awarded", today(), days, amt
	c.save()
	if c.hindrance and c.kind == "Extension of time":
		frappe.db.set_value("Hindrance", c.hindrance, {"eot_status": "Granted", "eot_days": days})
	sync_contract(c.project)
	return {"message": _("{0} awarded{1}{2}").format(c.name, _(" — {0} days").format(days) if days else "", _(" — {0}").format(CN.inr(amt)) if amt else "")}


def _a_clm_reject(name, a):
	CN._need([MD, PM], _("Recording the rejection"))
	c = _doc("Contract Claim", name)
	c.status, c.decided_on = "Rejected", today()
	c.save()
	if c.hindrance and c.kind == "Extension of time":
		frappe.db.set_value("Hindrance", c.hindrance, "eot_status", "Rejected")
	sync_contract(c.project)
	return {"message": _("{0} rejected by the client").format(c.name)}


def _a_fup_log(name, a):
	CN._need([AM, AU, MD, PM, BD], _("Logging a collection follow-up"))
	r = _doc("RA Bill", name, "read")
	frappe.has_permission("Collection Follow-up", "create", throw=True)
	d = date_diff(today(), r.due_date) if r.due_date else 0
	lvl = a.get("level") if a.get("level") in LEVELS else (level_for(d) or LEVELS[0])
	f = frappe.get_doc({"doctype": "Collection Follow-up", "ra_bill": r.name, "level": lvl, "followed_on": today(), "by": _who(),
		"note": a.get("note") or _("Reminder sent"), "promised_date": a.get("promised_date"), "promised_amount": a.get("promised_amount")})
	f.insert()
	return {"message": _("{0} logged on RA bill {1}").format(lvl.split(" — ")[0], r.bill_no)}


ACTIONS = {
	"opp_stage": _a_opp_stage, "opp_followed": _a_opp_followed, "opp_lost": _a_opp_lost, "opp_quote": _a_opp_quote,
	"qt_approve": _a_qt_approve, "qt_reject": _a_qt_reject, "qt_send": _a_qt_send, "qt_revise": _a_qt_revise, "qt_accept": _a_qt_accept, "qt_lost": _a_qt_lost,
	"clm_submit": _a_clm_submit, "clm_negotiate": _a_clm_negotiate, "clm_award": _a_clm_award, "clm_reject": _a_clm_reject,
	"fup_log": _a_fup_log,
}
