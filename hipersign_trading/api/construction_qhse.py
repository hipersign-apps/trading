"""v1.9.0 stage A4 (prototypes C4, C7): Construction (India) — quality, safety, drawings and handover (feature cn_qhse).

  · quality: the inspection & test plan (test, standard, frequency, hold / witness point; due vs passed from the BOQ quantity
    measured), inspection requests (approve, reject → re-inspect), cube tests (IS 456: 28-day mean ≥ fck + 3 N/mm² and no cube
    below fck − 3; 7-day ≈ 65% of fck), NCRs (closed only with root cause, corrective action and rework cost),
  · safety: incidents (LTI, first aid, near miss), LTI-free days and LTIFR (LTIs per million man-hours, man-hours from the
    DPRs × 8), permits to work issued by the safety officer, toolbox talks, weekly audits (below 80% flagged), PPE gaps,
  · drawings & RFIs: drawing register (number + revision unique; a GFC revision supersedes the earlier ones), RFIs with reply
    due and impact, transmittals with acknowledgement,
  · handover & DLP: snags (fix → client verifies), handover documents (NOCs, occupancy, as-built, manuals), DLP defects
    (respond within 7 days), warranties, the DLP tracker and retention release.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, getdate, today

from hipersign_trading.api import construction as CN

MD, PM, PMS, QA, SO, SE, QS, DC, AM, AU = ("Managing Director", "Project Manager", "Projects Manager", "QA/QC Engineer", "Safety Officer", "Site Engineer",
	"Quantity Surveyor", "Document Controller", "Accounts Manager", "Accounts User")
LTI = "Lost time injury (LTI)"


def _fck(grade):
	return flt((grade or "M25")[1:])


# ---------------------------------------------------------------- validation
def itp_validate(doc):
	doc.tests_done = frappe.db.count("Inspection Request", {"itp_item": doc.name, "status": "Approved"}) if not doc.is_new() else 0
	doc.tests_due = itp_due(doc)


def itp_due(doc):
	"""Inspections due so far: the BOQ quantity measured on the line ÷ the quantity per test (at least one once work starts)."""
	if not doc.boq_item or not flt(doc.per_qty):
		return cint(doc.tests_done)
	_b, r = CN.boq_line(doc.project, doc.boq_item)
	if not r:
		return 0
	done_qty = flt(r.qty) * flt(r.measured_pct) / 100
	return int(done_qty // flt(doc.per_qty)) + (1 if done_qty > 0 else 0)


def ir_validate(doc):
	if doc.itp_item and not doc.activity:
		doc.activity = frappe.db.get_value("ITP Item", doc.itp_item, "activity")


def cube_validate(doc):
	fck = _fck(doc.grade)
	s7 = [flt(x) for x in (doc.s7_1, doc.s7_2, doc.s7_3) if flt(x)]
	s28 = [flt(x) for x in (doc.s28_1, doc.s28_2, doc.s28_3) if flt(x)]
	if s7 and date_diff(today(), doc.cast_on) < 7:
		frappe.throw(_("7-day results before the cubes are 7 days old ({0})?").format(frappe.format(add_days(doc.cast_on, 7), {"fieldtype": "Date"})))
	if s28 and date_diff(today(), doc.cast_on) < 28:
		frappe.throw(_("28-day results before the cubes are 28 days old ({0})?").format(frappe.format(add_days(doc.cast_on, 28), {"fieldtype": "Date"})))
	doc.avg7 = flt(sum(s7) / len(s7), 2) if s7 else 0
	doc.avg28 = flt(sum(s28) / len(s28), 2) if s28 else 0
	if s28:
		doc.result = "Pass" if doc.avg28 >= fck + 3 and min(s28) >= fck - 3 else "Fail"
	elif s7:
		doc.result = "7-day OK" if doc.avg7 >= fck * .65 else "7-day low"
	else:
		doc.result = "Pending"


def ncr_validate(doc):
	if doc.status == "Closed" and not (doc.root_cause and doc.corrective_action):
		frappe.throw(_("An NCR is closed only with its root cause and the corrective action."))


def permit_validate(doc):
	if getdate(doc.valid_to) < getdate(doc.valid_from):
		frappe.throw(_("The permit ends before it starts."))
	if date_diff(doc.valid_to, doc.valid_from) > 7:
		frappe.throw(_("A permit to work is for at most 7 days — raise a new one after that."))


def drawing_validate(doc):
	doc.drawing_no = (doc.drawing_no or "").strip().upper()
	doc.revision = (doc.revision or "").strip().upper()
	if frappe.db.exists("Construction Drawing", {"project": doc.project, "drawing_no": doc.drawing_no, "revision": doc.revision, "name": ["!=", doc.name or ""]}):
		frappe.throw(_("{0} revision {1} is already in the register.").format(doc.drawing_no, doc.revision))


def rfi_validate(doc):
	if getdate(doc.reply_due) < getdate(doc.raised_on):
		frappe.throw(_("The reply is due before the RFI was raised."))


def warranty_validate(doc):
	doc.valid_to = add_months(doc.valid_from, cint(doc.months)) if doc.valid_from else None


def transmittal_validate(doc):
	if not doc.items:
		frappe.throw(_("Add the drawings sent."))
	for r in doc.items:
		if frappe.db.get_value("Construction Drawing", r.drawing, "status") == "Superseded" and doc.purpose == "For construction":
			frappe.throw(_("{0} rev {1} is superseded — send the current revision.").format(r.drawing_no, r.revision))


VALIDATE = {"ITP Item": itp_validate, "Inspection Request": ir_validate, "Cube Test": cube_validate, "NCR": ncr_validate, "Work Permit": permit_validate,
	"Construction Drawing": drawing_validate, "RFI": rfi_validate, "Construction Warranty": warranty_validate, "Transmittal": transmittal_validate}


# ---------------------------------------------------------------- figures
def safety(project):
	"""LTI-free days, LTIFR (per million man-hours), audit score, open permits."""
	inc = frappe.get_all("Safety Incident", filters={"project": project}, fields=["incident_date", "kind"])
	ltis = [i for i in inc if i.kind == LTI]
	start = frappe.db.get_value("Project", project, "expected_start_date") or add_days(today(), -365)
	last = max((getdate(i.incident_date) for i in ltis), default=getdate(start))
	md = flt(frappe.db.sql("select sum(own_labour + sub_labour) from `tabDaily Progress Report` where project = %s", project)[0][0])
	# the DPRs are kept for the last weeks only: the man-hours since the start are the DPR rate × the days worked
	dpr_days = cint(frappe.db.sql("select count(distinct report_date) from `tabDaily Progress Report` where project = %s", project)[0][0])
	worked = max(1, date_diff(today(), start)) * 26 / 30
	hours = (md / dpr_days * worked * 8) if dpr_days else 0
	audit = frappe.get_all("Safety Audit", filters={"project": project}, fields=["score", "audit_date"], order_by="audit_date desc", limit=1)
	return frappe._dict(ltis=len(ltis), lti_free=max(0, date_diff(today(), last)), hours=hours, ltifr=len(ltis) * 1e6 / hours if hours else 0,
		near_miss=len([i for i in inc if i.kind == "Near miss"]), first_aid=len([i for i in inc if i.kind == "First aid"]),
		audit=flt(audit[0].score) if audit else None, audit_on=audit[0].audit_date if audit else None)


def dlp(project):
	"""Defects liability: start (completion), end, retention held and released, the PBG's validity against DLP + 30 days."""
	p = frappe.get_cached_doc("Project", project)
	F = CN.fig(project)
	from hipersign_trading.api import construction_biz as B

	c = B.contract_of(project)
	done = getdate(p.get("hs_cn_completed_on") or p.expected_end_date or today())
	months = cint((c and c.dlp_months) or p.get("hs_dlp_months") or 12)
	end = getdate(add_months(done, months))
	released = released_retention(project)
	pbg = None
	if frappe.get_meta("Bank Guarantee").has_field("project"):
		g = frappe.get_all("Bank Guarantee", filters={"project": project, "docstatus": 1, "hs_bond_type": "Performance bond"} if frappe.get_meta("Bank Guarantee").has_field("hs_bond_type")
			else {"project": project, "docstatus": 1}, fields=["name", "end_date"], order_by="end_date desc", limit=1)
		pbg = g[0] if g else None
	return frappe._dict(start=done, end=end, months=months, retention=F.retention, released=released, held=max(0, F.retention - released),
		release_now=max(0, F.retention / 2 - released) if F.step >= 22 else 0, release_end=F.retention - max(released, F.retention / 2),
		pbg=pbg, pbg_ok=bool(pbg and pbg.end_date and getdate(pbg.end_date) >= getdate(add_days(end, 30))))


