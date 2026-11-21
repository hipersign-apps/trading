"""v1.9.1 stage B4: Labour & Workers › Pay day, Contractor pay proof, Wage ledgers; Client Portal › Inbox; Subcontractor Portal
› Inbox, Feature settings; Quotations & Sales › Unit sales; Cost Control › S-curve; Accounts › Approval matrix, Notification
rules (and more standard screens on Statements); Drawings & RFIs › Controlled documents; Safety › Site audits, PPE
compliance. Rules in api/construction_extra.py."""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_extra as X
from hipersign_trading.api.module import _perm, kpi

COLS = lambda *a: [{"label": x[0], "cls": "num"} if isinstance(x, tuple) else {"label": x} for x in a]


def _h():
	from hipersign_trading.api import module_cn as M

	return M


def _wrap(base_m, base_r, add_m, rows, keys):
	def m():
		return add_m(base_m())

	def r(tab, chip, q=None):
		return rows(tab, chip, q) if tab in keys else base_r(tab, chip, q)
	m.__name__, r.__name__ = base_m.__name__, base_r.__name__
	return m, r


def _tabs(m, new, at=None):
	m["tabs"] = (m["tabs"][:at] + new + m["tabs"][at:]) if at is not None else m["tabs"] + new
	return m


# ================================================================ Labour & Workers
def lab_m(m):
	M = _h()
	names = M._names(False)
	MU, _r = X.pay_day(names)
	C = frappe.get_list("Contractor Pay Proof", filters={"project": ["in", names or [""]], "status": ["in", ["Gap", "Missing proof"]]}, pluck="name") if _perm("Contractor Pay Proof") else []
	m["new"] = (m.get("new") or []) + [{"label": _("Contractor pay proof"), "doctype": "Contractor Pay Proof"}]
	return _tabs(m, [{"key": "pay", "label": _("Pay day") + (f" ({len(MU)})" if MU else ""), "chips": []},
		{"key": "cpp", "label": _("Contractor pay proof") + (f" ({len(C)})" if C else ""), "chips": [["open", _("Gaps & missing")], ["all", _("All")]]},
		{"key": "led", "label": _("Wage ledgers"), "chips": [[n, n] for n in names]}], 2)


