"""v1.9.1 stage B3: Site diary (DPR & Hindrances), Productivity (Labour & Workers), Diesel and Hire bills (Equipment),
Returnables and Scrap (Central Store), Advances, Issued material and Margin on scope (Subcontractors). Rules in
api/construction_ops.py."""

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, get_first_day, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_ops as OPS
from hipersign_trading.api.module import _perm, kpi

COLS = lambda *a: [{"label": x[0], "cls": "num"} if isinstance(x, tuple) else {"label": x} for x in a]


def _h():
	from hipersign_trading.api import module_cn as M

	return M


def _num(v, dp=1):
	return f"{flt(v):,.{dp}f}".rstrip("0").rstrip(".") if dp else f"{flt(v):,.0f}"


# ================================================================ DPR & Hindrances › Site diary
def site_module(base):
	def fn():
		m = base()
		M = _h()
		names = M._names(False)
		D = OPS.diaries(names, {"instruction_status": "To confirm in writing"})
		m["new"] = (m.get("new") or []) + [{"label": _("Site diary"), "doctype": "Site Diary"}]
		m["tabs"] = m["tabs"] + [{"key": "diary", "label": _("Site diary") + (f" ({len(D)})" if D else ""), "chips": [["all", _("Last 30 days")], ["instr", _("Instructions to confirm")]]
			+ [[n, n] for n in names]}]
		return m
	fn.__name__ = base.__name__
	return fn


def site_rows(base):
	def fn(tab, chip, q=None):
		if tab != "diary":
			return base(tab, chip, q)
		M = _h()
		names = M._names(False)
		chip = chip or "all"
		f = {"instruction_status": "To confirm in writing"} if chip == "instr" else {"diary_date": [">=", frappe.utils.add_days(today(), -30)]}
		if chip in names:
			f = {"project": chip}
		rows = []
		for d in OPS.diaries(names, f):
			if not M._q(q, d.project, d.instructions, d.events, d.visitors):
				continue
			st = d.instruction_status
			b = []
			if st == "To confirm in writing":
				b = [M._js(_("Confirmed…"), "cn_sd_confirm", d.name), M._js(_("Extra item…"), "cn_sd_ei", d.name), M._btn(_("No cost"), "sd_nocost", d.name)]
			old = st == "To confirm in writing" and (getdate(today()) - getdate(d.diary_date)).days > 7
			rows.append({"dt": "Site Diary", "name": d.name, "cells": [{"date": str(d.diary_date), "sub": f"{d.project} · {d.recorded_by or ''}"}, _(d.weather or ""),
				(d.visitors or "—")[:60], {"main": (d.instructions or "—")[:90], "sub": (_("by {0}").format(d.instruction_from) if d.instruction_from else "") +
				(f" · {d.extra_item}" if d.extra_item else ""), "late": 1 if old else 0},
				{"pill": _(st), "tone": {"To confirm in writing": "amber", "Confirmed in writing": "green", "Raised as extra item": "violet", "No cost effect": "grey"}.get(st, "grey")}
				if st != "None" else "—", (d.events or "—")[:70], {"buttons": b} if b else ""]})
		return {"title": _("Site diary — the legal day-book; verbal instructions recorded here are the evidence for variations and EOT"),
			"cols": COLS(_("Date"), _("Weather"), _("Visitors"), _("Instruction received"), _("Status"), _("Events"), ""), "rows": rows, "nototal": 1,
			"actions": [{"label": _("Diary entry"), "new": "Site Diary", "primary": 1}], "empty": _("No diary entries here.")}
	fn.__name__ = base.__name__
	return fn


# ================================================================ Labour & Workers › Productivity
def lab_module(base):
	def fn():
		m = base()
		m["tabs"] = m["tabs"] + [{"key": "prod", "label": _("Productivity"), "chips": [["30", _("Last 30 days")], ["7", _("Last 7 days")]]}]
		m["new"] = (m.get("new") or []) + [{"label": _("Productivity norm"), "doctype": "Productivity Norm"}]
		return m
	fn.__name__ = base.__name__
	return fn