def released_retention(project):
	return flt(frappe.db.sql("""select sum(credit - debit) from `tabGL Entry` where is_cancelled = 0 and project = %s and voucher_type = 'Journal Entry'
		and account in (select name from `tabAccount` where account_name = 'Retention Receivable')""", project)[0][0])


def flags(name):
	out = []
	if not frappe.db.exists("DocType", "NCR"):
		return out
	t = getdate(today())

	def add(lvl, text, dt, dn):
		out.append({"lvl": lvl, "text": text, "open": [dt, dn]})

	for c in frappe.get_all("Cube Test", filters={"project": name, "result": ["in", ["Fail", "7-day low"]]}, fields=["name", "pour", "grade", "avg28", "avg7", "result"]):
		add("High" if c.result == "Fail" else "Medium", _("Cube test {0} {1} at {2}: {3} N/mm²").format(c.grade, _("failed") if c.result == "Fail" else _("low at 7 days"), c.pour,
			c.avg28 if c.result == "Fail" else c.avg7), "Cube Test", c.name)
	for n in frappe.get_all("NCR", filters={"project": name, "status": "Open"}, fields=["name", "title", "severity", "close_by"]):
		if n.severity != "Minor" or (n.close_by and getdate(n.close_by) < t):
			add("High" if n.severity == "Critical" else "Medium", _("NCR {0} open — {1}").format(_(n.severity).lower(), n.title), "NCR", n.name)
	for r in frappe.get_all("RFI", filters={"project": name, "status": "Open", "reply_due": ["<", t]}, fields=["name", "subject", "impact", "reply_due"]):
		add("High" if r.impact == "Holds work" else "Medium", _("RFI late by {0} days{1} — {2}").format(date_diff(t, r.reply_due), _(", holding work") if r.impact == "Holds work" else "", r.subject),
			"RFI", r.name)
	a = frappe.get_all("Safety Audit", filters={"project": name}, fields=["name", "score"], order_by="audit_date desc", limit=1)
	if a and flt(a[0].score) < 80:
		add("Medium", _("Last safety audit {0:.0f}% (below 80%)").format(flt(a[0].score)), "Safety Audit", a[0].name)
	for i in frappe.get_all("Safety Incident", filters={"project": name, "status": "Open", "kind": ["in", [LTI, "Medical treatment", "Dangerous occurrence"]]}, fields=["name", "kind"]):
		add("High", _("{0} not closed — root cause and action pending").format(_(i.kind)), "Safety Incident", i.name)
	for d in frappe.get_all("DLP Defect", filters={"project": name, "status": "Reported"}, fields=["name", "location", "reported_on"]):
		if date_diff(t, d.reported_on) > 7:
			add("High", _("DLP defect at {0} not answered for {1} days — retention at risk").format(d.location, date_diff(t, d.reported_on)), "DLP Defect", d.name)
	sn = frappe.get_all("Snag", filters={"project": name, "status": "Open", "target": ["<", t]}, pluck="name")
	if sn:
		add("Medium", _("{0} snags past their fix-by date").format(len(sn)), "Project", name)
	return out


