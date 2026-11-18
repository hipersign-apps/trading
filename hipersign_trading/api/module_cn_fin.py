"""v1.9.0 stage A5 (prototype C8): the Construction (India) finance pages — Accounts & Cash, GST & TDS, Cost Control and
Payroll & Statutory — on the module page renderer. Rules in api/construction_fin.py."""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, get_first_day, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_fin as FN
from hipersign_trading.api import projects as P
from hipersign_trading.api.module import _perm, _scope, kpi
from hipersign_trading.api.module_cn import _btn, _cur, _date, _js, _m, _names, _pcell, _proj, _q

KEYS = ("cn_acc", "cn_tax", "cn_evm", "cn_pay")
BUCKETS = ["Not due", "1–30", "31–60", "61–90", "Over 90"]


def _co():
	cos = [c for c in (_scope()[0] or []) if c in FN.companies()]
	return cos[0] if cos else (FN.companies() or [None])[0]


def _month(chip):
	t = getdate(today())
	return get_first_day(add_months(t, -cint(chip or 1)))


# ================================================================ Accounts & Cash
def cn_acc_module():
	co = _co()
	cur = _cur()
	R, t = FN.receivables(co) if co else ([], getdate(today()))
	Pa = FN.payables(co) if co else []
	msme = [p for p in Pa if p.hs_msme_category in ("Micro", "Small") and date_diff(t, p.posting_date) > 45]
	wk = FN.cash_forecast(co) if co else []
	low = min((w.closing for w in wk), default=0)
	names = _names()
	rev = sum(_gl_rev(n) for n in names)
	cost = sum(CN.fig(n).cost for n in names)
	return {
		"title": _("Accounts & Cash"),
		"desc": _("The construction view of the books — project P&L from the ledger, money owed by clients and to suppliers, MSME payments, an eight-week cash forecast from the documents and the statements."),
		"new": [{"label": _("Journal entry"), "doctype": "Journal Entry", "primary": 1}],
		"kpis": [
			kpi(_("Bank"), wk[0].opening if wk else 0, _("lowest in 8 weeks {0}").format(_m(low, cur)), "navy", "landmark", True, cur, tab="cash"),
			kpi(_("Receivables"), sum(flt(r.outstanding_amount) for r in R), _("{0} overdue").format(_m(sum(flt(r.outstanding_amount) for r in R if r.due_date and getdate(r.due_date) < t), cur)),
				"blue", "banknote", True, cur, tab="ar"),
			kpi(_("Payables"), sum(flt(p.outstanding_amount) for p in Pa), _("{0} to MSME past 45 days").format(_m(sum(flt(p.outstanding_amount) for p in msme), cur)),
				"red" if msme else "orange", "receipt", True, cur, tab="ap"),
			kpi(_("Gross margin (projects)"), f"{(rev - cost) / rev * 100:.1f}%" if rev else "—", _("revenue {0} · cost {1}").format(_m(rev, cur), _m(cost, cur)), "green", "chart-line", tab="pl"),
		],
		"tabs": [
			{"key": "pl", "label": _("Project P&L"), "chips": []},
			{"key": "cash", "label": _("Cash forecast"), "chips": []},
			{"key": "ar", "label": _("Receivables ageing"), "chips": []},
			{"key": "ap", "label": _("Payables ageing"), "chips": [["all", _("All")], ["msme", _("MSME")]]},
			{"key": "rep", "label": _("Statements & matrix"), "chips": []},
		],
	}


def _gl_rev(project):
	return flt(frappe.db.sql("""select sum(credit - debit) from `tabGL Entry` where is_cancelled = 0 and project = %s and account in
		(select name from `tabAccount` where root_type = 'Income')""", project)[0][0])


