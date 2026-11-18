"""v1.9.0 stage A6 (prototype C9): Project Controls, Client Portal, Subcontractor Portal and Site & Worker App — the desk
pages on the module page renderer. Rules in api/construction_portal.py; the portals themselves are www/cn-client,
www/cn-partner, www/cn-site and www/cn-worker."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_portal as PT
from hipersign_trading.api.module import _perm, kpi
from hipersign_trading.api.module_cn import _btn, _cur, _date, _js, _m, _names, _pcell, _proj, _q

KEYS = ("cn_ctl", "cn_cpo", "cn_spo", "cn_app")
TONE = {"Green": "green", "Amber": "orange", "Red": "red"}


def _gl(dt, **kw):
	"""A list the user may read — empty for a role without access (the page itself is open to more roles)."""
	return frappe.get_list(dt, **kw) if _perm(dt) else []


def _live():
	return [n for n in _names(False) if 10 <= CN.fig(n).step < 24]


# ================================================================ Project Controls
def cn_ctl_module():
	names = _live()
	R = {n: PT.rag(n) for n in names}
	ov = {n: PT.overall(R[n])[0] for n in names}
	t = getdate(today())
	cons = frappe.get_all("Project Constraint", filters={"project": ["in", names or [""]], "status": "Open"}, fields=["need_by"]) if _perm("Project Constraint") else []
	ms = frappe.get_all("Construction Milestone", filters={"project": ["in", names or [""]], "status": ["!=", "Done"]}, fields=["status"]) if _perm("Construction Milestone") else []
	mon = PT.week_monday()
	reviewed = frappe.db.count("Project Review", {"project": ["in", names or [""]], "week_start": mon}) if _perm("Project Review") else 0
	return {
		"title": _("Project Controls"),
		"desc": _("Every live project on eleven dimensions — red, amber or green from the records, with the reasons — the constraints that must be removed before the work, milestones with their slip, the portfolio timeline and the weekly review."),
		"new": [{"label": _("Constraint"), "doctype": "Project Constraint", "primary": 1}, {"label": _("Milestone"), "doctype": "Construction Milestone"}],
		"kpis": [
			kpi(_("Projects red"), len([n for n in names if ov[n] == "Red"]), _("{0} amber · {1} green").format(len([n for n in names if ov[n] == "Amber"]),
				len([n for n in names if ov[n] == "Green"])), "red", "traffic-cone", tab="rag"),
			kpi(_("Constraints open"), len(cons), _("{0} past need-by").format(len([c for c in cons if getdate(c.need_by) < t])), "orange", "octagon-alert", tab="con"),
			kpi(_("Milestones late"), len([m for m in ms if m.status == "Late"]), _("{0} at risk").format(len([m for m in ms if m.status == "At risk"])), "amber", "flag", tab="ms"),
			kpi(_("Reviewed this week"), f"{reviewed} / {len(names)}", _("weekly review"), "green" if reviewed >= len(names) else "blue", "clipboard-list", tab="rev"),
		],
		"tabs": [
			{"key": "rag", "label": _("RAG"), "chips": []},
			{"key": "why", "label": _("Reasons"), "chips": [[n, _proj(n).project_name.split(" — ")[0]] for n in names]},
			{"key": "con", "label": _("Constraints"), "chips": [["open", _("Open")], ["all", _("All")]]},
			{"key": "ms", "label": _("Milestones"), "chips": [["open", _("Not done")], ["all", _("All")]]},
			{"key": "tl", "label": _("Timeline"), "chips": []},
			{"key": "rev", "label": _("Weekly review"), "chips": []},
		],
	}


def cn_ctl_rows(tab, chip, q=None):
	names = _live()
	t = getdate(today())
	if tab == "why":
		n = chip if chip in names else (names[0] if names else None)
		if not n:
			return {"rows": [], "cols": [], "empty": _("No live projects.")}
		last = PT.last_review(n, PT.week_monday())
		rows = []
		for d in PT.rag(n):
			was = (last.rag.get(d.key) or ["—"])[0] if last else "—"
			rows.append({"cells": [{"main": _(d.label)}, {"pill": _(d.state), "tone": TONE[d.state]}, {"pill": _(was), "tone": TONE.get(was, "grey")} if was != "—" else "—",
				{"lines": d.why[:4] or [_("Nothing to act on")]}]})
		return {"title": _("Why — {0}").format(_proj(n).project_name), "cols": [{"label": _("Dimension")}, {"label": _("Now")}, {"label": _("Last review")}, {"label": _("Reasons")}],
			"rows": rows, "nototal": 1}
	if tab == "con":
		rows = []
		for c in _gl("Project Constraint", filters={"project": ["in", names or [""]], **({"status": "Open"} if (chip or "open") == "open" else {})},
				fields=["name", "project", "description", "category", "activity", "owner_name", "need_by", "status", "removed_on"], order_by="need_by asc", limit_page_length=0):
			if not _q(q, c.description, c.owner_name, c.project, c.category):
				continue
			late = c.status == "Open" and getdate(c.need_by) < t
			rows.append({"dt": "Project Constraint", "name": c.name, "cells": [{"main": c.description, "sub": c.activity or ""}, _pcell(c.project), _(c.category), c.owner_name or "—",
				_date(c.need_by, late), {"pill": _(c.status) if not late else _("Past need-by"), "tone": "green" if c.status == "Removed" else "red" if late else "orange",
					"sub": frappe.format(c.removed_on, {"fieldtype": "Date"}) if c.removed_on else (_("{0} days").format(date_diff(c.need_by, t)) if not late else "")},
				{"buttons": [_js(_("Remove…"), "cn_con_remove", c.name)]} if c.status == "Open" else ""]})
		return {"title": _("Constraints look-ahead — what must be in place before the work starts"), "cols": [{"label": _("Constraint")}, {"label": _("Project")}, {"label": _("Category")},
			{"label": _("Owner")}, {"label": _("Need by")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No constraints.")}
	if tab == "ms":
		rows = []
		for m in _gl("Construction Milestone", filters={"project": ["in", names or [""]], **({"status": ["!=", "Done"]} if (chip or "open") == "open" else {})},
				fields=["name", "project", "title", "kind", "planned", "forecast", "actual", "slip_days", "status", "client_visible"], order_by="planned asc", limit_page_length=0):
			if not _q(q, m.title, m.project):
				continue
			b = [_js(_("Re-forecast…"), "cn_ms_forecast", m.name), _btn(_("Done"), "ms_done", m.name, True, confirm=_("Mark {0} done today?").format(m.title))] if m.status != "Done" else []
			rows.append({"dt": "Construction Milestone", "name": m.name, "cells": [{"main": m.title, "sub": _(m.kind) + (" · " + _("client sees") if m.client_visible else "")},
				_pcell(m.project), _date(m.planned), _date(m.forecast, m.status == "Late"), _date(m.actual), {"main": f"{m.slip_days} d" if m.slip_days else "—"},
				{"pill": _(m.status), "tone": {"Done": "green", "On track": "blue", "At risk": "orange", "Late": "red"}.get(m.status)}, {"buttons": b} if b else ""]})
		return {"title": _("Milestones and deliverables — planned, forecast, actual"), "cols": [{"label": _("Milestone")}, {"label": _("Project")}, {"label": _("Planned")},
			{"label": _("Forecast")}, {"label": _("Actual")}, {"label": _("Slip")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No milestones.")}
	if tab == "tl":
		from hipersign_trading.api import construction_fin as FN

		rows = []
		for n in names:
			p = _proj(n)
			if not (p.expected_start_date and p.expected_end_date):
				continue
			x = FN.evm(n)
			total = max(1, date_diff(p.expected_end_date, p.expected_start_date))
			fc_total = total / x.spi if x.spi and x.spi < 1 else total
			fc = add_days(p.expected_start_date, int(fc_total))
			slip = max(0, date_diff(fc, p.expected_end_date))
			elapsed = min(100, max(0, date_diff(t, p.expected_start_date) / total * 100))
			rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), _date(p.expected_start_date), _date(p.expected_end_date), _date(fc, slip > 30),
				{"main": f"{slip} d" if slip else "—", "late": 1 if slip > 30 else 0}, {"bar": round(elapsed)}, {"bar": round(x.done)}]})
		return {"title": _("Portfolio timeline — finish forecast from the schedule performance (SPI)"), "cols": [{"label": _("Project")}, {"label": _("Start")},
			{"label": _("Planned finish")}, {"label": _("Forecast finish")}, {"label": _("Slip")}, {"label": _("Time gone")}, {"label": _("Work done")}], "rows": rows, "nototal": 1}
	if tab == "rev":
		mon = PT.week_monday()
		rows = []
		for n in names:
			R = PT.rag(n)
			now, reds, ambers = PT.overall(R)
			cur = frappe.db.get_value("Project Review", {"project": n, "week_start": mon}, ["name", "notes", "reviewed_by"], as_dict=True)
			last = PT.last_review(n, mon)
			moved = []
			if last:
				for d in R:
					was = (last.rag.get(d.key) or [d.state])[0]
					if was != d.state:
						moved.append(f"{_(d.label)}: {_(was)} → {_(d.state)}")
			rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), {"pill": _(now), "tone": TONE[now], "sub": _("{0} red · {1} amber").format(reds, ambers)},
				{"pill": _(last.overall), "tone": TONE.get(last.overall), "sub": frappe.format(last.week_start, {"fieldtype": "Date"})} if last else "—",
				{"lines": moved[:4] or ([_("No change")] if last else [_("First review")])},
				{"main": (cur.notes or "")[:80] or _("Reviewed"), "sub": cur.reviewed_by} if cur else {"buttons": [_js(_("Review…"), "cn_review", n)]}]})
		return {"title": _("Weekly review — week of {0}, against the last review").format(frappe.format(mon, {"fieldtype": "Date"})), "cols": [{"label": _("Project")},
			{"label": _("Now")}, {"label": _("Last review")}, {"label": _("What moved")}, {"label": _("This week")}], "rows": rows, "nototal": 1}
	rows = []
	for n in names:
		R = PT.rag(n)
		o = PT.overall(R)[0]
		rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), {"pill": _(o), "tone": TONE[o]}] + [{"pill": d.state[0], "tone": TONE[d.state]} for d in R]})
	return {"title": _("RAG — open Reasons for the why"), "cols": [{"label": _("Project")}, {"label": _("Overall")}] + [{"label": _(l)[:9]} for _k, l in PT.DIMS],
		"rows": rows, "nototal": 1, "empty": _("No live projects.")}


# ================================================================ Client Portal
def _clients():
	return sorted({_proj(n).customer for n in _names() if _proj(n).customer})


def _portal_users(kind, parties):
	if not parties:
		return []
	return frappe.db.sql("""select distinct u.name, u.full_name, u.enabled, u.last_login, l.link_name as party from `tabUser` u join `tabContact` c on c.user = u.name
		join `tabDynamic Link` l on l.parent = c.name and l.parenttype = 'Contact' and l.link_doctype = %s where l.link_name in %s and u.user_type = 'Website User'
		order by u.full_name""", (kind, tuple(parties)), as_dict=True)


def cn_cpo_module():
	names = _names()
	if _perm("Client Publication"):
		PT.sync_publications(_live())
	W = frappe.get_all("Client Publication", filters={"project": ["in", names or [""]], "status": "Waiting"}, fields=["creation"]) if _perm("Client Publication") else []
	C = _clients()
	U = _portal_users("Customer", C)
	A = frappe.db.count("Portal Activity", {"party_type": "Customer", "creation": [">=", add_days(today(), -7)]}) if _perm("Portal Activity") else 0
	return {
		"title": _("Client Portal"),
		"desc": _("What each client sees of their project — progress and milestones, published photos, RA bills (certified online by private clients), documents and weekly reports, variations to approve and snags. Photos, reports and drawings wait here for the PM."),
		"new": [],
		"kpis": [
			kpi(_("Waiting to publish"), len(W), _("{0} older than a week").format(len([w for w in W if date_diff(today(), w.creation) > 7])), "orange" if W else "green", "send", tab="pub"),
			kpi(_("Clients"), len(C), _("with construction projects"), "navy", "building-2", tab="cli"),
			kpi(_("Portal users"), len([u for u in U if u.enabled]), _("{0} logged in").format(len([u for u in U if u.last_login])), "blue", "users", tab="usr"),
			kpi(_("Client activity"), A, _("last 7 days"), "green", "activity", tab="log"),
		],
		"tabs": [
			{"key": "pub", "label": _("Publishing queue"), "chips": [["Waiting", _("Waiting")], ["Published", _("Published")], ["Kept internal", _("Kept internal")]]},
			{"key": "cli", "label": _("Clients & features"), "chips": []},
			{"key": "usr", "label": _("Users"), "chips": []},
			{"key": "log", "label": _("Activity"), "chips": []},
		],
	}


def cn_cpo_rows(tab, chip, q=None):
	names = _names()
	if tab == "cli":
		rows = []
		for c in _clients():
			f = PT.client_features(c)
			ps = [n for n in names if _proj(n).customer == c]
			govt = any(cint(_proj(n).get("hs_cn_govt")) for n in ps)
			on = [_(PT.FEATURES[k][0]).split(" (")[0] for k in PT.FEATURES if f.get(k) and not (k == "certify" and govt)]
			rows.append({"dt": "Customer", "name": c, "cells": [{"main": c, "sub": _("Government — certified on the MB") if govt else _("Private")}, {"lines": [_proj(n).project_name.split(" — ")[0] for n in ps]},
				{"main": _("{0} of {1} on").format(len(on), len(PT.FEATURES)), "sub": ", ".join(on)[:90]},
				{"buttons": [_js(_("Features…"), "cn_cp_features", c), _js(_("Invite…"), "cn_invite", "Customer::" + c), {"url": f"/cn-client?party={frappe.utils.quote(c)}", "label": _("Preview")}]}]})
		return {"title": _("Clients — what each one sees (cost and margin stay off unless agreed)"), "cols": [{"label": _("Client")}, {"label": _("Projects")}, {"label": _("Features")},
			{"label": ""}], "rows": rows, "nototal": 1}
	if tab == "usr":
		rows = []
		for u in _portal_users("Customer", _clients()):
			if not _q(q, u.name, u.full_name, u.party):
				continue
			rows.append({"cells": [{"main": u.full_name, "sub": u.name}, u.party, {"main": frappe.format(u.last_login, {"fieldtype": "Datetime"}) if u.last_login else _("Never")},
				{"pill": _("Active") if u.enabled else _("Disabled"), "tone": "green" if u.enabled else "grey"},
				{"buttons": [_btn(_("Disable") if u.enabled else _("Enable"), "user_enable", u.name, False, {"enabled": 0 if u.enabled else 1}), _btn(_("Resend"), "user_resend", u.name)]}]})
		return {"title": _("Client portal users — invited by e-mail; two-step login can be switched on in System Settings"), "cols": [{"label": _("User")}, {"label": _("Client")},
			{"label": _("Last login")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "nototal": 1, "empty": _("No client users yet — invite one from Clients & features.")}
	if tab == "log":
		return _activity("Customer", q)
	st = chip if chip in ("Waiting", "Published", "Kept internal") else "Waiting"
	rows = []
	for p in _gl("Client Publication", filters={"project": ["in", names or [""]], "status": st}, fields=["name", "project", "kind", "title", "photo", "drawing",
			"creation", "published_on", "published_by"], order_by="creation desc", limit_page_length=300):
		if not _q(q, p.title, p.project):
			continue
		img = frappe.db.get_value("Site Photo", p.photo, ["image", "source", "taken_by"], as_dict=True) if p.photo else None
		b = [_btn(_("Publish"), "pub", p.name, True), _btn(_("Keep internal"), "pub", p.name, False, {"keep": 1})] if st == "Waiting" else []
		if img:
			b.insert(0, {"url": img.image, "label": _("View")})
		rows.append({"dt": "Client Publication", "name": p.name, "cells": [{"main": p.title, "sub": (img.taken_by if img else "") or ""}, _pcell(p.project),
			{"pill": _(p.kind), "tone": {"Photo": "blue", "Weekly report": "violet", "Drawing": "teal"}.get(p.kind)},
			_date(str(p.creation)[:10]) if st == "Waiting" else {"main": frappe.format(p.published_on, {"fieldtype": "Date"}) if p.published_on else "—", "sub": p.published_by or ""},
			{"buttons": b} if b else ""]})
	return {"title": _("Publishing queue — nothing reaches the client until the PM publishes it"), "cols": [{"label": _("What")}, {"label": _("Project")}, {"label": _("Kind")},
		{"label": _("Since") if st == "Waiting" else _("Published")}, {"label": ""}], "rows": rows, "nototal": 1,
		"empty": _("Nothing waiting.") if st == "Waiting" else _("Nothing yet."), "actions": [{"label": _("Publish all"), "primary": 1, "method": "hipersign_trading.api.construction.act", "args": {"action": "pub", "name": "all", "args": "{}"}}]
		if st == "Waiting" and rows else None}


def _activity(kind, q):
	rows = []
	if not (_perm("Client Publication") or _perm("Subcontractor Bill")):
		return {"rows": [], "cols": [], "empty": _("Not permitted.")}
	for a in frappe.get_all("Portal Activity", filters={"party_type": kind}, fields=["user", "party", "project", "action", "reference_doctype", "reference_name", "creation"],
			order_by="creation desc", limit_page_length=150):
		if not _q(q, a.party, a.action, a.user):
			continue
		rows.append({"cells": [{"main": frappe.format(a.creation, {"fieldtype": "Datetime"})}, {"main": a.party, "sub": a.user or ""}, a.project or "—", a.action,
			{"link": [a.reference_doctype, a.reference_name]} if a.reference_name else ""]})
	return {"title": _("Activity on the portal"), "cols": [{"label": _("When")}, {"label": _("Who")}, {"label": _("Project")}, {"label": _("What")}, {"label": _("Record")}],
		"rows": rows, "nototal": 1, "empty": _("No activity yet.")}


# ================================================================ Subcontractor Portal
def _partners():
	names = _names()
	return sorted({r.supplier for r in frappe.get_all("Subcontractor Work Order", filters={"project": ["in", names or [""]], "status": ["!=", "Draft"]}, fields=["supplier"])})


def _queue():
	names = _names()
	out = []
	for b in frappe.get_all("Subcontractor Bill", filters={"project": ["in", names or [""]], "partner_submitted": 1, "partner_verified": 0, "status": "Draft"},
			fields=["name", "supplier", "project", "bill_no", "net_payable", "creation"]):
		out.append(frappe._dict(kind="Running bill", dt="Subcontractor Bill", name=b.name, party=b.supplier, project=b.project, since=b.creation,
			what=_("Bill {0} — {1} net").format(b.bill_no, CN.inr(b.net_payable)), act="ver_bill", label=_("Verify for the QS")))
	for c in frappe.get_all("Labour Compliance", filters={"project": ["in", names or [""]], "partner_submitted": 1, "status": "Missing"},
			fields=["name", "supplier", "project", "month", "modified"]):
		out.append(frappe._dict(kind="Labour documents", dt="Labour Compliance", name=c.name, party=c.supplier, project=c.project, since=c.modified,
			what=_("Wage register, PF ECR, ESI — {0}").format(frappe.utils.formatdate(c.month, "MMM yyyy")), act="ver_lc", label=_("Verify & release")))
	for p in frappe.get_all("Site Photo", filters={"project": ["in", names or [""]], "status": "To verify"}, fields=["name", "supplier", "project", "caption", "creation", "image"]):
		out.append(frappe._dict(kind="Photo", dt="Site Photo", name=p.name, party=p.supplier, project=p.project, since=p.creation, what=p.caption, act="ver_photo",
			label=_("Add to project log"), url=p.image))
	return sorted(out, key=lambda x: str(x.since))


def cn_spo_module():
	Q = _queue()
	S = _partners()
	U = _portal_users("Supplier", S)
	return {
		"title": _("Subcontractor Portal"),
		"desc": _("What partners see — their work orders, running bills (submitted online, never above the last cumulative or the work order + 10%), payments with TDS and retention, labour documents and progress photos. Everything they send waits here."),
		"kpis": [
			kpi(_("To verify"), len(Q), _("{0} bills · {1} documents · {2} photos").format(len([x for x in Q if x.kind == "Running bill"]), len([x for x in Q if x.kind == "Labour documents"]),
				len([x for x in Q if x.kind == "Photo"])), "orange" if Q else "green", "inbox", tab="q"),
			kpi(_("Partners"), len(S), _("with work orders"), "navy", "briefcase", tab="par"),
			kpi(_("Partner users"), len([u for u in U if u.enabled]), _("{0} logged in").format(len([u for u in U if u.last_login])), "blue", "users", tab="usr"),
			kpi(_("Bills on hold"), frappe.db.count("Subcontractor Bill", {"compliance_hold": 1, "status": ["in", ["Draft", "Certified", "Approved"]]}), _("labour documents missing"), "red",
				"pause", tab="q"),
		],
		"tabs": [{"key": "q", "label": _("Verification queue"), "chips": []}, {"key": "par", "label": _("Partners"), "chips": []}, {"key": "usr", "label": _("Users"), "chips": []},
			{"key": "log", "label": _("Activity"), "chips": []}],
	}


def cn_spo_rows(tab, chip, q=None):
	if tab == "par":
		rows = []
		for s in _partners():
			wos = frappe.get_all("Subcontractor Work Order", filters={"supplier": s, "status": ["!=", "Draft"]}, fields=["name", "project", "value", "status"])
			billed = flt(frappe.db.sql("select sum(net_payable) from `tabSubcontractor Bill` where supplier = %s and status != 'Cancelled'", s)[0][0])
			rows.append({"dt": "Supplier", "name": s, "cells": [{"main": s}, {"lines": [f"{w.name} · {w.project}" for w in wos][:3]}, {"money": sum(flt(w.value) for w in wos), "currency": _cur()},
				{"money": billed, "currency": _cur()}, {"buttons": [_js(_("Invite…"), "cn_invite", "Supplier::" + s), {"url": f"/cn-partner?party={frappe.utils.quote(s)}", "label": _("Preview")}]}]})
		return {"title": _("Partners with work orders"), "cols": [{"label": _("Subcontractor")}, {"label": _("Work orders")}, {"label": _("Order value"), "cls": "num"},
			{"label": _("Billed (net)"), "cls": "num"}, {"label": ""}], "rows": rows}
	if tab == "usr":
		rows = []
		for u in _portal_users("Supplier", _partners()):
			rows.append({"cells": [{"main": u.full_name, "sub": u.name}, u.party, {"main": frappe.format(u.last_login, {"fieldtype": "Datetime"}) if u.last_login else _("Never")},
				{"pill": _("Active") if u.enabled else _("Disabled"), "tone": "green" if u.enabled else "grey"},
				{"buttons": [_btn(_("Disable") if u.enabled else _("Enable"), "user_enable", u.name, False, {"enabled": 0 if u.enabled else 1}), _btn(_("Resend"), "user_resend", u.name)]}]})
		return {"title": _("Partner users"), "cols": [{"label": _("User")}, {"label": _("Subcontractor")}, {"label": _("Last login")}, {"label": _("Status")}, {"label": ""}],
			"rows": rows, "nototal": 1, "empty": _("No partner users yet — invite one from Partners.")}
	if tab == "log":
		return _activity("Supplier", q)
	rows = []
	for x in _queue():
		if not _q(q, x.party, x.what, x.project):
			continue
		b = [_btn(x.label, x.act, x.name, True)]
		if x.get("url"):
			b.insert(0, {"url": x.url, "label": _("View")})
		rows.append({"dt": x.dt, "name": x.name, "cells": [{"main": x.what, "sub": x.name}, x.party, _pcell(x.project), {"pill": _(x.kind), "tone": "blue"}, _date(str(x.since)[:10]),
			{"buttons": b}]})
	return {"title": _("Verification queue — verified bills go to the QS, verified documents release held bills, verified photos join the project log"),
		"cols": [{"label": _("What")}, {"label": _("From")}, {"label": _("Project")}, {"label": _("Kind")}, {"label": _("Since")}, {"label": ""}], "rows": rows, "nototal": 1,
		"empty": _("Nothing to verify.")}


# ================================================================ Site & Worker App
def cn_app_module():
	names = _live()
	t = today()
	att = frappe.db.count("Site Attendance", {"project": ["in", names or [""]], "attendance_date": t}) if _perm("Site Attendance") else 0
	workers = frappe.db.count("Site Worker", {"project": ["in", names or [""]], "status": "Active", "contractor": ["is", "not set"]})
	X = frappe.get_all("Site Expense", filters={"project": ["in", names or [""]], "status": "Waiting for approval"}, fields=["amount"]) if _perm("Site Expense") else []
	pins = frappe.db.sql("""select count(*) from `tabSite Worker` w where w.status = 'Active' and exists (select 1 from `__Auth` a where a.doctype = 'Site Worker'
		and a.name = w.name and a.fieldname = 'app_pin')""")[0][0]
	return {
		"title": _("Site & Worker App"),
		"desc": _("The phone apps: the site app for engineers (check-in with GPS, gang check-in, DPR, geo-tagged photos, site cash, deliveries, site chat), the worker app in Malayalam, Tamil, Hindi and English (attendance, pay slip, advance, report a danger) and site deliveries in the driver app."),
		"kpis": [
			kpi(_("Checked in today"), att, _("of {0} own workers").format(workers), "blue", "user-check", tab="att"),
			kpi(_("Site cash to approve"), sum(flt(x.amount) for x in X), _("{0} above the limit of {1}").format(len(X), CN.inr(PT.limits().cash)), "orange" if X else "green", "wallet",
				True, _cur(), tab="cash"),
			kpi(_("Workers on the app"), pins, _("PIN set"), "navy", "smartphone", tab="wrk"),
			kpi(_("Dangers reported"), frappe.db.count("Safety Incident", {"project": ["in", names or [""]], "description": ["like", "%worker app%"], "status": "Open"}),
				_("open, from the worker app"), "red", "siren", tab="dng"),
		],
		"tabs": [{"key": "att", "label": _("Today on site"), "chips": []}, {"key": "cash", "label": _("Site cash"), "chips": [["Waiting for approval", _("To approve")], ["Booked", _("Booked")]]},
			{"key": "pho", "label": _("Photos"), "chips": []}, {"key": "wrk", "label": _("Worker app"), "chips": [[n, _proj(n).project_name.split(" — ")[0]] for n in names]},
			{"key": "dng", "label": _("Dangers reported"), "chips": []}],
	}


def cn_app_rows(tab, chip, q=None):
	names = _live()
	t = today()
	cur = _cur()
	if tab == "cash":
		st = chip if chip in ("Waiting for approval", "Booked") else "Waiting for approval"
		rows = []
		for x in _gl("Site Expense", filters={"project": ["in", names or [""]], "status": st}, fields=["name", "project", "expense_date", "head", "description", "paid_to",
				"amount", "receipt", "requested_by", "approved_by"], order_by="expense_date desc", limit_page_length=200):
			b = [_btn(_("Approve"), "exp_approve", x.name, True), _btn(_("Reject"), "exp_reject", x.name)] if st == "Waiting for approval" else []
			if x.receipt:
				b.insert(0, {"url": x.receipt, "label": _("Bill")})
			rows.append({"dt": "Site Expense", "name": x.name, "cells": [{"main": x.description, "sub": x.paid_to or ""}, _pcell(x.project), _(x.head), _date(x.expense_date),
				{"money": x.amount, "currency": cur}, {"main": x.requested_by or "—", "sub": x.approved_by or ""}, {"buttons": b} if b else ""]})
		return {"title": _("Site cash — a site engineer books up to {0} at once; above it waits for the PM").format(CN.inr(PT.limits().cash)), "cols": [{"label": _("For")}, {"label": _("Project")},
			{"label": _("Head")}, {"label": _("Date")}, {"label": _("Amount"), "cls": "num"}, {"label": _("By · approved")}, {"label": ""}], "rows": rows, "empty": _("Nothing here.")}
	if tab == "pho":
		rows = []
		for p in _gl("Site Photo", filters={"project": ["in", names or [""]]}, fields=["name", "project", "caption", "location", "taken_on", "taken_by", "source", "status",
				"latitude", "longitude", "image"], order_by="taken_on desc", limit_page_length=60):
			pub = frappe.db.get_value("Client Publication", {"photo": p.name}, "status")
			rows.append({"dt": "Site Photo", "name": p.name, "cells": [{"main": p.caption, "sub": p.location or ""}, _pcell(p.project), {"main": frappe.format(p.taken_on, {"fieldtype": "Datetime"}),
				"sub": p.taken_by or ""}, {"main": _(p.source), "sub": f"{p.latitude:.4f}, {p.longitude:.4f}" if p.latitude else ""},
				{"pill": _(pub or p.status), "tone": {"Published": "green", "Waiting": "orange", "To verify": "orange"}.get(pub or p.status, "grey")}, {"url": p.image, "label": _("View")}]})
		return {"title": _("Site photos — geo-tagged; the client sees them only once published"), "cols": [{"label": _("Photo")}, {"label": _("Project")}, {"label": _("Taken")},
			{"label": _("From · GPS")}, {"label": _("Client")}, {"label": ""}], "rows": rows, "nototal": 1, "empty": _("No photos yet.")}
	if tab == "wrk":
		n = chip if chip in names else (names[0] if names else None)
		if not n:
			return {"rows": [], "cols": []}
		from frappe.utils.password import get_decrypted_password

		rows = []
		for w in _gl("Site Worker", filters={"project": n, "status": "Active"}, fields=["name", "worker_name", "trade", "mobile", "contractor", "app_language", "app_last_login"],
				order_by="worker_name asc", limit_page_length=0):
			if not _q(q, w.worker_name, w.mobile, w.trade):
				continue
			has = bool(get_decrypted_password("Site Worker", w.name, "app_pin", raise_exception=False))
			days = frappe.db.count("Site Attendance", {"worker": w.name, "attendance_date": [">=", add_days(t, -6)]})
			rows.append({"dt": "Site Worker", "name": w.name, "cells": [{"main": w.worker_name, "sub": _(w.trade) + (f" · {w.contractor}" if w.contractor else "")}, w.mobile or "—",
				w.app_language or "English", {"pill": _("PIN set") if has else _("No PIN"), "tone": "green" if has else "grey",
					"sub": frappe.format(w.app_last_login, {"fieldtype": "Datetime"}) if w.app_last_login else ""}, {"main": f"{days}", "sub": _("days in 7")},
				{"buttons": [_js(_("Reset PIN…") if has else _("Set PIN…"), "cn_wpin", w.name)]}]})
		return {"title": _("Worker app — the worker logs in at /cn-worker with the mobile number and a four-digit PIN"), "cols": [{"label": _("Worker")}, {"label": _("Mobile")},
			{"label": _("Language")}, {"label": _("App")}, {"label": _("Attendance")}, {"label": ""}], "rows": rows, "nototal": 1}
	if tab == "dng":
		rows = []
		for i in _gl("Safety Incident", filters={"project": ["in", names or [""]], "description": ["like", "%worker app%"]}, fields=["name", "project", "incident_date",
				"location", "description", "reported_by", "status"], order_by="incident_date desc", limit_page_length=100):
			rows.append({"dt": "Safety Incident", "name": i.name, "cells": [{"main": (i.description or "").split(": ", 1)[-1][:90], "sub": i.location or ""}, _pcell(i.project),
				_date(i.incident_date), i.reported_by or "—", {"pill": _(i.status), "tone": "orange" if i.status == "Open" else "green"}]})
		return {"title": _("Dangers reported by workers — each is a near-miss for the Safety Officer"), "cols": [{"label": _("Danger")}, {"label": _("Project")}, {"label": _("Date")},
			{"label": _("Reported by")}, {"label": _("Status")}], "rows": rows, "nototal": 1, "empty": _("Nothing reported.")}
	rows = []
	for n in names:
		own = frappe.db.count("Site Worker", {"project": n, "status": "Active", "contractor": ["is", "not set"]})
		present = frappe.get_all("Site Attendance", filters={"project": n, "attendance_date": t}, fields=["method"])
		eng = frappe.db.sql("""select e.employee_name, min(c.time) from `tabEmployee Checkin` c join `tabEmployee` e on e.name = c.employee where c.time >= %s
			and c.device_id = %s group by e.employee_name""", (t, f"Site app — {n}"))
		dpr = frappe.db.count("Daily Progress Report", {"project": n, "report_date": t})
		rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), {"main": f"{len(present)} / {own}", "sub": _("{0} by gang check-in").format(len([p for p in present if p.method == "Gang check-in"]))},
			{"lines": [f"{e} {str(tm)[11:16]}" for e, tm in eng] or [_("No engineer checked in")]}, {"pill": _("DPR in") if dpr else _("No DPR yet"), "tone": "green" if dpr else "orange"},
			{"main": str(frappe.db.count("Site Photo", {"project": n, "taken_on": [">=", t]})), "sub": _("photos today")}]})
	return {"title": _("Today on site — from the site app"), "actions": [{"label": _("Open the site app"), "url": "/cn-site", "primary": 1},
		{"label": _("Worker app"), "url": "/cn-worker"}], "cols": [{"label": _("Project")}, {"label": _("Workers present")}, {"label": _("Engineers checked in")}, {"label": _("DPR")},
		{"label": _("Photos")}], "rows": rows, "nototal": 1}