def lab_rows(tab, chip, q=None):
	M = _h()
	names = M._names(False)
	cur = M._cur()
	if tab == "pay":
		MU, R = X.pay_day(names)
		rows = []
		for m in MU:
			b = [M._btn(_("Approve"), "mus_approve", m.name, True)] if m.status == "Draft" else [M._btn(_("Pay by UPI"), "mus_pay", m.name, True,
				confirm=_("Pay {0} by UPI and post the wage journal?").format(CN.inr(m.net)))]
			rows.append({"cls": "hsx-grp-row", "dt": "Weekly Muster", "name": m.name, "cells": [{"main": f"{m.project} · {m.name}", "sub": _("week from {0}").format(
				frappe.format(m.week_start, {"fieldtype": "Date"}))}, "", "", "", "", "", {"money": m.net, "currency": cur}, {"pill": _(m.status), "tone": "amber" if m.status == "Draft" else "blue"},
				{"buttons": b}]})
			for r in [x for x in R if x.muster == m.name]:
				if not M._q(q, r.worker_name, r.project, r.trade):
					continue
				rows.append({"cells": [{"main": r.worker_name, "sub": r.trade or ""}, f"{flt(r.days):g}", f"{flt(r.ot_hours):g}", {"money": r.earned, "currency": cur},
					{"money": flt(r.pf) + flt(r.esi), "currency": cur}, {"money": r.advance_recovery, "currency": cur}, {"money": r.net, "currency": cur},
					{"main": r.upi or "—", "late": 0 if r.upi else 1}, ""]})
		return {"title": _("Pay day — Wednesday: approve each site's muster, then pay by UPI; PF / ESI and advance recovery come off the wages"),
			"cols": COLS(_("Worker"), (_("Days"),), (_("OT h"),), (_("Earned"),), (_("PF + ESI"),), (_("Advance"),), (_("Net"),), _("UPI"), ""), "rows": rows, "nototal": 1,
			"empty": _("No muster waiting — every week is paid.")}
	if tab == "cpp":
		f = {"project": ["in", names or [""]]}
		if (chip or "open") == "open":
			f["status"] = ["in", ["Gap", "Missing proof"]]
		rows = []
		for c in frappe.get_list("Contractor Pay Proof", filters=f, fields=["name", "project", "supplier", "work_order", "week_start", "workers", "mandays", "due", "paid", "gap", "status", "proof",
				"journal_entry", "recovered_in"], order_by="week_start desc", limit_page_length=0) if _perm("Contractor Pay Proof") else []:
			if not M._q(q, c.supplier, c.project, c.work_order):
				continue
			st = {"buttons": [M._btn(_("Pay direct & recover"), "cpp_pay_direct", c.name, True, confirm=_("Pay {0} to the workers and recover it from {1}?").format(CN.inr(c.gap), c.supplier))]} \
				if c.status == "Gap" else {"pill": _(c.status), "tone": {"Verified": "green", "Paid direct": "violet", "Missing proof": "red"}.get(c.status, "grey"),
				"sub": c.recovered_in or c.journal_entry or ""}
			rows.append({"dt": "Contractor Pay Proof", "name": c.name, "cells": [{"date": str(c.week_start), "sub": c.name}, {"main": c.supplier, "sub": f"{c.work_order} · {c.project}"},
				str(cint(c.workers)), f"{flt(c.mandays):g}", {"money": c.due, "currency": cur}, {"money": c.paid, "currency": cur},
				{"money": c.gap, "currency": cur, "late": 1 if flt(c.gap) else 0, "sub": f"{flt(c.gap) / flt(c.due) * 100:.1f}%" if flt(c.gap) and flt(c.due) else ""}, st]})
		return {"title": _("Contractor pay proof — our gate muster against what the labour contractor paid; as principal employer we pay any shortfall and recover it from their bill"),
			"cols": COLS(_("Week"), _("Contractor"), (_("Workers"),), (_("Man-days"),), (_("Due"),), (_("Paid per proof"),), (_("Gap"),), _("Status")), "rows": rows,
			"actions": [{"label": _("New pay proof"), "new": "Contractor Pay Proof", "primary": 1}], "empty": _("No pay proofs here.")}
	pj = chip if chip in names else (names[0] if names else None)
	if not pj:
		return {"rows": [], "cols": [], "empty": _("No sites.")}
	wk, L = X.wage_ledger([pj])
	rows = []
	for w in L:
		if not M._q(q, w.worker_name, w.trade):
			continue
		rows.append({"dt": "Site Worker", "name": w.name, "cells": [{"main": w.worker_name, "sub": f"{w.trade} · ₹{flt(w.daily_rate):,.0f}/day"}]
			+ [({"money": r.net, "currency": cur, "sub": _("{0:g} days").format(flt(r.days)) + ("" if r.status == "Paid" else " · " + _(r.status))} if r else "—") for r in w.weeks]
			+ [{"money": w.advance, "currency": cur}, {"main": w.upi_id or "—"}]})
	return {"title": _("Wage ledgers — {0}: net wages week by week (Wednesday → Tuesday) and the advance still owed").format(pj),
		"cols": COLS(_("Worker"), *[(frappe.format(d, {"fieldtype": "Date"})[:5],) for d in wk], (_("Advance owed"),), _("UPI")), "rows": rows, "empty": _("No own workers on this site.")}