def lab_rows(base):
	def fn(tab, chip, q=None):
		if tab != "prod":
			return base(tab, chip, q)
		M = _h()
		R = OPS.productivity(M._names(False), cint(chip or 30))
		rows = [{"cells": [M._pcell(r.project), r.trade, {"main": r.activity, "sub": _("{0} DPRs").format(r.reports)}, f"{_num(r.norm, 2)} {r.unit or ''}",
			f"{_num(r.actual, 2)} {r.unit or ''}", {"main": f"{_num(r.qty, 1)} {r.unit or ''}", "sub": _("{0:g} man-days").format(r.mandays)}, {"bar": min(130, round(r.pct)),
			"sub": f"{r.pct:.0f}%", "late": 1 if r.pct < 85 else 0}]} for r in R if M._q(q, r.project, r.trade, r.activity)]
		return {"title": _("Productivity against standard — DPR quantity ÷ man-days of the trade; the standards are the company norms (editable)"),
			"cols": COLS(_("Site"), _("Trade"), _("Activity"), (_("Standard / man-day"),), (_("Actual / man-day"),), (_("Done"),), _("vs standard")), "rows": rows, "nototal": 1,
			"actions": [{"label": _("Norms"), "route": ["List", "Productivity Norm"]}], "empty": _("No DPR with man-days for an activity that has a norm.")}
	fn.__name__ = base.__name__
	return fn


# ================================================================ Equipment › Diesel, Hire bills
def _hired():
	MS = _site()
	return [e for e in MS._eqs({"ownership": "Hired"})]


def _site():
	from hipersign_trading.api import module_cn_site as MS

	return MS


def eqp_module(base):
	def fn():
		m = base()
		MS = _site()
		cur = _h()._cur()
		last = add_months(get_first_day(today()), -1)
		H = [(e, OPS.hire_fig(frappe.get_doc("Construction Equipment", e.name), last)) for e in _hired()]
		tob = [(e, h) for e, h in H if h.logs and not h.invoice]
		over = [e for e in MS._eqs({"diesel_norm_lph": [">", 0]}) if OPS.diesel_fig(e).over]
		m["kpis"] = m["kpis"] + [kpi(_("Hire bills to book"), sum(h.amount for e, h in tob), _("{0} for {1}").format(len(tob), last.strftime("%B")), "orange" if tob else "green", "file-input",
			True, cur, tab="hire")]
		m["tabs"] = m["tabs"][:2] + [{"key": "dsl", "label": _("Diesel") + (f" ({len(over)})" if over else ""), "chips": [["month", _("This month")], ["last", _("Last month")]]},
			{"key": "hire", "label": _("Hire bills") + (f" ({len(tob)})" if tob else ""), "chips": [["last", last.strftime("%b %Y")], ["month", _("This month so far")]]}] + m["tabs"][2:]
		return m
	fn.__name__ = base.__name__
	return fn


def eqp_rows(base):
	def fn(tab, chip, q=None):
		if tab not in ("dsl", "hire"):
			return base(tab, chip, q)
		M, MS = _h(), _site()
		cur = M._cur()
		this = get_first_day(today())
		mon = add_months(this, -1) if chip == "last" or (tab == "hire" and chip in (None, "")) else this
		if tab == "dsl":
			a, b = (mon, OPS.month_range(mon)[1]) if mon != this else (this, today())
			rows = []
			for e in MS._eqs({"diesel_norm_lph": [">", 0]}):
				if not M._q(q, e.equipment_name, e.project):
					continue
				D = OPS.diesel_fig(e, a, b)
				rows.append({"dt": "Construction Equipment", "name": e.name, "cells": [{"main": e.equipment_name, "sub": _(e.ownership)}, M._pcell(e.project) if e.project else "—",
					_num(D.hours), _num(D.diesel, 0), {"main": f"{D.rate:.1f}", "late": 1 if D.over else 0}, f"{D.norm:g}",
					{"main": _num(D.excess, 0) if D.excess > .5 else "—", "late": 1 if D.over else 0}, {"money": D.value if D.over else 0, "currency": cur}]})
			return {"title": _("Diesel against the norm — {0}: issued litres ÷ logbook hours; more than 10% over the norm is flagged for checking (diesel at ₹{1}/L)").format(
				a.strftime("%B %Y"), OPS.DIESEL_RATE), "cols": COLS(_("Equipment"), _("Site"), (_("Hours"),), (_("Diesel (L)"),), (_("Actual L/h"),), (_("Norm L/h"),),
				(_("Excess (L)"),), (_("Excess value"),)), "rows": rows, "empty": _("No machine with a diesel norm.")}
		rows = []
		for e in _hired():
			if not M._q(q, e.equipment_name, e.project, e.supplier):
				continue
			ed = frappe.get_doc("Construction Equipment", e.name)
			H = OPS.hire_fig(ed, mon)
			if not H.logs and not H.invoice:
				continue
			unit = {"Hour": "h", "Day": _("days"), "Month": _("month")}[H.basis]
			b = H.invoice and {"pill": _("Booked"), "tone": "green", "sub": H.invoice} or (
				{"buttons": [M._btn(_("Book bill"), "eq_hire_book", e.name, True, args={"month": str(mon)})]} if mon < this else {"pill": _("Month running"), "tone": "grey"})
			rows.append({"dt": "Construction Equipment", "name": e.name, "cells": [{"main": e.equipment_name, "sub": e.reg_no or ""}, {"main": e.supplier, "sub": e.project or ""},
				{"main": f"{_num(H.hours)} h" if H.basis == "Hour" else f"{H.days} {_('days')}", "sub": _("min {0:g} h").format(H.min) if H.min else ""},
				{"main": f"{_num(H.billable)} {unit}", "late": 1 if H.short else 0, "sub": _("{0:g} h below the minimum").format(H.short) if H.short else ""},
				{"money": H.rate, "currency": cur, "dp": 0}, {"money": H.amount, "currency": cur}, b]})
		return {"title": _("Hire bills — {0}: hours from the logbook (at least the minimum in the hire terms) × rate; booking makes the purchase invoice with GST 18% and TDS 194I 2%").format(
			mon.strftime("%B %Y")), "cols": COLS(_("Equipment"), _("Hirer · site"), (_("Logbook"),), (_("Billable"),), (_("Rate"),), (_("Amount excl. GST"),), ""), "rows": rows,
			"empty": _("No hired machine worked in {0}.").format(mon.strftime("%B %Y"))}
	fn.__name__ = base.__name__
	return fn