# ---------------------------------------------------------------- actions
def _who():
	return frappe.utils.get_fullname(frappe.session.user)


def _doc(dt, name, perm="write"):
	d = frappe.get_doc(dt, name)
	d.check_permission(perm)
	return d


def _refresh_itp(name):
	if name:
		i = frappe.get_doc("ITP Item", name)
		i.flags.ignore_permissions = True
		i.save()


def _a_ir_approve(name, a):
	CN._need([QA, PM, MD], _("Recording the inspection"))
	r = _doc("Inspection Request", name)
	if r.status != "Requested":
		frappe.throw(_("{0} is {1}.").format(r.name, _(r.status)))
	r.status, r.inspected_on, r.result_note = "Approved", today(), a.get("note") or r.result_note or _("Accepted — proceed")
	r.save()
	_refresh_itp(r.itp_item)
	return {"message": _("{0} approved — the next activity can start").format(r.name)}


def _a_ir_reject(name, a):
	CN._need([QA, PM, MD], _("Recording the inspection"))
	r = _doc("Inspection Request", name)
	if r.status != "Requested":
		frappe.throw(_("{0} is {1}.").format(r.name, _(r.status)))
	r.status, r.inspected_on, r.result_note = "Rejected", today(), a.get("note") or _("Not accepted")
	r.save()
	n = frappe.copy_doc(r)
	n.status, n.result_note, n.inspected_on, n.reinspection_of = "Requested", None, None, r.name
	n.requested_on, n.wanted_on = today(), add_days(today(), 2)
	n.insert()
	frappe.db.set_value("Inspection Request", r.name, "status", "Re-inspected")
	return {"message": _("{0} rejected — re-inspection {1} on {2}").format(r.name, n.name, frappe.format(n.wanted_on, {"fieldtype": "Date"})), "open": ["Inspection Request", n.name]}