# ================================================================ portals
def _msg_rows(kind, chip, q):
	M = _h()
	rows = []
	for x in X.messages(kind, status="Open" if (chip or "open") == "open" else None):
		if not M._q(q, x.party, x.subject, x.message, x.project):
			continue
		b = [M._js(_("Reply…"), "cn_msg_reply", x.name), M._btn(_("Close"), "msg_close", x.name)] if x.status == "Open" else []
		rows.append({"dt": "Portal Message", "name": x.name, "cells": [{"main": x.party, "sub": f"{x.from_name or ''}{' · ' + x.project if x.project else ''}"},
			{"main": x.subject or "", "sub": (x.message or "")[:140]}, {"main": frappe.format(x.sent_on, {"fieldtype": "Datetime"})[:16]},
			{"main": (x.reply or "—")[:120], "sub": f"{x.replied_by or ''}"}, {"buttons": b} if b else {"pill": _(x.status), "tone": "green" if x.status == "Replied" else "grey"}]})
	return {"title": _("Messages from {0} on the portal — the reply goes back to the portal and by e-mail").format(_("clients") if kind == "Customer" else _("subcontractors")),
		"cols": COLS(_("From"), _("Message"), _("Received"), _("Our reply"), ""), "rows": rows, "nototal": 1, "empty": _("No messages.")}


def cpo_m(m):
	n = len(X.messages("Customer", status="Open"))
	return _tabs(m, [{"key": "in", "label": _("Client inbox") + (f" ({n})" if n else ""), "chips": [["open", _("Open")], ["all", _("All")]]}], 1)


def cpo_rows(tab, chip, q=None):
	return _msg_rows("Customer", chip, q)


def spo_m(m):
	n = len(X.messages("Supplier", status="Open"))
	return _tabs(m, [{"key": "in", "label": _("Inbox") + (f" ({n})" if n else ""), "chips": [["open", _("Open")], ["all", _("All")]]},
		{"key": "set", "label": _("Feature settings"), "chips": []}], 1)


def spo_rows(tab, chip, q=None):
	if tab == "in":
		return _msg_rows("Supplier", chip, q)
	M = _h()
	S = sorted({r[0] for r in frappe.db.sql("select distinct supplier from `tabSubcontractor Work Order` where status != 'Draft' and project in %s", (tuple(M._names(False)) or ("",),))})
	rows = []
	for s in S:
		f = X.partner_features(s)
		rows.append({"dt": "Supplier", "name": s, "cells": [{"main": s}] + [{"buttons": [M._btn(_("On") if f[k] else _("Off"), "sp_features", s, bool(f[k]), args={k: 0 if f[k] else 1})]}
			for k in X.SP_FEATURES]})
	return {"title": _("What each subcontractor can see and do on the partner portal — click to switch"), "cols": COLS(_("Subcontractor"), *[_(l) for l in X.SP_SHORT.values()]),
		"rows": rows, "nototal": 1, "empty": _("No subcontractors with work orders.")}


# ================================================================ Quotations & Sales › Unit sales
def sales_m(m):
	D = X.developments()
	if D:
		m = _tabs(m, [{"key": "unit", "label": _("Unit sales"), "chips": [[d.name, d.project_name.split(" — ")[0]] for d in D]}])
	return m