# ================================================================ Central Store › Returnables, Scrap
def _lots(f=None):
	if not _perm("Scrap Lot"):
		return []
	co = _site()._co()
	return frappe.get_list("Scrap Lot", filters=dict({"company": co} if co else {}, **(f or {})), fields=["name", "project", "lot_date", "description", "hazardous", "qty", "uom",
		"estimate", "status", "buyer", "sale_amount", "sold_on", "sales_invoice"], order_by="lot_date desc", limit_page_length=0)


def store_module(base):
	def fn():
		m = base()
		M = _h()
		cur = M._cur()
		L = _lots({"status": ["in", ["Identified", "Bids invited"]]})
		R = OPS.returnables(M._names(False))
		m["new"] = (m.get("new") or []) + [{"label": _("Scrap lot"), "doctype": "Scrap Lot"}]
		m["kpis"] = m["kpis"] + [kpi(_("Returnables at sites"), sum(r.value for r in R), _("hire {0} a month while out").format(CN.inr(sum(r.per_month for r in R))), "violet", "layers",
			True, cur, tab="ret")]
		k = m["kpis"][3]
		k["sub"] = (k.get("sub") or "") + " · " + _("scrap to sell {0}").format(CN.inr(sum(flt(x.estimate) for x in L)))
		m["tabs"] = m["tabs"] + [{"key": "ret", "label": _("Returnables at sites"), "chips": []},
			{"key": "scrap", "label": _("Scrap") + (f" ({len(L)})" if L else ""), "chips": [["open", _("To sell")], ["Sold", _("Sold")], ["all", _("All")]]}]
		return m
	fn.__name__ = base.__name__
	return fn