def cn_acc_rows(tab, chip, q=None):
	co = _co()
	cur = _cur()
	t = getdate(today())
	if tab == "cash":
		rows = []
		for i, w in enumerate(FN.cash_forecast(co) if co else []):
			ins = {}
			for what, amt, inflow in w.lines:
				ins[(what, inflow)] = ins.get((what, inflow), 0) + amt
			rows.append({"cells": [{"main": _("Week {0}").format(i + 1), "sub": frappe.format(w.start, {"fieldtype": "Date"})}, {"money": w.opening, "currency": cur},
				{"money": w.inflow, "currency": cur, "sub": "; ".join(f"{k[0]}" for k in ins if k[1])[:60]}, {"money": w.outflow, "currency": cur, "sub": "; ".join(f"{k[0]}" for k in ins if not k[1])[:60]},
				{"money": w.closing, "currency": cur, "neg": 1 if w.closing < 0 else 0}]})
		return {"title": _("Cash forecast — eight weeks from the documents"), "cols": [{"label": _("Week")}, {"label": _("Opening"), "cls": "num"}, {"label": _("Receipts"), "cls": "num"},
			{"label": _("Payments"), "cls": "num"}, {"label": _("Closing"), "cls": "num"}], "rows": rows, "nototal": 1, "empty": _("No construction company.")}
	if tab in ("ar", "ap"):
		data = (FN.receivables(co)[0] if tab == "ar" else FN.payables(co)) if co else []
		by = {}
		for r in data:
			party = r.get("customer") or r.get("supplier")
			if tab == "ap" and chip == "msme" and r.get("hs_msme_category") in (None, "", "Not MSME"):
				continue
			x = by.setdefault(party, [0.0] * 5 + [r.get("hs_msme_category"), 0.0])
			b = FN.bucket(date_diff(t, r.due_date) if r.due_date else 0)
			x[b] += flt(r.outstanding_amount)
			if tab == "ap" and r.get("hs_msme_category") in ("Micro", "Small") and date_diff(t, r.posting_date) > 45:
				x[6] += flt(r.outstanding_amount)
		rows = []
		for party, x in sorted(by.items(), key=lambda z: -sum(z[1][:5])):
			if not _q(q, party):
				continue
			cells = [{"main": party, "sub": (_(x[5]) if x[5] and x[5] != "Not MSME" else "")}] + [{"money": v, "currency": cur, "neg": 1 if i >= 3 and v else 0} for i, v in enumerate(x[:5])] + \
				[{"money": sum(x[:5]), "currency": cur}]
			if tab == "ap":
				cells.append({"money": x[6], "currency": cur, "neg": 1 if x[6] else 0} if x[6] else "—")
			rows.append({"dt": "Customer" if tab == "ar" else "Supplier", "name": party, "cells": cells})
		cols = [{"label": _("Client") if tab == "ar" else _("Supplier")}] + [{"label": _(b), "cls": "num"} for b in BUCKETS] + [{"label": _("Total"), "cls": "num"}]
		if tab == "ap":
			cols.append({"label": _("MSME > 45 days"), "cls": "num"})
		return {"title": _("Receivables ageing — days past due") if tab == "ar" else _("Payables ageing — MSME bills unpaid after 45 days lose the deduction (sec. 43B(h))"),
			"cols": cols, "rows": rows, "empty": _("Nothing outstanding.")}
	if tab == "rep":
		L = FN.limits()
		from hipersign_trading.api import construction_biz as B
		from hipersign_trading.api import construction_site as S

		BL = B.limits()
		lines = [(_("Trial Balance"), "query-report/Trial Balance"), (_("Profit and Loss Statement"), "query-report/Profit and Loss Statement"),
			(_("Balance Sheet"), "query-report/Balance Sheet"), (_("General Ledger"), "query-report/General Ledger"), (_("Accounts Receivable"), "query-report/Accounts Receivable"),
			(_("Accounts Payable"), "query-report/Accounts Payable"), (_("Bank Reconciliation"), "bank-reconciliation-tool"), (_("GST Sales Register"), "query-report/GST Sales Register"),
			(_("GSTR-3B Details"), "query-report/GSTR-3B Details"), (_("HSN-wise summary of outward supplies"), "query-report/HSN-wise-summary of outward supplies"),
			(_("TDS Computation Summary"), "query-report/TDS Computation Summary"), (_("Project-wise profitability"), "query-report/Project Profitability")]
		rows = [{"cells": [_("Statement"), name, {"url": f"/app/{route}", "label": _("Open")}]} for name, route in lines]
		matrix = [(_("Quotation discount — MD above"), f"{BL.disc:g}%"), (_("Quotation margin — MD below"), f"{BL.margin:g}%"), (_("Manual journal — MD above"), CN.inr(L.jv_md)),
			(_("Worker advance — PM above"), CN.inr(S.limits().wadv)), (_("Project late (LD flag) after"), _("{0} days").format(BL.ld_days)),
			(_("Purchase orders"), _("Hipersign Purchase Order Approval workflow")), (_("Indents above the BOQ need"), _("Project Manager / MD")),
			(_("Permits to work"), _("Safety Officer")), (_("RA bill certification · tax invoice · receipt"), _("QS / PM · Accounts"))]
		rows += [{"cells": [_("Approval"), a, b]} for a, b in matrix]
		return {"title": _("Statements and the approval matrix (limits in Hipersign Settings)"), "cols": [{"label": _("Kind")}, {"label": _("What")}, {"label": ""}], "rows": rows, "nototal": 1}
	rows = []
	for n in _names():
		F = CN.fig(n)
		if not F.cost and not F.billed:
			continue
		rev = _gl_rev(n)
		c = P.cost_of(n) if CN.boq(n) else None
		h = (c.H if c else {})
		gp = rev - F.cost
		rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), {"money": rev, "currency": cur}] + [{"money": flt(h[k].actual) if k in h else 0, "currency": cur} for k in P.HEADS] +
			[{"money": F.cost, "currency": cur}, {"money": gp, "currency": cur, "neg": 1 if gp < 0 else 0, "sub": f"{gp / rev * 100:.1f}%" if rev else ""}]})
	return {"title": _("Project P&L from the ledger — revenue booked (invoiced) against cost by head"), "cols": [{"label": _("Project")}, {"label": _("Revenue"), "cls": "num"}] +
		[{"label": _(h), "cls": "num"} for h in P.HEADS] + [{"label": _("Total cost"), "cls": "num"}, {"label": _("Gross profit"), "cls": "num"}], "rows": rows, "empty": _("Nothing booked yet.")}