def sales_rows(tab, chip, q=None):
	M = _h()
	cur = M._cur()
	D = X.developments()
	d = next((x for x in D if x.name == chip), D[0] if D else None)
	if not d:
		return {"rows": [], "cols": [], "empty": _("No own development (tick Own development on a project).")}
	done = max(2, cint(d.hs_dev_stage)) if frappe.db.count("Development Unit", {"project": d.name, "status": "Booked"}) else cint(d.hs_dev_stage)
	stages = " · ".join(("✓ " if i < done else "→ " if i == done else "") + f"{s} {p}%" for i, (s, p) in enumerate(X.UNIT_PLAN))
	rows = []
	for u in frappe.get_list("Development Unit", filters={"project": d.name}, fields=["name", "unit_no", "unit_type", "area_sqft", "agreement_value", "status", "customer", "booked_on",
			"demanded", "received", "outstanding", "overdue"], order_by="unit_no asc", limit_page_length=0) if _perm("Development Unit") else []:
		if not M._q(q, u.unit_no, u.customer, u.unit_type):
			continue
		b = [M._js(_("Book…"), "cn_unit_book", u.name)] if u.status == "Available" else [M._js(_("Received…"), "cn_unit_receive", u.name)] if flt(u.outstanding) > .5 else []
		rows.append({"dt": "Development Unit", "name": u.name, "cells": [{"main": u.unit_no, "sub": f"{_(u.unit_type)} · {flt(u.area_sqft):,.0f} sq ft"},
			{"main": u.customer, "sub": _("booked {0}").format(frappe.format(u.booked_on, {"fieldtype": "Date"}))} if u.customer else {"pill": _("Available"), "tone": "green"},
			{"money": u.agreement_value, "currency": cur}, {"money": u.demanded, "currency": cur, "sub": _("GST 5% {0}").format(CN.inr(flt(u.demanded) * .05)) if flt(u.demanded) else ""},
			{"money": u.received, "currency": cur}, {"money": u.overdue, "currency": cur, "late": 1 if flt(u.overdue) > .5 else 0, "sub": _("{0} due").format(CN.inr(u.outstanding))
				if flt(u.outstanding) > flt(u.overdue) + .5 else ""}, {"buttons": b} if b else ""]})
	acts = [{"label": _("{0} completed on site").format(X.UNIT_PLAN[max(2, cint(d.hs_dev_stage))][0]), "primary": 1, "method": M.ACT, "args": {"action": "dev_stage", "name": d.name,
		"args": "{}"}}] if max(2, cint(d.hs_dev_stage)) < len(X.UNIT_PLAN) else []
	return {"title": _("{0}{1} — construction-linked plan: {2}").format(d.project_name, f" · RERA {d.hs_rera_no}" if d.hs_rera_no else "", stages),
		"cols": COLS(_("Unit"), _("Buyer"), (_("Agreement value"),), (_("Demanded"),), (_("Received"),), (_("Overdue"),), ""), "rows": rows, "actions": acts,
		"empty": _("No units — add them as Development Units.")}


# ================================================================ Cost Control › S-curve
def evm_m(m):
	return _tabs(m, [{"key": "curve", "label": _("S-curve"), "chips": [c for c in _h()._chips([n for n in _h()._names() if CN.boq(n)])]}])


def evm_rows(tab, chip, q=None):
	M = _h()
	names = [n for n in M._names() if CN.boq(n)]
	pj = M._pick(chip, names)
	if not pj:
		return {"rows": [], "cols": [], "empty": _("No project with a budget.")}
	C = X.s_curve(pj)
	R = C.rows
	lab = [r.month.strftime("%b %y") for r in R]
	L = lambda v: round(flt(v) / 1e5, 1) if v is not None else None
	card = {"type": "cols", "kind": "line", "title": _("S-curve — {0} (₹ lakh)").format(M._proj(pj).project_name), "sub": _("budget {0}").format(CN.inr(C.bac)), "labels": lab, "count": 1,
		"series": [{"name": _("Planned value"), "data": [L(r.pv) for r in R], "color": "blue"}, {"name": _("Earned value"), "data": [L(r.ev) for r in R], "color": "green"},
			{"name": _("Actual cost"), "data": [L(r.ac) for r in R], "color": "orange"}], "wide": 1}
	t = getdate(today())
	last = [r for r in R if r.ev is not None][-1] if any(r.ev is not None for r in R) else None
	mo = lambda v: {"money": round(flt(v)), "currency": M._cur(), "dp": 0}
	rows = [{"cells": [r.month.strftime("%b %Y"), mo(r.pv), mo(r.ev) if r.ev is not None else "—", mo(r.ac) if r.ac is not None else "—"]} for r in R if r.month <= t][-12:]
	E = C.E
	return {"blocks": [{"type": "card", "card": card},
		{"type": "table", "title": _("By month (cumulative) — SPI {0:.2f} · CPI {1:.2f}").format(flt(E.spi), flt(E.cpi)), "cols": COLS(_("Month"), (_("Planned value"),), (_("Earned value"),),
			(_("Actual cost"),)), "rows": rows}]}


