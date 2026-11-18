"""v1.9.0 stage A2 (prototype C5): the Construction (India) business pages — CRM & Clients, Quotations & Sales and
Contracts & Claims — on the module page renderer. Rules in api/construction_biz.py."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_biz as B
from hipersign_trading.api.module import _perm, _scope, kpi
from hipersign_trading.api.module_cn import _btn, _cur, _date, _js, _m, _names, _pcell, _proj, _q

KEYS = ("cn_crm", "cn_sales", "cn_con")


def _cos():
	return _scope()[0]


def _co_filter():
	cos = _cos()
	return {"company": ["in", cos]} if cos else {}


def _opps(f=None):
	if not _perm("Opportunity") or not frappe.get_meta("Opportunity").has_field("hs_cn"):
		return []
	return frappe.get_list("Opportunity", filters=dict(_co_filter(), hs_cn=1, **(f or {})), fields=["name", "title", "party_name", "customer_name", "opportunity_from",
		"status", "sales_stage", "probability", "opportunity_amount", "expected_closing", "opportunity_owner", "utm_source", "hs_cn_category", "hs_cn_location",
		"hs_cn_next_date", "hs_cn_competition", "hs_cn_project", "order_lost_reason", "lost_on", "transaction_date"], order_by="opportunity_amount desc", limit_page_length=0)


def _who(o):
	return frappe.utils.get_fullname(o.opportunity_owner) if o.opportunity_owner else ""


# ================================================================ CRM & Clients
def cn_crm_module():
	O = _opps()
	cur = _cur()
	open_ = [o for o in O if o.status in ("Open", "Quotation", "Replied")]
	t = getdate(today())
	due = [o for o in open_ if o.hs_cn_next_date and getdate(o.hs_cn_next_date) <= t]
	won = [o for o in O if o.status == "Converted"]
	lost = [o for o in O if o.status in ("Lost", "Closed")]
	V = frappe.get_list("Client Visit", filters=dict(_co_filter(), visit_date=[">=", add_days(today(), -30)]), pluck="name", limit_page_length=0) if _perm("Client Visit") else []
	stages = [s for s in B.STAGES] + sorted({o.sales_stage for o in open_ if o.sales_stage and o.sales_stage not in B.STAGES})
	return {
		"title": _("CRM & Clients"),
		"desc": _("Construction enquiries from first call to award — stage, value, chance, competition and the next follow-up — the client master, site visits and why jobs were lost."),
		"new": [{"label": _("New enquiry"), "doctype": "Opportunity", "primary": 1}, {"label": _("Log a visit"), "doctype": "Client Visit"}, {"label": _("New client"), "doctype": "Customer"}],
		"kpis": [
			kpi(_("Open pipeline"), sum(flt(o.opportunity_amount) for o in open_), _("{0} enquiries").format(len(open_)), "navy", "filter", True, cur, tab="pipe"),
			kpi(_("Weighted by chance"), sum(flt(o.opportunity_amount) * flt(o.probability) / 100 for o in open_), _("value × probability"), "violet", "percent", True, cur),
			kpi(_("Follow-ups due"), len(due), _("today or overdue"), "red" if due else "green", "phone", tab="pipe", chip="due"),
			kpi(_("Win rate"), f"{len(won) / (len(won) + len(lost)) * 100:.0f}%" if won or lost else "—", _("{0} won · {1} lost").format(len(won), len(lost)), "green", "trophy", tab="lost"),
			kpi(_("Visits & meetings"), len(V), _("last 30 days"), "blue", "map-pin", tab="visit"),
		],
		"cards": [{"title": _("Pipeline by stage"), "sub": _("open enquiries"), "type": "bars", "currency": cur,
			"rows": [[_(s), sum(flt(o.opportunity_amount) for o in open_ if o.sales_stage == s)] for s in stages if any(o.sales_stage == s for o in open_)]}],
		"tabs": [
			{"key": "pipe", "label": _("Pipeline"), "chips": [["open", _("Open")], ["due", _("Follow-up due")]] + [[s, _(s)] for s in stages if any(o.sales_stage == s for o in open_)]
				+ [["won", _("Won")], ["all", _("All")]]},
			{"key": "cli", "label": _("Clients"), "chips": []},
			{"key": "visit", "label": _("Visits & meetings"), "chips": [["recent", _("Last 30 days")], ["next", _("Next steps due")], ["all", _("All")]]},
			{"key": "lost", "label": _("Lost analysis"), "chips": []},
		],
	}


def _opp_btns(o):
	if o.status not in ("Open", "Quotation", "Replied"):
		return {"link": ["Project", o.hs_cn_project]} if o.hs_cn_project else ""
	b = []
	if o.status == "Open" and not frappe.db.exists("Quotation", {"opportunity": o.name, "docstatus": ["<", 2]}):
		b.append(_btn(_("Quote"), "opp_quote", o.name, True))
	elif o.sales_stage in B.STAGES and B.STAGES.index(o.sales_stage) < len(B.STAGES) - 1:
		b.append(_btn(_("Next stage"), "opp_stage", o.name))
	b.append(_js(_("Follow-up…"), "cn_opp_followed", o.name))
	b.append(_js("✕", "cn_opp_lost", o.name))
	return {"buttons": b}


def cn_crm_rows(tab, chip, q=None):
	cur = _cur()
	t = getdate(today())
	if tab == "cli":
		rows = []
		names = CN.project_names(_cos())
		custs = {}
		for o in _opps():
			if o.opportunity_from == "Customer":
				custs.setdefault(o.party_name, {"opps": 0, "pipe": 0})
				if o.status in ("Open", "Quotation", "Replied"):
					custs[o.party_name]["opps"] += 1
					custs[o.party_name]["pipe"] += flt(o.opportunity_amount)
		for n in names:
			c = _proj(n).customer
			if c:
				custs.setdefault(c, {"opps": 0, "pipe": 0})
		meta = frappe.get_meta("Customer")
		for c, x in sorted(custs.items()):
			if not _q(q, c):
				continue
			cu = frappe.db.get_value("Customer", c, ["name", "customer_name"] + [f for f in ("gstin", "pan", "gst_category") if meta.has_field(f)], as_dict=True) or {}
			pj = [n for n in names if _proj(n).customer == c]
			F = [CN.fig(n) for n in pj]
			rows.append({"dt": "Customer", "name": c, "cells": [{"main": cu.get("customer_name") or c, "sub": cu.get("gstin") or _("no GSTIN")}, cu.get("pan") or "—",
				{"main": len(pj), "sub": _("{0} open enquiries").format(x["opps"]) if x["opps"] else ""}, {"money": sum(f.revised for f in F), "currency": cur},
				{"money": sum(f.billed for f in F), "currency": cur}, {"money": sum(f.outstanding for f in F), "currency": cur,
					"sub": _("{0} overdue").format(_m(sum(f.overdue for f in F), cur)) if sum(f.overdue for f in F) > 1 else "", "neg": 1 if sum(f.overdue for f in F) > 1 else 0},
				{"money": x["pipe"], "currency": cur}]})
		return {"title": _("Clients"), "cols": [{"label": _("Client")}, {"label": _("PAN")}, {"label": _("Projects")}, {"label": _("Contracts"), "cls": "num"},
			{"label": _("Certified"), "cls": "num"}, {"label": _("Outstanding"), "cls": "num"}, {"label": _("Open pipeline"), "cls": "num"}], "rows": rows, "empty": _("No clients yet.")}
	if tab == "visit":
		chip = chip or "recent"
		f = _co_filter()
		if chip == "recent":
			f["visit_date"] = [">=", add_days(today(), -30)]
		elif chip == "next":
			f["next_date"] = ["<=", add_days(today(), 7)]
		rows = []
		for v in frappe.get_list("Client Visit", filters=f, fields=["name", "party_name", "opportunity", "visit_date", "kind", "visited_by", "met", "notes", "next_step", "next_date"],
				order_by="visit_date desc", limit_page_length=0) if _perm("Client Visit") else []:
			if not _q(q, v.party_name, v.notes, v.opportunity):
				continue
			rows.append({"dt": "Client Visit", "name": v.name, "cells": [_date(v.visit_date), {"main": v.party_name or "—", "sub": v.opportunity or ""}, _(v.kind),
				{"main": v.visited_by or "", "sub": v.met or ""}, (v.notes or "")[:90], {"main": v.next_step or "—", "sub": frappe.format(v.next_date, {"fieldtype": "Date"}) if v.next_date else "",
					"late": 1 if v.next_date and getdate(v.next_date) < t else 0}]})
		return {"title": _("Site visits & meetings"), "cols": [{"label": _("Date")}, {"label": _("Client")}, {"label": _("Kind")}, {"label": _("People")}, {"label": _("Outcome")},
			{"label": _("Next step")}], "rows": rows, "empty": _("No visits here.")}
	if tab == "lost":
		L = [o for o in _opps() if o.status in ("Lost", "Closed")]
		by = {}
		for o in L:
			r = frappe.db.get_value("Opportunity Lost Reason Detail", {"parent": o.name}, "lost_reason") or o.order_lost_reason or _("Not given")
			x = by.setdefault(r, {"n": 0, "v": 0, "names": []})
			x["n"] += 1
			x["v"] += flt(o.opportunity_amount)
			x["names"].append(o.title or o.name)
		rows = [{"cells": [r, x["n"], {"money": x["v"], "currency": cur}, {"lines": x["names"][:4]}]} for r, x in sorted(by.items(), key=lambda z: -z[1]["v"])]
		return {"title": _("Why we lose"), "cols": [{"label": _("Reason")}, {"label": _("Enquiries")}, {"label": _("Value"), "cls": "num"}, {"label": _("Jobs")}],
			"rows": rows, "empty": _("Nothing lost yet.")}
	chip = chip or "open"
	rows = []
	for o in _opps():
		live = o.status in ("Open", "Quotation", "Replied")
		if chip == "open" and not live:
			continue
		if chip == "due" and not (live and o.hs_cn_next_date and getdate(o.hs_cn_next_date) <= t):
			continue
		if chip == "won" and o.status != "Converted":
			continue
		if chip in B.STAGES and not (live and o.sales_stage == chip):
			continue
		if chip not in ("open", "due", "won", "all") and chip not in B.STAGES and not (live and o.sales_stage == chip):
			continue
		if not _q(q, o.name, o.title, o.customer_name, o.party_name, o.hs_cn_location):
			continue
		late = o.hs_cn_next_date and getdate(o.hs_cn_next_date) <= t and live
		rows.append({"dt": "Opportunity", "name": o.name, "cells": [{"main": o.title or o.party_name, "sub": " · ".join(x for x in (o.customer_name or o.party_name, _(o.hs_cn_category or ""),
			o.utm_source or "") if x)}, {"money": o.opportunity_amount, "currency": cur},
			{"pill": _(o.sales_stage or o.status) if live else _({"Converted": "Won"}.get(o.status, o.status)), "tone": "green" if o.status == "Converted" else "red" if o.status == "Lost" else "blue",
				"sub": f"{cint(o.probability)}%"},
			{"main": (o.hs_cn_competition or "—")[:40], "sub": _who(o)}, _date(o.hs_cn_next_date, late), _opp_btns(o)]})
	return {"title": _("Enquiries"), "cols": [{"label": _("Enquiry")}, {"label": _("Value"), "cls": "num"}, {"label": _("Stage")},
		{"label": _("Competition · owner")}, {"label": _("Next follow-up")}, {"label": ""}], "rows": rows, "empty": _("No enquiries here.")}


# ================================================================ Quotations & Sales
def _quotes(f=None):
	if not _perm("Quotation") or not frappe.get_meta("Quotation").has_field("hs_cn"):
		return []
	return frappe.get_list("Quotation", filters=dict(_co_filter(), hs_cn=1, **(f or {})), fields=["name", "party_name", "customer_name", "quotation_to", "opportunity",
		"transaction_date", "valid_till", "base_net_total", "base_grand_total", "docstatus", "status", "hs_cn_cost", "hs_estimated_margin", "hs_cn_discount_pct", "hs_cn_approval",
		"hs_cn_approved_by", "hs_cn_outcome", "hs_cn_project", "hs_cn_revision", "hs_cn_revision_of", "hs_subject"], order_by="transaction_date desc, name desc", limit_page_length=0)


def _overdue_bills():
	names = _names()
	if not names or not _perm("RA Bill"):
		return []
	R = frappe.get_list("RA Bill", filters={"project": ["in", names], "status": ["in", ["Invoiced", "Part paid"]]}, fields=["name", "project", "bill_no", "net_receivable",
		"received_amount", "due_date", "sales_invoice", "customer"], order_by="due_date asc", limit_page_length=0)
	t = getdate(today())
	out = []
	for r in R:
		bal = flt(r.net_receivable) - flt(r.received_amount)
		if bal <= 1 or not r.due_date:
			continue
		r.bal, r.days = bal, date_diff(t, r.due_date)
		r.level = B.level_for(r.days)
		last = frappe.get_all("Collection Follow-up", filters={"ra_bill": r.name}, fields=["level", "followed_on", "promised_date", "promised_amount", "note"],
			order_by="followed_on desc, creation desc", limit=1) if _perm("Collection Follow-up") else []
		r.last = last[0] if last else None
		out.append(r)
	return out


def cn_sales_module():
	Q = _quotes()
	cur = _cur()
	open_ = [x for x in Q if x.hs_cn_outcome in ("Open", None, "") and x.docstatus < 2]
	appr = [x for x in open_ if x.hs_cn_approval == "Pending"]
	acc = [x for x in Q if x.hs_cn_outcome == "Accepted"]
	C = frappe.get_list("Construction Contract", filters={"project": ["in", _names() or [""]]}, fields=["revised_value"], limit_page_length=0) if _perm("Construction Contract") else []
	OD = [r for r in _overdue_bills() if r.days > 0]
	L = B.limits()
	return {
		"title": _("Quotations & Sales"),
		"desc": _("Construction quotations with cost and margin — the MD approves a discount above {0:g}% or a margin below {1:g}% — revisions with reasons, award to project and LOA, and the collections ladder.").format(L.disc, L.margin),
		"new": [{"label": _("New quotation"), "doctype": "Quotation", "primary": 1}],
		"kpis": [
			kpi(_("Quotations out"), sum(flt(x.base_net_total) for x in open_ if x.docstatus == 1), _("{0} sent · {1} drafts").format(len([x for x in open_ if x.docstatus == 1]),
				len([x for x in open_ if x.docstatus == 0])), "navy", "file-text", True, cur, tab="qt"),
			kpi(_("Awaiting MD approval"), len(appr), _m(sum(flt(x.base_net_total) for x in appr), cur), "orange" if appr else "green", "shield-check", tab="qt", chip="approval"),
			kpi(_("Won"), sum(flt(x.base_net_total) for x in acc), _("{0} quotations accepted").format(len(acc)), "green", "trophy", True, cur, tab="qt", chip="accepted"),
			kpi(_("Order book (contracts)"), sum(flt(c.revised_value) for c in C), _("{0} LOAs").format(len(C)), "violet", "briefcase", True, cur, tab="loa"),
			kpi(_("Overdue collections"), sum(r.bal for r in OD), _("{0} bills · {1} at L3–L4").format(len(OD), len([r for r in OD if r.level in B.LEVELS[2:]])),
				"red" if OD else "green", "banknote", True, cur, tab="col"),
		],
		"tabs": [
			{"key": "qt", "label": _("Quotations"), "chips": [["open", _("Open")], ["approval", _("MD approval")], ["accepted", _("Won")], ["lost", _("Lost")], ["revised", _("Revised")], ["all", _("All")]]},
			{"key": "loa", "label": _("LOAs & work orders"), "chips": []},
			{"key": "col", "label": _("Collections"), "chips": [["over", _("Overdue")], ["L3", _("L3–L4")], ["soon", _("Due in 15 days")], ["all", _("All open")]]},
			{"key": "fup", "label": _("Follow-up log"), "chips": []},
		],
	}


def _qt_btns(x):
	b = []
	if x.hs_cn_approval == "Pending":
		b += [_btn(_("Approve"), "qt_approve", x.name, True), _btn(_("Send back"), "qt_reject", x.name)]
	elif x.docstatus == 0 and x.hs_cn_approval == "Rejected":
		b.append({"button": _("Rework"), "open": ["Quotation", x.name]})
	elif x.docstatus == 0:
		b.append(_btn(_("Send"), "qt_send", x.name, True, confirm=_("Send {0} to the client?").format(x.name)))
	elif x.docstatus == 1 and x.hs_cn_outcome in ("Open", None, ""):
		b += [_js(_("Won…"), "cn_qt_accept", x.name), _js(_("Revise…"), "cn_qt_revise", x.name), _js("✕", "cn_qt_lost", x.name)]
	return {"buttons": b} if b else ""


def cn_sales_rows(tab, chip, q=None):
	cur = _cur()
	t = getdate(today())
	if tab == "loa":
		rows = []
		for c in frappe.get_list("Construction Contract", filters={"project": ["in", _names() or [""]]}, fields=["name", "project", "loa_no", "loa_date", "original_value",
				"revised_value", "status", "start_date", "completion_date", "extended_completion"], order_by="loa_date desc", limit_page_length=0) if _perm("Construction Contract") else []:
			if not _q(q, c.name, c.project, c.loa_no):
				continue
			F = CN.fig(c.project)
			rows.append({"dt": "Construction Contract", "name": c.name, "cells": [{"main": c.loa_no or c.name, "sub": frappe.format(c.loa_date, {"fieldtype": "Date"}) if c.loa_date else ""},
				_pcell(c.project), {"money": c.revised_value, "currency": cur, "sub": _("original {0}").format(_m(c.original_value, cur)) if flt(c.revised_value) != flt(c.original_value) else ""},
				{"money": F.billed, "currency": cur}, {"money": max(0, flt(c.revised_value) - F.billed), "currency": cur}, {"bar": F.pct},
				_date(c.extended_completion or c.completion_date), {"pill": _(c.status)}]})
		return {"title": _("LOAs & work orders — billed and still to bill"), "cols": [{"label": _("LOA")}, {"label": _("Project")}, {"label": _("Contract"), "cls": "num"},
			{"label": _("Certified"), "cls": "num"}, {"label": _("To bill"), "cls": "num"}, {"label": _("Done")}, {"label": _("Completion")}, {"label": _("Status")}],
			"rows": rows, "empty": _("No contracts yet — accept a quotation or award a tender.")}
	if tab == "col":
		chip = chip or "over"
		rows = []
		for r in _overdue_bills():
			if chip == "over" and r.days <= 0:
				continue
			if chip == "L3" and r.level not in B.LEVELS[2:]:
				continue
			if chip == "soon" and not (-15 <= r.days <= 0):
				continue
			if not _q(q, r.name, r.project, r.customer):
				continue
			last = r.last
			rows.append({"dt": "RA Bill", "name": r.name, "cells": [{"main": _("RA bill {0}").format(r.bill_no), "sub": r.sales_invoice or r.name}, _pcell(r.project),
				{"money": r.bal, "currency": cur}, {"date": str(r.due_date), "late": 1 if r.days > 0 else 0},
				{"pill": (r.level or _("Not due")).split(" — ")[0], "tone": {None: "green"}.get(r.level, "red" if r.level in B.LEVELS[2:] else "orange"),
					"sub": _("{0} days overdue").format(r.days) if r.days > 0 else _("due in {0} days").format(-r.days)},
				{"main": last.level.split(" — ")[0] + " · " + frappe.format(last.followed_on, {"fieldtype": "Date"}) if last else "—",
					"sub": _("promised {0}").format(frappe.format(last.promised_date, {"fieldtype": "Date"})) if last and last.promised_date else ((last.note or "")[:40] if last else "")},
				{"buttons": [_js(_("Log follow-up…"), "cn_fup_log", r.name)]}]})
		return {"title": _("Collections ladder — L1 e-mail · L2 PM call · L3 MD letter · L4 legal notice"), "cols": [{"label": _("Bill")}, {"label": _("Project")},
			{"label": _("Balance"), "cls": "num"}, {"label": _("Due")}, {"label": _("Level")}, {"label": _("Last follow-up")}, {"label": ""}], "rows": rows,
			"empty": _("Nothing overdue — every client is paying on time.")}
	if tab == "fup":
		rows = []
		for f in frappe.get_list("Collection Follow-up", filters={"project": ["in", _names() or [""]]}, fields=["name", "ra_bill", "project", "level", "followed_on", "by", "note",
				"promised_date", "promised_amount"], order_by="followed_on desc, creation desc", limit_page_length=200) if _perm("Collection Follow-up") else []:
			if not _q(q, f.ra_bill, f.project, f.note):
				continue
			rows.append({"dt": "Collection Follow-up", "name": f.name, "cells": [_date(f.followed_on), _pcell(f.project), f.ra_bill, {"pill": f.level.split(" — ")[0], "sub": f.level.split(" — ")[-1]},
				{"main": (f.note or "")[:80], "sub": f.by or ""}, {"main": frappe.format(f.promised_date, {"fieldtype": "Date"}) if f.promised_date else "—",
					"sub": _m(f.promised_amount, cur) if flt(f.promised_amount) else ""}]})
		return {"title": _("Follow-up log"), "cols": [{"label": _("Date")}, {"label": _("Project")}, {"label": _("RA bill")}, {"label": _("Level")}, {"label": _("What was said")},
			{"label": _("Promised")}], "rows": rows, "empty": _("No follow-ups logged yet.")}
	chip = chip or "open"
	rows = []
	for x in _quotes():
		o = x.hs_cn_outcome or "Open"
		if chip == "open" and not (o == "Open" and x.docstatus < 2):
			continue
		if chip == "approval" and x.hs_cn_approval != "Pending":
			continue
		if chip == "accepted" and o != "Accepted":
			continue
		if chip == "lost" and o != "Lost":
			continue
		if chip == "revised" and o != "Revised":
			continue
		if not _q(q, x.name, x.customer_name, x.party_name, x.hs_subject):
			continue
		state = {"Accepted": _("Won"), "Lost": _("Lost"), "Revised": _("Revised")}.get(o) or (_("Draft") if x.docstatus == 0 else _("Sent"))
		rows.append({"dt": "Quotation", "name": x.name, "cells": [{"main": x.hs_subject or x.customer_name, "sub": f"{x.name}" + (_(" · rev {0}").format(x.hs_cn_revision) if cint(x.hs_cn_revision) else "")},
			{"main": x.customer_name or x.party_name, "sub": frappe.format(x.transaction_date, {"fieldtype": "Date"})}, {"money": x.base_net_total, "currency": cur,
				"sub": _("discount {0:.1f}%").format(flt(x.hs_cn_discount_pct)) if flt(x.hs_cn_discount_pct) else ""},
			{"main": f"{flt(x.hs_estimated_margin):.1f}%" if flt(x.hs_cn_cost) else "—", "sub": _("cost {0}").format(_m(x.hs_cn_cost, cur)) if flt(x.hs_cn_cost) else "",
				"late": 1 if flt(x.hs_cn_cost) and flt(x.hs_estimated_margin) < B.limits().margin else 0},
			{"pill": _(x.hs_cn_approval or "Not needed"), "tone": {"Pending": "orange", "Approved": "green", "Rejected": "red"}.get(x.hs_cn_approval, "grey"), "sub": x.hs_cn_approved_by or ""},
			{"pill": state, "tone": {"Won": "green", "Lost": "red", "Revised": "grey", "Sent": "blue"}.get(state, "grey"),
				"sub": (_("valid till {0}").format(frappe.format(x.valid_till, {"fieldtype": "Date"})) if x.valid_till and o == "Open" else (x.hs_cn_project or "")),
				"late": 1 if o == "Open" and x.valid_till and getdate(x.valid_till) < t else 0}, _qt_btns(x)]})
	return {"title": _("Construction quotations"), "cols": [{"label": _("Quotation")}, {"label": _("Client")}, {"label": _("Value"), "cls": "num"}, {"label": _("Margin %")},
		{"label": _("MD approval")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No quotations here.")}


# ================================================================ Contracts & Claims
def cn_con_module():
	names = _names()
	cur = _cur(names)
	C = frappe.get_list("Construction Contract", filters={"project": ["in", names or [""]]}, fields=["name", "project", "original_value", "revised_value", "eot_days"],
		limit_page_length=0) if _perm("Construction Contract") else []
	K = frappe.get_list("Contract Claim", filters={"project": ["in", names or [""]]}, fields=["status", "claimed_amount", "awarded_amount", "claimed_days", "awarded_days"],
		limit_page_length=0) if _perm("Contract Claim") else []
	X = [B.ld(c.project) for c in C]
	late = [x for x in X if x.delay > 0]
	return {
		"title": _("Contracts & Claims"),
		"desc": _("Every contract — LOA, agreement, value with extra items and awarded claims, retention, advance, completion with EOT — the claims register and the liquidated-damages exposure."),
		"new": [{"label": _("New claim"), "doctype": "Contract Claim", "primary": 1}, {"label": _("New contract"), "doctype": "Construction Contract"}],
		"kpis": [
			kpi(_("Revised contract value"), sum(flt(c.revised_value) for c in C), _("original {0}").format(_m(sum(flt(c.original_value) for c in C), cur)), "navy", "signature", True, cur, tab="reg"),
			kpi(_("Claims pending"), sum(flt(k.claimed_amount) for k in K if k.status in ("Submitted", "Under negotiation")),
				_("{0} claims · {1} days").format(len([k for k in K if k.status in ("Submitted", "Under negotiation")]), sum(cint(k.claimed_days) for k in K if k.status in ("Submitted", "Under negotiation"))),
				"orange", "scale", True, cur, tab="clm"),
			kpi(_("Awarded"), sum(flt(k.awarded_amount) for k in K if k.status == "Awarded"), _("{0} days of EOT granted").format(sum(cint(c.eot_days) for c in C)), "green", "check", True, cur, tab="clm", chip="Awarded"),
			kpi(_("LD exposure"), sum(x.amount for x in X), _("{0} projects behind the extended completion").format(len(late)), "red" if late else "green", "triangle-alert", True, cur, tab="ld"),
		],
		"tabs": [
			{"key": "reg", "label": _("Contract register"), "chips": []},
			{"key": "clm", "label": _("EOT & claims"), "chips": [["open", _("Open")], ["Draft", _("Draft")], ["Awarded", _("Awarded")], ["all", _("All")]]},
			{"key": "ld", "label": _("LD exposure"), "chips": []},
		],
	}


def cn_con_rows(tab, chip, q=None):
	names = _names()
	cur = _cur(names)
	if tab == "clm":
		chip = chip or "open"
		f = {"project": ["in", names or [""]]}
		if chip == "open":
			f["status"] = ["in", ["Draft", "Submitted", "Under negotiation"]]
		elif chip != "all":
			f["status"] = chip
		rows = []
		for k in frappe.get_list("Contract Claim", filters=f, fields=["name", "project", "title", "kind", "status", "claimed_days", "claimed_amount", "awarded_days", "awarded_amount",
				"submitted_on", "hindrance"], order_by="creation desc", limit_page_length=0) if _perm("Contract Claim") else []:
			if not _q(q, k.name, k.title, k.project):
				continue
			b = {"Draft": [_btn(_("Submit"), "clm_submit", k.name, True)], "Submitted": [_btn(_("Negotiating"), "clm_negotiate", k.name), _js(_("Awarded…"), "cn_clm_award", k.name)],
				"Under negotiation": [_js(_("Awarded…"), "cn_clm_award", k.name), _btn("✕", "clm_reject", k.name, confirm=_("Record that the client rejected {0}?").format(k.name))]}.get(k.status)
			age = date_diff(today(), k.submitted_on) if k.submitted_on and k.status in ("Submitted", "Under negotiation") else None
			rows.append({"dt": "Contract Claim", "name": k.name, "cells": [{"main": k.title, "sub": f"{k.name}" + (f" · {k.hindrance}" if k.hindrance else "")}, _pcell(k.project), _(k.kind),
				{"main": _("{0} days").format(k.claimed_days) if cint(k.claimed_days) else "—", "sub": _m(k.claimed_amount, cur) if flt(k.claimed_amount) else ""},
				{"main": _("{0} days").format(k.awarded_days) if cint(k.awarded_days) else ("—" if k.status != "Awarded" else _("0 days")),
					"sub": _m(k.awarded_amount, cur) if flt(k.awarded_amount) else ""},
				{"pill": _(k.status), "tone": {"Awarded": "green", "Rejected": "red", "Draft": "grey"}.get(k.status, "orange"), "sub": _("{0} days with the client").format(age) if age else ""},
				{"buttons": b} if b else ""]})
		return {"title": _("EOT & claims"), "cols": [{"label": _("Claim")}, {"label": _("Project")}, {"label": _("Kind")}, {"label": _("Claimed")}, {"label": _("Awarded")},
			{"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No claims here.")}
	if tab == "ld":
		rows = []
		for n in names:
			x = B.ld(n)
			if not x.contract:
				continue
			rows.append({"dt": "Construction Contract", "name": x.contract.name, "cells": [_pcell(n), {"main": f"{x.planned:.0f}% / {x.actual:.0f}%", "sub": _("planned / done")},
				_date(x.contract.completion_date), {"main": frappe.format(x.contract.extended_completion, {"fieldtype": "Date"}) if x.contract.extended_completion else "—",
					"sub": _("+{0} days EOT").format(x.contract.eot_days) if cint(x.contract.eot_days) else ""},
				_date(x.forecast, x.delay > 0), {"main": _("{0} days").format(x.delay) if x.delay else _("On time"), "sub": _("{0} weeks").format(x.weeks) if x.weeks else "", "late": 1 if x.delay else 0},
				{"money": x.amount, "currency": cur, "sub": _("cap {0}").format(_m(x.cap, cur)), "neg": 1 if x.amount else 0},
				{"main": _("{0} days").format(x.claimable) if x.claimable else "—", "sub": _("hindrance days, no EOT yet") if x.claimable else ""}]})
		return {"title": _("Liquidated damages — programme slip beyond the completion date extended by EOT"), "cols": [{"label": _("Project")}, {"label": _("Progress")},
			{"label": _("Completion")}, {"label": _("With EOT")}, {"label": _("Forecast")}, {"label": _("Delay")}, {"label": _("LD exposure"), "cls": "num"}, {"label": _("Still claimable")}],
			"rows": rows, "empty": _("No contracts yet.")}
	rows = []
	for c in frappe.get_list("Construction Contract", filters={"project": ["in", names or [""]]}, fields=["name", "project", "loa_no", "agreement_no", "original_value", "variations",
			"claims_awarded", "revised_value", "retention_pct", "advance_pct", "ld_rate_pct", "ld_cap_pct", "dlp_months", "status", "price_escalation"],
			order_by="revised_value desc", limit_page_length=0) if _perm("Construction Contract") else []:
		if not _q(q, c.name, c.project, c.loa_no, c.agreement_no):
			continue
		rows.append({"dt": "Construction Contract", "name": c.name, "cells": [{"main": c.loa_no or c.name, "sub": c.agreement_no or ""}, _pcell(c.project), {"money": c.original_value, "currency": cur},
			{"money": flt(c.variations) + flt(c.claims_awarded), "currency": cur, "sub": _("claims {0}").format(_m(c.claims_awarded, cur)) if flt(c.claims_awarded) else ""},
			{"money": c.revised_value, "currency": cur}, {"main": _("{0:g}% · {1:g}%").format(flt(c.retention_pct), flt(c.advance_pct)), "sub": _("retention · advance")},
			{"main": _("{0:g}%/wk, cap {1:g}%").format(flt(c.ld_rate_pct), flt(c.ld_cap_pct)), "sub": _("DLP {0} months").format(c.dlp_months)}, {"pill": _(c.status)}]})
	return {"title": _("Contract register"), "cols": [{"label": _("LOA / agreement")}, {"label": _("Project")}, {"label": _("Original"), "cls": "num"}, {"label": _("Extras & claims"), "cls": "num"},
		{"label": _("Revised"), "cls": "num"}, {"label": _("Retention · advance")}, {"label": _("LD · DLP")}, {"label": _("Status")}], "rows": rows, "empty": _("No contracts yet.")}
