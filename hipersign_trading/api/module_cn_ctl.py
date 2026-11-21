"""v1.9.1 stage B2: Tasks, Risks & issues and Meetings on Project Controls; RA workbench, Mobilisation advance and Final
bill on RA Billing. Rules in api/construction_ctl.py; the Construction Tracker page calls construction_ctl.tracker."""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_ctl as CTL
from hipersign_trading.api.module import _perm, kpi

CTL_TABS = ("task", "risk", "mtg")
RA_TABS = ("wb", "adv", "fin")
TONE = {"High": "red", "Medium": "amber", "Low": "grey"}


def _h():
	from hipersign_trading.api import module_cn as M

	return M


def _risks(names, f=None):
	return frappe.get_list("Project Risk", filters=dict({"project": ["in", names or [""]]}, **(f or {})), fields=["name", "project", "kind", "title", "category", "probability",
		"impact", "score", "owner_name", "review_by", "mitigation", "status", "closed_on", "cost_impact", "days_impact"], order_by="status desc, score desc, review_by asc",
		limit_page_length=0) if _perm("Project Risk") else []


def _mtgs(names):
	return frappe.get_list("Project Meeting", filters={"project": ["in", names or [""]]}, fields=["name", "project", "title", "meeting_type", "meeting_date", "chaired_by",
		"next_meeting"], order_by="meeting_date desc", limit_page_length=0) if _perm("Project Meeting") else []


def _tasks(names, open_only=False):
	return [t for t in CTL.tasks(names, open_only) if not CTL._snag_type(t)] if _perm("Task") else []


# ================================================================ Project Controls
def ctl_module(base):
	def fn():
		m = base()
		M = _h()
		names = M._names(False)
		t = getdate(today())
		T = _tasks(names, True)
		late = [x for x in T if x.exp_end_date and getdate(x.exp_end_date) < t]
		R = _risks(names, {"status": "Open"})
		hi = [r for r in R if cint(r.score) >= 6]
		MT = _mtgs(names)
		m["new"] = (m.get("new") or []) + [{"label": _("Task"), "doctype": "Task"}, {"label": _("Risk / issue"), "doctype": "Project Risk"},
			{"label": _("Minutes of meeting"), "doctype": "Project Meeting"}]
		m["kpis"] = m["kpis"][:4] + [kpi(_("Tasks overdue"), len(late), _("{0} open · {1} high risks").format(len(T), len(hi)), "red" if late else "green", "list-checks", tab="task")]
		m["tabs"] = m["tabs"] + [
			{"key": "task", "label": _("Tasks") + (f" ({len(late)})" if late else ""), "chips": [["open", _("Open")], ["late", _("Overdue")], ["done", _("Done")], ["all", _("All")]]},
			{"key": "risk", "label": _("Risks & issues"), "chips": [["open", _("Open")], ["Risk", _("Risks")], ["Issue", _("Issues")], ["Closed", _("Closed")], ["all", _("All")]]},
			{"key": "mtg", "label": _("Meetings"), "chips": [["all", _("All")]] + [[n, M._proj(n).project_name.split(" — ")[0]] for n in names if any(x.project == n for x in MT)]},
		]
		return m
	fn.__name__ = base.__name__
	return fn