# ================================================================ Accounts › Approval matrix, Notification rules, more standard screens
# v1.9.2 U5: the India Compliance filing tools stay tools; the staff lists open the Payroll page's Attendance & leave tab
EXTRA_LINKS = [("GSTR-1 (India Compliance)", "GSTR-1", "app/gstr-1"), ("GSTR-2B reconciliation", "Purchase Reconciliation Tool", "app/purchase-reconciliation-tool"),
	("GST return log", "GST Return Log", "app/gst-return-log")]
EXTRA_TABS = [("e-Way bills", "e-Waybill Log", ["hipersign-cn-tax"], {"hs_tab": "einv"}), ("Leave applications", "Leave Application", ["hipersign-cn-payroll"], {"hs_tab": "att", "hs_chip": "leave"}),
	("Attendance", "Attendance", ["hipersign-cn-payroll"], {"hs_tab": "att", "hs_chip": "att"}), ("Employee advances (loans)", "Employee Advance", ["hipersign-cn-payroll"], {"hs_tab": "att", "hs_chip": "adv"}),
	("Staff payroll", "Staff Payroll", ["hipersign-cn-payroll"], {"hs_tab": "run"})]


def acc_m(m):
	for t in m["tabs"]:
		if t["key"] == "rep":
			t["label"] = _("Statements")
	return _tabs(m, [{"key": "am", "label": _("Approval matrix"), "chips": []}, {"key": "nt", "label": _("Notification rules"), "chips": []}])


def acc_rows_wrap(base):
	def fn(tab, chip, q=None):
		if tab == "rep":
			r = base(tab, chip, q)
			r["rows"] = [x for x in r["rows"] if x["cells"][0] != _("Approval")]
			r["rows"] += [{"cells": [_("Filing tool"), _(n), {"url": "/" + route, "label": _("Open")}]} for n, dt, route in EXTRA_LINKS if frappe.db.exists("DocType", dt)
				and frappe.has_permission(dt, "read")]
			r["rows"] += [{"cells": [_("Staff & logistics"), _(n), {"buttons": [{"label": _("Open"), "route": route, "options": opts}]}]} for n, dt, route, opts in EXTRA_TABS
				if frappe.db.exists("DocType", dt) and frappe.has_permission(dt, "read")]
			r["title"] = _("Statements, filing tools and staff lists")
			return r
		if tab not in ("am", "nt"):
			return base(tab, chip, q)
		M = _h()
		if tab == "am":
			md = "Managing Director" in frappe.get_roles() or frappe.session.user == "Administrator"
			rows = [{"cells": [{"main": a, "sub": b}, c, d, {"buttons": [M._js(_("Change limits…"), "cn_am_limits", ",".join(k))]} if k and md else ""]} for a, b, c, d, k in X.matrix()]
			V = X.limits_changed()
			ch = []
			for v in V:
				for f, old, new in (frappe.parse_json(v.data or "{}").get("changed") or []):
					if f in dict((x[0], 1) for x in X.LIMITS):
						ch.append(f"{frappe.format(v.creation, {'fieldtype': 'Date'})} · {frappe.utils.get_fullname(v.owner)}: {next(l for k, l, _t in X.LIMITS if k == f)} {old} → {new}")
			if ch:
				rows.append({"cells": [{"main": _("Changes"), "sub": _("from the audit trail")}, {"lines": ch[:6]}, "", ""]})
			return {"title": _("Approval matrix — who approves what and up to how much; the limits drive the live rules and every change is logged"),
				"cols": COLS(_("Document"), _("Level 1"), _("Level 2"), ""), "rows": rows, "nototal": 1}
		rows = []
		for n in X.notifications():
			ch = [x for x, on in ((_("In-app"), n.send_system_notification or n.channel == "System Notification"), (_("E-mail"), n.channel == "Email"), (_("SMS"), n.channel == "SMS"),
				(_("Slack"), n.channel == "Slack")) if on]
			rows.append({"cells": [{"main": n.subject or n.name, "sub": f"{n.document_type} · {_(n.event)}"}, ", ".join(ch) or "—",
				{"buttons": [M._btn(_("On") if n.enabled else _("Off"), "nt_toggle", n.name, bool(n.enabled))]}]})
		return {"title": _("Notification rules — which events notify whom, on which channel"), "cols": COLS(_("Event"), _("Channels"), _("On")), "rows": rows, "nototal": 1,
			"actions": [{"label": _("New rule"), "new": "Notification", "primary": 1}], "empty": _("No notification rules for the construction records yet.")}
	fn.__name__ = base.__name__
	return fn