# ================================================================ GST & TDS
def cn_tax_module():
	co = _co()
	cur = _cur()
	cal = FN.calendar_items(co) if co else []
	od = [x for x in cal if x.state == "Overdue"]
	m = _month(1)
	g = FN.gst_month(co, m) if co else {}
	names = _names()
	R = frappe.get_list("RA Bill", filters={"project": ["in", names or [""]], "status": ["in", ["Part paid", "Paid"]]}, fields=["tds", "tds_in_26as", "gst_tds", "gst_tds_ok"],
		limit_page_length=0) if _perm("RA Bill") else []
	cess = sum(FN.cess_due(n).due for n in names if CN.fig(n).step >= 10)
	return {
		"title": _("GST & TDS"),
		"desc": _("GST by registration and month with its payment, TDS both ways — deducted by clients (Form 26AS) and from subcontractors and salaries — GST-TDS, BOCW labour cess and the compliance calendar. Returns and e-invoices are filed through India Compliance."),
		"new": [{"label": _("Statutory payment"), "doctype": "Statutory Deposit", "primary": 1}],
		"kpis": [
			kpi(_("GST to pay — {0}").format(frappe.utils.formatdate(m, "MMM")), sum(x.cash for x in g.values()), _("{0} GSTINs · ITC {1}").format(len(g), _m(sum(x.inp for x in g.values()), cur)),
				"navy", "percent", True, cur, tab="gst"),
			kpi(_("Due or overdue"), len([x for x in cal if x.state not in ("Paid", "Filed")]), _("{0} overdue").format(len(od)), "red" if od else "orange", "calendar-clock", tab="cal"),
			kpi(_("TDS not in 26AS"), sum(flt(r.tds) for r in R if not cint(r.tds_in_26as)), _("deducted by clients"), "orange", "receipt-indian-rupee", True, cur, tab="tds"),
			kpi(_("BOCW cess to pay"), cess, _("private work — 1% of cost"), "amber", "hard-hat", True, cur, tab="cess"),
		],
		"tabs": [
			{"key": "cal", "label": _("Compliance calendar"), "chips": [["open", _("Due & overdue")], ["all", _("All")]]},
			{"key": "gst", "label": _("GST by GSTIN"), "chips": [["1", _("Last month")], ["0", _("This month")], ["2", _("Two months ago")]]},
			{"key": "tds", "label": _("TDS both ways"), "chips": []},
			{"key": "cess", "label": _("BOCW cess"), "chips": []},
			{"key": "einv", "label": _("E-invoices"), "chips": [["1", _("Last month")], ["0", _("This month")]]},
		],
	}


