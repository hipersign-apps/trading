"""v1.9.1 stage B2 (prototype C12): the Construction Tracker — every contract through the 26 Indian steps, with the facts
behind each step and its red flags — and the project-control registers: tasks (ERPNext Task), risks & issues, minutes of
meeting with action points that become tasks; on RA Billing the RA workbench (the next bill quantity-wise from the
client-checked measurement book), the mobilisation advance (received against the advance BG, recovered from each bill)
and the final bill.

Money: the mobilisation advance is a liability — Dr Bank, Cr Mobilisation Advance Received (project on the line); each
RA bill's advance recovery debits it when the client pays (api/construction.py). Recovery is capped at what was actually
received, so a project whose advance has not come in recovers nothing."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from hipersign_trading.api import construction as CN

# (name, short, what happens, who, documents, approval)
STEPS = [
	("Tender identified (CPPP, state e-procurement or private enquiry)", "Enquiry", "The NIT or enquiry is logged with the tender documents, estimated cost, EMD, pre-bid date and bid due date.", "Tender Engineer", "NIT, tender documents, enquiry file", "Bid / no-bid by the Managing Director"),
	("Pre-bid meeting & site visit", "Pre-bid", "Site visit, soil and access check, pre-bid queries raised and the corrigendum read into the estimate.", "Tender Engineer · Site Engineer", "Site visit report, pre-bid queries, corrigenda", "None"),
	("Estimate & rate analysis (DSR / market rates)", "Estimate", "Every BOQ item gets a rate analysis — material, labour and plant from DSR coefficients and current market rates, plus overheads and profit.", "Estimation Engineer · QS", "Rate analysis, priced BOQ", "Managing Director approves the margin"),
	("Bid submission with EMD", "Bid", "Technical and financial bids uploaded on the portal with the EMD (online or bank guarantee), DSC-signed.", "Tender Engineer", "Technical bid, financial bid (BOQ), EMD receipt / BG", "Managing Director signs the bid"),
	("Bid opening — technical & financial (L1)", "L1", "Technical evaluation, then financial bid opening; ranking L1 / L2 / L3; negotiation if called.", "Tender Engineer · Managing Director", "Comparative statement, negotiation letter", "Managing Director accepts the negotiation"),
	("Letter of acceptance / work order", "LOA", "The client issues the LOA or work order; the tender becomes a contract and a project.", "Managing Director", "LOA / work order", "None"),
	("Agreement & performance security (PBG)", "Agreement", "Contract agreement signed on stamp paper; performance bank guarantee (3–5%) submitted; EMD refunded or adjusted.", "Managing Director · Accounts", "Agreement, performance BG", "Finance Manager"),
	("Mobilisation advance against BG", "Mob. advance", "Mobilisation advance (usually 10%) claimed against an advance BG; recovered from each RA bill.", "Accounts", "Advance claim, advance BG", "Finance Manager"),
	("Mobilisation (labour licence, BOCW, insurance)", "Mobilise", "Site office and stores, CLRA labour licence, BOCW registration, CAR and workmen compensation policies, site team.", "Project Manager", "Labour licence, BOCW registration, CAR / WC policies", "Project Manager"),
	("Budget, schedule & cost codes", "Budget", "Budget per cost head from the estimate, baseline schedule, cost codes per BOQ chapter.", "Project Manager · QS", "Project budget, baseline programme", "Managing Director approves the budget"),
	("Indent & procurement", "Procure", "Site indents against BOQ quantities; quotations, comparison and PO; cement and steel tracked against theoretical consumption.", "Site Engineer · Purchase", "Indent, comparison, purchase order", "Purchase / Project Manager"),
	("Site stores & material issue", "Stores", "GRN at site stores, issue to work fronts, material reconciliation of cement and steel each month.", "Storekeeper", "GRN, material issue slip, reconciliation", "Project Manager signs reconciliation"),
	("Subcontract work orders", "Subcon", "Labour and item-rate subcontracts with their own BOQ, retention and TDS (194C).", "Project Manager · QS", "Subcontract work order", "Managing Director"),
	("Execution & daily progress reports", "DPR", "Daily progress report: manpower, work done vs plan, materials, equipment, weather, hindrances and photos.", "Site Engineer", "DPR, site photos, hindrance register", "Project Manager"),
	("Labour & wages (CLRA, PF / ESI)", "Labour", "Contract labour attendance, wages through bank, PF / ESI and minimum-wage compliance.", "Site Engineer · HR", "Muster roll, wage register, PF / ESI challans", "Project Manager"),
	("Measurement Book (joint measurement)", "MB", "Work measured in the MB — L × B × D × nos per BOQ item and location; checked by our QS and the client's engineer.", "Site Engineer · QS · Client engineer", "MB pages, abstract of measurement", "Client engineer"),
	("RA bill submission", "RA bill", "Running account bill from the checked MB: work to date, less previous bills, this bill.", "QS", "RA bill, MB abstract", "Project Manager (bills above ₹ 1 Cr)"),
	("Client certification", "Certify", "The client's engineer certifies the RA bill — quantities may be cut or kept on hold.", "Client engineer · QS", "Certified RA bill", "Client"),
	("GST invoice & receipt (net of deductions)", "Invoice", "GST tax invoice on the certified value; the client pays net of retention, advance recovery, TDS 194C, GST-TDS and labour cess.", "Accounts", "GST tax invoice, receipt, 26AS / GSTR-2X check", "Finance Manager"),
	("Extra items, deviations & EOT", "Deviations", "Extra items and excess quantities priced and approved by the client; hindrances turned into an extension of time.", "QS · Project Manager", "Extra item statement, deviation statement, EOT application", "Client"),
	("Cost control & material reconciliation", "Cost", "Budget vs actual per cost head, forecast to complete, cement and steel reconciliation, margin.", "Project Manager · Finance", "Cost report, reconciliation", "Monthly review by the Managing Director"),
	("Quality & safety (QA/QC, HSE)", "QA/HSE", "Inspection requests, cube tests, NCRs, permits to work and toolbox talks.", "QA/QC Engineer · Safety Officer", "IR, cube test reports, NCR, permits", "Project Manager"),
	("Completion certificate & handover", "Handover", "Joint inspection, snag list closed, completion certificate, as-built drawings and handover.", "Project Manager", "Completion certificate, as-built set, handover note", "Client"),
	("Final bill", "Final bill", "Final measurement, all extra items and deviations closed, final bill certified.", "QS", "Final bill, no-claim certificate", "Client + Managing Director"),
	("Defect liability & security deposit release", "DLP", "Defects attended during the DLP; retention / security deposit and the PBG released at its end.", "Project Manager · Accounts", "Defect register, release letter", "Client"),
	("Closure & profit report", "Closure", "BGs returned, accounts closed, final cost and profit vs estimate.", "Managing Director", "Profit report, close-out report", "Managing Director"),
]
PHASES = [("Win the work", 0, 6), ("Contract & mobilise", 6, 10), ("Build", 10, 15), ("Measure & bill", 15, 20), ("Control", 20, 22), ("Complete & close", 22, 26)]
STATUS_TONE = {"Tender": "violet", "Mobilising": "amber", "Execution": "blue", "Handover": "green", "DLP": "green", "Closed": "grey"}
LVL = {"Low": 1, "Medium": 2, "High": 3}


def status_of(step):
	step = cint(step)
	return "Closed" if step >= 26 else "DLP" if step >= 24 else "Handover" if step >= 22 else "Execution" if step >= 10 else "Mobilising" if step >= 6 else "Tender"


def _has(dt):
	return frappe.db.exists("DocType", dt)


def _rows(dt, project, fields, f=None, order=None):
	if not _has(dt):
		return []
	return frappe.get_all(dt, filters=dict({"project": project}, **(f or {})), fields=fields, order_by=order or "creation asc")


# ---------------------------------------------------------------- mobilisation advance
def adv_received(project, exclude=None):
	"""Advance received from the client: credits to Mobilisation Advance Received for the project (recoveries are debits)."""
	co = frappe.get_cached_value("Project", project, "company")
	acc = CN.accounts(co).advance
	return flt(frappe.db.sql("""select sum(credit) from `tabGL Entry` where account = %s and project = %s and is_cancelled = 0 and voucher_type = 'Journal Entry'
		and voucher_no != %s""", (acc, project, exclude or ""))[0][0])


def adv_entries(project):
	co = frappe.get_cached_value("Project", project, "company")
	acc = CN.accounts(co).advance
	return frappe.db.sql("""select je.name, je.posting_date, je.cheque_no, sum(gl.credit) amount from `tabGL Entry` gl join `tabJournal Entry` je on je.name = gl.voucher_no
		where gl.account = %s and gl.project = %s and gl.is_cancelled = 0 and gl.voucher_type = 'Journal Entry' and gl.credit > 0
		group by je.name, je.posting_date, je.cheque_no order by je.posting_date""", (acc, project), as_dict=True)


def adv_bg(project):
	if not _has("Bank Guarantee") or not frappe.get_meta("Bank Guarantee").has_field("hs_bond_type"):
		return []
	return frappe.get_all("Bank Guarantee", filters={"project": project, "docstatus": 1, "hs_bond_type": ["like", "%dvance%"]},
		fields=["name", "amount", "end_date", "hs_bond_status", "bank_guarantee_number"], order_by="start_date asc")


def adv_fig(project):
	p = frappe.get_cached_doc("Project", project)
	F = CN.fig(project)
	due = flt(p.get("hs_contract_value")) * flt(p.get("hs_advance_pct")) / 100
	rec = adv_received(project)
	got = F.adv_recovered
	return frappe._dict(pct=flt(p.get("hs_advance_pct")), due=due, received=rec, recovered=got, balance=max(0, rec - got), to_claim=max(0, due - rec))


def _a_adv_receive(name, a):
	"""The client paid the mobilisation advance — Dr Bank, Cr Mobilisation Advance Received (against the advance BG)."""
	CN._need([CN.MD, CN.AM, CN.AU], _("Recording the mobilisation advance"))
	if not CN.is_cn(name):
		frappe.throw(_("{0} is not a Construction (India) project.").format(name))
	A = adv_fig(name)
	if not A.pct:
		frappe.throw(_("{0} has no mobilisation advance in its terms.").format(name))
	amt = flt(a.get("amount")) or A.to_claim
	if amt <= 0:
		frappe.throw(_("The advance of {0} is already received in full.").format(CN.inr(A.due)))
	if amt > A.to_claim + 1:
		frappe.throw(_("{0} is more than the advance still to come ({1} of {2}).").format(CN.inr(amt), CN.inr(A.to_claim), CN.inr(A.due)))
	bg = [g for g in adv_bg(name) if g.hs_bond_status != "Returned"]
	if not bg:
		frappe.throw(_("No advance payment guarantee on {0} — the advance is released against a BG. Add the BG first.").format(name))
	p = frappe.get_cached_doc("Project", name)
	co = p.company
	acc = CN.accounts(co)
	d = a.get("date") or today()
	cc = frappe.get_cached_value("Company", co, "cost_center")
	je = frappe.get_doc({"doctype": "Journal Entry", "company": co, "posting_date": d, "voucher_type": "Bank Entry", "cheque_no": a.get("ref") or f"MOB/{name}",
		"cheque_date": d, "user_remark": _("Mobilisation advance {0} — against {1}").format(name, bg[0].bank_guarantee_number or bg[0].name),
		"accounts": [{"account": CN.bank_account(co), "debit_in_account_currency": amt, "cost_center": cc, "project": name},
			{"account": acc.advance, "credit_in_account_currency": amt, "cost_center": cc, "project": name}]})
	je.flags.hs_system_entry = True
	with CN._elevated():
		je.insert()
		je.submit()
	if cint(p.get("hs_step")) == 7:
		frappe.db.set_value("Project", name, "hs_step", 8)
	return {"message": _("Mobilisation advance {0} received on {1} — {2}").format(CN.inr(amt), name, je.name), "open": ["Journal Entry", je.name]}


# ---------------------------------------------------------------- RA workbench and final bill
def workbench(project):
	"""Per BOQ line: certified / billed before, client-checked measurements not yet billed (this bill), measured but not yet
	checked (waiting), cumulative and the BOQ balance."""
	b = CN.boq(project)
	if not b:
		return []
	billed = {}
	for x in CN._bills(project):
		if x.status == "Draft":
			continue
		for it in frappe.get_all("RA Bill Item", filters={"parent": x.name}, fields=["item_no", "this_qty"]):
			billed[it.item_no] = billed.get(it.item_no, 0) + flt(it.this_qty)
	now, wait = {}, {}
	for m in frappe.get_all("Measurement Book", filters={"project": project, "status": ["in", ["Draft", "Checked by QS", "Client checked"]], "ra_bill": ["is", "not set"]},
		fields=["item_no", "qty", "status"]):
		tgt = now if m.status == "Client checked" else wait
		tgt[m.item_no] = tgt.get(m.item_no, 0) + flt(m.qty)
	out = []
	for r in b.items:
		k = r.item_no
		pv, nw, wt = flt(billed.get(k), 3), flt(now.get(k), 3), flt(wait.get(k), 3)
		if not (pv or nw or wt):
			continue
		out.append(frappe._dict(item_no=k, description=r.description, unit=r.unit, rate=flt(r.rate), qty=flt(r.qty), prev=pv, now=nw, wait=wt, cum=pv + nw,
			bal=flt(r.qty) - pv - nw, amount=flt(nw * flt(r.rate), 2)))
	return out


def final_fig(project):
	F = CN.fig(project)
	B = CN._bills(project)
	fin = [x for x in B if cint(x.is_final)]
	prev = [x for x in B if not cint(x.is_final) and x.status in CN.CERTIFIED]
	b = CN.boq(project)
	work100 = sum(flt(r.amount) * min(100, flt(r.measured_pct)) / 100 for r in (b.items if b else []))
	E = CN.eis(project)
	ei_billed = sum(flt(frappe.db.get_value("RA Bill", x.name, "extra_items_amount")) for x in B if x.status != "Draft")
	return frappe._dict(F=F, final=fin[-1] if fin else None, prev=prev, prev_cert=sum(flt(x.certified_amount) for x in prev), work=work100, ei=F.ei, ei_billed=ei_billed,
		ei_open=[e for e in E if e.status in ("Draft", "Pending client")],
		mb_open=frappe.db.count("Measurement Book", {"project": project, "status": ["in", ["Draft", "Checked by QS"]]}),
		snags_open=frappe.db.count("Snag", {"project": project, "status": "Open"}) if _has("Snag") else 0)


def _a_ra_final(name, a):
	"""The final bill: every client-checked measurement not yet billed, the approved extra items not yet billed, and the
	whole balance of the mobilisation advance recovered."""
	CN._need([CN.QS, CN.PM, CN.MD], _("Preparing the final bill"))
	frappe.has_permission("RA Bill", "create", throw=True)
	X = final_fig(name)
	if X.final:
		frappe.throw(_("{0} already has the final bill {1}.").format(name, X.final.name))
	if cint(X.F.step) < 22:
		frappe.throw(_("The final bill follows the completion certificate and handover — {0} is at step {1}.").format(name, cint(X.F.step) + 1))
	wc = [x.name for x in CN._bills(name) if x.status == "Submitted to client"]
	if wc:
		frappe.throw(_("{0} is still with the client — get it certified before the final bill.").format(", ".join(wc)))
	if X.mb_open:
		frappe.throw(_("{0} measurements are not yet checked by the client — close the measurement book first.").format(X.mb_open))
	if X.ei_open:
		frappe.throw(_("{0} extra items / deviations are still open ({1}) — settle them before the final bill.").format(len(X.ei_open), ", ".join(e.name for e in X.ei_open[:3])))
	if frappe.db.exists("RA Bill", {"project": name, "status": "Draft"}):
		frappe.throw(_("{0} has a draft RA bill — submit or cancel it first.").format(name))
	has_mb = frappe.db.exists("Measurement Book", {"project": name, "status": "Client checked", "ra_bill": ["is", "not set"]})
	if has_mb:
		n = CN.new_ra(name)
		ra = frappe.get_doc("RA Bill", n)
	else:
		ra = frappe.get_doc({"doctype": "RA Bill", "project": name, "bill_date": today(), "period_to": today(), "status": "Draft", "items": []})
	ra.is_final = 1
	ra.extra_items_amount = flt(max(0, X.ei - X.ei_billed), 2)
	ra.remarks = _("Final bill — all measurements and extra items closed")
	ra.flags.ignore_permissions = True
	ra.save() if not ra.is_new() else ra.insert()
	if flt(ra.claimed_amount) <= 0:
		frappe.throw(_("Nothing left to bill on {0} — every measurement and extra item is already billed.").format(name))
	return {"message": _("Final bill {0} prepared — {1}").format(ra.name, CN.inr(ra.claimed_amount)), "open": ["RA Bill", ra.name]}


# ---------------------------------------------------------------- risks, meetings, tasks
def risk_validate(doc):
	if doc.project and not CN.is_cn(doc.project):
		frappe.throw(_("{0} is not a Construction (India) project.").format(doc.project))
	if doc.project:
		doc.company = frappe.get_cached_value("Project", doc.project, "company")
	if doc.kind == "Issue":
		doc.probability = "High"
	doc.score = LVL.get(doc.probability, 2) * LVL.get(doc.impact, 2)


def meeting_validate(doc):
	if doc.project and not CN.is_cn(doc.project):
		frappe.throw(_("{0} is not a Construction (India) project.").format(doc.project))
	if doc.project:
		doc.company = frappe.get_cached_value("Project", doc.project, "company")
	for r in doc.actions:
		if r.due and doc.meeting_date and getdate(r.due) < getdate(doc.meeting_date):
			frappe.throw(_("Row {0}: an action cannot be due before the meeting.").format(r.idx))


def _a_risk_close(name, a):
	d = CN._doc("Project Risk", name)
	if d.status == "Closed":
		frappe.throw(_("{0} is already closed.").format(name))
	d.status, d.closed_on = "Closed", today()
	d.outcome = a.get("outcome") or d.outcome or _("Closed by {0}").format(CN._who())
	d.save()
	return {"message": _("{0} closed").format(d.title)}


def _a_risk_reopen(name, a):
	d = CN._doc("Project Risk", name)
	d.status, d.closed_on = "Open", None
	d.save()
	return {"message": _("{0} reopened").format(d.title)}


def _a_mtg_tasks(name, a):
	"""Each action point without a task becomes a Task on the project, owned by the person named, due when agreed."""
	d = CN._doc("Project Meeting", name)
	if not d.project:
		frappe.throw(_("{0} has no project.").format(name))
	frappe.has_permission("Task", "create", throw=True)
	n = 0
	for r in d.actions:
		if r.task:
			continue
		t = frappe.get_doc({"doctype": "Task", "subject": r.action[:140], "project": d.project, "company": d.company, "exp_end_date": r.due, "status": "Open",
			"priority": "Medium", "hs_task_owner": r.owner_name, "description": _("From {0} — {1} ({2})").format(d.name, d.title, frappe.format(d.meeting_date, {"fieldtype": "Date"}))})
		t.insert()
		r.task = t.name
		n += 1
	if not n:
		frappe.throw(_("Every action point on {0} already has a task.").format(name))
	d.save()
	return {"message": _("{0} tasks raised from {1}").format(n, name)}


def _a_task_done(name, a):
	d = CN._doc("Task", name)
	if d.status in ("Completed", "Cancelled"):
		frappe.throw(_("{0} is {1}.").format(name, _(d.status)))
	d.status = "Completed"
	if d.meta.has_field("completed_on"):
		d.completed_on = today()
	if d.meta.has_field("completed_by") and not d.completed_by:
		d.completed_by = frappe.session.user
	d.save()
	return {"message": _("{0} done").format(d.subject)}


def tasks(names, open_only=False):
	if not names:
		return []
	f = {"project": ["in", names]}
	if open_only:
		f["status"] = ["not in", ["Completed", "Cancelled", "Template"]]
	return frappe.get_list("Task", filters=f, fields=["name", "subject", "project", "status", "priority", "exp_end_date", "hs_task_owner", "type"],
		order_by="exp_end_date asc", limit_page_length=0)


def _snag_type(t):
	return (t.get("type") or "") == "Snag"


def flags(name):
	"""Red flags from B2: an advance not received after mobilisation, high risks past their review date, overdue tasks."""
	out = []
	t = getdate(today())
	p = frappe.get_cached_doc("Project", name)
	step = cint(p.get("hs_step"))
	if flt(p.get("hs_advance_pct")) and 8 <= step < 22:
		A = adv_fig(name)
		if A.received <= 0:
			out.append({"lvl": "Medium", "text": _("Mobilisation advance {0} not received — claim it against the advance BG").format(CN.inr(A.due)), "open": ["Project", name], "step": 7})
	if _has("Project Risk"):
		for r in frappe.get_all("Project Risk", filters={"project": name, "status": "Open", "score": [">=", 6], "review_by": ["<", t]}, fields=["name", "title", "kind"]):
			out.append({"lvl": "High", "text": _("{0} past its review date — {1}").format(_(r.kind), r.title), "open": ["Project Risk", r.name], "step": 20})
	late = [x for x in frappe.get_all("Task", filters={"project": name, "status": ["not in", ["Completed", "Cancelled", "Template"]], "exp_end_date": ["<", t]},
		fields=["name", "subject", "type"]) if not _snag_type(x)]
	if len(late) >= 1 and step < 26:
		out.append({"lvl": "Medium", "text": _("{0} tasks overdue — {1}").format(len(late), late[0].subject), "open": ["Task", late[0].name], "step": 13})
	return out


# ---------------------------------------------------------------- the tracker
FLAG_STEP = {"Tender": 3, "Bank Guarantee": 6, "Construction Contract": 6, "Material Request": 10, "Purchase Order": 10, "Stock Entry": 11, "Subcontractor Work Order": 12,
	"Subcontractor Bill": 12, "Daily Progress Report": 13, "Weekly Muster": 14, "Labour Compliance": 14, "Site Worker": 14, "Measurement Book": 15, "RA Bill": 17,
	"Sales Invoice": 18, "Collection Follow-up": 18, "Extra Item": 19, "Hindrance": 19, "Contract Claim": 19, "NCR": 21, "Cube Test": 21, "Inspection Request": 21,
	"Work Permit": 21, "Safety Incident": 21, "Toolbox Talk": 21, "Snag": 22, "Handover Document": 22, "DLP Defect": 24, "Construction Warranty": 24,
	"Project Constraint": 13, "Construction Milestone": 13, "Project Risk": 20, "Task": 13, "Construction Equipment": 13, "Equipment Log": 13,
	"Equipment Maintenance": 13, "RFI": 13, "Construction Drawing": 13, "Transmittal": 13, "Safety Audit": 21, "Staff Payroll": 14, "Statutory Deposit": 18}
# what a flag says when it opens the project itself (or a record shared by several steps)
FLAG_WORDS = [("Advance payment guarantee", 7), ("obilisation advance", 7), ("labour cess", 18), ("behind the extended completion", 19), ("over theory", 11),
	("indents", 10), ("snag", 22), ("Margin", 20), ("beyond the BOQ", 19), ("TDS", 18)]


def flag_step(f, step):
	if f.get("step") is not None:
		return cint(f["step"])
	dt = (f.get("open") or ["Project"])[0]
	txt = f.get("text") or ""
	for w, i in FLAG_WORDS:
		if w in txt:
			return i
	if dt == "RA Bill":
		return 16 if "not certified" in txt else 18 if ("overdue" in txt or "26AS" in txt) else 17
	if dt in FLAG_STEP:
		return FLAG_STEP[dt]
	return min(25, max(0, cint(step)))


def _fd(d):
	return frappe.format(d, {"fieldtype": "Date"}) if d else "—"


def _cnt(rows, fn):
	return len([r for r in rows if fn(r)])


def states(name):
	p = frappe.get_cached_doc("Project", name)
	F = CN.fig(name)
	step = F.step
	t = getdate(today())
	inr = CN.inr
	out = [frappe._dict(st="done" if i < step else "cur" if i == step else "wait", pct=100 if i < step else 40 if i == step else 0, date=None, info=[],
		tag=_("Done") if i < step else _("In progress") if i == step else _("Pending")) for i in range(26)]

	def s(i, **kw):
		out[i].update(kw)

	tn = frappe.get_all("Tender", filters={"project": name}, fields=["name", "published_on", "due_date", "estimated_value", "our_bid", "rank", "status"], limit=1)
	tn = tn[0] if tn else None
	if tn:
		s(0, date=tn.published_on, info=[[_("Tender"), tn.name], [_("Estimate"), inr(tn.estimated_value)]])
		s(3, date=tn.due_date, info=[[_("Our bid"), inr(tn.our_bid)], [_("Due"), _fd(tn.due_date)]])
		s(4, info=[[_("Rank"), tn.rank or "—"]])
	else:
		s(0, date=p.get("hs_enquiry_date"), info=[[_("Client"), p.customer or "—"]])
	b = CN.boq(name)
	if b:
		s(2, info=[[_("BOQ"), b.name], [_("Lines"), len(b.items)]])
	s(5, date=p.get("hs_award_date"), info=[[_("Contract"), inr(F.contract)], [_("Retention"), f"{flt(p.get('hs_retention_pct')):g}%"]])
	bg = frappe.get_all("Bank Guarantee", filters={"project": name, "docstatus": 1}, fields=["name", "amount", "end_date", "hs_bond_type", "hs_bond_status"]) \
		if _has("Bank Guarantee") and frappe.get_meta("Bank Guarantee").has_field("hs_bond_type") else []
	pbg = [g for g in bg if "erformance" in (g.hs_bond_type or "")]
	s(6, info=[[_("PBG"), f"{inr(g.amount)} · {_('exp.')} {_fd(g.end_date)}"] for g in pbg] or [[_("PBG"), _("not yet")]])
	if flt(p.get("hs_advance_pct")):
		A = adv_fig(name)
		s(7, info=[[_("Advance due"), inr(A.due)], [_("Received"), inr(A.received)], [_("Recovered"), inr(A.recovered)], [_("Balance"), inr(A.balance)]],
			pct=100 if A.received >= A.due - 1 else (A.received / A.due * 100 if A.due else 0) if step >= 7 else 0)
		if step > 7:
			s(7, tag=_("{0} recovered").format(f"{A.recovered / A.received * 100:.0f}%") if A.received else _("Not received"))
	else:
		s(7, info=[[_("Advance"), _("none in the terms")]], tag=_("Not applicable") if step > 7 else _("Pending"))
	if step >= 8:
		lc = _rows("Labour Compliance", name, ["status"])
		s(8, info=[[_("Labour compliance"), _("{0} of {1} complete").format(_cnt(lc, lambda r: r.status == "Complete"), len(lc))]])
		s(9, info=[[_("Budget"), inr(F.budget)], [_("Revised value"), inr(F.revised)]])
	if 10 <= step:
		live = step < 22
		mrs = frappe.get_all("Material Request", filters={"hs_project": name, "docstatus": ["<", 2]}, fields=["docstatus", "per_ordered"]) \
			if frappe.get_meta("Material Request").has_field("hs_project") else []
		pos = frappe.get_all("Purchase Order", filters={"hs_project": name, "docstatus": 1}, fields=["base_net_total", "per_received", "schedule_date"]) \
			if frappe.get_meta("Purchase Order").has_field("hs_project") else []
		po_v = sum(flt(x.base_net_total) for x in pos)
		rc_v = sum(flt(x.base_net_total) * flt(x.per_received) / 100 for x in pos)
		late_po = [x for x in pos if x.schedule_date and getdate(x.schedule_date) < t and flt(x.per_received) < 100]
		s(10, info=[[_("Indents"), len(mrs)], [_("Ordered"), inr(po_v)]], tag=_("{0} POs").format(len(pos)))
		s(11, info=[[_("Received at site"), inr(rc_v)], [_("Late deliveries"), len(late_po), "neg" if late_po else ""]], pct=rc_v / po_v * 100 if po_v else 0)
		wo = _rows("Subcontractor Work Order", name, ["name", "supplier", "status", "value"])
		s(12, info=[[x.name, f"{x.supplier} · {inr(x.value)}"] for x in wo[:3]] or [[_("Work orders"), 0]], tag=_("{0} work orders").format(len(wo)),
			pct=_cnt(wo, lambda r: r.status != "Draft") / len(wo) * 100 if wo else 0)
		dp = _rows("Daily Progress Report", name, ["report_date"], order="report_date desc")
		last = dp[0].report_date if dp else None
		s(13, date=last, pct=F.pct, tag=_("{0}% complete").format(round(F.pct)),
			info=[[_("DPRs"), len(dp)], [_("Last DPR"), _fd(last), "neg" if live and last and date_diff(t, last) > 3 else ""]])
		mu = _rows("Weekly Muster", name, ["status", "net"])
		s(14, info=[[_("Musters"), len(mu)], [_("To pay"), _cnt(mu, lambda r: r.status != "Paid")]])
		mb = frappe.get_all("Measurement Book", filters={"project": name}, fields=["status", "ra_bill"])
		s(15, pct=F.pct, info=[[_("Measurements"), len(mb)], [_("Client checked, not billed"), _cnt(mb, lambda r: r.status == "Client checked" and not r.ra_bill)],
			[_("Waiting for check"), _cnt(mb, lambda r: r.status in ("Draft", "Checked by QS"))]])
		Bs = CN._bills(name)
		s(16, pct=F.billed / F.revised * 100 if F.revised else 0, date=Bs[-1].bill_date if Bs else None, tag=_("{0} bills").format(len(Bs)),
			info=[[_("Bills"), len(Bs)], [_("With the client"), inr(F.pending_cert)]])
		s(17, pct=F.billed / F.revised * 100 if F.revised else 0, info=[[_("Certified to date"), inr(F.billed)]])
		s(18, pct=F.received / (F.billed or 1) * 100 if F.billed else 0, tag=_("{0} overdue").format(inr(F.overdue)) if F.overdue > 1 else _("Received {0}").format(inr(F.received)),
			info=[[_("Received"), inr(F.received)], [_("Outstanding"), inr(F.outstanding)], [_("Overdue"), inr(F.overdue), "neg" if F.overdue > 1 else ""]])
		E = CN.eis(name)
		hin = _rows("Hindrance", name, ["to_date", "eot_status"])
		s(19, info=[[_("Extra items approved"), inr(F.ei)], [_("Pending with the client"), inr(F.ei_pending)], [_("Open hindrances"), _cnt(hin, lambda h: not h.to_date)]],
			pct=_cnt(E, lambda e: e.status == "Approved") / len(E) * 100 if E else 100, tag=_("{0} of {1} approved").format(_cnt(E, lambda e: e.status == "Approved"), len(E)))
		s(20, pct=F.cost / F.fac * 100 if F.fac else 0, tag=_("Margin {0:.1f}%").format(F.margin),
			info=[[_("Budget margin"), f"{F.bud_margin:.1f}%"], [_("Margin on work done"), f"{F.margin:.1f}%"], [_("Cost to date"), inr(F.cost)]])
		nc = _rows("NCR", name, ["status"])
		pw = _rows("Work Permit", name, ["status"])
		s(21, info=[[_("NCRs open"), _cnt(nc, lambda r: r.status == "Open")], [_("Permits issued"), _cnt(pw, lambda r: r.status == "Issued")]],
			pct=_cnt(nc, lambda r: r.status == "Closed") / len(nc) * 100 if nc else 100)
		if live:
			for i in range(10, 22):
				if out[i].st == "done" or out[i].st == "wait" and flt(out[i].pct) > 0:
					out[i].st = "cur"
					out[i].tag = _("Running") if out[i].tag in (_("Done"), _("Pending")) else out[i].tag
	if step >= 21:
		sn = _rows("Snag", name, ["status"])
		s(22, info=[[_("Snags"), _("{0} listed · {1} open").format(len(sn), _cnt(sn, lambda r: r.status == "Open"))]],
			pct=100 if step > 22 else (_cnt(sn, lambda r: r.status != "Open") / len(sn) * 100 if sn else 50))
		X = final_fig(name)
		s(23, info=[[_("Final bill"), X.final.name if X.final else _("not yet")], [_("Certified before"), inr(X.prev_cert)]],
			pct=100 if X.final and X.final.status in CN.CERTIFIED else 50 if X.final else 0)
		df = _rows("DLP Defect", name, ["status"])
		s(24, info=[[_("Defects open"), _cnt(df, lambda r: r.status != "Rectified")], [_("Retention held"), inr(F.retention)]])
	if step >= 26:
		s(25, info=[[_("Final value"), inr(F.revised)], [_("Margin"), f"{F.margin:.1f}%"]])
	for f in CN.flags(name):
		i = flag_step(f, step)
		if out[i].st != "done":
			out[i].st = "late"
	return out


@frappe.whitelist()
def tracker(filter=None, q=None):
	"""The Construction Tracker: every Construction (India) project on one line through the 26 steps."""
	from hipersign_trading.api import module_cn as M

	allowed = set(frappe.get_all("Has Role", filters={"parenttype": "Page", "parent": "hipersign-cn-tracker"}, pluck="role")) | {"System Manager", "Administrator"}
	if not allowed & set(frappe.get_roles()):
		frappe.throw(_("The Construction Tracker is not open to your role."), frappe.PermissionError)
	names = M._names()
	cur = M._cur(names)
	out, allF, nfl, nprj = [], [], 0, 0
	for n in names:
		p = frappe.get_cached_doc("Project", n)
		F = CN.fig(n)
		fl = CN.flags(n)
		allF.append(F)
		nfl += len(fl)
		nprj += 1 if fl else 0
		st = status_of(F.step)
		if filter in (None, "", "open") and F.step >= 26 or filter == "flags" and not fl or filter in STATUS_TONE and st != filter:
			continue
		if q and q.lower() not in f"{n} {p.project_name} {p.customer}".lower():
			continue
		paid = F.received
		out.append({"name": n, "title": p.project_name, "client": p.customer, "location": p.get("hs_location"), "finish": p.expected_end_date, "status": st, "tone": STATUS_TONE[st],
			"rev": F.revised, "pct": F.pct, "billed": F.billed, "certified": F.billed, "collected": paid, "overdue": F.overdue, "out": F.outstanding, "margin": F.margin,
			"bud_margin": F.bud_margin, "step": F.step, "next": _(STEPS[min(25, F.step)][1]),
			"flags": [{"step": flag_step(f, F.step), "text": f["text"], "open": f.get("open")} for f in fl],
			"states": [{"st": x.st, "pct": x.pct, "date": x.date, "tag": x.tag, "info": x.info} for x in states(n)]})
	rev = sum(f.revised for f in allF if f.step >= 5)
	cert = sum(f.billed for f in allF if f.step >= 5)
	from hipersign_trading.api.module import kpi

	return {"currency": cur, "projects": out, "steps": [{"name": _(s[0]), "short": _(s[1]), "who": _(s[3]), "docs": _(s[4]), "what": _(s[2]), "approve": _(s[5])} for s in STEPS],
		"phases": [{"name": _(a), "a": b, "b": c} for a, b, c in PHASES],
		"counts": {"all": len(names), "open": len([f for f in allF if f.step < 26]), "flags": nprj},
		"kpis": [kpi(_("Projects tracked"), len(names), _("{0} on site").format(len([f for f in allF if 10 <= f.step < 22])), "blue", "list"),
			kpi(_("Order book"), rev, _("Incl. approved extra items"), "navy", "file-text", True, cur),
			kpi(_("Certified"), cert, _("{0}% of the order book").format(round(cert / rev * 100) if rev else 0), "violet", "check", True, cur),
			kpi(_("Received"), sum(f.received for f in allF), _("{0} retention held").format(CN.inr(sum(f.retention for f in allF))), "green", "banknote", True, cur),
			kpi(_("Red flags"), nfl, _("{0} projects need attention").format(nprj), "red" if nfl else "green", "flag")]}


VALIDATE = {"Project Risk": risk_validate, "Project Meeting": meeting_validate}
ACTIONS = {"adv_receive": _a_adv_receive, "ra_final": _a_ra_final, "risk_close": _a_risk_close, "risk_reopen": _a_risk_reopen, "mtg_tasks": _a_mtg_tasks,
	"task_done": _a_task_done}