def _a_ncr_close(name, a):
	CN._need([QA, PM, MD], _("Closing an NCR"))
	n = _doc("NCR", name)
	for f in ("root_cause", "corrective_action", "rework_cost"):
		if a.get(f) is not None and a.get(f) != "":
			n.set(f, a.get(f))
	n.status, n.closed_on = "Closed", today()
	n.save()
	return {"message": _("{0} closed").format(n.name)}


def _a_inc_close(name, a):
	CN._need([SO, PM, MD], _("Closing an incident"))
	i = _doc("Safety Incident", name)
	for f in ("root_cause", "action"):
		if a.get(f):
			i.set(f, a.get(f))
	if i.kind != "Near miss" and not (i.root_cause and i.action):
		frappe.throw(_("Record the root cause and the corrective action first."))
	i.status = "Closed"
	i.save()
	return {"message": _("{0} closed").format(i.name)}


def _a_ptw_issue(name, a):
	CN._need([SO, MD], _("Issuing a permit to work"))
	p = _doc("Work Permit", name, "read")
	if p.status != "Requested":
		frappe.throw(_("{0} is {1}.").format(p.name, _(p.status)))
	frappe.db.set_value("Work Permit", p.name, {"status": "Issued", "issued_by": _who()})
	return {"message": _("{0} issued — {1} at {2}").format(p.name, _(p.kind).lower(), p.location)}


def _a_ptw_reject(name, a):
	CN._need([SO, MD], _("Refusing a permit to work"))
	p = _doc("Work Permit", name, "read")
	frappe.db.set_value("Work Permit", p.name, {"status": "Rejected", "issued_by": _who()})
	if a.get("note"):
		frappe.get_doc("Work Permit", p.name).add_comment("Comment", a.get("note"))
	return {"message": _("{0} refused").format(p.name)}


def _a_ptw_close(name, a):
	CN._need([SO, SE, PM, MD], _("Closing a permit"))
	p = _doc("Work Permit", name, "read")
	if p.status != "Issued":
		frappe.throw(_("{0} is {1}.").format(p.name, _(p.status)))
	frappe.db.set_value("Work Permit", p.name, "status", "Closed")
	return {"message": _("{0} closed — area handed back").format(p.name)}


def _a_drg_gfc(name, a):
	CN._need([DC, PM, MD, SE], _("Issuing a drawing for construction"))
	d = _doc("Construction Drawing", name)
	if d.status == "Superseded":
		frappe.throw(_("{0} rev {1} is superseded.").format(d.drawing_no, d.revision))
	d.status, d.gfc_on = "GFC", today()
	d.save()
	n = 0
	for o in frappe.get_all("Construction Drawing", filters={"project": d.project, "drawing_no": d.drawing_no, "name": ["!=", d.name], "status": ["!=", "Superseded"]}, pluck="name"):
		frappe.db.set_value("Construction Drawing", o, {"status": "Superseded", "superseded_by": d.name})
		n += 1
	return {"message": _("{0} rev {1} is GFC{2}").format(d.drawing_no, d.revision, _(" — {0} earlier revisions superseded").format(n) if n else "")}


def _a_rfi_answer(name, a):
	CN._need([DC, PM, MD, SE, QS], _("Recording the answer"))
	r = _doc("RFI", name)
	if not a.get("answer") and not r.answer:
		frappe.throw(_("Enter the answer."))
	r.answer = a.get("answer") or r.answer
	r.status, r.answered_on = "Answered", a.get("date") or today()
	r.save()
	return {"message": _("{0} answered").format(r.name)}


def _a_rfi_close(name, a):
	CN._need([DC, PM, MD, SE], _("Closing an RFI"))
	r = _doc("RFI", name)
	r.status = "Closed"
	r.save()
	return {"message": _("{0} closed").format(r.name)}


def _a_trn_ack(name, a):
	CN._need([DC, PM, MD, SE], _("Recording the acknowledgement"))
	t = _doc("Transmittal", name)
	t.status, t.acknowledged_on = "Acknowledged", a.get("date") or today()
	t.save()
	return {"message": _("{0} acknowledged by {1}").format(t.name, t.sent_to)}


def _a_snag_fixed(name, a):
	CN._need([SE, PM, MD, QA], _("Recording a fixed snag"))
	s = _doc("Snag", name)
	if s.status != "Open":
		frappe.throw(_("{0} is {1}.").format(s.name, _(s.status)))
	s.status, s.fixed_on = "Fixed", today()
	s.save()
	return {"message": _("{0} fixed — for the client to verify").format(s.name)}