def cn_tax_rows(tab, chip, q=None):
	co = _co()
	cur = _cur()
	if tab == "gst":
		m = _month(chip or "1")
		rows = []
		for gstin, x in sorted((FN.gst_month(co, m) if co else {}).items()):
			addr = frappe.db.get_value("Address", {"gstin": gstin, "is_your_company_address": 1}, "address_title") if gstin != "—" else ""
			rows.append({"cells": [{"main": gstin, "sub": (addr or "").split(" — ")[-1]}, frappe.utils.formatdate(m, "MMM yyyy"), {"money": x.out, "currency": cur}, {"money": x.inp, "currency": cur, "sub": _("+ {0} carried in").format(_m(x.carried_in, cur)) if x.carried_in else ""},
				{"money": x.cash, "currency": cur}, {"money": x.carry, "currency": cur} if x.carry else "—",
				{"pill": _("Paid") if x.paid else _("Due"), "tone": "green" if x.paid else "orange", "sub": frappe.format(FN.due_date("GST", m), {"fieldtype": "Date"})},
				{"buttons": [_js(_("Pay…"), "cn_gst_pay", f"{gstin}|{m}")]} if not x.paid and (x.out or x.inp) else ""]})
		return {"title": _("GST by registration — output tax, input tax credit and cash to pay (RCM separate)"), "cols": [{"label": _("GSTIN")}, {"label": _("Month")},
			{"label": _("Output tax"), "cls": "num"}, {"label": _("ITC"), "cls": "num"}, {"label": _("Cash"), "cls": "num"}, {"label": _("ITC carried"), "cls": "num"}, {"label": _("Status")},
			{"label": ""}], "rows": rows, "empty": _("No GST in this month.")}
	if tab == "tds":
		names = _names()
		rows = []
		for n in names:
			R = frappe.get_all("RA Bill", filters={"project": n, "status": ["in", ["Part paid", "Paid"]]}, fields=["tds", "tds_in_26as", "gst_tds", "gst_tds_ok"])
			if not R:
				continue
			rows.append({"dt": "Project", "name": n, "cells": [_("Deducted by the client"), _pcell(n), {"money": sum(flt(r.tds) for r in R), "currency": cur},
				{"money": sum(flt(r.tds) for r in R if not cint(r.tds_in_26as)), "currency": cur, "sub": _("not in 26AS")},
				{"money": sum(flt(r.gst_tds) for r in R), "currency": cur, "sub": _("GST-TDS")}]})
		for kind in ("TDS 194C (contractors)", "TDS 192 (salaries)"):
			for k in (2, 1, 0):
				m = get_first_day(add_months(today(), -k))
				amt = FN.liability_for(co, m, kind) if co else 0
				if not amt:
					continue
				paid = frappe.db.get_value("Statutory Deposit", {"kind": kind, "month": m, "company": co, "status": "Paid"}, ["name", "challan_no"], as_dict=True)
				rows.append({"cells": [_("We deducted — {0}").format(kind.split(" ")[1]), frappe.utils.formatdate(m, "MMM yyyy"), {"money": amt, "currency": cur},
					{"pill": _("Deposited") if paid else _("Due {0}").format(frappe.format(FN.due_date(kind, m), {"fieldtype": "Date"})), "tone": "green" if paid else "orange", "sub": (paid or {}).get("challan_no") or ""},
					{"buttons": [_js(_("Deposit…"), "cn_dep_pay", f"{kind}|{m}|{amt}")]} if not paid and k else ""]})
		return {"title": _("TDS — what clients deducted from us (claim it from Form 26AS) and what we deducted (deposit by the 7th, file 26Q / 24Q)"),
			"cols": [{"label": _("Side")}, {"label": _("Project / month")}, {"label": _("TDS"), "cls": "num"}, {"label": _("Status"), "cls": "num"}, {"label": ""}], "rows": rows, "nototal": 1,
			"empty": _("No TDS yet.")}
	if tab == "cess":
		rows = []
		for n in _names():
			if CN.fig(n).step < 10:
				continue
			c = FN.cess_due(n)
			st = BR = frappe.db.get_value("Address", _proj(n).get("hs_cn_address"), "state") if _proj(n).get("hs_cn_address") else ""
			rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), st or "—", _(c.mode), {"money": c.base, "currency": cur, "sub": _("billed") if c.mode.startswith("Deducted") else _("cost to date")},
				{"money": c.paid, "currency": cur}, {"money": c.due, "currency": cur, "neg": 1 if c.due > 1 else 0},
				{"buttons": [_js(_("Pay to board…"), "cn_cess_pay", f"{n}|{round(c.due)}")]} if c.due > 1 else ""]})
		return {"title": _("BOCW labour cess — 1% of the cost of construction"), "cols": [{"label": _("Project")}, {"label": _("State")}, {"label": _("How")}, {"label": _("Base"), "cls": "num"},
			{"label": _("Paid / deducted"), "cls": "num"}, {"label": _("To pay"), "cls": "num"}, {"label": ""}], "rows": rows, "empty": _("No sites at work.")}
	if tab == "einv":
		m = _month(chip or "1")
		end = add_months(m, 1)
		rows = []
		for s in frappe.get_list("Sales Invoice", filters={"company": co, "docstatus": 1, "posting_date": ["between", [m, add_days(end, -1)]]},
				fields=["name", "customer", "posting_date", "base_grand_total", "company_gstin", "billing_address_gstin", "irn", "einvoice_status", "project"], order_by="posting_date desc",
				limit_page_length=0) if co and _perm("Sales Invoice") else []:
			if not _q(q, s.name, s.customer, s.project):
				continue
			late = not s.irn and s.einvoice_status != "Not Applicable" and date_diff(today(), s.posting_date) > 30
			rows.append({"dt": "Sales Invoice", "name": s.name, "cells": [{"main": s.name, "sub": frappe.format(s.posting_date, {"fieldtype": "Date"})}, {"main": s.customer, "sub": s.billing_address_gstin or ""},
				s.company_gstin or "—", {"money": s.base_grand_total, "currency": cur}, {"pill": _(s.einvoice_status or ("Generated" if s.irn else "Pending")),
					"tone": "green" if s.irn else "grey" if s.einvoice_status == "Not Applicable" else "red" if late else "orange", "sub": _("past the 30-day limit") if late else (s.irn or "")[:18]}]})
		return {"title": _("E-invoices — IRN from India Compliance (within 30 days of the invoice; cancel within 24 hours)"), "cols": [{"label": _("Invoice")}, {"label": _("Client")},
			{"label": _("Our GSTIN")}, {"label": _("Value"), "cls": "num"}, {"label": _("IRN")}], "rows": rows, "empty": _("No invoices in this month.")}
	cal = FN.calendar_items(co) if co else []
	rows = []
	for x in sorted(cal, key=lambda z: (z.state in ("Paid", "Filed"), z.due)):
		if (chip or "open") == "open" and x.state in ("Paid", "Filed"):
			continue
		code = "|".join([x.kind, str(x.month), x.ref if x.kind in ("GST", "GSTR-1") else str(round(x.amount))])
		b = ""
		if x.state != "Paid" and x.kind == "GST":
			b = {"buttons": [_js(_("Pay…"), "cn_gst_pay", f"{x.ref}|{x.month}")]}
		elif x.state == "Paid" or x.state == "Filed":
			b = ""
		elif x.kind == "GSTR-1":
			b = {"url": "/app/gstr-1", "label": _("File")}
		elif x.kind != "GSTR-1":
			b = {"buttons": [_js(_("Pay…"), "cn_dep_pay", f"{x.kind}|{x.month}|{round(x.amount)}")]}
		rows.append({"cells": [{"main": _(x.label), "sub": x.ref or ""}, frappe.utils.formatdate(x.month, "MMM yyyy"), _date(x.due, x.state == "Overdue"), {"money": x.amount, "currency": cur},
			{"pill": _(x.state), "tone": {"Paid": "green", "Filed": "green", "Overdue": "red"}.get(x.state, "orange")}, b]})
	return {"title": _("Compliance calendar — GST 11th / 20th, TDS 7th, PF & ESI 15th, professional tax"), "cols": [{"label": _("Return / payment")}, {"label": _("For")}, {"label": _("Due")},
		{"label": _("Amount"), "cls": "num"}, {"label": _("Status")}, {"label": ""}], "rows": rows, "nototal": 1, "empty": _("Nothing due.")}