def ctl_rows(base):
	def fn(tab, chip, q=None):
		if tab not in CTL_TABS:
			return base(tab, chip, q)
		M = _h()
		names = M._names(False)
		t = getdate(today())
		if tab == "task":
			chip = chip or "open"
			T = _tasks(names, chip in ("open", "late"))
			rows = []
			for x in T:
				lt = x.exp_end_date and getdate(x.exp_end_date) < t and x.status not in ("Completed", "Cancelled")
				if chip == "late" and not lt or chip == "done" and x.status != "Completed" or not M._q(q, x.subject, x.project, x.hs_task_owner):
					continue
				rows.append({"dt": "Task", "name": x.name, "cells": [{"main": x.subject, "sub": x.name}, M._pcell(x.project), x.hs_task_owner or "—",
					{"pill": _(x.priority or "Medium"), "tone": TONE.get(x.priority or "Medium")}, {"date": str(x.exp_end_date) if x.exp_end_date else None, "late": 1 if lt else 0},
					{"pill": _(x.status), "tone": "green" if x.status == "Completed" else "blue" if x.status == "Working" else "amber" if x.status == "Overdue" else "grey"},
					{"buttons": [M._btn(_("Done"), "task_done", x.name, True)]} if x.status not in ("Completed", "Cancelled") else ""]})
			rows.sort(key=lambda r: (r["cells"][5]["pill"] == _("Completed"), r["cells"][4]["date"] or "9999"))
			return {"title": _("Tasks on the live projects — action points from meetings become tasks here"), "cols": [{"label": _("Task")}, {"label": _("Project")},
				{"label": _("Owner")}, {"label": _("Priority")}, {"label": _("Due")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "nototal": 1,
				"actions": [{"label": _("New task"), "new": "Task", "primary": 1}], "empty": _("No tasks match.")}
		if tab == "risk":
			chip = chip or "open"
			f = {"status": "Open"} if chip in ("open", "Risk", "Issue") else {"status": "Closed"} if chip == "Closed" else {}
			if chip in ("Risk", "Issue"):
				f["kind"] = chip
			rows = []
			for r in _risks(names, f):
				if not M._q(q, r.title, r.project, r.owner_name, r.category):
					continue
				lt = r.status == "Open" and r.review_by and getdate(r.review_by) < t
				rows.append({"dt": "Project Risk", "name": r.name, "cells": [{"main": r.title, "sub": f"{r.name} · {_(r.kind)} · {_(r.category or '')}"}, M._pcell(r.project),
					{"pill": _(r.probability), "tone": TONE.get(r.probability)}, {"pill": _(r.impact), "tone": TONE.get(r.impact)},
					{"main": str(cint(r.score)), "late": 1 if cint(r.score) >= 6 and r.status == "Open" else 0},
					{"main": CN.inr(r.cost_impact) if flt(r.cost_impact) else "—", "sub": _("{0} days").format(r.days_impact) if cint(r.days_impact) else ""},
					{"main": r.owner_name or "—", "sub": (r.mitigation or "")[:80]}, {"date": str(r.review_by) if r.review_by else None, "late": 1 if lt else 0},
					{"buttons": [M._js(_("Close…"), "cn_risk_close", r.name)]} if r.status == "Open" else {"pill": _("Closed"), "tone": "green", "sub": str(r.closed_on or "")}]})
			return {"title": _("Risk & issue register — probability × impact (1–9); 6 and above is high"), "cols": [{"label": _("Risk / issue")}, {"label": _("Project")},
				{"label": _("Probability")}, {"label": _("Impact")}, {"label": _("Score")}, {"label": _("If it happens")}, {"label": _("Owner · mitigation")},
				{"label": _("Review by")}, {"label": ""}], "rows": rows, "nototal": 1, "actions": [{"label": _("New risk / issue"), "new": "Project Risk", "primary": 1}],
				"empty": _("No risks or issues match.")}
		MT = _mtgs(names)
		rows = []
		for x in MT:
			if chip and chip != "all" and x.project != chip or not M._q(q, x.title, x.project, x.meeting_type):
				continue
			A = frappe.get_all("Meeting Action", filters={"parent": x.name, "parenttype": "Project Meeting"}, fields=["action", "owner_name", "due", "task"], order_by="idx asc")
			todo = [a for a in A if not a.task]
			rows.append({"dt": "Project Meeting", "name": x.name, "cells": [{"main": x.title, "sub": f"{x.name} · {_(x.meeting_type)}"}, M._pcell(x.project),
				{"date": str(x.meeting_date)}, x.chaired_by or "—", {"lines": [f"{a.action} — {a.owner_name or '?'}" + (f" ({a.task})" if a.task else "") for a in A[:4]] or ["—"]},
				{"date": str(x.next_meeting) if x.next_meeting else None},
				{"buttons": [M._btn(_("Raise {0} tasks").format(len(todo)), "mtg_tasks", x.name, True)]} if todo else {"pill": _("Tasks raised") if A else _("No actions"), "tone": "green" if A else "grey"}]})
		return {"title": _("Minutes of meeting — progress reviews, client / PMC and subcontractor meetings"), "cols": [{"label": _("Meeting")}, {"label": _("Project")},
			{"label": _("Date")}, {"label": _("Chaired by")}, {"label": _("Action points")}, {"label": _("Next")}, {"label": ""}], "rows": rows, "nototal": 1,
			"actions": [{"label": _("Minutes"), "new": "Project Meeting", "primary": 1}], "empty": _("No minutes recorded yet.")}
	fn.__name__ = base.__name__
	return fn


# ================================================================ RA Billing
def ra_module(base):
	def fn():
		m = base()
		M = _h()
		names = M._names()
		cur = M._cur(names)
		adv = [n for n in names if flt(M._proj(n).get("hs_advance_pct")) and cint(M._proj(n).hs_step) >= 5]
		A = {n: CTL.adv_fig(n) for n in adv}
		wb = [n for n in names if 13 <= cint(M._proj(n).hs_step) < 23 and CN.boq(n)]
		fin = [n for n in names if cint(M._proj(n).hs_step) >= 21]
		k = m["kpis"][3]
		k["sub"] = _("advance still to recover {0}").format(CN.inr(sum(a.balance for a in A.values())))
		m["tabs"] = m["tabs"][:1] + [{"key": "wb", "label": _("RA workbench"), "chips": [c for c in M._chips(wb)]},
			{"key": "adv", "label": _("Mobilisation advance"), "chips": []},
			{"key": "fin", "label": _("Final bill"), "chips": [c for c in M._chips(fin)]}] + m["tabs"][1:]
		return m
	fn.__name__ = base.__name__
	return fn


def ra_rows(base):
	def fn(tab, chip, q=None):
		if tab not in RA_TABS:
			return base(tab, chip, q)
		M = _h()
		names = M._names()
		cur = M._cur(names)
		if tab == "wb":
			wb = [n for n in names if 13 <= cint(M._proj(n).hs_step) < 23 and CN.boq(n)]
			pj = M._pick(chip, wb)
			if not pj:
				return {"rows": [], "cols": [], "empty": _("No project on site with a BOQ.")}
			W = CTL.workbench(pj)
			rows = [{"cells": [{"main": (r.description or "")[:60], "sub": f"{r.item_no} · {r.unit or ''}"}, round(r.qty, 3), round(r.prev, 3),
				{"main": f"{r.now:,.3f}" if r.now else "—", "sub": _("to date {0:,.3f}").format(r.cum) if r.now else ""}, {"main": f"{r.wait:,.3f}" if r.wait else "—"},
				{"main": f"{r.bal:,.3f}", "late": 1 if r.bal < -0.0005 and (r.unit or "").upper() != "LS" else 0}, {"money": r.rate, "currency": cur, "dp": 2},
				{"money": r.amount, "currency": cur}]} for r in W if M._q(q, r.item_no, r.description)]
			tot = sum(r.amount for r in W)
			draft = frappe.db.get_value("RA Bill", {"project": pj, "status": "Draft"}, "name")
			acts = [{"label": _("Open draft {0}").format(draft), "url": f"/app/ra-bill/{draft}"}] if draft else (
				[{"label": _("Create RA bill — {0}").format(CN.inr(tot)), "primary": 1, "method": M.ACT, "args": {"action": "ra_new", "name": pj, "args": "{}"}}] if tot > 0 else [])
			return {"title": _("RA workbench — next bill for {0}: {1} from {2} client-checked lines (only checked measurements are billed)").format(
				M._proj(pj).project_name, CN.inr(tot), len([r for r in W if r.now])), "cols": [{"label": _("BOQ item")}, {"label": _("BOQ qty"), "cls": "num"},
				{"label": _("Billed before"), "cls": "num"}, {"label": _("This bill"), "cls": "num"}, {"label": _("Not yet checked"), "cls": "num"},
				{"label": _("Balance"), "cls": "num"}, {"label": _("Rate"), "cls": "num"}, {"label": _("Amount"), "cls": "num"}],
				"rows": rows, "actions": acts, "empty": _("Nothing measured on {0} since the last bill.").format(pj)}
		if tab == "adv":
			rows = []
			for n in names:
				p = M._proj(n)
				if not flt(p.get("hs_advance_pct")) or cint(p.hs_step) < 5 or not M._q(q, n, p.project_name):
					continue
				A = CTL.adv_fig(n)
				bg = CTL.adv_bg(n)
				t = getdate(today())
				b = []
				if A.to_claim > 1 and cint(p.hs_step) < 22:
					b = [M._js(_("Advance received…"), "cn_adv_receive", n)]
				pc = M._pcell(n)
				pc["sub"] = f"{n} · {A.pct:g}% " + _("advance")
				rows.append({"dt": "Project", "name": n, "cells": [pc, {"money": A.due, "currency": cur}, {"money": A.received, "currency": cur},
					{"money": A.recovered, "currency": cur, "sub": f"{A.recovered / A.received * 100:.0f}%" if A.received else ""}, {"money": A.balance, "currency": cur},
					{"lines": [f"{g.bank_guarantee_number or g.name} · {CN.inr(g.amount)} · {_('exp.')} {frappe.format(g.end_date, {'fieldtype': 'Date'})} · {_(g.hs_bond_status or '')}"
						for g in bg] or [_("No advance BG")], "late": 1 if any(g.hs_bond_status == "Active" and g.end_date and (getdate(g.end_date) - t).days <= 45 and A.balance > 1
						for g in bg) else 0}, {"buttons": b} if b else ""]})
			return {"title": _("Mobilisation advance — received against the advance BG, recovered from each RA bill; the BG is reduced as it is recovered"),
				"cols": [{"label": _("Project")}, {"label": _("As per terms"), "cls": "num"}, {"label": _("Received"), "cls": "num"},
				{"label": _("Recovered"), "cls": "num"}, {"label": _("To recover"), "cls": "num"}, {"label": _("Advance BG")}, {"label": ""}],
				"rows": rows, "empty": _("No project has a mobilisation advance.")}
		fin = [n for n in names if cint(M._proj(n).hs_step) >= 21]
		pj = M._pick(chip, fin)
		if not pj:
			return {"rows": [], "cols": [], "empty": _("No project has reached completion yet — the final bill follows the completion certificate.")}
		X = CTL.final_fig(pj)
		F = X.F
		p = M._proj(pj)
		pbg = [g for g in (frappe.get_all("Bank Guarantee", filters={"project": pj, "docstatus": 1, "hs_bond_type": "Performance bond"}, fields=["name", "bank_guarantee_number",
			"end_date", "hs_bond_status"]) if frappe.get_meta("Bank Guarantee").has_field("hs_bond_type") else [])]
		kv = lambda a, v, s="", neg=0: {"cells": [{"main": a, "sub": s} if s else a, {"money": v, "currency": cur, "neg": neg} if not isinstance(v, str) else {"main": v}]}
		fb = X.final
		rows = [kv(_("Work measured at the BOQ rates"), X.work), kv(_("Approved extra items & deviations"), X.ei), kv(_("Gross value of the work"), X.work + X.ei),
			kv(_("Less RA bills 1–{0} certified").format(len(X.prev)), -X.prev_cert, neg=1),
			kv(_("Final bill"), fb.name + " · " + _(fb.status) + " · " + CN.inr(fb.certified_amount or fb.claimed_amount) if fb else _("not prepared")),
			kv(_("Retention held"), F.retention, _("released after the {0}-month DLP").format(cint(p.get("hs_dlp_months")) or 12)),
			kv(_("Mobilisation advance left to recover"), CTL.adv_fig(pj).balance if flt(p.get("hs_advance_pct")) else 0, _("recovered in full on the final bill")),
			kv(_("Performance BG"), ", ".join(f"{g.bank_guarantee_number or g.name} · {_(g.hs_bond_status or '')}" for g in pbg) or "—"),
			kv(_("Open before the final bill"), _("{0} measurements to check · {1} extra items open · {2} snags open").format(X.mb_open, len(X.ei_open), X.snags_open))]
		acts = [{"label": _("Prepare final bill"), "primary": 1, "method": M.ACT, "args": {"action": "ra_final", "name": pj, "args": "{}"}}] if not fb else \
			[{"label": _("Open {0}").format(fb.name), "url": f"/app/ra-bill/{fb.name}"}]
		return {"title": _("Final bill — {0}: closes the contract account — every RA bill, every extra item, the retention and the guarantees").format(p.project_name),
			"cols": [{"label": ""}, {"label": _("Amount"), "cls": "num"}], "rows": rows, "nototal": 1, "actions": acts}
	fn.__name__ = base.__name__
	return fn


def extend(g):
	"""Wraps the Project Controls and RA Billing pages of module_cn (g = its globals)."""
	g["cn_ctl_module"] = ctl_module(g["cn_ctl_module"])
	g["cn_ctl_rows"] = g["_whole"](ctl_rows(g["cn_ctl_rows"]))
	g["cn_ra_module"] = ra_module(g["cn_ra_module"])
	g["cn_ra_rows"] = g["_whole"](ra_rows(g["cn_ra_rows"]))