def store_rows(base):
	def fn(tab, chip, q=None):
		if tab not in ("ret", "scrap"):
			return base(tab, chip, q)
		M = _h()
		cur = M._cur()
		if tab == "ret":
			rows = []
			for r in OPS.returnables(M._names(False)):
				if not M._q(q, r.project, r.item_name):
					continue
				b = [M._js(_("Return to store…"), "cn_ret_back", f"{r.project}|{r.item}")] if r.qty - r.returning > 0 else []
				rows.append({"cells": [M._pcell(r.project), {"main": r.item_name, "sub": r.item}, {"main": f"{_num(r.qty, 2)} {r.uom}", "sub": _("{0:g} on a return request").format(r.returning)
					if r.returning else ""}, {"date": str(r.since) if r.since else None, "sub": _("{0:.1f} months").format(r.months)}, {"money": r.value, "currency": cur},
					{"money": r.per_month, "currency": cur}, {"money": r.charged, "currency": cur}, {"buttons": b} if b else ""]})
			return {"title": _("Returnable items at sites — props, scaffolding and plywood out of the central store, charged to the site at {0}% a month of value until returned").format(OPS.RET_HIRE),
				"cols": COLS(_("Site"), _("Item"), (_("At site"),), _("Since"), (_("Value"),), (_("Hire / month"),), (_("Charged so far"),), ""), "rows": rows,
				"empty": _("No returnable items at the sites (mark items as returnable on the item).")}
		chip = chip or "open"
		f = {"status": ["in", ["Identified", "Bids invited"]]} if chip == "open" else {"status": "Sold"} if chip == "Sold" else {}
		rows = []
		for x in _lots(f):
			if not M._q(q, x.description, x.project, x.buyer):
				continue
			bids = frappe.get_all("Scrap Bid", filters={"parent": x.name, "parenttype": "Scrap Lot"}, fields=["bidder", "amount", "pcb_authorised"], order_by="amount desc")
			if x.status == "Identified":
				st = {"buttons": [M._btn(_("Invite bids"), "scrap_invite", x.name)]}
			elif x.status == "Bids invited":
				st = {"buttons": [M._btn(_("Sell to H1"), "scrap_sell", x.name, True, confirm=_("Sell {0} to the highest bidder with GST 18% and TCS 1%?").format(x.name))]} if bids \
					else {"pill": _("Waiting for bids"), "tone": "amber"}
			else:
				st = {"pill": _(x.status), "tone": "green" if x.status == "Sold" else "grey", "sub": x.buyer or ""}
			rows.append({"dt": "Scrap Lot", "name": x.name, "cells": [{"main": x.description, "sub": f"{x.name} · {x.project or _('Central store')}", "late": 0},
				{"pill": _("Hazardous"), "tone": "red"} if cint(x.hazardous) else "", f"{_num(x.qty, 2)} {x.uom or ''}", {"money": x.estimate, "currency": cur},
				{"lines": [f"{b.bidder} · {CN.inr(b.amount)}" + (" · PCB" if cint(b.pcb_authorised) else "") for b in bids[:3]] or ["—"]},
				{"money": x.sale_amount, "currency": cur, "sub": _("GST {0} · TCS {1}").format(CN.inr(flt(x.sale_amount) * .18), CN.inr(flt(x.sale_amount) * 1.18 * .01)) if flt(x.sale_amount) else ""},
				st]})
		return {"title": _("Scrap — sealed bids, sold to the highest bidder; a taxable supply at GST 18% with TCS 1% under section 206C(1)"),
			"cols": COLS(_("Lot"), "", (_("Quantity"),), (_("Estimate"),), _("Bids"), (_("Sale (excl. GST)"),), _("Status")), "rows": rows,
			"actions": [{"label": _("New scrap lot"), "new": "Scrap Lot", "primary": 1}], "empty": _("No scrap lots here.")}
	fn.__name__ = base.__name__
	return fn


# ================================================================ Subcontractors › Advances, Issued material, Margin
def sub_module(base):
	def fn():
		m = base()
		m["tabs"] = m["tabs"][:3] + [{"key": "sadv", "label": _("Advances"), "chips": []}, {"key": "iss", "label": _("Issued material"), "chips": []},
			{"key": "mar", "label": _("Margin on scope"), "chips": []}] + m["tabs"][3:]
		return m
	fn.__name__ = base.__name__
	return fn