# ================================================================ Cost Control
def cn_evm_module():
	names = [n for n in _names(False) if 10 <= CN.fig(n).step < 22]
	cur = _cur()
	X = {n: FN.evm(n) for n in names}
	bad = [n for n, x in X.items() if x.ac and x.cpi < .92]
	return {
		"title": _("Cost Control"),
		"desc": _("Earned value for every live project — budget at completion, planned and earned value, actual cost, CPI and SPI, the forecast at completion — and the cost heads with budget, committed, actual and forecast."),
		"kpis": [
			kpi(_("Budget at completion"), sum(x.bac for x in X.values()), _("{0} live projects").format(len(X)), "navy", "calculator", True, cur, tab="evm"),
			kpi(_("Earned value"), sum(x.ev for x in X.values()), _("actual cost {0}").format(_m(sum(x.ac for x in X.values()), cur)), "blue", "chart-line", True, cur, tab="evm"),
			kpi(_("Portfolio CPI"), f"{sum(x.ev for x in X.values()) / sum(x.ac for x in X.values()):.2f}" if sum(x.ac for x in X.values()) else "—",
				_("{0} projects below 0.92").format(len(bad)), "red" if bad else "green", "gauge", tab="evm"),
			kpi(_("Forecast overrun"), -sum(min(0, x.vac) for x in X.values()), _("EAC − BAC where over budget"), "amber", "triangle-alert", True, cur, tab="heads"),
		],
		"cards": [{"title": _("CPI by project"), "sub": _("earned ÷ actual — below 1 means over cost"), "type": "bars", "rows": [[_proj(n).project_name.split(" — ")[0], round(X[n].cpi, 2)] for n in names]}],
		"tabs": [
			{"key": "evm", "label": _("Earned value"), "chips": []},
			{"key": "heads", "label": _("Cost heads"), "chips": [[n, _proj(n).project_name.split(" — ")[0]] for n in names]},
		],
	}


