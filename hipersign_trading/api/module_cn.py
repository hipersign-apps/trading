"""v1.9.0 (prototype C11): the Construction (India) pages — Construction Projects, Tenders & EMD, BOQ & Extra Items,
Measurement Book, RA Billing and DPR & Hindrances — on the module page renderer (hs_module.js). Figures, red flags and
the actions come from api.construction (one place for the rules)."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import projects as P
from hipersign_trading.api.module import _perm, _scope, kpi

KEYS = ("cn_home", "cn_tnd", "cn_boq", "cn_mb", "cn_ra", "cn_site")


def _whole(fn):
	"""Whole rupees in the tables (₹1,03,06,152 — paise only widen the columns); rates keep theirs."""
	def wrap(tab, chip, q=None):
		r = fn(tab, chip, q)
		cols = r.get("cols") or []
		for row in r.get("rows") or []:
			for i, c in enumerate(row.get("cells") or []):
				if isinstance(c, dict) and c.get("money") is not None and "rate" not in ((cols[i].get("label") if i < len(cols) else "") or "").lower():
					c["money"], c["dp"] = round(flt(c["money"])), 0
		return r
	wrap.__name__ = fn.__name__
	return wrap
ACT = "hipersign_trading.api.construction.act"
CUR = "INR"


def _names(include_closed=True):
	return CN.project_names(_scope()[0], include_closed)


def _cos():
	return _scope()[0]


def _cur(names=None):
	names = names if names is not None else _names()
	if names:
		return frappe.get_cached_value("Company", frappe.get_cached_value("Project", names[0], "company"), "default_currency")
	return _scope()[4] or CUR


def _proj(name):
	return frappe.get_cached_doc("Project", name)


def _pcell(name, full=False):
	"""The project in a table: its short name and number (full: with the client — the portfolio)."""
	p = _proj(name)
	short = (p.project_name or "").split(" — ")[0]
	return {"main": short, "sub": f"{p.name} · {p.customer or ''}" if full else p.name}


def _btn(label, action, name, primary=False, args=None, confirm=None):
	return {"button": label, "act": action, "name": name, "method": ACT, "args": args or {}, "primary": 1 if primary else 0, "confirm": confirm}


def _js(label, fn, name):
	return {"button": label, "js": fn, "name": name}


def _m(v, cur=CUR):
	return CN.inr(v, cur)


def _status_pill(step):
	s = P.status_of(step)
	return {"pill": _(s if s != "Handover" else "DLP"), "tone": P.STATUS_TONE[s]}


def _chips(names):
	ps = [_proj(n) for n in names]
	ps.sort(key=lambda p: (0 if 10 <= cint(p.hs_step) < 22 else 1 if 5 <= cint(p.hs_step) < 10 else 2 if 22 <= cint(p.hs_step) < 26 else 3, -flt(p.hs_contract_value)))
	return [[p.name, p.project_name.split(" — ")[0]] for p in ps]


def _pick(chip, names):
	return chip if chip in names else (_chips(names)[0][0] if names else None)


def _empty():
	return _("No Construction (India) projects yet — award a tender, or tick “Construction (India) project” on a project.")


def _q(q, *parts):
	return not q or q.lower() in " ".join(str(x or "") for x in parts).lower()


def _date(d, late=False):
	return {"date": str(d) if d else None, "late": 1 if late else 0}


# ================================================================ Construction Projects
def cn_home_module():
	names = _names()
	cur = _cur(names)
	live = [n for n in names if 5 <= cint(_proj(n).hs_step) < 26]
	F = [CN.fig(n) for n in live]
	rev = sum(f.revised for f in F)
	work = sum(f.work for f in F)
	nfl = sum(len(CN.flags(n)) for n in names)
	by = {}
	for n in names:
		s = P.status_of(_proj(n).hs_step)
		by[s] = by.get(s, 0) + 1
	tone = {"Tender": "violet", "Mobilising": "orange", "Execution": "blue", "Handover": "green", "Closed": "grey"}
	return {
		"title": _("Construction Projects"),
		"desc": _("Every site from award to DLP — contract and extra items, work done, RA bills certified, money received after the client's deductions, and margin."),
		"new": [{"label": _("New project"), "doctype": "Project", "primary": 1}, {"label": _("New tender"), "doctype": "Tender"}],
		"kpis": [
			kpi(_("Contract value (incl. extra items)"), rev, _("{0} projects · {1} in pipeline").format(len(live), len([n for n in names if cint(_proj(n).hs_step) < 5])),
				"navy", "file-text", True, cur),
			kpi(_("Work done"), f"{work / rev * 100:.0f}%" if rev else "0%", _("{0} of work").format(_m(work, cur)), "blue", "chart-gantt"),
			kpi(_("Certified (RA bills)"), sum(f.billed for f in F), _("{0} with the client").format(_m(sum(f.pending_cert for f in F), cur)), "violet", "check", True, cur,
				["hipersign-cn-billing"]),
			kpi(_("Received"), sum(f.received for f in F), _("{0} outstanding · {1} overdue").format(_m(sum(f.outstanding for f in F), cur), _m(sum(f.overdue for f in F), cur)),
				"green", "banknote", True, cur, ["hipersign-cn-billing"]),
			kpi(_("Retention held by clients"), sum(f.retention for f in F), _("TDS {0} · GST-TDS {1}").format(_m(sum(f.tds for f in F), cur), _m(sum(f.gst_tds for f in F), cur)),
				"amber", "landmark", True, cur),
			kpi(_("Red flags"), nfl, _("{0} projects need action").format(len([n for n in names if CN.flags(n)])), "red" if nfl else "green", "flag", tab="flags"),
		],
		"cards": [
			{"title": _("Contract value by project"), "sub": _("incl. approved extra items"), "type": "bars", "currency": cur,
				"rows": [[_proj(n).project_name.split(" — ")[0], CN.fig(n).revised] for n in live]},
			{"title": _("Where the projects are"), "type": "donut", "count": 1, "center": str(len(names)), "center_label": _("projects"),
				"rows": [[_(s if s != "Handover" else "DLP"), by[s], tone[s]] for s in ("Tender", "Mobilising", "Execution", "Handover", "Closed") if by.get(s)]},
		],
		"tabs": [
			{"key": "port", "label": _("Portfolio"), "chips": [[k, _(v)] for k, v in (("all", "All"), ("Mobilising", "Mobilising"), ("Execution", "Execution"),
				("Handover", "DLP"), ("Closed", "Closed"), ("risk", "At risk"))]},
			{"key": "flags", "label": _("Red flags") + (f" ({nfl})" if nfl else ""), "chips": []},
			{"key": "bg", "label": _("Bank guarantees"), "chips": [["all", _("All")], ["exp", _("Expiring in 60 days")]]},
			{"key": "how", "label": _("How it works"), "chips": []},
		],
	}


def _how():
	return {"blocks": [{"type": "how", "span": 3, "title": _("How it works — a contract from tender to DLP"),
		"sub": _("{0} stages · who does what, the documents and the approvals").format(len(CN.STAGES)),
		"phases": [{"name": _("Win"), "a": 0, "b": 2}, {"name": _("Build & bill"), "a": 2, "b": 7}, {"name": _("Close"), "a": 7, "b": 8}],
		"steps": [{"name": _(s[0]), "short": _(s[0]), "what": _(s[1]), "who": _(s[2]), "docs": _(s[3]), "approval": _(s[4]), "next": ""} for s in CN.STAGES]}]}


def cn_home_rows(tab, chip, q=None):
	names = _names()
	cur = _cur(names)
	if tab == "how":
		return _how()
	if tab == "flags":
		rows = []
		for n in names:
			for f in CN.flags(n):
				rows.append({"dt": f["open"][0], "name": f["open"][1], "cells": [_pcell(n), {"pill": _(f["lvl"]), "tone": "red" if f["lvl"] == "High" else "orange"}, f["text"],
					{"button": _("Open"), "open": f["open"]}]})
		return {"title": _("Red flags — every project"), "cols": [{"label": _("Project")}, {"label": _("Level")}, {"label": _("Issue")}, {"label": ""}],
			"rows": rows, "empty": _("No red flags — every project is on track."), "nototal": 1}
	if tab == "bg":
		return _bg_rows(names, chip, q, cur)
	chip = chip or "all"
	rows = []
	for n in names:
		p, F = _proj(n), CN.fig(n)
		fl = CN.flags(n)
		if chip == "risk" and not fl:
			continue
		if chip not in ("all", "risk") and F.status != chip:
			continue
		if not _q(q, n, p.project_name, p.customer, p.get("hs_location")):
			continue
		rows.append({"dt": "Project", "name": n, "cells": [_pcell(n, True), dict(_status_pill(F.step), sub=_("{0} flags").format(len(fl)) if fl else "", late=1 if fl else 0),
			{"money": F.revised, "currency": cur, "sub": _("+{0} extra").format(_m(F.ei, cur)) if F.ei else ""}, {"bar": F.pct},
			{"money": F.billed, "currency": cur, "sub": _("{0} RA bills").format(F.bills) if F.bills else ""}, {"money": F.received, "currency": cur},
			{"money": F.outstanding, "currency": cur, "sub": _("{0} overdue").format(_m(F.overdue, cur)) if F.overdue > 1 else "", "neg": 1 if F.overdue > 1 else 0},
			{"main": f"{F.margin:.1f}%" if F.cost else "—", "sub": _("estimate {0:.1f}%").format(F.bud_margin) if F.bud_margin else "",
				"late": 1 if F.cost and F.margin < F.bud_margin - 3 else 0}]})
	return {"title": _("Project portfolio"), "cols": [{"label": _("Project")}, {"label": _("Stage")}, {"label": _("Contract"), "cls": "num"}, {"label": _("Done")},
		{"label": _("Certified"), "cls": "num"}, {"label": _("Received"), "cls": "num"}, {"label": _("Outstanding"), "cls": "num"},
		{"label": _("Margin %")}], "rows": rows, "empty": _empty()}


def _bg_rows(names, chip, q, cur):
	meta = frappe.get_meta("Bank Guarantee")
	if not meta.has_field("project") or not _perm("Bank Guarantee"):
		return {"rows": [], "cols": [], "empty": _("No bank guarantees.")}
	f = {"project": ["in", names or [""]], "docstatus": ["<", 2]}
	fields = ["name", "project", "bank", "amount", "start_date", "end_date", "bank_guarantee_number", "docstatus"] + \
		[x for x in ("hs_bond_type", "hs_bond_status") if meta.has_field(x)]
	gs = frappe.get_list("Bank Guarantee", filters=f, fields=fields, order_by="end_date asc", limit_page_length=0)
	t = getdate(today())
	rows = []
	for g in gs:
		days = date_diff(g.end_date, t) if g.end_date else None
		if chip == "exp" and (days is None or days > 60 or g.get("hs_bond_status") == "Returned"):
			continue
		if not _q(q, g.name, g.project, g.bank, g.get("hs_bond_type")):
			continue
		rows.append({"dt": "Bank Guarantee", "name": g.name, "cells": [{"main": g.get("hs_bond_type") or _("Bank guarantee"), "sub": g.bank_guarantee_number or g.name},
			_pcell(g.project), g.bank or "—", {"money": g.amount, "currency": cur}, _date(g.start_date), _date(g.end_date, days is not None and days < 30),
			{"pill": _(g.get("hs_bond_status") or ("Active" if g.docstatus == 1 else "Draft")), "sub": _("{0} days left").format(days) if days is not None and days >= 0 else ""}]})
	return {"title": _("Bank guarantees — performance, mobilisation advance and EMD"), "cols": [{"label": _("Guarantee")}, {"label": _("Project")}, {"label": _("Bank")},
		{"label": _("Amount"), "cls": "num"}, {"label": _("Issued")}, {"label": _("Expires")}, {"label": _("Status")}], "rows": rows, "empty": _("No bank guarantees.")}


# ================================================================ Tenders & EMD
def _tenders():
	if not _perm("Tender"):
		return []
	cos = _cos()
	return frappe.get_list("Tender", filters={"company": ["in", cos]} if cos else {}, fields=["name", "tender_name", "client_name", "customer", "portal", "tender_ref",
		"estimated_value", "our_bid", "our_margin_pct", "published_on", "due_date", "status", "bid_decision", "rank", "project", "emd_amount", "emd_mode", "emd_status",
		"result_note"], order_by="due_date desc", limit_page_length=0)


def cn_tnd_module():
	T = _tenders()
	cur = _cur()
	t = getdate(today())
	open_ = [x for x in T if x.status in CN.OPEN_TENDER]
	due7 = [x for x in open_ if x.due_date and 0 <= date_diff(x.due_date, t) <= 7 and x.status in ("Bid / no-bid", "Being priced")]
	decided = [x for x in T if x.status in ("Awarded", "Lost")]
	won = [x for x in decided if x.status == "Awarded"]
	emd = sum(flt(x.emd_amount) for x in T if x.emd_status in ("Held by client", "Refund pending"))
	return {
		"title": _("Tenders & EMD"),
		"desc": _("The tender register — bid / no-bid, pricing, submission, technical and financial evaluation, award or loss — and the EMD the clients hold."),
		"new": [{"label": _("New tender"), "doctype": "Tender", "primary": 1}],
		"kpis": [
			kpi(_("Open tenders"), len(open_), _("{0} in the pipeline").format(_m(sum(flt(x.our_bid) or flt(x.estimated_value) for x in open_), cur)), "navy", "file-text", tab="tnd", chip="open"),
			kpi(_("Due in 7 days"), len(due7), _("still being priced") if due7 else _("nothing due"), "red" if due7 else "green", "clock", tab="tnd", chip="open"),
			kpi(_("Win rate"), f"{len(won) / len(decided) * 100:.0f}%" if decided else "—", _("{0} won of {1} decided").format(len(won), len(decided)), "green", "trophy"),
			kpi(_("EMD with clients"), emd, _("{0} refunds pending").format(len([x for x in T if x.emd_status == "Refund pending"])), "amber", "landmark", True, cur, tab="emd"),
		],
		"tabs": [
			{"key": "tnd", "label": _("Tenders"), "chips": [["open", _("Open")], ["Awarded", _("Awarded")], ["Lost", _("Lost / no bid")], ["all", _("All")]]},
			{"key": "emd", "label": _("EMD"), "chips": [["held", _("With clients")], ["all", _("All")]]},
		],
	}


def _tnd_btns(x):
	b = []
	if x.status == "Bid / no-bid":
		b = [_btn(_("Bid"), "tnd_bid", x.name, True), _btn(_("No bid"), "tnd_nobid", x.name, confirm=_("Record no bid on {0}?").format(x.name))]
	elif x.status == "Being priced":
		b = [_btn(_("Submit bid"), "tnd_submit", x.name, True)]
	elif x.status in CN.EVAL_NEXT:
		b = [_btn(_("Next: {0}").format(_(CN.EVAL_NEXT[x.status])), "tnd_next", x.name), _js(_("Lost…"), "cn_tnd_lost", x.name)]
	if x.status == "L1 — LOA awaited":
		b = [_btn(_("LOA received — award"), "tnd_award", x.name, True, confirm=_("Accept the award of {0} and create the project?").format(x.name)), _js(_("Lost…"), "cn_tnd_lost", x.name)]
	return {"buttons": b} if b else ""


def cn_tnd_rows(tab, chip, q=None):
	T = _tenders()
	cur = _cur()
	t = getdate(today())
	if tab == "emd":
		rows = []
		for x in T:
			if not flt(x.emd_amount):
				continue
			if (chip or "held") == "held" and x.emd_status not in ("Held by client", "Refund pending"):
				continue
			if not _q(q, x.name, x.tender_name, x.client_name):
				continue
			rows.append({"dt": "Tender", "name": x.name, "cells": [{"main": x.tender_name, "sub": f"{x.name} · {x.client_name or ''}"}, {"money": x.emd_amount, "currency": cur},
				x.emd_mode, {"pill": _(x.emd_status), "tone": "orange" if x.emd_status == "Refund pending" else "blue" if x.emd_status == "Held by client" else "green"},
				{"pill": _(x.status)}, {"buttons": [_btn(_("Refund received"), "emd_refunded", x.name)]} if x.emd_status == "Refund pending" else ""]})
		return {"title": _("EMD"), "cols": [{"label": _("Tender")}, {"label": _("EMD"), "cls": "num"}, {"label": _("Mode")}, {"label": _("EMD status")}, {"label": _("Tender status")},
			{"label": ""}], "rows": rows, "empty": _("No EMD with clients.")}
	chip = chip or "open"
	rows = []
	for x in T:
		if chip == "open" and x.status not in CN.OPEN_TENDER:
			continue
		if chip == "Lost" and x.status not in ("Lost", "No bid"):
			continue
		if chip == "Awarded" and x.status != "Awarded":
			continue
		if not _q(q, x.name, x.tender_name, x.client_name, x.portal, x.tender_ref):
			continue
		days = date_diff(x.due_date, t) if x.due_date else None
		rows.append({"dt": "Tender", "name": x.name, "cells": [{"main": x.tender_name, "sub": f"{x.name} · {x.client_name or ''}"}, {"main": x.portal, "sub": x.tender_ref or ""},
			{"money": flt(x.our_bid) or flt(x.estimated_value), "currency": cur, "sub": (_("our bid") if flt(x.our_bid) else _("estimate"))
				+ (_(" · margin {0:.1f}%").format(flt(x.our_margin_pct)) if x.our_margin_pct else "")}, {"money": x.emd_amount, "currency": cur},
			{"date": str(x.due_date) if x.due_date else None, "late": 1 if days is not None and days <= 7 and x.status in ("Bid / no-bid", "Being priced") else 0},
			{"pill": _(x.status), "tone": "green" if x.status == "Awarded" else "red" if x.status in ("Lost", "No bid") else "orange" if x.status == "Bid / no-bid" else "blue",
				"sub": x.rank or ""},
			{"link": ["Project", x.project]} if x.project else _tnd_btns(x)]})
	return {"title": _("Tender register"), "cols": [{"label": _("Tender")}, {"label": _("Source")}, {"label": _("Value"), "cls": "num"},
		{"label": _("EMD"), "cls": "num"}, {"label": _("Bid due")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No tenders here.")}


# ================================================================ BOQ & Extra Items
def cn_boq_module():
	names = _names()
	cur = _cur(names)
	E = frappe.get_list("Extra Item", filters={"project": ["in", names or [""]]}, fields=["status", "amount"], limit_page_length=0) if _perm("Extra Item") else []
	bq = [n for n in names if CN.boq(n)]
	return {
		"title": _("BOQ & Extra Items"),
		"desc": _("Each project's bill of quantities — quantity, rate, measured and certified — and the extra items, substituted items and deviations that raise the contract."),
		"new": [{"label": _("New extra item"), "doctype": "Extra Item", "primary": 1}, {"label": _("New BOQ"), "doctype": "Project BOQ"}],
		"kpis": [
			kpi(_("BOQ value"), sum(flt(CN.boq(n).total_amount) for n in bq), _("{0} projects").format(len(bq)), "navy", "calculator", True, cur),
			kpi(_("Extra items approved"), sum(flt(e.amount) for e in E if e.status == "Approved"), _("{0} items").format(len([e for e in E if e.status == "Approved"])), "green", "check", True, cur, tab="ei", chip="Approved"),
			kpi(_("Waiting for the client"), sum(flt(e.amount) for e in E if e.status == "Pending client"), _("{0} items").format(len([e for e in E if e.status == "Pending client"])),
				"orange", "clock", True, cur, tab="ei", chip="Pending client"),
			kpi(_("Drafts"), len([e for e in E if e.status == "Draft"]), _("not sent yet"), "grey", "file", tab="ei", chip="Draft"),
		],
		"tabs": [
			{"key": "boq", "label": _("BOQ"), "chips": _chips(bq)},
			{"key": "ei", "label": _("Extra items & deviations"), "chips": [["open", _("Open")], ["Pending client", _("With the client")], ["Draft", _("Draft")], ["Approved", _("Approved")],
				["all", _("All")]]},
		],
	}


def cn_boq_rows(tab, chip, q=None):
	names = _names()
	cur = _cur(names)
	if tab == "ei":
		chip = chip or "open"
		f = {"project": ["in", names or [""]]}
		if chip == "open":
			f["status"] = ["in", ["Draft", "Pending client"]]
		elif chip != "all":
			f["status"] = chip
		rows = []
		for e in frappe.get_list("Extra Item", filters=f, fields=["name", "project", "title", "kind", "amount", "status", "reference", "raised_on", "sent_on", "approved_on"],
				order_by="raised_on desc", limit_page_length=0) if _perm("Extra Item") else []:
			if not _q(q, e.name, e.title, e.project, e.reference):
				continue
			b = {"Draft": [_btn(_("Send to client"), "ei_send", e.name, True)],
				"Pending client": [_btn(_("Client approved"), "ei_approve", e.name, True), _btn(_("Rejected"), "ei_reject", e.name, confirm=_("Record that the client rejected {0}?").format(e.name))]}.get(e.status)
			age = date_diff(today(), e.sent_on) if e.sent_on and e.status == "Pending client" else None
			rows.append({"dt": "Extra Item", "name": e.name, "cells": [{"main": e.title, "sub": f"{e.name} · {e.reference or ''}"}, _pcell(e.project), _(e.kind),
				{"money": e.amount, "currency": cur}, _date(e.raised_on), {"pill": _(e.status), "tone": {"Approved": "green", "Rejected": "red", "Draft": "grey"}.get(e.status, "orange"),
					"sub": _("{0} days with the client").format(age) if age else "", "late": 1 if age and age > 30 else 0}, {"buttons": b} if b else ""]})
		return {"title": _("Extra items, substituted items and deviations"), "cols": [{"label": _("Item")}, {"label": _("Project")}, {"label": _("Kind")}, {"label": _("Value"), "cls": "num"},
			{"label": _("Raised")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No extra items here.")}
	bq = [n for n in names if CN.boq(n)]
	pj = _pick(chip, bq)
	if not pj:
		return {"rows": [], "cols": [], "empty": _("No BOQ yet — make one with New BOQ.")}
	b = CN.boq(pj)
	rows = []
	for r in b.items:
		if not _q(q, r.item_no, r.description, r.section_name):
			continue
		mq = CN.measured_qty(pj, r.item_no)
		over = flt(r.qty) and (r.unit or "").upper() != "LS" and mq > flt(r.qty) * 1.0001
		rows.append({"dt": "Project BOQ", "name": b.name, "cells": [{"code": r.item_no}, {"main": r.description, "sub": r.section_name or ""}, r.unit, flt(r.qty),
			{"money": r.rate, "currency": cur}, {"money": r.amount, "currency": cur}, {"bar": flt(r.measured_pct)}, {"bar": flt(r.certified_pct)},
			{"pill": _("Beyond BOQ"), "tone": "red", "sub": _("{0} measured").format(round(mq, 2))} if over else ""]})
	return {"title": _("BOQ — {0}").format(_proj(pj).project_name), "cols": [{"label": _("Item")}, {"label": _("Description")}, {"label": _("Unit")}, {"label": _("Qty"), "cls": "num"},
		{"label": _("Rate"), "cls": "num"}, {"label": _("Amount"), "cls": "num"}, {"label": _("Measured")}, {"label": _("Certified")}, {"label": ""}], "rows": rows,
		"empty": _("This BOQ has no lines.")}


# ================================================================ Measurement Book
def _mbs(names, f=None):
	if not _perm("Measurement Book"):
		return []
	return frappe.get_list("Measurement Book", filters=dict({"project": ["in", names or [""]]}, **(f or {})), fields=["name", "project", "item_no", "description", "unit",
		"location", "measured_on", "mb_page", "nos", "length", "breadth", "depth", "qty", "amount", "status", "ra_bill", "over_boq", "measured_by", "bbs_ref"],
		order_by="measured_on desc", limit_page_length=0)


def cn_mb_module():
	names = _names(False)
	cur = _cur(names)
	M = _mbs(names, {"status": ["!=", "Rejected"]})
	unb = [m for m in M if m.status == "Client checked" and not m.ra_bill]
	return {
		"title": _("Measurement Book"),
		"desc": _("Work measured on site — dimensions or bar bending schedule, the QS check and the client engineer's check. Checked measurements become the next RA bill."),
		"new": [{"label": _("New measurement"), "doctype": "Measurement Book", "primary": 1}],
		"kpis": [
			kpi(_("To check (QS)"), len([m for m in M if m.status == "Draft"]), _("{0} of work").format(_m(sum(flt(m.amount) for m in M if m.status == "Draft"), cur)), "orange", "ruler", tab="mb", chip="Draft"),
			kpi(_("With the client's engineer"), len([m for m in M if m.status == "Checked by QS"]), _("{0} of work").format(_m(sum(flt(m.amount) for m in M if m.status == "Checked by QS"), cur)),
				"blue", "user-check", tab="mb", chip="Checked by QS"),
			kpi(_("Checked, not billed"), sum(flt(m.amount) for m in unb), _("{0} entries — bill them").format(len(unb)), "green", "receipt", True, cur, tab="mb", chip="unbilled"),
			kpi(_("Beyond the BOQ"), len([m for m in M if m.over_boq]), _("deviation statement needed") if any(m.over_boq for m in M) else _("none"),
				"red" if any(m.over_boq for m in M) else "green", "triangle-alert", tab="mb", chip="over"),
		],
		"tabs": [
			{"key": "mb", "label": _("Entries"), "chips": [["Draft", _("To check")], ["Checked by QS", _("With the client")], ["unbilled", _("Checked, not billed")], ["over", _("Beyond BOQ")],
				["all", _("All")]]},
			{"key": "ready", "label": _("Ready to bill"), "chips": []},
		],
	}


def _dims(m):
	if m.bbs_ref and not (m.length or m.breadth or m.depth):
		return m.bbs_ref
	parts = [f"{flt(x):g}" for x in (m.nos, m.length, m.breadth, m.depth) if flt(x)]
	return " × ".join(parts) or "—"


def cn_mb_rows(tab, chip, q=None):
	names = _names(False)
	cur = _cur(names)
	if tab == "ready":
		rows = []
		for n in names:
			M = _mbs([n], {"status": "Client checked", "ra_bill": ["is", "not set"]})
			if not M:
				continue
			draft = frappe.db.get_value("RA Bill", {"project": n, "status": "Draft"})
			rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), len(M), len({m.item_no for m in M}), {"money": sum(flt(m.amount) for m in M), "currency": cur},
				_date(min(m.measured_on for m in M)), {"link": ["RA Bill", draft]} if draft else {"buttons": [_btn(_("Prepare RA bill"), "ra_new", n, True)]}]})
		return {"title": _("Checked measurements ready for the next RA bill"), "cols": [{"label": _("Project")}, {"label": _("Entries")}, {"label": _("BOQ items")},
			{"label": _("Value at BOQ rates"), "cls": "num"}, {"label": _("Oldest")}, {"label": ""}], "rows": rows, "empty": _("Nothing checked and unbilled.")}
	chip = chip or "Draft"
	f = {"status": ["!=", "Rejected"]}
	if chip in ("Draft", "Checked by QS"):
		f["status"] = chip
	elif chip == "unbilled":
		f.update(status="Client checked", ra_bill=["is", "not set"])
	elif chip == "over":
		f["over_boq"] = 1
	rows = []
	for m in _mbs(names, f):
		if not _q(q, m.name, m.project, m.item_no, m.description, m.location):
			continue
		b = {"Draft": [_btn(_("QS checked"), "mb_qs", m.name, True), _btn("✕", "mb_reject", m.name, confirm=_("Reject {0}?").format(m.name))],
			"Checked by QS": [_btn(_("Client checked"), "mb_client", m.name, True), _btn("✕", "mb_reject", m.name, confirm=_("Reject {0}?").format(m.name))]}.get(m.status)
		rows.append({"dt": "Measurement Book", "name": m.name, "cells": [{"main": m.name, "sub": " · ".join(x for x in (frappe.format(m.measured_on, {"fieldtype": "Date"}),
			_("p. {0}").format(m.mb_page) if m.mb_page else "") if x)}, _pcell(m.project),
			{"main": f"{m.item_no} · {(m.description or '')[:40]}", "sub": m.location or ""}, _dims(m), {"main": f"{flt(m.qty):,.2f} {m.unit or ''}"}, {"money": m.amount, "currency": cur},
			{"pill": _(m.status), "tone": {"Draft": "grey", "Checked by QS": "blue", "Client checked": "green"}.get(m.status, "red"),
				"sub": (_("beyond BOQ") if m.over_boq else "") or (m.ra_bill or ""), "late": 1 if m.over_boq else 0}, {"buttons": b} if b else ""]})
	return {"title": _("Measurement book"), "cols": [{"label": _("Entry")}, {"label": _("Project")}, {"label": _("BOQ item · location")}, {"label": _("Dimensions")},
		{"label": _("Quantity")}, {"label": _("Value"), "cls": "num"}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No measurements here.")}


# ================================================================ RA Billing
def _ras(names, f=None):
	if not _perm("RA Bill"):
		return []
	return frappe.get_list("RA Bill", filters=dict({"project": ["in", names or [""]]}, **(f or {})), fields=["name", "project", "bill_no", "is_final", "status", "bill_date",
		"submitted_on", "certified_on", "claimed_amount", "certified_amount", "cut_amount", "gst_amount", "gross_with_gst", "retention", "advance_recovery", "tds", "gst_tds",
		"labour_cess", "total_deductions", "net_receivable", "received_amount", "received_on", "due_date", "sales_invoice", "tds_in_26as", "gst_tds_ok", "government_client"],
		order_by="bill_date desc, bill_no desc", limit_page_length=0)


def cn_ra_module():
	names = _names()
	cur = _cur(names)
	R = _ras(names, {"status": ["!=", "Cancelled"]})
	t = getdate(today())
	sub = [r for r in R if r.status == "Submitted to client"]
	cert = [r for r in R if r.status == "Certified"]
	inv = [r for r in R if r.status in ("Invoiced", "Part paid")]
	bal = lambda r: flt(r.net_receivable) - flt(r.received_amount)
	od = [r for r in inv if r.due_date and getdate(r.due_date) < t and bal(r) > 1]
	tds = [r for r in R if r.received_on and flt(r.tds) and not cint(r.tds_in_26as)]
	return {
		"title": _("RA Billing"),
		"desc": _("Running account bills from the measurement book to the client's certificate, the GST tax invoice and the payment — net of retention, advance recovery, TDS, GST-TDS and labour cess."),
		"new": [{"label": _("New RA bill"), "doctype": "RA Bill", "primary": 1}],
		"kpis": [
			kpi(_("With the client"), sum(flt(r.claimed_amount) for r in sub), _("{0} bills awaiting certification").format(len(sub)), "violet", "send", True, cur, tab="ra", chip="Submitted to client"),
			kpi(_("Certified, to invoice"), sum(flt(r.certified_amount) for r in cert), _("{0} bills").format(len(cert)), "blue", "file-check", True, cur, tab="ra", chip="Certified"),
			kpi(_("Outstanding"), sum(bal(r) for r in inv), _("{0} overdue in {1} bills").format(_m(sum(bal(r) for r in od), cur), len(od)), "red" if od else "green", "banknote", True, cur,
				tab="ra", chip="Invoiced"),
			kpi(_("Retention held"), sum(flt(r.retention) for r in R if r.status in CN.CERTIFIED), _("released at completion and after DLP"), "amber", "landmark", True, cur, tab="ded"),
			kpi(_("TDS to match in 26AS"), len(tds), _m(sum(flt(r.tds) for r in tds), cur), "orange" if tds else "green", "receipt-indian-rupee", tab="tds"),
		],
		"tabs": [
			{"key": "ra", "label": _("RA bills"), "chips": [["open", _("Open")], ["Draft", _("Draft")], ["Submitted to client", _("With the client")], ["Certified", _("Certified")],
				["Invoiced", _("Invoiced")], ["Paid", _("Paid")], ["all", _("All")]]},
			{"key": "ded", "label": _("Deductions by project"), "chips": []},
			{"key": "tds", "label": _("TDS & GST-TDS"), "chips": [["open", _("To match")], ["all", _("All")]]},
		],
	}


def _ra_btns(r):
	b = {"Draft": [_btn(_("Submit"), "ra_submit", r.name, True, confirm=_("Submit {0} to the client?").format(r.name)), _btn("✕", "ra_cancel", r.name, confirm=_("Cancel {0}?").format(r.name))],
		"Submitted to client": [_js(_("Certified…"), "cn_ra_certify", r.name)],
		"Certified": [_btn(_("Invoice"), "ra_invoice", r.name, True, confirm=_("Raise the GST tax invoice for {0}?").format(r.name))],
		"Invoiced": [_btn(_("Received"), "ra_receive", r.name, True, confirm=_("Record the client's payment of {0} (net of deductions)?").format(_m(r.net_receivable)))],
		"Part paid": [_btn(_("Received"), "ra_receive", r.name, True)]}.get(r.status)
	return {"buttons": b} if b else ""


def cn_ra_rows(tab, chip, q=None):
	names = _names()
	cur = _cur(names)
	t = getdate(today())
	if tab == "ded":
		rows = []
		for n in names:
			F = CN.fig(n)
			if not F.bills:
				continue
			rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), {"money": F.billed, "currency": cur}, {"money": F.gst, "currency": cur}, {"money": F.retention, "currency": cur},
				{"money": F.adv_recovered, "currency": cur, "sub": _("of {0}").format(_m(F.adv_total, cur)) if F.adv_total else ""}, {"money": F.tds, "currency": cur},
				{"money": F.gst_tds, "currency": cur}, {"money": F.cess, "currency": cur}]})
		return {"title": _("What the clients deducted — certified bills"), "cols": [{"label": _("Project")}, {"label": _("Certified"), "cls": "num"}, {"label": _("GST"), "cls": "num"},
			{"label": _("Retention"), "cls": "num"}, {"label": _("Advance recovered"), "cls": "num"}, {"label": _("TDS 194C"), "cls": "num"}, {"label": _("GST-TDS"), "cls": "num"},
			{"label": _("Labour cess"), "cls": "num"}], "rows": rows, "empty": _("No certified bills yet.")}
	if tab == "tds":
		rows = []
		for r in _ras(names, {"status": ["in", ["Part paid", "Paid"]]}):
			if (chip or "open") == "open" and cint(r.tds_in_26as) and (not flt(r.gst_tds) or cint(r.gst_tds_ok)):
				continue
			if not _q(q, r.name, r.project):
				continue
			late = r.received_on and date_diff(t, r.received_on) > 45 and not cint(r.tds_in_26as)
			rows.append({"dt": "RA Bill", "name": r.name, "cells": [{"main": _("RA bill {0}").format(r.bill_no), "sub": r.name}, _pcell(r.project), _date(r.received_on),
				{"money": r.tds, "currency": cur}, {"pill": _("In 26AS") if cint(r.tds_in_26as) else _("Not yet"), "tone": "green" if cint(r.tds_in_26as) else "orange", "late": 1 if late else 0},
				{"money": r.gst_tds, "currency": cur}, {"pill": (_("Matched") if cint(r.gst_tds_ok) else _("Not yet")) if flt(r.gst_tds) else "—", "tone": "green" if cint(r.gst_tds_ok) else "orange"},
				{"buttons": [_btn(_("Matched"), "ra_26as", r.name)]} if not cint(r.tds_in_26as) else ""]})
		return {"title": _("TDS (194C) and GST-TDS — match the client's deductions with Form 26AS and GSTR-2X"), "cols": [{"label": _("Bill")}, {"label": _("Project")},
			{"label": _("Received")}, {"label": _("TDS"), "cls": "num"}, {"label": _("Form 26AS")}, {"label": _("GST-TDS"), "cls": "num"}, {"label": _("GSTR-2X")}, {"label": ""}],
			"rows": rows, "empty": _("Every deduction is matched.")}
	chip = chip or "open"
	f = {}
	if chip == "open":
		f["status"] = ["in", ["Draft", "Submitted to client", "Certified", "Invoiced", "Part paid"]]
	elif chip != "all":
		f["status"] = chip
	rows = []
	for r in _ras(names, f):
		if not _q(q, r.name, r.project, _proj(r.project).project_name):
			continue
		bal = flt(r.net_receivable) - flt(r.received_amount)
		late = r.status in ("Invoiced", "Part paid") and r.due_date and getdate(r.due_date) < t and bal > 1
		base = flt(r.certified_amount) if r.status in CN.CERTIFIED else flt(r.claimed_amount)
		rows.append({"dt": "RA Bill", "name": r.name, "cells": [{"main": _("RA bill {0}{1}").format(r.bill_no, _(" (final)") if cint(r.is_final) else ""), "sub": r.name},
			_pcell(r.project), {"money": base, "currency": cur, "sub": (_("certified · {0} cut").format(_m(r.cut_amount, cur)) if flt(r.cut_amount) > 1 else _("certified"))
				if r.status in CN.CERTIFIED else _("claimed")}, {"money": r.gst_amount, "currency": cur},
			{"money": r.total_deductions, "currency": cur}, {"money": r.net_receivable, "currency": cur, "sub": _("{0} received").format(_m(r.received_amount, cur)) if flt(r.received_amount) else ""},
			{"pill": _(r.status), "tone": {"Draft": "grey", "Submitted to client": "violet", "Certified": "blue", "Invoiced": "orange", "Paid": "green"}.get(r.status, "blue"),
				"sub": (_("due {0}").format(frappe.format(r.due_date, {"fieldtype": "Date"})) if r.due_date and bal > 1 else "") or (r.sales_invoice or ""), "late": 1 if late else 0},
			_ra_btns(r)]})
	return {"title": _("RA bills"), "cols": [{"label": _("Bill")}, {"label": _("Project")}, {"label": _("Bill value"), "cls": "num"},
		{"label": _("GST"), "cls": "num"}, {"label": _("Deductions"), "cls": "num"}, {"label": _("Net due"), "cls": "num"}, {"label": _("Status")}, {"label": ""}],
		"rows": rows, "empty": _("No RA bills here.")}


# ================================================================ DPR & Hindrances
def cn_site_module():
	names = _names(False)
	t = today()
	D = frappe.get_list("Daily Progress Report", filters={"project": ["in", names or [""]], "report_date": [">=", add_days(t, -7)]},
		fields=["name", "status", "own_labour", "sub_labour", "achievement_pct", "hours_lost", "report_date"], limit_page_length=0) if _perm("Daily Progress Report") else []
	H = frappe.get_list("Hindrance", filters={"project": ["in", names or [""]], "to_date": ["is", "not set"]}, fields=["name", "days", "eot_status"], limit_page_length=0) \
		if _perm("Hindrance") else []
	last = [d for d in D if str(d.report_date) == str(max((d.report_date for d in D), default=""))]
	return {
		"title": _("DPR & Hindrances"),
		"desc": _("Daily progress reports from every site — labour, work done against plan, weather, materials and equipment — and the hindrance register behind extension-of-time claims."),
		"new": [{"label": _("New DPR"), "doctype": "Daily Progress Report", "primary": 1}, {"label": _("New hindrance"), "doctype": "Hindrance"}],
		"kpis": [
			kpi(_("Labour on site"), sum(cint(d.own_labour) + cint(d.sub_labour) for d in last), _("latest DPRs · {0} sites").format(len(last)), "navy", "users"),
			kpi(_("Achievement — last 7 days"), f"{sum(flt(d.achievement_pct) for d in D) / len(D):.0f}%" if D else "—", _("{0} DPRs · {1} h lost to weather").format(len(D), sum(flt(d.hours_lost) for d in D)),
				"blue", "chart-line", tab="dpr"),
			kpi(_("DPRs to approve"), len([d for d in D if d.status == "Submitted"]), _("submitted by the site engineers"), "orange", "inbox", tab="dpr", chip="Submitted"),
			kpi(_("Open hindrances"), len(H), _("{0} days · {1} without EOT").format(sum(cint(h.days) for h in H), len([h for h in H if h.eot_status == "Not applied"])),
				"red" if H else "green", "construction", tab="hin"),
		],
		"tabs": [
			{"key": "dpr", "label": _("Daily progress"), "chips": [["week", _("Last 7 days")], ["Submitted", _("To approve")], ["all", _("All")]]},
			{"key": "hin", "label": _("Hindrances"), "chips": [["open", _("Continuing")], ["all", _("All")]]},
		],
	}


def cn_site_rows(tab, chip, q=None):
	names = _names(False)
	if tab == "hin":
		f = {"project": ["in", names or [""]]}
		if (chip or "open") == "open":
			f["to_date"] = ["is", "not set"]
		rows = []
		for h in frappe.get_list("Hindrance", filters=f, fields=["name", "project", "cause", "attributable_to", "from_date", "to_date", "days", "eot_status", "eot_ref"],
				order_by="from_date desc", limit_page_length=0) if _perm("Hindrance") else []:
			if not _q(q, h.name, h.project, h.cause):
				continue
			d = date_diff(h.to_date or today(), h.from_date) + 1
			b = []
			if not h.to_date:
				b.append(_btn(_("Ended today"), "hin_close", h.name))
			if h.eot_status == "Not applied" and h.attributable_to in ("Client", "Authority", "Weather"):
				b.append(_btn(_("Apply EOT"), "hin_eot", h.name, True))
			rows.append({"dt": "Hindrance", "name": h.name, "cells": [{"main": h.cause, "sub": h.name}, _pcell(h.project), _(h.attributable_to), _date(h.from_date),
				_date(h.to_date) if h.to_date else {"pill": _("Continuing"), "tone": "red"}, d,
				{"pill": _(h.eot_status), "tone": {"Granted": "green", "Applied": "blue", "Rejected": "red"}.get(h.eot_status, "orange"), "sub": h.eot_ref or ""},
				{"buttons": b} if b else ""]})
		return {"title": _("Hindrance register"), "cols": [{"label": _("Hindrance")}, {"label": _("Project")}, {"label": _("Attributable to")}, {"label": _("From")}, {"label": _("To")},
			{"label": _("Days")}, {"label": _("EOT")}, {"label": ""}], "rows": rows, "empty": _("No hindrances here.")}
	chip = chip or "week"
	f = {"project": ["in", names or [""]]}
	if chip == "week":
		f["report_date"] = [">=", add_days(today(), -7)]
	elif chip == "Submitted":
		f["status"] = "Submitted"
	rows = []
	for d in frappe.get_list("Daily Progress Report", filters=f, fields=["name", "project", "report_date", "weather", "hours_lost", "own_labour", "sub_labour", "activity", "unit",
			"planned_qty", "actual_qty", "achievement_pct", "status", "reported_by", "hindrance"], order_by="report_date desc, project asc", limit_page_length=200) \
			if _perm("Daily Progress Report") else []:
		if not _q(q, d.name, d.project, d.activity, d.reported_by):
			continue
		b = {"Draft": [_btn(_("Submit"), "dpr_submit", d.name)], "Submitted": [_btn(_("Approve"), "dpr_approve", d.name, True)]}.get(d.status)
		rows.append({"dt": "Daily Progress Report", "name": d.name, "cells": [_date(d.report_date), _pcell(d.project), {"main": cint(d.own_labour) + cint(d.sub_labour),
			"sub": _("{0} own · {1} sub").format(cint(d.own_labour), cint(d.sub_labour))}, {"main": d.activity or "—", "sub": d.reported_by or ""},
			{"main": f"{flt(d.actual_qty):g} / {flt(d.planned_qty):g} {d.unit or ''}"}, {"bar": flt(d.achievement_pct)},
			{"main": _(d.weather or "Fair"), "sub": _("{0} h lost").format(flt(d.hours_lost)) if flt(d.hours_lost) else "", "late": 1 if flt(d.hours_lost) else 0},
			{"pill": _(d.status), "tone": {"Approved": "green", "Submitted": "blue"}.get(d.status, "grey"), "sub": d.hindrance or ""}, {"buttons": b} if b else ""]})
	return {"title": _("Daily progress reports"), "cols": [{"label": _("Date")}, {"label": _("Project")}, {"label": _("Labour")}, {"label": _("Activity")},
		{"label": _("Achieved / planned")}, {"label": _("Achieved %")}, {"label": _("Weather")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No DPRs here.")}


for _k in KEYS:
	globals()[_k + "_rows"] = _whole(globals()[_k + "_rows"])