def _a_snag_verify(name, a):
	CN._need([PM, MD, QA], _("Recording the client's verification"))
	s = _doc("Snag", name)
	if s.status != "Fixed":
		frappe.throw(_("{0} is {1} — fix it first.").format(s.name, _(s.status)))
	s.status, s.verified_on = "Verified", today()
	s.save()
	return {"message": _("{0} verified by the client").format(s.name)}


def _a_hdoc(name, a):
	CN._need([PM, MD, SE, QA, DC], _("Updating a handover document"))
	d = _doc("Handover Document", name)
	nxt = a.get("status") or {"Not started": "Applied", "Applied": "Received"}.get(d.status)
	if not nxt:
		frappe.throw(_("{0} is {1}.").format(d.name, _(d.status)))
	d.status = nxt
	if nxt == "Applied":
		d.applied_on = today()
	if nxt == "Received":
		d.received_on = today()
		d.reference = a.get("reference") or d.reference
	d.save()
	return {"message": _("{0}: {1}").format(d.document, _(nxt))}


def _a_def_respond(name, a):
	CN._need([PM, MD, SE, QA], _("Responding to a defect"))
	d = _doc("DLP Defect", name)
	if d.status != "Reported":
		frappe.throw(_("{0} is {1}.").format(d.name, _(d.status)))
	d.status, d.responded_on = "Responded", today()
	d.save()
	return {"message": _("{0}: response sent — team on site").format(d.name)}


def _a_def_rectify(name, a):
	CN._need([PM, MD, SE, QA], _("Recording the rectification"))
	d = _doc("DLP Defect", name)
	if d.status == "Rectified":
		frappe.throw(_("{0} is already rectified.").format(d.name))
	d.status, d.rectified_on = "Rectified", today()
	if not d.responded_on:
		d.responded_on = today()
	if a.get("cost") is not None:
		d.cost = flt(a.get("cost"))
	d.save()
	return {"message": _("{0} rectified").format(d.name)}


def release_retention(project, amount, posting_date=None, reference=None):
	"""The client pays retention back: Dr Bank · Cr Retention Receivable (the project's)."""
	p = frappe.get_cached_doc("Project", project)
	acc = CN.accounts(p.company)
	cc = p.cost_center or frappe.get_cached_value("Company", p.company, "cost_center")
	je = frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Bank Entry", "company": p.company, "posting_date": posting_date or today(), "cheque_no": reference or f"RET/{project}",
		"cheque_date": posting_date or today(), "user_remark": _("Retention released by {0} — {1}").format(p.customer, p.project_name),
		"accounts": [{"account": CN.bank_account(p.company), "debit_in_account_currency": flt(amount, 2), "cost_center": cc, "project": project},
			{"account": acc.retention, "credit_in_account_currency": flt(amount, 2), "cost_center": cc, "project": project}]})
	je.flags.ignore_permissions = True
	je.flags.hs_system_entry = True
	je.insert()
	je.submit()
	return je.name


def _a_ret_release(name, a):
	CN._need([AM, AU, MD], _("Recording the retention received"))
	frappe.get_doc("Project", name).check_permission("read")
	x = dlp(name)
	amt = flt(a.get("amount")) or x.release_now or x.held
	if amt <= 0:
		frappe.throw(_("No retention to release on {0}.").format(name))
	if amt > x.held + 1:
		frappe.throw(_("Only {0} of retention is held on {1}.").format(CN.inr(x.held), name))
	with CN._elevated():
		je = release_retention(name, amt, a.get("date"))
	return {"message": _("Retention {0} received — {1}").format(CN.inr(amt), je)}


ACTIONS = {
	"ir_approve": _a_ir_approve, "ir_reject": _a_ir_reject, "ncr_close": _a_ncr_close, "inc_close": _a_inc_close, "ptw_issue": _a_ptw_issue, "ptw_reject": _a_ptw_reject,
	"ptw_close": _a_ptw_close, "drg_gfc": _a_drg_gfc, "rfi_answer": _a_rfi_answer, "rfi_close": _a_rfi_close, "trn_ack": _a_trn_ack, "snag_fixed": _a_snag_fixed,
	"snag_verify": _a_snag_verify, "hdoc": _a_hdoc, "def_respond": _a_def_respond, "def_rectify": _a_def_rectify, "ret_release": _a_ret_release,
}