def cn_evm_rows(tab, chip, q=None):
	names = [n for n in _names(False) if 10 <= CN.fig(n).step < 22]
	cur = _cur()
	if tab == "heads":
		n = chip if chip in names else (names[0] if names else None)
		if not n:
			return {"rows": [], "cols": [], "empty": _("No live projects.")}
		x = FN.evm(n)
		rows = []
		for h in P.HEADS:
			c = x.heads.get(h) or frappe._dict(budget=0, earned=0, actual=0, committed=0, fac=0)
			var = flt(c.budget) - flt(c.fac)
			rows.append({"cells": [_(h), {"money": c.budget, "currency": cur}, {"money": c.earned, "currency": cur}, {"money": c.committed, "currency": cur}, {"money": c.actual, "currency": cur},
				{"money": c.fac, "currency": cur}, {"money": var, "currency": cur, "neg": 1 if var < 0 else 0}]})
		return {"title": _("Cost heads — {0}").format(_proj(n).project_name), "cols": [{"label": _("Head")}, {"label": _("Budget"), "cls": "num"}, {"label": _("Earned"), "cls": "num"},
			{"label": _("Committed"), "cls": "num"}, {"label": _("Actual"), "cls": "num"}, {"label": _("Forecast"), "cls": "num"}, {"label": _("Variance"), "cls": "num"}], "rows": rows}
	rows = []
	for n in names:
		x = FN.evm(n)
		if not _q(q, n, _proj(n).project_name):
			continue
		rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), {"money": x.bac, "currency": cur}, {"main": f"{x.planned:.0f}% / {x.done:.0f}%", "sub": _("planned / done")},
			{"money": x.pv, "currency": cur}, {"money": x.ev, "currency": cur}, {"money": x.ac, "currency": cur},
			{"main": f"{x.cpi:.2f}" if x.ac else "—", "sub": _("SPI {0:.2f}").format(x.spi) if x.pv else "", "late": 1 if x.ac and x.cpi < .92 else 0},
			{"money": x.eac, "currency": cur, "sub": _("VAC {0}").format(_m(x.vac, cur)), "neg": 1 if x.vac < 0 else 0}]})
	return {"title": _("Earned value — BAC, PV, EV, AC, CPI, SPI, EAC"), "cols": [{"label": _("Project")}, {"label": _("BAC"), "cls": "num"}, {"label": _("Progress")}, {"label": _("PV"), "cls": "num"},
		{"label": _("EV"), "cls": "num"}, {"label": _("AC"), "cls": "num"}, {"label": _("CPI · SPI")}, {"label": _("EAC"), "cls": "num"}], "rows": rows, "nototal": 1, "empty": _("No live projects.")}


