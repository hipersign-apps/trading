"""v1.9.1 stage B1: the estimating tabs on the BOQ page (rate analysis, cost build-up, BOQ versions, rate library vs SOR,
tender price & margin, templates) and on the Tenders page (submission checklist, bid analysis). Rules in
api/construction_est.py."""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_est as EST
from hipersign_trading.api.module import _perm, kpi

BOQ_TABS = ("ra", "cost", "ver", "lib", "price", "tpl")
TND_TABS = ("chk", "bid")


def _h():
	from hipersign_trading.api import module_cn as M

	return M


def _ras():
	return frappe.get_list("Rate Analysis", fields=["name", "title", "code", "category", "unit", "analysed_rate", "sor_rate", "sor_name", "sor_code", "status", "based_on",
		"rates_as_of", "approved_by"], order_by="category asc, title asc", limit_page_length=0) if _perm("Rate Analysis") else []


def _tender_boqs():
	return frappe.get_list("Project BOQ", filters={"version_type": "Tender BOQ", "status": ["in", ["Being priced", "Submitted"]]}, fields=["name", "title", "tender", "status"],
		order_by="creation desc", limit_page_length=0) if _perm("Project BOQ") else []


# ================================================================ BOQ page
def boq_module(base):
	def fn():
		m = base()
		M = _h()
		names = M._names()
		cur = M._cur(names)
		R = _ras()
		T = _tender_boqs()
		bq = [n for n in names if CN.boq(n)]
		m["title"] = _("BOQ & Estimating")
		m["desc"] = _("Each project's bill of quantities with the rate analysis behind its main items and the cost build-up that becomes the budget, the BOQ versions (tender → contract → revised), our rates against the schedule of rates, the tender price and margin, the standard BOQ templates — and the extra items and deviations.")
		m["new"] = (m.get("new") or []) + [{"label": _("Rate analysis"), "doctype": "Rate Analysis"}, {"label": _("BOQ template"), "doctype": "BOQ Template"}]
		low = [r for n in bq for r in CN.boq(n).items if r.rate_analysis and flt(r.analysed_rate) and flt(r.rate) < flt(r.analysed_rate) * .97]
		m["kpis"] = [m["kpis"][0], m["kpis"][2]] + [
			kpi(_("Rate analyses"), len(R), _("{0} approved · {1} BOQ lines below the analysed rate").format(len([r for r in R if r.status == "Approved"]), len(low)),
				"blue", "calculator", tab="lib"),
			kpi(_("Tenders being priced"), len(T), ", ".join(x.tender or x.name for x in T[:2]) or _("none"), "violet", "file-text", tab="price"),
		]
		chips = M._chips(bq)
		m["tabs"] = [m["tabs"][0],
			{"key": "ra", "label": _("Rate analysis"), "chips": [[r.name, (r.code + " " if r.code else "") + r.title[:28]] for r in R][:30]},
			{"key": "cost", "label": _("Cost build-up"), "chips": chips},
			{"key": "ver", "label": _("BOQ versions"), "chips": chips + [[f"tb::{x.name}", (x.tender or x.name)] for x in T]},
			{"key": "lib", "label": _("Rate library vs SOR"), "chips": []},
			{"key": "price", "label": _("Tender price & margin"), "chips": [[x.name, x.tender or x.title[:24]] for x in T]},
			{"key": "tpl", "label": _("Templates"), "chips": []}] + m["tabs"][1:]
		return m
	return fn


def _kv(label, value, cur, strong=False, sub="", neg=False):
	return {"cells": [{"main": label, "sub": sub} if sub else ({"main": label} if strong else label), {"money": value, "currency": cur, "neg": 1 if neg else 0} if not isinstance(value, str)
		else {"main": value}]}