# ================================================================ Drawings & RFIs › Controlled documents
def doc_m(m):
	return _tabs(m, [{"key": "cdoc", "label": _("Controlled documents"), "chips": [["Current", _("Current")], ["review", _("Review due")], ["all", _("All")]]}])


def doc_rows(tab, chip, q=None):
	M = _h()
	chip = chip or "Current"
	f = {}
	if chip == "Current":
		f["status"] = "Current"
	elif chip == "review":
		f.update({"status": ["!=", "Withdrawn"], "review_on": ["<=", frappe.utils.add_days(today(), 30)]})
	names = set(M._names(False))
	rows = []
	t = getdate(today())
	for d in frappe.get_list("Controlled Document", filters=f, fields=["name", "title", "doc_no", "category", "project", "revision", "status", "access", "owner_name", "issued_on", "review_on",
			"file"], order_by="category asc, title asc", limit_page_length=0) if _perm("Controlled Document") else []:
		if d.project and d.project not in names or not M._q(q, d.title, d.doc_no, d.category, d.project):
			continue
		late = d.review_on and getdate(d.review_on) < t and d.status != "Withdrawn"
		b = [M._js(_("New revision…"), "cn_cdoc_rev", d.name)] + ([M._btn(_("Under review"), "cdoc_status", d.name, args={"status": "Under review"})] if d.status == "Current" else []) \
			if d.status != "Withdrawn" else []
		if d.file:
			b.insert(0, {"url": d.file, "label": _("Open")})
		rows.append({"dt": "Controlled Document", "name": d.name, "cells": [{"main": d.title, "sub": " · ".join(x for x in (d.doc_no, d.name) if x)}, _(d.category),
			d.project or _("Company-wide"), {"main": d.revision, "sub": frappe.format(d.issued_on, {"fieldtype": "Date"}) if d.issued_on else ""},
			{"date": str(d.review_on) if d.review_on else None, "late": 1 if late else 0}, {"main": _(d.access), "sub": d.owner_name or ""},
			{"pill": _(d.status), "tone": {"Current": "green", "Under review": "amber", "Withdrawn": "grey"}.get(d.status)}, {"buttons": b} if b else ""]})
	return {"title": _("Controlled documents — method statements, procedures, ITPs and policies; one current revision, reviewed every year"),
		"cols": COLS(_("Document"), _("Category"), _("Scope"), _("Revision"), _("Review by"), _("Access"), _("Status"), ""), "rows": rows,
		"actions": [{"label": _("New document"), "new": "Controlled Document", "primary": 1}], "empty": _("No controlled documents here.")}


# ================================================================ Safety › Site audits, PPE compliance
def hse_m(m):
	M = _h()
	n = frappe.db.count("Site Worker", {"project": ["in", M._names(False) or [""]], "status": "Active", "ppe_issued": 0})
	return _tabs(m, [{"key": "aud", "label": _("Site audits"), "chips": [["all", _("All")]]}, {"key": "ppe", "label": _("PPE compliance") + (f" ({n})" if n else ""), "chips": []}])