# ================================================================ Payroll & Statutory
def cn_pay_module():
	co = _co()
	cur = _cur()
	S = frappe.get_list("Staff Payroll", filters={"company": co}, fields=["name", "month", "status", "net", "gross", "employees"], order_by="month desc", limit_page_length=0) \
		if co and _perm("Staff Payroll") else []
	E = frappe.get_list("Employee", filters={"company": co, "status": "Active"}, fields=["name", "date_of_joining", "hs_cn_basic"], limit_page_length=0) if co and _perm("Employee") else []
	gr = [FN.gratuity(e) for e in E]
	L = frappe.get_list("Leave Application", filters={"company": co, "status": "Open", "docstatus": 0}, pluck="name", limit_page_length=0) \
		if co and frappe.db.exists("DocType", "Leave Application") and _perm("Leave Application") else []
	return {
		"title": _("Payroll & Statutory"),
		"desc": _("Staff payroll with PF, ESI, professional tax and TDS on the new regime, posted to the projects the staff work on; statutory payments with challans; gratuity provision and leave."),
		"new": [{"label": _("Monthly payroll"), "doctype": "Staff Payroll", "primary": 1}, {"label": _("Statutory payment"), "doctype": "Statutory Deposit"}, {"label": _("Employee"), "doctype": "Employee"}],
		"kpis": [
			kpi(_("Staff"), len(E), _("on the payroll"), "navy", "users", tab="emp"),
			kpi(_("Last payroll"), flt(S[0].gross) if S else 0, _("{0} · {1}").format(frappe.utils.formatdate(S[0].month, "MMM yyyy"), _(S[0].status)) if S else "—", "blue", "wallet", True, cur, tab="run"),
			kpi(_("Gratuity provision"), sum(g.amount for g in gr), _("{0} staff past 5 years").format(len([g for g in gr if g.eligible])), "amber", "landmark", True, cur, tab="emp"),
			kpi(_("Leave to approve"), len(L), _("in Approvals"), "orange" if L else "green", "calendar", route=["hipersign-approvals"]),
		],
		"tabs": [
			{"key": "run", "label": _("Monthly payroll"), "chips": []},
			{"key": "emp", "label": _("Staff"), "chips": []},
			{"key": "dep", "label": _("Statutory payments"), "chips": []},
		],
	}