def boq_rows(base):
	def fn(tab, chip, q=None):
		if tab not in BOQ_TABS:
			return base(tab, chip, q)
		M = _h()
		names = M._names()
		cur = M._cur(names)
		bq = [n for n in names if CN.boq(n)]
		if tab == "ra":
			R = _ras()
			name = chip if chip in [r.name for r in R] else (R[0].name if R else None)
			if not name:
				return {"rows": [], "cols": [], "empty": _("No rate analysis yet — add one with New › Rate analysis.")}
			a = frappe.get_doc("Rate Analysis", name)
			tone = {"Material": "blue", "Labour": "orange", "Plant": "violet"}
			rows = [{"cells": [{"main": r.description, "sub": r.item or ""}, {"pill": _(r.resource_type), "tone": tone.get(r.resource_type)}, r.unit or "", round(flt(r.coefficient), 4),
				{"money": r.rate, "currency": cur, "dp": 2}, {"money": r.amount, "currency": cur, "dp": 2}, {"main": r.rate_source or "—"}]} for r in a.resources]
			used = frappe.db.sql("""select i.rate, i.item_no, b.project, b.name from `tabProject BOQ Item` i join `tabProject BOQ` b on b.name = i.parent where i.rate_analysis = %s
				and b.status != 'Superseded' order by b.creation desc limit 5""", a.name, as_dict=True)
			for lbl, v in ((_("Material, labour & plant"), a.base_cost), (_("Water charges {0:g}%").format(flt(a.water_pct)), a.water),
					(_("Contractor overheads {0:g}%").format(flt(a.overhead_pct)), a.overheads), (_("Profit {0:g}%").format(flt(a.profit_pct)), a.profit)):
				rows.append({"cells": [{"main": lbl}, "", "", "", "", {"money": v, "currency": cur, "dp": 2}, ""]})
			rows.append({"cells": [{"main": _("Analysed rate per {0}").format(a.unit)}, {"pill": _(a.status), "tone": "green" if a.status == "Approved" else "grey", "sub": a.approved_by or ""},
				"", "", "", {"money": a.analysed_rate, "currency": cur, "dp": 2}, {"main": _("SOR {0}").format(CN.inr(a.sor_rate)) if a.sor_rate else ""}]})
			for u in used:
				d = (flt(u.rate) - flt(a.analysed_rate)) / flt(a.analysed_rate) * 100 if flt(a.analysed_rate) else 0
				rows.append({"dt": "Project BOQ", "name": u.name, "cells": [{"main": _("Quoted in {0} item {1}").format(u.project or u.name, u.item_no)}, "", "", "",
					"", {"money": u.rate, "currency": cur, "dp": 2}, {"main": f"{d:+.1f}% " + _("vs analysis"), "late": 1 if d < -3 else 0}]})
			acts = [{"label": _("Refresh rates from purchases"), "method": M.ACT, "args": {"action": "ran_refresh", "name": a.name, "args": "{}"}}]
			if a.status != "Approved":
				acts.insert(0, {"label": _("Approve"), "primary": 1, "method": M.ACT, "args": {"action": "ran_approve", "name": a.name, "args": "{}"}})
			return {"title": _("Rate analysis — {0} ({1}) · {2}").format(a.title, a.unit, _(a.based_on)), "cols": [{"label": _("Resource")}, {"label": _("Type")}, {"label": _("Unit")},
				{"label": _("Qty per {0}").format(a.unit), "cls": "num"}, {"label": _("Rate"), "cls": "num"}, {"label": _("Amount (rate)"), "cls": "num"}, {"label": _("Rate from")}],
				"rows": rows, "nototal": 1, "actions": acts}
		if tab == "cost":
			pj = M._pick(chip, bq)
			if not pj:
				return {"rows": [], "cols": [], "empty": _("No BOQ yet.")}
			b = CN.boq(pj)
			rows = []
			for r in b.items:
				if not M._q(q, r.item_no, r.description):
					continue
				sh = sum(flt(r.get(s)) for s in ("mat_share", "lab_share", "sub_share", "plant_share", "ovh_share"))
				low = r.rate_analysis and flt(r.analysed_rate) and flt(r.rate) < flt(r.analysed_rate) * .97
				rows.append({"dt": "Project BOQ", "name": b.name, "cells": [{"code": r.item_no}, {"main": r.description[:70], "sub": (_("analysed {0}").format(CN.inr(r.analysed_rate))
					if r.rate_analysis else "")}] + [f"{flt(r.get(s)):.0f}%" if flt(r.get(s)) else "—" for s in ("mat_share", "lab_share", "plant_share", "sub_share", "ovh_share")]
					+ [{"money": flt(r.cost_rate) * flt(r.qty), "currency": cur}, {"main": f"{100 - sh:.1f}%", "late": 1 if sh > 100 or low else 0,
						"sub": _("below the analysed rate") if low else ""}]})
			return {"title": _("Cost build-up — {0} · direct cost {1}, margin after overheads {2:.1f}% (it becomes the budget)").format(M._proj(pj).project_name, CN.inr(b.direct_cost), flt(b.margin_pct)),
				"cols": [{"label": _("Item")}, {"label": _("Description")}, {"label": _("Material")}, {"label": _("Labour")}, {"label": _("Plant")}, {"label": _("Subcontract")},
				{"label": _("Overheads")}, {"label": _("Direct cost"), "cls": "num"}, {"label": _("Item margin")}], "rows": rows}
		if tab == "ver":
			if chip and chip.startswith("tb::"):
				head = frappe.get_doc("Project BOQ", chip[4:])
				f = {"tender": head.tender} if head.tender else {"name": head.name}
			else:
				pj = M._pick(chip, bq)
				if not pj:
					return {"rows": [], "cols": [], "empty": _("No BOQ yet.")}
				tnd = frappe.db.get_value("Tender", {"project": pj}, "name")
				f = None
			V = frappe.get_all("Project BOQ", filters=f, fields=["name", "version_type", "revision", "status", "total_amount", "revised_value", "approved_variations", "creation",
				"owner", "tender", "project", "version_of"], order_by="revision asc, creation asc") if f else frappe.db.sql("""select name, version_type, revision, status,
				total_amount, revised_value, approved_variations, creation, owner, tender, project, version_of from `tabProject BOQ` where project = %s or (tender is not null
				and tender = %s) order by revision asc, creation asc""", (pj, tnd or "—"), as_dict=True)
			rows = []
			for v in V:
				cur_v = v.status != "Superseded"
				b = []
				if cur_v and v.version_type == "Tender BOQ":
					b = [M._js(_("Contract version…"), "cn_boq_contract", v.name)]
				elif cur_v and v.project:
					b = [M._btn(_("Revise with approved variations"), "boq_ver", v.name, True, {"kind": "Revised"},
						confirm=_("Make a revised BOQ of {0} with the approved variations? The current version is kept, superseded.").format(v.project))]
				rows.append({"dt": "Project BOQ", "name": v.name, "cells": [{"main": f"V{cint(v.revision)}", "sub": v.name}, _(v.version_type or "—"),
					{"money": flt(v.revised_value) or flt(v.total_amount), "currency": cur, "sub": _("incl. {0} variations").format(CN.inr(v.approved_variations)) if flt(v.approved_variations) else ""},
					M._date(str(v.creation)[:10]), frappe.utils.get_fullname(v.owner), {"pill": _("Current") if cur_v else _("Superseded"), "tone": "green" if cur_v else "grey",
						"sub": _(v.status) if cur_v else ""}, {"buttons": b} if b else ""]})
			return {"title": _("BOQ versions — tender → contract → revised · the measurement book works on the current version"), "cols": [{"label": _("Version")},
				{"label": _("Type")}, {"label": _("Value"), "cls": "num"}, {"label": _("Date")}, {"label": _("By")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "nototal": 1,
				"empty": _("No versions.")}
		if tab == "lib":
			rows = []
			for r in _ras():
				if not M._q(q, r.title, r.code, r.category, r.sor_code):
					continue
				vs = (flt(r.analysed_rate) / flt(r.sor_rate) - 1) * 100 if flt(r.sor_rate) else None
				hist = EST.quoted_history(r.name)
				rows.append({"dt": "Rate Analysis", "name": r.name, "cells": [{"main": r.title, "sub": " · ".join(x for x in (r.code, _(r.category)) if x)}, r.unit,
					{"money": r.analysed_rate, "currency": cur, "dp": 2}, {"money": r.sor_rate, "currency": cur, "dp": 2, "sub": (r.sor_code or "")} if flt(r.sor_rate) else "—",
					{"main": f"{vs:+.1f}%" if vs is not None else "—", "late": 1 if vs is not None and vs > 5 else 0}, {"lines": [CN.inr(h.rate) + " · " + (h.title or h.name)[:22] for h in hist]
						or [_("not quoted yet")]}, {"pill": _(r.status), "tone": "green" if r.status == "Approved" else "grey", "sub": frappe.format(r.rates_as_of, {"fieldtype": "Date"})
						if r.rates_as_of else ""}]})
			return {"title": _("Rate library — our analysed rates against the schedule of rates, and what we quoted in the last tenders"), "cols": [{"label": _("Item of work")},
				{"label": _("Unit")}, {"label": _("Our rate"), "cls": "num"}, {"label": _("SOR rate"), "cls": "num"}, {"label": _("vs SOR")}, {"label": _("Last quoted")},
				{"label": _("Status")}], "rows": rows, "nototal": 1, "empty": _("No rate analyses yet.")}
		if tab == "price":
			T = _tender_boqs()
			name = chip if chip in [x.name for x in T] else (T[0].name if T else None)
			if not name:
				return {"rows": [], "cols": [], "empty": _("No tender being priced — start one from Templates › New BOQ from template.")}
			b = frappe.get_doc("Project BOQ", name)
			t = frappe.get_doc("Tender", b.tender) if b.tender else None
			p = EST.price(b)
			est = flt(t.estimated_value) if t else 0
			rows = [_kv(_("Direct cost (material, labour, plant, subcontract)"), p.direct, cur), _kv(_("Site overheads {0:g}%").format(flt(b.site_oh_pct)), p.site, cur),
				_kv(_("Head-office overheads {0:g}%").format(flt(b.ho_oh_pct)), p.ho, cur), _kv(_("Contingency {0:g}%").format(flt(b.contingency_pct)), p.cont, cur),
				_kv(_("Total cost"), p.total, cur, True), _kv(_("Target margin"), f"{p.margin:g}%", cur), _kv(_("Bid price"), p.bid, cur, True,
					sub=_("the MD sets bids above ₹20 Cr") if p.bid > EST.MD_BID_LIMIT else "")]
			if est:
				d = (p.bid / est - 1) * 100
				rows += [_kv(_("Client's estimate"), est, cur), _kv(_("Bid vs estimate"), f"{d:+.1f}%", cur)]
			if t:
				rows.append(_kv(_("Quoted on the tender"), flt(t.our_bid), cur, sub=_(t.status)))
			acts = [{"label": f"{m:g}%", "primary": 1 if abs(m - p.margin) < .01 else 0, "method": M.ACT, "args": {"action": "boq_price", "name": b.name, "args": frappe.as_json({"margin": m})}}
				for m in sorted({8, 10, 12, 14, round(p.margin, 1)})] + [{"label": _("Other margin…"), "js": "cn_boq_margin", "arg": b.name}]
			return {"title": _("Tender price & margin — {0}").format(b.title), "cols": [{"label": _("From the cost build-up of the BOQ ({0})").format(b.name)}, {"label": "", "cls": "num"}],
				"rows": rows, "nototal": 1, "actions": acts}
		rows = []
		for T in frappe.get_list("BOQ Template", fields=["name", "title", "category", "total_weight"], limit_page_length=0) if _perm("BOQ Template") else []:
			ch = frappe.get_all("BOQ Template Item", filters={"parent": T.name}, pluck="section_name")
			used = frappe.db.count("Project BOQ", {"template": T.name})
			rows.append({"dt": "BOQ Template", "name": T.name, "cells": [{"main": T.title, "sub": T.category or ""}, len(ch), {"main": ", ".join(dict.fromkeys(x for x in ch if x))[:80]},
				f"{flt(T.total_weight):g}%", str(used) if used else "—", {"buttons": [M._js(_("New BOQ from template…"), "cn_boq_tpl", T.name)]}]})
		return {"title": _("BOQ templates — a new tender or project starts from one; quantities follow the value"), "cols": [{"label": _("Template")}, {"label": _("Items"), "cls": "num"},
			{"label": _("Chapters")}, {"label": _("Shares")}, {"label": _("BOQs made")}, {"label": ""}], "rows": rows, "nototal": 1, "empty": _("No templates yet.")}
	fn.__name__ = base.__name__
	return fn


# ================================================================ Tenders page
def tnd_module(base):
	def fn():
		m = base()
		M = _h()
		T = M._tenders()
		t = getdate(today())
		open_ = [x for x in T if x.status in ("Bid / no-bid", "Being priced")]
		chk = {x.name: frappe.db.get_value("Tender", x.name, ["checklist_done", "checklist_total"], as_dict=True) for x in open_}
		risky = [x for x in open_ if x.due_date and date_diff(x.due_date, t) <= 7 and chk[x.name] and cint(chk[x.name].checklist_done) < cint(chk[x.name].checklist_total)]
		m["kpis"] = m["kpis"][:3] + [kpi(_("Checklists not ready"), len(risky), _("bids due in 7 days with documents missing") if risky else _("all due bids ready"),
			"red" if risky else "green", "list-checks", tab="chk")] + m["kpis"][3:]
		bids = [x for x in T if frappe.db.count("Tender Bidder", {"parent": x.name})]
		m["tabs"] = m["tabs"][:1] + [{"key": "chk", "label": _("Submission checklist"), "chips": [["open", _("Open")], ["all", _("All")]]},
			{"key": "bid", "label": _("Bid analysis"), "chips": [[x.name, x.tender_name[:26]] for x in bids]}] + m["tabs"][1:]
		return m
	return fn


def tnd_rows(base):
	def fn(tab, chip, q=None):
		if tab not in TND_TABS:
			return base(tab, chip, q)
		M = _h()
		T = M._tenders()
		cur = M._cur()
		t = getdate(today())
		if tab == "chk":
			rows = []
			for x in T:
				if (chip or "open") == "open" and x.status not in ("Bid / no-bid", "Being priced"):
					continue
				d = frappe.get_doc("Tender", x.name)
				if not d.checklist:
					continue
				miss = [r.item for r in d.checklist if not cint(r.done)]
				days = date_diff(x.due_date, t) if x.due_date else None
				pct = cint(d.checklist_done) / max(1, cint(d.checklist_total)) * 100
				rows.append({"dt": "Tender", "name": x.name, "cells": [{"main": x.tender_name, "sub": f"{x.name} · {x.client_name or ''}"}, {"bar": round(pct)},
					{"main": f"{d.checklist_done} / {d.checklist_total}"}, {"lines": miss[:3] + ([_("+ {0} more").format(len(miss) - 3)] if len(miss) > 3 else []) or [_("All ready")]},
					{"date": str(x.due_date) if x.due_date else None, "late": 1 if miss and days is not None and days <= 7 else 0}, {"pill": _(x.status)},
					{"buttons": [M._js(_("Checklist…"), "cn_tnd_chk", x.name)]} if x.status in ("Bid / no-bid", "Being priced") else ""]})
			return {"title": _("Submission checklist — a bid is not submitted with items missing"), "cols": [{"label": _("Tender")}, {"label": _("Ready")}, {"label": ""},
				{"label": _("Missing")}, {"label": _("Bid due")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "nototal": 1, "empty": _("No open tenders.")}
		bids = [x for x in T if frappe.db.count("Tender Bidder", {"parent": x.name})]
		name = chip if chip in [x.name for x in bids] else (bids[0].name if bids else None)
		if not name:
			return {"rows": [], "cols": [], "empty": _("No bids recorded yet — enter the bids opened on the tender.")}
		d = frappe.get_doc("Tender", name)
		est = flt(d.estimated_value)
		rows = []
		for r in sorted(d.bidders, key=lambda r: cint(r.rank) or 99):
			vs1 = (flt(r.bid_amount) / flt(d.l1_amount) - 1) * 100 if flt(d.l1_amount) else 0
			rows.append({"cells": [{"main": r.bidder + (" " + _("(us)") if cint(r.is_us) else ""), "sub": r.remarks or ""}, {"money": r.bid_amount, "currency": cur},
				{"pill": f"L{cint(r.rank)}", "tone": "green" if cint(r.rank) == 1 else "blue" if cint(r.is_us) else "grey"}, {"main": _("L1") if cint(r.rank) == 1 else f"+{vs1:.1f}%"},
				{"main": f"{(flt(r.bid_amount) / est - 1) * 100:+.1f}%" if est else "—"}]})
		return {"title": _("Bids opened — {0} · {1} · estimate {2}").format(d.name, d.tender_name, CN.inr(est)), "cols": [{"label": _("Bidder")}, {"label": _("Bid"), "cls": "num"},
			{"label": _("Rank")}, {"label": _("vs L1")}, {"label": _("vs estimate")}], "rows": rows, "nototal": 1,
			"actions": [{"label": _("Edit bids"), "url": f"/app/tender/{d.name}"}]}
	fn.__name__ = base.__name__
	return fn


def extend(g):
	"""Wraps the BOQ and Tenders pages of module_cn (g = its globals)."""
	g["cn_boq_module"] = boq_module(g["cn_boq_module"])
	g["cn_boq_rows"] = g["_whole"](boq_rows(g["cn_boq_rows"]))
	g["cn_tnd_module"] = tnd_module(g["cn_tnd_module"])
	g["cn_tnd_rows"] = g["_whole"](tnd_rows(g["cn_tnd_rows"]))