def hse_rows(tab, chip, q=None):
	M = _h()
	names = M._names(False)
	if tab == "aud":
		rows = []
		for a in frappe.get_list("Safety Audit", filters={"project": ["in", names or [""]]}, fields=["name", "project", "audit_date", "auditor", "score", "observations", "findings"],
				order_by="audit_date desc", limit_page_length=0) if _perm("Safety Audit") else []:
			if not M._q(q, a.project, a.auditor, a.findings):
				continue
			rows.append({"dt": "Safety Audit", "name": a.name, "cells": [M._pcell(a.project), {"date": str(a.audit_date)}, a.auditor or "—", {"bar": round(flt(a.score)),
				"sub": f"{flt(a.score):.0f}%", "late": 1 if flt(a.score) < 80 else 0}, str(cint(a.observations)), (a.findings or "—")[:110]]})
		return {"title": _("Weekly site safety audits — PPE, edge protection, housekeeping, electrical, scaffolds, fire extinguishers; below 80% is flagged"),
			"cols": COLS(_("Site"), _("Audited"), _("Auditor"), _("Score"), (_("Observations"),), _("Main gaps")), "rows": rows,
			"actions": [{"label": _("New audit"), "new": "Safety Audit", "primary": 1}], "empty": _("No audits yet.")}
	W = frappe.get_list("Site Worker", filters={"project": ["in", names or [""]], "status": "Active"}, fields=["name", "worker_name", "project", "contractor", "trade", "ppe_issued",
		"induction_done"], limit_page_length=0) if _perm("Site Worker") else []
	rows = []
	for pj in names:
		ws = [w for w in W if w.project == pj]
		if not ws:
			continue
		ok = [w for w in ws if cint(w.ppe_issued)]
		rows.append({"cls": "hsx-grp-row", "cells": [M._pcell(pj), str(len(ws)), str(len(ok)), {"bar": round(len(ok) / len(ws) * 100), "late": 1 if len(ok) < len(ws) else 0}, ""]})
		for w in ws:
			if cint(w.ppe_issued) or not M._q(q, w.worker_name, w.trade, w.contractor):
				continue
			rows.append({"dt": "Site Worker", "name": w.name, "cells": [{"main": w.worker_name, "sub": f"{w.trade} · {w.contractor or _('own')}"}, "", "", {"pill": _("No PPE"), "tone": "red"},
				{"buttons": [M._btn(_("PPE issued"), "ppe_issue", w.name, True)]}]})
	return {"title": _("PPE compliance by site — helmet, safety shoes, reflective vest (harness for work at height); workers without PPE are not allowed on site"),
		"cols": COLS(_("Site / worker"), (_("Workers"),), (_("With PPE"),), _("Compliance"), ""), "rows": rows, "nototal": 1, "empty": _("No workers.")}


def extend(g):
	for k, add_m, rows, keys in (("cn_lab", lab_m, lab_rows, ("pay", "cpp", "led")), ("cn_cpo", cpo_m, cpo_rows, ("in",)), ("cn_spo", spo_m, spo_rows, ("in", "set")),
			("cn_sales", sales_m, sales_rows, ("unit",)), ("cn_evm", evm_m, evm_rows, ("curve",)), ("cn_doc", doc_m, doc_rows, ("cdoc",)), ("cn_hse", hse_m, hse_rows, ("aud", "ppe"))):
		m, r = _wrap(g[k + "_module"], g[k + "_rows"], add_m, rows, keys)
		g[k + "_module"], g[k + "_rows"] = m, g["_whole"](r)
	base = g["cn_acc_module"]

	def acc():
		return acc_m(base())
	acc.__name__ = base.__name__
	g["cn_acc_module"] = acc
	g["cn_acc_rows"] = g["_whole"](acc_rows_wrap(g["cn_acc_rows"]))