def cn_pay_rows(tab, chip, q=None):
	co = _co()
	cur = _cur()
	if tab == "emp":
		rows = []
		for e in frappe.get_list("Employee", filters={"company": co, "status": "Active"}, fields=["name", "employee_name", "designation", "date_of_joining", "hs_cn_project", "hs_cn_state",
				"hs_cn_basic", "hs_cn_hra", "hs_cn_special", "pan_number", "hs_cn_uan"], order_by="employee_name asc", limit_page_length=0) if co and _perm("Employee") else []:
			if not _q(q, e.employee_name, e.designation, e.hs_cn_project):
				continue
			g = FN.gratuity(e)
			gross = flt(e.hs_cn_basic) + flt(e.hs_cn_hra) + flt(e.hs_cn_special)
			rows.append({"dt": "Employee", "name": e.name, "cells": [{"main": e.employee_name, "sub": e.designation or ""}, _pcell(e.hs_cn_project) if e.hs_cn_project else _("Head office"),
				{"main": e.hs_cn_state or "—", "sub": ("PAN ••••" + (e.pan_number or "")[-4:]) if e.pan_number else ""}, {"money": gross, "currency": cur, "sub": _("CTC {0}/yr").format(_m(gross * 12 * 1.1, cur))},
				{"money": FN.income_tax_annual(gross * 12) / 12, "currency": cur}, {"main": f"{g.years:.1f} yrs", "sub": _("eligible") if g.eligible else ""}, {"money": g.amount, "currency": cur}]})
		return {"title": _("Staff — pay, TDS and gratuity (15/26 × basic × years, payable after 5 years, cap ₹20 lakh)"), "cols": [{"label": _("Employee")}, {"label": _("Posted at")},
			{"label": _("State")}, {"label": _("Gross / month"), "cls": "num"}, {"label": _("TDS / month"), "cls": "num"}, {"label": _("Service")}, {"label": _("Gratuity"), "cls": "num"}],
			"rows": rows, "empty": _("No staff on the payroll — add employees with their pay.")}
	if tab == "dep":
		rows = []
		for d in frappe.get_list("Statutory Deposit", filters={"company": co}, fields=["name", "kind", "month", "gstin", "project", "amount", "itc_used", "due_date", "paid_on", "challan_no", "status"],
				order_by="paid_on desc", limit_page_length=200) if co and _perm("Statutory Deposit") else []:
			if not _q(q, d.kind, d.gstin, d.challan_no, d.project):
				continue
			rows.append({"dt": "Statutory Deposit", "name": d.name, "cells": [{"main": _(d.kind), "sub": d.gstin or d.project or ""}, frappe.utils.formatdate(d.month, "MMM yyyy"),
				{"money": d.amount, "currency": cur, "sub": _("ITC {0}").format(_m(d.itc_used, cur)) if flt(d.itc_used) else ""}, _date(d.due_date),
				{"main": frappe.format(d.paid_on, {"fieldtype": "Date"}) if d.paid_on else "—", "sub": d.challan_no or "", "late": 1 if d.paid_on and d.due_date and getdate(d.paid_on) > getdate(d.due_date) else 0},
				{"pill": _(d.status), "tone": "green" if d.status == "Paid" else "orange"}]})
		return {"title": _("Statutory payments"), "cols": [{"label": _("Payment")}, {"label": _("For")}, {"label": _("Cash"), "cls": "num"}, {"label": _("Due")}, {"label": _("Paid · challan")},
			{"label": _("Status")}], "rows": rows, "empty": _("No payments yet.")}
	rows = []
	for s in frappe.get_list("Staff Payroll", filters={"company": co}, fields=["name", "month", "status", "employees", "gross", "pf", "esi", "pt", "tds", "net", "approved_by", "employer_pf",
			"employer_esi"], order_by="month desc", limit_page_length=0) if co and _perm("Staff Payroll") else []:
		b = {"Draft": [_btn(_("Approve"), "pay_approve", s.name, True)], "Approved": [_btn(_("Pay"), "pay_pay", s.name, True, confirm=_("Pay {0} in salaries?").format(_m(s.net)))]}.get(s.status)
		rows.append({"dt": "Staff Payroll", "name": s.name, "cells": [{"main": frappe.utils.formatdate(s.month, "MMMM yyyy"), "sub": s.name}, s.employees, {"money": s.gross, "currency": cur},
			{"money": flt(s.pf) + flt(s.esi) + flt(s.pt), "currency": cur, "sub": _("PF, ESI, PT")}, {"money": s.tds, "currency": cur}, {"money": s.net, "currency": cur},
			{"money": flt(s.employer_pf) + flt(s.employer_esi), "currency": cur, "sub": _("employer PF + ESI")},
			{"pill": _(s.status), "tone": {"Paid": "green", "Approved": "blue"}.get(s.status, "grey"), "sub": s.approved_by or ""}, {"buttons": b} if b else ""]})
	return {"title": _("Monthly payroll"), "cols": [{"label": _("Month")}, {"label": _("Staff")}, {"label": _("Gross"), "cls": "num"}, {"label": _("Deductions"), "cls": "num"},
		{"label": _("TDS 192"), "cls": "num"}, {"label": _("Net"), "cls": "num"}, {"label": _("Employer cost"), "cls": "num"}, {"label": _("Status")}, {"label": ""}], "rows": rows,
		"empty": _("No payroll yet.")}
