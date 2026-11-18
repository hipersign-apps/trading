"""v1.9.0 stage A4 (prototypes C4, C7): the Construction (India) pages Quality (QA/QC), Safety (HSE), Drawings & RFIs and
Handover & DLP — on the module page renderer. Rules in api/construction_qhse.py."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_qhse as Q
from hipersign_trading.api.module import _perm, kpi
from hipersign_trading.api.module_cn import _btn, _chips, _cur, _date, _js, _m, _names, _pcell, _pick, _proj, _q

KEYS = ("cn_qa", "cn_hse", "cn_doc", "cn_hnd")


def _list(dt, f, fields, order="creation desc", names=None, limit=0):
	if not _perm(dt):
		return []
	return frappe.get_list(dt, filters=dict({"project": ["in", (names if names is not None else _names()) or [""]]}, **(f or {})), fields=fields, order_by=order,
		limit_page_length=limit)


def _t():
	return getdate(today())


# ================================================================ Quality (QA/QC)
def cn_qa_module():
	names = _names(False)
	IR = _list("Inspection Request", {"status": "Requested"}, ["name", "wanted_on"], names=names)
	CT = _list("Cube Test", {}, ["result", "cast_on"], names=names)
	NC = _list("NCR", {"status": "Open"}, ["severity", "close_by"], names=names)
	ITP = _list("ITP Item", {}, ["tests_done", "tests_due", "point"], names=names)
	behind = [i for i in ITP if cint(i.tests_due) > cint(i.tests_done)]
	t = _t()
	return {
		"title": _("Quality (QA/QC)"),
		"desc": _("The inspection & test plan, inspection requests at hold and witness points, concrete cube tests against IS 456 and non-conformances closed with root cause and action."),
		"new": [{"label": _("Inspection request"), "doctype": "Inspection Request", "primary": 1}, {"label": _("Cube test"), "doctype": "Cube Test"}, {"label": _("NCR"), "doctype": "NCR"},
			{"label": _("ITP line"), "doctype": "ITP Item"}],
		"kpis": [
			kpi(_("Inspections waiting"), len(IR), _("{0} past the date wanted").format(len([i for i in IR if getdate(i.wanted_on) < t])), "orange" if IR else "green", "clipboard-check", tab="ir"),
			kpi(_("Cube tests"), len(CT), _("{0} failed · {1} awaiting 28 days").format(len([c for c in CT if c.result == "Fail"]), len([c for c in CT if c.result in ("Pending", "7-day OK", "7-day low")])),
				"red" if any(c.result == "Fail" for c in CT) else "blue", "box", tab="cube"),
			kpi(_("Open NCRs"), len(NC), _("{0} major / critical").format(len([n for n in NC if n.severity != "Minor"])), "red" if any(n.severity != "Minor" for n in NC) else "orange" if NC else "green",
				"triangle-alert", tab="ncr"),
			kpi(_("ITP behind"), len(behind), _("of {0} lines — tests due not done").format(len(ITP)), "orange" if behind else "green", "list-checks", tab="itp", chip="behind"),
		],
		"tabs": [
			{"key": "ir", "label": _("Inspection requests"), "chips": [["Requested", _("Waiting")], ["all", _("All")]]},
			{"key": "cube", "label": _("Cube tests"), "chips": [["open", _("Awaiting results")], ["Fail", _("Failed")], ["all", _("All")]]},
			{"key": "ncr", "label": _("NCRs"), "chips": [["Open", _("Open")], ["all", _("All")]]},
			{"key": "itp", "label": _("Inspection & test plan"), "chips": [["all", _("All")], ["behind", _("Behind")]] + _chips(names)},
		],
	}


def cn_qa_rows(tab, chip, q=None):
	names = _names(False)
	cur = _cur()
	t = _t()
	if tab == "cube":
		chip = chip or "open"
		f = {"result": ["in", ["Pending", "7-day OK", "7-day low"]]} if chip == "open" else {"result": "Fail"} if chip == "Fail" else {}
		rows = []
		for c in _list("Cube Test", f, ["name", "project", "pour", "grade", "cast_on", "lab", "avg7", "avg28", "result", "s28_1", "s28_2", "s28_3"], "cast_on desc", names):
			if not _q(q, c.name, c.pour, c.grade, c.project):
				continue
			fck = Q._fck(c.grade)
			age = date_diff(t, c.cast_on)
			s28 = [flt(x) for x in (c.s28_1, c.s28_2, c.s28_3) if flt(x)]
			rows.append({"dt": "Cube Test", "name": c.name, "cells": [{"main": c.pour, "sub": c.name}, _pcell(c.project), {"main": c.grade, "sub": _("needs {0:g} (each ≥ {1:g})").format(fck + 3, fck - 3)},
				{"main": _date(c.cast_on)["date"] and frappe.format(c.cast_on, {"fieldtype": "Date"}), "sub": _("{0} days old").format(age)},
				{"main": f"{flt(c.avg7):.1f}" if flt(c.avg7) else "—", "sub": _("{0:.0f}% of fck").format(flt(c.avg7) / fck * 100) if flt(c.avg7) else (_("due {0}").format(frappe.format(add_days(c.cast_on, 7), {"fieldtype": "Date"})) if age < 7 else _("enter results"))},
				{"main": f"{flt(c.avg28):.1f}" if flt(c.avg28) else "—", "sub": (_("lowest {0:.1f}").format(min(s28)) if s28 else (_("due {0}").format(frappe.format(add_days(c.cast_on, 28), {"fieldtype": "Date"})) if age < 28 else _("enter results"))),
					"late": 1 if not s28 and age >= 28 else 0},
				{"pill": _(c.result), "tone": {"Pass": "green", "Fail": "red", "7-day low": "orange", "7-day OK": "blue"}.get(c.result, "grey")}]})
		return {"title": _("Concrete cube tests — IS 456: 28-day mean ≥ fck + 3, no cube below fck − 3"), "cols": [{"label": _("Pour")}, {"label": _("Project")}, {"label": _("Grade")},
			{"label": _("Cast")}, {"label": _("7 days")}, {"label": _("28 days")}, {"label": _("Result")}], "rows": rows, "nototal": 1, "empty": _("No cube tests here.")}
	if tab == "ncr":
		rows = []
		for n in _list("NCR", {} if chip == "all" else {"status": "Open"}, ["name", "project", "title", "severity", "responsible", "supplier", "raised_on", "close_by", "status", "rework_cost",
				"root_cause"], "raised_on desc", names):
			if not _q(q, n.name, n.title, n.project, n.supplier):
				continue
			late = n.status == "Open" and n.close_by and getdate(n.close_by) < t
			rows.append({"dt": "NCR", "name": n.name, "cells": [{"main": n.title, "sub": n.name}, _pcell(n.project), {"pill": _(n.severity), "tone": {"Critical": "red", "Major": "orange"}.get(n.severity, "grey")},
				{"main": _(n.responsible), "sub": n.supplier or ""}, _date(n.close_by, late), {"money": n.rework_cost, "currency": cur},
				{"pill": _(n.status), "tone": "green" if n.status == "Closed" else "orange", "sub": (n.root_cause or "")[:40]},
				{"buttons": [_js(_("Close…"), "cn_ncr_close", n.name)]} if n.status == "Open" else ""]})
		return {"title": _("Non-conformance reports"), "cols": [{"label": _("NCR")}, {"label": _("Project")}, {"label": _("Severity")}, {"label": _("Responsible")}, {"label": _("Close by")},
			{"label": _("Rework"), "cls": "num"}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No NCRs here.")}
	if tab == "itp":
		chip = chip or "all"
		rows = []
		ps = names if chip in ("all", "behind") else [chip]
		for i in _list("ITP Item", {}, ["name", "project", "activity", "test", "standard", "point", "frequency", "tests_done", "tests_due", "boq_item"], "project asc, creation asc", ps):
			if chip == "behind" and cint(i.tests_due) <= cint(i.tests_done):
				continue
			if not _q(q, i.activity, i.test, i.standard, i.project):
				continue
			gap = cint(i.tests_due) - cint(i.tests_done)
			rows.append({"dt": "ITP Item", "name": i.name, "cells": [{"main": i.activity, "sub": i.boq_item and _("BOQ {0}").format(i.boq_item) or ""}, _pcell(i.project), {"main": i.test, "sub": i.standard or ""},
				{"pill": _(i.point), "tone": {"Hold": "red", "Witness": "orange"}.get(i.point, "blue")}, i.frequency or "—",
				{"main": f"{cint(i.tests_done)} / {cint(i.tests_due)}", "sub": _("{0} behind").format(gap) if gap > 0 else _("up to date"), "late": 1 if gap > 0 else 0}]})
		return {"title": _("Inspection & test plan — inspections passed vs due from the work measured"), "cols": [{"label": _("Activity")}, {"label": _("Project")}, {"label": _("Test · standard")},
			{"label": _("Point")}, {"label": _("Frequency")}, {"label": _("Done / due")}], "rows": rows, "nototal": 1, "empty": _("No ITP lines here.")}
	rows = []
	for r in _list("Inspection Request", {} if chip == "all" else {"status": "Requested"}, ["name", "project", "activity", "location", "wanted_on", "inspector", "status", "result_note",
			"reinspection_of", "requested_by"], "wanted_on desc", names):
		if not _q(q, r.name, r.activity, r.location, r.project):
			continue
		late = r.status == "Requested" and getdate(r.wanted_on) < t
		rows.append({"dt": "Inspection Request", "name": r.name, "cells": [{"main": r.activity, "sub": r.name + (_(" · re-inspection") if r.reinspection_of else "")}, _pcell(r.project),
			r.location or "—", _date(r.wanted_on, late), {"main": r.inspector or "—", "sub": r.requested_by or ""},
			{"pill": _(r.status), "tone": {"Approved": "green", "Rejected": "red", "Re-inspected": "grey"}.get(r.status, "orange"), "sub": (r.result_note or "")[:40]},
			{"buttons": [_btn(_("Approved"), "ir_approve", r.name, True), _js(_("Rejected…"), "cn_ir_reject", r.name)]} if r.status == "Requested" else ""]})
	return {"title": _("Inspection requests"), "cols": [{"label": _("Activity")}, {"label": _("Project")}, {"label": _("Location")}, {"label": _("Wanted on")}, {"label": _("Inspector")},
		{"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No inspection requests here.")}


# ================================================================ Safety (HSE)
def cn_hse_module():
	names = _names(False)
	S_ = {n: Q.safety(n) for n in names if CN.fig(n).step >= 10}  # sites at work
	ltis = sum(x.ltis for x in S_.values())
	hours = sum(x.hours for x in S_.values())
	free = min((x.lti_free for x in S_.values()), default=0)
	P_ = _list("Work Permit", {"status": ["in", ["Requested", "Issued"]]}, ["status", "valid_to"], names=names)
	A = [(n, x.audit) for n, x in S_.items() if x.audit is not None]
	ppe = frappe.db.count("Site Worker", {"project": ["in", names or [""]], "status": "Active", "ppe_issued": 0}) if _perm("Site Worker") else 0
	return {
		"title": _("Safety (HSE)"),
		"desc": _("Incidents and near misses, LTI-free days and LTIFR from the DPR man-hours, permits to work issued by the safety officer, toolbox talks, weekly audits and PPE."),
		"new": [{"label": _("Report incident"), "doctype": "Safety Incident", "primary": 1}, {"label": _("Permit to work"), "doctype": "Work Permit"},
			{"label": _("Toolbox talk"), "doctype": "Toolbox Talk"}, {"label": _("Safety audit"), "doctype": "Safety Audit"}],
		"kpis": [
			kpi(_("LTI-free days"), free, _("lowest of {0} sites").format(len(S_)), "green" if free > 90 else "orange", "shield-check", tab="inc"),
			kpi(_("LTIFR"), f"{ltis * 1e6 / hours:.2f}" if hours else "—", _("{0} LTIs · {1:,.0f} man-hours").format(ltis, hours), "blue", "chart-line", tab="site"),
			kpi(_("Permits"), len([p for p in P_ if p.status == "Requested"]), _("to issue · {0} live").format(len([p for p in P_ if p.status == "Issued"])), "orange" if any(p.status == "Requested" for p in P_) else "blue",
				"file-check", tab="ptw"),
			kpi(_("Site audits"), f"{sum(a for _n, a in A) / len(A):.0f}%" if A else "—", _("{0} sites below 80%").format(len([1 for _n, a in A if a < 80])), "red" if any(a < 80 for _n, a in A) else "green",
				"clipboard-check", tab="site"),
			kpi(_("Workers without PPE"), ppe, _("issue before work"), "red" if ppe else "green", "hard-hat", route=["hipersign-cn-labour"]),
		],
		"tabs": [
			{"key": "inc", "label": _("Incidents"), "chips": [["open", _("Open")], ["all", _("All")]]},
			{"key": "site", "label": _("By site"), "chips": []},
			{"key": "ptw", "label": _("Permits to work"), "chips": [["live", _("Requested & live")], ["all", _("All")]]},
			{"key": "tbt", "label": _("Toolbox talks"), "chips": []},
		],
	}


def cn_hse_rows(tab, chip, q=None):
	names = _names(False)
	t = _t()
	if tab == "site":
		rows = []
		for n in names:
			x = Q.safety(n)
			tb = frappe.db.count("Toolbox Talk", {"project": n, "talk_date": [">=", add_days(t, -30)]}) if _perm("Toolbox Talk") else 0
			rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), {"main": _("{0} days").format(x.lti_free), "sub": _("{0} LTIs").format(x.ltis)}, f"{x.ltifr:.2f}",
				{"main": f"{x.hours:,.0f}"}, {"main": _("{0} · {1}").format(x.near_miss, x.first_aid), "sub": _("near miss · first aid")},
				{"main": f"{x.audit:.0f}%" if x.audit is not None else "—", "sub": frappe.format(x.audit_on, {"fieldtype": "Date"}) if x.audit_on else "", "late": 1 if x.audit is not None and x.audit < 80 else 0},
				{"main": tb, "sub": _("last 30 days")}]})
		return {"title": _("Safety by site"), "cols": [{"label": _("Project")}, {"label": _("LTI-free")}, {"label": _("LTIFR")}, {"label": _("Man-hours")}, {"label": _("Near miss · first aid")},
			{"label": _("Last audit")}, {"label": _("Toolbox talks")}], "rows": rows, "nototal": 1, "empty": _("No sites.")}
	if tab == "ptw":
		f = {"status": ["in", ["Requested", "Issued"]]} if (chip or "live") == "live" else {}
		rows = []
		for p in _list("Work Permit", f, ["name", "project", "kind", "location", "valid_from", "valid_to", "status", "requested_by", "issued_by", "work"], "valid_from desc", names):
			if not _q(q, p.name, p.kind, p.location, p.project):
				continue
			exp = p.status == "Issued" and getdate(p.valid_to) < t
			b = {"Requested": [_btn(_("Issue"), "ptw_issue", p.name, True), _btn("✕", "ptw_reject", p.name, confirm=_("Refuse {0}?").format(p.name))],
				"Issued": [_btn(_("Close"), "ptw_close", p.name)]}.get(p.status)
			rows.append({"dt": "Work Permit", "name": p.name, "cells": [{"main": _(p.kind), "sub": p.name}, _pcell(p.project), {"main": p.location, "sub": (p.work or "")[:40]},
				{"main": f"{frappe.format(p.valid_from, {'fieldtype': 'Date'})} → {frappe.format(p.valid_to, {'fieldtype': 'Date'})}", "late": 1 if exp else 0},
				{"main": p.requested_by or "—", "sub": p.issued_by or ""}, {"pill": _(p.status) if not exp else _("Expired"), "tone": {"Issued": "green", "Requested": "orange", "Rejected": "red"}.get(p.status, "grey") if not exp else "red"},
				{"buttons": b} if b else ""]})
		return {"title": _("Permits to work"), "cols": [{"label": _("Permit")}, {"label": _("Project")}, {"label": _("Location · work")}, {"label": _("Valid")}, {"label": _("Requested · issued")},
			{"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No permits here.")}
	if tab == "tbt":
		rows = [{"dt": "Toolbox Talk", "name": x.name, "cells": [_date(x.talk_date), _pcell(x.project), x.topic, {"main": x.conducted_by or "—", "sub": _(x.language or "")}, x.attendees or 0]}
			for x in _list("Toolbox Talk", {}, ["name", "project", "talk_date", "topic", "conducted_by", "attendees", "language"], "talk_date desc", names, 100) if _q(q, x.topic, x.project)]
		return {"title": _("Toolbox talks"), "cols": [{"label": _("Date")}, {"label": _("Project")}, {"label": _("Topic")}, {"label": _("By · language")}, {"label": _("Attendees")}], "rows": rows,
			"empty": _("No toolbox talks yet.")}
	rows = []
	for i in _list("Safety Incident", {} if chip == "all" else {"status": "Open"}, ["name", "project", "incident_date", "kind", "location", "person", "days_lost", "status", "description", "root_cause"],
			"incident_date desc", names):
		if not _q(q, i.name, i.kind, i.description, i.project):
			continue
		rows.append({"dt": "Safety Incident", "name": i.name, "cells": [_date(i.incident_date), _pcell(i.project), {"pill": _(i.kind), "tone": "red" if i.kind == Q.LTI else "orange" if i.kind != "Near miss" else "blue"},
			{"main": (i.description or "")[:60], "sub": " · ".join(x for x in (i.location, i.person) if x)}, i.days_lost or "—",
			{"pill": _(i.status), "tone": "green" if i.status == "Closed" else "orange", "sub": (i.root_cause or "")[:40]},
			{"buttons": [_js(_("Close…"), "cn_inc_close", i.name)]} if i.status == "Open" else ""]})
	return {"title": _("Incidents and near misses"), "cols": [{"label": _("Date")}, {"label": _("Project")}, {"label": _("Kind")}, {"label": _("What happened")}, {"label": _("Days lost")},
		{"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No incidents here.")}


# ================================================================ Drawings & RFIs
def cn_doc_module():
	names = _names(False)
	t = _t()
	D = _list("Construction Drawing", {}, ["status"], names=names)
	R = _list("RFI", {"status": "Open"}, ["reply_due", "impact"], names=names)
	late = [r for r in R if getdate(r.reply_due) < t]
	T = _list("Transmittal", {"status": "Sent"}, ["sent_on"], names=names)
	return {
		"title": _("Drawings & RFIs"),
		"desc": _("The drawing register with revisions — a GFC revision supersedes the earlier ones — requests for information with reply dates and impact, and transmittals with acknowledgement."),
		"new": [{"label": _("New drawing"), "doctype": "Construction Drawing", "primary": 1}, {"label": _("New RFI"), "doctype": "RFI"}, {"label": _("Transmittal"), "doctype": "Transmittal"}],
		"kpis": [
			kpi(_("Drawings current"), len([d for d in D if d.status in ("GFC", "For approval", "For information")]), _("{0} GFC · {1} for approval").format(len([d for d in D if d.status == "GFC"]),
				len([d for d in D if d.status == "For approval"])), "navy", "file-text", tab="dwg"),
			kpi(_("Open RFIs"), len(R), _("{0} late · {1} holding work").format(len(late), len([r for r in late if r.impact == "Holds work"])), "red" if late else "blue", "message-circle-question", tab="rfi"),
			kpi(_("Transmittals not acknowledged"), len(T), _("{0} over 7 days").format(len([x for x in T if date_diff(t, x.sent_on) > 7])), "orange" if T else "green", "send", tab="trn"),
		],
		"tabs": [
			{"key": "dwg", "label": _("Drawing register"), "chips": [["current", _("Current")], ["For approval", _("For approval")], ["Superseded", _("Superseded")], ["all", _("All")]]},
			{"key": "rfi", "label": _("RFIs"), "chips": [["Open", _("Open")], ["late", _("Late")], ["all", _("All")]]},
			{"key": "trn", "label": _("Transmittals"), "chips": []},
		],
	}


def cn_doc_rows(tab, chip, q=None):
	names = _names(False)
	t = _t()
	if tab == "rfi":
		chip = chip or "Open"
		f = {} if chip == "all" else {"status": "Open"}
		rows = []
		for r in _list("RFI", f, ["name", "project", "subject", "impact", "raised_on", "reply_due", "status", "answered_on", "raised_by", "drawing"], "reply_due asc", names):
			late = r.status == "Open" and getdate(r.reply_due) < t
			if chip == "late" and not late:
				continue
			if not _q(q, r.name, r.subject, r.project):
				continue
			b = {"Open": [_js(_("Answered…"), "cn_rfi_answer", r.name)], "Answered": [_btn(_("Close"), "rfi_close", r.name)]}.get(r.status)
			rows.append({"dt": "RFI", "name": r.name, "cells": [{"main": r.subject, "sub": r.name + (f" · {r.drawing}" if r.drawing else "")}, _pcell(r.project),
				{"pill": _(r.impact), "tone": "red" if r.impact == "Holds work" else "orange" if r.impact != "None" else "grey"}, _date(r.raised_on),
				{"main": frappe.format(r.reply_due, {"fieldtype": "Date"}), "sub": _("{0} days late").format(date_diff(t, r.reply_due)) if late else "", "late": 1 if late else 0},
				{"pill": _(r.status), "tone": {"Answered": "blue", "Closed": "green"}.get(r.status, "orange")}, {"buttons": b} if b else ""]})
		return {"title": _("Requests for information"), "cols": [{"label": _("RFI")}, {"label": _("Project")}, {"label": _("Impact")}, {"label": _("Raised")}, {"label": _("Reply due")},
			{"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No RFIs here.")}
	if tab == "trn":
		rows = []
		for x in _list("Transmittal", {}, ["name", "project", "sent_to", "purpose", "sent_on", "acknowledged_on", "status"], "sent_on desc", names):
			if not _q(q, x.name, x.sent_to, x.project):
				continue
			n = frappe.db.count("Transmittal Item", {"parent": x.name})
			rows.append({"dt": "Transmittal", "name": x.name, "cells": [{"main": x.sent_to, "sub": x.name}, _pcell(x.project), _(x.purpose), _("{0} drawings").format(n), _date(x.sent_on),
				{"pill": _(x.status), "tone": "green" if x.status == "Acknowledged" else "orange", "sub": frappe.format(x.acknowledged_on, {"fieldtype": "Date"}) if x.acknowledged_on else ""},
				{"buttons": [_btn(_("Acknowledged"), "trn_ack", x.name, True)]} if x.status == "Sent" else ""]})
		return {"title": _("Transmittals"), "cols": [{"label": _("To")}, {"label": _("Project")}, {"label": _("Purpose")}, {"label": _("Drawings")}, {"label": _("Sent")}, {"label": _("Status")},
			{"label": ""}], "rows": rows, "empty": _("No transmittals yet.")}
	chip = chip or "current"
	f = {"status": ["!=", "Superseded"]} if chip == "current" else {} if chip == "all" else {"status": chip}
	rows = []
	for d in _list("Construction Drawing", f, ["name", "project", "drawing_no", "revision", "title", "discipline", "status", "issued_on", "gfc_on", "superseded_by", "file"],
			"project asc, drawing_no asc, revision desc", names):
		if not _q(q, d.drawing_no, d.title, d.project, d.discipline):
			continue
		rows.append({"dt": "Construction Drawing", "name": d.name, "cells": [{"main": d.drawing_no, "sub": d.title}, _pcell(d.project), {"main": d.revision}, _(d.discipline),
			_date(d.gfc_on or d.issued_on), {"pill": _(d.status), "tone": {"GFC": "green", "Superseded": "grey", "For approval": "orange"}.get(d.status, "blue"), "sub": d.superseded_by or ""},
			{"url": d.file, "label": _("Open")} if d.file else "",
			{"buttons": [_btn(_("Issue GFC"), "drg_gfc", d.name, True, confirm=_("Issue {0} rev {1} for construction? Earlier revisions are superseded.").format(d.drawing_no, d.revision))]}
			if d.status == "For approval" else ""]})
	return {"title": _("Drawing register"), "cols": [{"label": _("Drawing")}, {"label": _("Project")}, {"label": _("Rev")}, {"label": _("Discipline")}, {"label": _("Date")}, {"label": _("Status")},
		{"label": _("File")}, {"label": ""}], "rows": rows, "empty": _("No drawings here.")}


# ================================================================ Handover & DLP
def cn_hnd_module():
	names = _names()
	cur = _cur(names)
	t = _t()
	SN = _list("Snag", {"status": ["in", ["Open", "Fixed"]]}, ["status", "target"], names=names)
	HD = _list("Handover Document", {"status": ["in", ["Not started", "Applied"]]}, ["status"], names=names)
	DF = _list("DLP Defect", {"status": ["in", ["Reported", "Responded"]]}, ["status", "reported_on"], names=names)
	dl = [n for n in names if CN.fig(n).step >= 22]
	held = sum(Q.dlp(n).held for n in names if CN.fig(n).bills)
	return {
		"title": _("Handover & DLP"),
		"desc": _("Snags before handover, the handover documents (NOCs, occupancy, as-built, manuals), defects in the liability period, warranties, the DLP tracker and retention release."),
		"new": [{"label": _("New snag"), "doctype": "Snag", "primary": 1}, {"label": _("DLP defect"), "doctype": "DLP Defect"}, {"label": _("Handover document"), "doctype": "Handover Document"},
			{"label": _("Warranty"), "doctype": "Construction Warranty"}],
		"kpis": [
			kpi(_("Open snags"), len([s for s in SN if s.status == "Open"]), _("{0} past fix-by · {1} to verify").format(len([s for s in SN if s.status == "Open" and s.target and getdate(s.target) < t]),
				len([s for s in SN if s.status == "Fixed"])), "orange" if SN else "green", "list-todo", tab="snag"),
			kpi(_("Handover documents pending"), len(HD), _("{0} applied, awaiting").format(len([h for h in HD if h.status == "Applied"])), "blue", "folder-check", tab="docs"),
			kpi(_("DLP defects open"), len(DF), _("{0} not answered in 7 days").format(len([d for d in DF if d.status == "Reported" and date_diff(t, d.reported_on) > 7])),
				"red" if any(d.status == "Reported" and date_diff(t, d.reported_on) > 7 for d in DF) else "orange" if DF else "green", "wrench", tab="def"),
			kpi(_("Retention held by clients"), held, _("{0} projects in DLP").format(len(dl)), "amber", "landmark", True, cur, tab="dlp"),
		],
		"tabs": [
			{"key": "snag", "label": _("Snags"), "chips": [["open", _("Open & to verify")], ["all", _("All")]] + _chips(names)},
			{"key": "docs", "label": _("Handover documents"), "chips": []},
			{"key": "def", "label": _("DLP defects"), "chips": [["open", _("Open")], ["all", _("All")]]},
			{"key": "dlp", "label": _("DLP tracker & retention"), "chips": []},
			{"key": "wty", "label": _("Warranties"), "chips": []},
		],
	}


def cn_hnd_rows(tab, chip, q=None):
	names = _names()
	cur = _cur(names)
	t = _t()
	if tab == "docs":
		rows = []
		for d in _list("Handover Document", {}, ["name", "project", "document", "authority", "status", "applied_on", "received_on", "reference"], "project asc, creation asc", names):
			if not _q(q, d.document, d.authority, d.project):
				continue
			b = {"Not started": [_btn(_("Applied"), "hdoc", d.name)], "Applied": [_btn(_("Received"), "hdoc", d.name, True)]}.get(d.status)
			rows.append({"dt": "Handover Document", "name": d.name, "cells": [{"main": d.document, "sub": d.authority or ""}, _pcell(d.project),
				{"pill": _(d.status), "tone": {"Received": "green", "Applied": "blue", "Not needed": "grey"}.get(d.status, "orange")},
				{"main": frappe.format(d.received_on or d.applied_on, {"fieldtype": "Date"}) if (d.received_on or d.applied_on) else "—",
					"sub": _("applied {0} days ago").format(date_diff(t, d.applied_on)) if d.status == "Applied" and d.applied_on else (d.reference or "")}, {"buttons": b} if b else ""]})
		return {"title": _("Handover documents"), "cols": [{"label": _("Document")}, {"label": _("Project")}, {"label": _("Status")}, {"label": _("Date")}, {"label": ""}], "rows": rows,
			"nototal": 1, "empty": _("No handover documents yet.")}
	if tab == "def":
		f = {"status": ["in", ["Reported", "Responded"]]} if (chip or "open") == "open" else {}
		rows = []
		for d in _list("DLP Defect", f, ["name", "project", "location", "description", "reported_on", "responded_on", "rectified_on", "status", "cost"], "reported_on desc", names):
			if not _q(q, d.location, d.description, d.project):
				continue
			age = date_diff(t, d.reported_on)
			b = {"Reported": [_btn(_("Responded"), "def_respond", d.name, True)], "Responded": [_js(_("Rectified…"), "cn_def_rectify", d.name)]}.get(d.status)
			rows.append({"dt": "DLP Defect", "name": d.name, "cells": [{"main": d.location, "sub": (d.description or "")[:60]}, _pcell(d.project), _date(d.reported_on),
				{"pill": _(d.status), "tone": {"Rectified": "green", "Responded": "blue"}.get(d.status, "red" if age > 7 else "orange"),
					"sub": _("{0} days, not answered").format(age) if d.status == "Reported" else "", "late": 1 if d.status == "Reported" and age > 7 else 0},
				{"money": d.cost, "currency": cur}, {"buttons": b} if b else ""]})
		return {"title": _("Defects in the liability period — answer within 7 days"), "cols": [{"label": _("Defect")}, {"label": _("Project")}, {"label": _("Reported")}, {"label": _("Status")},
			{"label": _("Cost"), "cls": "num"}, {"label": ""}], "rows": rows, "empty": _("No defects here.")}
	if tab == "dlp":
		rows = []
		for n in names:
			F = CN.fig(n)
			if F.step < 15 or not F.bills:
				continue
			x = Q.dlp(n)
			b = [_js(_("Retention received…"), "cn_ret_release", n)] if x.held > 1 and F.step >= 22 else []
			rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), {"pill": _("In DLP") if F.step >= 22 else _("Building"), "tone": "green" if F.step >= 22 else "blue"},
				{"main": frappe.format(x.end, {"fieldtype": "Date"}), "sub": _("{0} months from {1}").format(x.months, frappe.format(x.start, {"fieldtype": "Date"}))},
				{"money": x.retention, "currency": cur}, {"money": x.released, "currency": cur}, {"money": x.held, "currency": cur,
					"sub": _("{0} due now (half at completion)").format(_m(x.release_now, cur)) if x.release_now > 1 else ""},
				{"pill": _("Valid") if x.pbg_ok else _("Short of DLP + 30") if x.pbg else _("No PBG"), "tone": "green" if x.pbg_ok else "red",
					"sub": frappe.format(x.pbg.end_date, {"fieldtype": "Date"}) if x.pbg else ""}, {"buttons": b} if b else ""]})
		return {"title": _("DLP tracker — retention and performance guarantee"), "cols": [{"label": _("Project")}, {"label": _("Stage")}, {"label": _("DLP ends")}, {"label": _("Retention"), "cls": "num"},
			{"label": _("Released"), "cls": "num"}, {"label": _("Held"), "cls": "num"}, {"label": _("PBG")}, {"label": ""}], "rows": rows, "empty": _("No projects billed yet.")}
	if tab == "wty":
		rows = []
		for w in _list("Construction Warranty", {}, ["name", "project", "item", "supplier", "months", "valid_from", "valid_to", "handed_over", "certificate"], "valid_to asc", names):
			if not _q(q, w.item, w.supplier, w.project):
				continue
			rows.append({"dt": "Construction Warranty", "name": w.name, "cells": [{"main": w.item, "sub": w.supplier or ""}, _pcell(w.project), _("{0} months").format(w.months),
				_date(w.valid_to, w.valid_to and getdate(w.valid_to) < getdate(add_days(today(), 60))), {"pill": _("Handed over") if w.handed_over else _("Not yet"), "tone": "green" if w.handed_over else "orange"},
				{"url": w.certificate, "label": _("Certificate")} if w.certificate else ""]})
		return {"title": _("Warranties"), "cols": [{"label": _("Item")}, {"label": _("Project")}, {"label": _("Period")}, {"label": _("Valid to")}, {"label": _("Client")}, {"label": ""}], "rows": rows,
			"nototal": 1, "empty": _("No warranties yet.")}
	chip = chip or "open"
	ps = names if chip in ("open", "all") else [chip]
	rows = []
	for s in _list("Snag", {"status": ["in", ["Open", "Fixed"]]} if chip == "open" else {}, ["name", "project", "location", "trade", "supplier", "description", "target", "status", "fixed_on"],
			"target asc", ps):
		if not _q(q, s.location, s.description, s.trade, s.supplier):
			continue
		late = s.status == "Open" and s.target and getdate(s.target) < t
		b = {"Open": [_btn(_("Fixed"), "snag_fixed", s.name, True)], "Fixed": [_btn(_("Client verified"), "snag_verify", s.name, True)]}.get(s.status)
		rows.append({"dt": "Snag", "name": s.name, "cells": [{"main": s.location, "sub": (s.description or "")[:60]}, _pcell(s.project), {"main": _(s.trade), "sub": s.supplier or _("Own team")},
			_date(s.target, late), {"pill": _(s.status), "tone": {"Verified": "green", "Fixed": "blue"}.get(s.status, "orange")}, {"buttons": b} if b else ""]})
	return {"title": _("Snags"), "cols": [{"label": _("Snag")}, {"label": _("Project")}, {"label": _("Trade")}, {"label": _("Fix by")}, {"label": _("Status")}, {"label": ""}], "rows": rows,
		"empty": _("No snags here.")}