def sub_rows(base):
	def fn(tab, chip, q=None):
		if tab not in ("sadv", "iss", "mar"):
			return base(tab, chip, q)
		M, MS = _h(), _site()
		cur = M._cur()
		W = MS._wos({"status": ["in", ["Active", "Completed", "Closed"]]})
		if tab == "sadv":
			rows = []
			for w in W:
				if not flt(w.advance) or not M._q(q, w.name, w.supplier, w.scope):
					continue
				wd = frappe.db.get_value("Subcontractor Work Order", w.name, ["advance_paid_on", "advance_recovery_pct"], as_dict=True)
				A = OPS.sub_adv(w.name)
				due = flt(w.advance) - A.paid
				b = [M._js(_("Pay advance…"), "cn_swo_adv_pay", w.name)] if due > 1 and w.status == "Active" else []
				rows.append({"dt": "Subcontractor Work Order", "name": w.name, "cells": [{"main": w.supplier, "sub": f"{w.name} · {w.project}"}, {"money": w.advance, "currency": cur},
					{"money": A.paid, "currency": cur, "sub": frappe.format(wd.advance_paid_on, {"fieldtype": "Date"}) if wd.advance_paid_on else _("not paid")},
					f"{flt(wd.advance_recovery_pct):g}%", {"money": A.recovered, "currency": cur}, {"money": A.balance, "currency": cur, "late": 0},
					{"main": ", ".join(_("bill {0}").format(x.bill_no) for x in A.bills) or "—"}, {"buttons": b} if b else
					({"pill": _("Fully recovered"), "tone": "green"} if A.paid and not A.balance else "")]})
			return {"title": _("Mobilisation advances to subcontractors — paid against their BG or undertaking, recovered from every running bill until nil"),
				"cols": COLS(_("Subcontractor"), (_("Agreed"),), (_("Paid"),), _("Recovery"), (_("Recovered"),), (_("Balance"),), _("Recovered in"), ""), "rows": rows,
				"empty": _("No work order with an advance (set the advance on the work order).")}
		if tab == "iss":
			rows = []
			for w in W:
				if not (w.kind or "").startswith("Labour") or not M._q(q, w.name, w.supplier):
					continue
				X = OPS.free_issue(w.name)
				rec = flt(frappe.db.sql("select sum(material_recovery) from `tabSubcontractor Bill` where work_order = %s and status != 'Cancelled'", w.name)[0][0])
				for i, x in enumerate(X):
					rows.append({"dt": "Subcontractor Work Order", "name": w.name, "cells": [{"main": w.supplier.split(" (")[0], "sub": w.name} if not i else "",
						{"main": x.item_name, "sub": x.uom}, {"main": _num(x.issued, 2), "sub": _("{0} returned").format(_num(x.returned, 2)) if x.returned else ""},
						{"main": _num(x.allowed, 2), "sub": _("theory {0}").format(_num(x.theory, 2))},
						{"main": _num(x.excess, 2) if x.excess > .005 else "—", "late": 1 if x.excess > .005 else 0},
						{"money": x.recover, "currency": cur, "sub": _("{0:g}× rate").format(x.factor) if x.recover else ""},
						({"buttons": [M._btn(_("Recover on draft bill"), "swo_matrec", w.name)], "sub": _("{0} recovered so far").format(CN.inr(rec))}
							if sum(y.recover for y in X) > rec + 1 else {"main": _("{0} recovered").format(CN.inr(rec))}) if i == len(X) - 1 else ""]})
			return {"title": _("Free-issue material — cement and steel issued to labour-only subcontractors; beyond the theoretical for the work billed plus wastage is recovered from their bill"),
				"cols": COLS(_("Work order"), _("Material"), (_("Issued"),), (_("Allowed for work billed"),), (_("Excess"),),
				(_("To recover"),), ""), "rows": rows, "nototal": 1, "empty": _("No material issued to a labour-only work order (tick the work order on the material issue).")}
		rows = []
		for w in W:
			if not M._q(q, w.name, w.supplier, w.scope):
				continue
			X = OPS.margin(w.name)
			if not X:
				continue
			ours = sum(x.ours * x.qty for x in X)
			val = sum(x.value for x in X)
			rows.append({"dt": "Subcontractor Work Order", "name": w.name, "cells": [{"main": w.scope, "sub": f"{w.name} · {w.supplier}"}, M._pcell(w.project),
				{"pill": _("Labour only") if (w.kind or "").startswith("Labour") else _("Item rate"), "tone": "blue"}, {"money": ours, "currency": cur}, {"money": w.value, "currency": cur},
				{"money": val, "currency": cur, "neg": 1 if val < 0 else 0}, {"bar": max(0, round(val / ours * 100)) if ours else 0, "sub": f"{val / ours * 100:.1f}%" if ours else "",
				"late": 1 if ours and val / ours < .05 else 0}, {"lines": [f"{x.item_no}: {x.margin:.1f}%" for x in X[:3]]}]})
		return {"title": _("Margin on subcontracted scope — our BOQ rate (its labour share for labour-only work) against the subcontract rate"),
			"cols": COLS(_("Scope"), _("Project"), _("Kind"), (_("Our BOQ value"),), (_("Work order"),), (_("Margin"),), _("Margin %"), _("By line")), "rows": rows,
			"empty": _("No work orders.")}
	fn.__name__ = base.__name__
	return fn


def extend(g):
	for k, mod, rows in (("cn_site", site_module, site_rows), ("cn_lab", lab_module, lab_rows), ("cn_eqp", eqp_module, eqp_rows), ("cn_store", store_module, store_rows),
			("cn_sub", sub_module, sub_rows)):
		g[k + "_module"] = mod(g[k + "_module"])
		g[k + "_rows"] = g["_whole"](rows(g[k + "_rows"]))
