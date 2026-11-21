"""v1.9.0 stage A3 (prototypes C3, C6, C7): the Construction (India) site-resource pages — Procurement & Stores, Vendors,
Central Store, Subcontractors, Labour & Workers and Equipment — on the module page renderer. Rules in api/construction_site.py."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, get_first_day, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_site as S
from hipersign_trading.api import projects as P
from hipersign_trading.api.module import _perm, _scope, kpi
from hipersign_trading.api.module_cn import _btn, _chips, _cur, _date, _js, _m, _names, _pcell, _pick, _proj, _q

KEYS = ("cn_proc", "cn_ven", "cn_store", "cn_sub", "cn_lab", "cn_eqp")


def _cos():
	return _scope()[0]


def _cof():
	cos = _cos()
	return {"company": ["in", cos]} if cos else {}


def _co():
	cos = _cos()
	n = _names()
	return cos[0] if cos else (_proj(n[0]).company if n else frappe.defaults.get_user_default("Company"))


def _iname(code):
	return frappe.get_cached_value("Item", code, "item_name") or code


def _qty(v, uom=""):
	return {"main": f"{flt(v):,.2f}".rstrip("0").rstrip(".") + (f" {uom}" if uom else "")}


# ================================================================ Procurement & Stores
def _mrs(f=None):
	if not _perm("Material Request"):
		return []
	return frappe.get_list("Material Request", filters=dict({"hs_project": ["in", _names(False) or [""]], "material_request_type": "Purchase"}, **(f or {})),
		fields=["name", "hs_project", "transaction_date", "schedule_date", "status", "docstatus", "per_ordered", "hs_over_boq", "hs_rejected_lines", "owner"],
		order_by="transaction_date desc", limit_page_length=0)


def _pos(f=None):
	if not _perm("Purchase Order"):
		return []
	return frappe.get_list("Purchase Order", filters=dict({"hs_project": ["in", _names() or [""]]}, **(f or {})), fields=["name", "supplier", "hs_project", "transaction_date",
		"schedule_date", "base_grand_total", "status", "docstatus", "per_received", "per_billed", "workflow_state"] if frappe.get_meta("Purchase Order").has_field("workflow_state")
		else ["name", "supplier", "hs_project", "transaction_date", "schedule_date", "base_grand_total", "status", "docstatus", "per_received", "per_billed"],
		order_by="transaction_date desc", limit_page_length=0)


def cn_proc_module():
	names = _names(False)
	cur = _cur(names)
	M = _mrs({"docstatus": ["<", 2]})
	over = [m for m in M if m.docstatus == 0 and cint(m.hs_over_boq)]
	to_appr = [m for m in M if m.docstatus == 0]
	POs = _pos({"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]})
	ex = []
	for n in names:
		ex += S.material_status(n)
	excess = sum(x.excess_value for x in ex)
	return {
		"title": _("Procurement & Stores"),
		"desc": _("Indents checked against what the BOQ still needs, quotations compared on landed cost, orders, receipts at the site stores, issues to the work and the material reconciliation."),
		"new": [{"label": _("New indent"), "doctype": "Material Request", "primary": 1}, {"label": _("Supplier quotation"), "doctype": "Supplier Quotation"},
			{"label": _("Material issue"), "doctype": "Stock Entry"}],
		"kpis": [
			kpi(_("Indents to approve"), len(to_appr), _("{0} above the BOQ need — PM").format(len(over)), "orange" if over else "blue", "inbox", tab="ind", chip="draft"),
			kpi(_("Open purchase orders"), sum(flt(p.base_grand_total) * (100 - flt(p.per_received)) / 100 for p in POs), _("{0} POs to receive").format(len(POs)), "navy", "shopping-cart",
				True, cur, tab="po"),
			kpi(_("Site stock"), sum(_store_value(n) for n in names), _("{0} site stores").format(len(names)), "blue", "warehouse", True, cur, tab="store"),
			kpi(_("Material over theory"), excess, _("recover {0} from contractors").format(_m(sum(x.recovery for x in ex), cur)), "red" if excess else "green", "triangle-alert", True, cur,
				tab="rec"),
		],
		"tabs": [
			{"key": "ind", "label": _("Indents"), "chips": [["draft", _("To approve")], ["open", _("Approved, to order")], ["all", _("All")]]},
			{"key": "cmp", "label": _("Quotation comparison"), "chips": []},
			{"key": "po", "label": _("Purchase orders"), "chips": [["open", _("To receive")], ["draft", _("Draft")], ["all", _("All")]]},
			{"key": "grn", "label": _("Receipts (GRN)"), "chips": [["unbilled", _("Not billed")], ["all", _("All")]]},
			{"key": "store", "label": _("Site stores"), "chips": _chips(names)},
			{"key": "rec", "label": _("Material reconciliation"), "chips": [["all", _("All projects")]] + _chips(names)},
			{"key": "iss", "label": _("Issues to the work"), "chips": []},
		],
	}


def _store_value(project):
	w = frappe.db.get_value("Project", project, "hs_site_warehouse")
	return flt(frappe.db.sql("select sum(stock_value) from `tabBin` where warehouse = %s", w)[0][0]) if w else 0


def cn_proc_rows(tab, chip, q=None):
	names = _names(False)
	cur = _cur(names)
	if tab == "ind":
		chip = chip or "draft"
		f = {"docstatus": 0} if chip == "draft" else {"docstatus": 1, "per_ordered": ["<", 100], "status": ["not in", ["Stopped", "Cancelled"]]} if chip == "open" else {"docstatus": ["<", 2]}
		rows = []
		for m in _mrs(f):
			items = frappe.get_all("Material Request Item", filters={"parent": m.name}, fields=["item_code", "qty", "uom"])
			if not _q(q, m.name, m.hs_project, *[i.item_code for i in items]):
				continue
			b = []
			if m.docstatus == 0:
				b = [_btn(_("Approve"), "ind_approve", m.name, True), _btn("✕", "ind_reject", m.name, confirm=_("Reject {0}?").format(m.name))]
			elif flt(m.per_ordered) < 100 and frappe.db.exists("Supplier Quotation Item", {"material_request": m.name, "docstatus": 1}):
				b = [_btn(_("PO to L1"), "po_l1", m.name, True)]
			rows.append({"dt": "Material Request", "name": m.name, "cells": [{"main": m.name, "sub": frappe.format(m.transaction_date, {"fieldtype": "Date"})}, _pcell(m.hs_project),
				{"lines": [f"{_iname(i.item_code)} — {flt(i.qty):g} {i.uom}" for i in items][:3]}, _date(m.schedule_date),
				{"pill": _("Above BOQ need") if cint(m.hs_over_boq) else _("Within BOQ need"), "tone": "red" if cint(m.hs_over_boq) else "green",
					"sub": (m.hs_rejected_lines or "")[:70] if cint(m.hs_over_boq) else ""},
				{"pill": _("To approve") if m.docstatus == 0 else _(m.status), "sub": _("{0:.0f}% ordered").format(flt(m.per_ordered)) if m.docstatus == 1 else ""}, {"buttons": b} if b else ""]})
		return {"title": _("Indents"), "cols": [{"label": _("Indent")}, {"label": _("Project")}, {"label": _("Material")}, {"label": _("Needed by")}, {"label": _("BOQ check")},
			{"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No indents here.")}
	if tab == "cmp":
		rows = []
		for m in _mrs({"docstatus": 1}):
			Q = S.comparison(m.name)
			if not Q or not _q(q, m.name, m.hs_project):
				continue
			low_basic = min(flt(x.base_net_total) for x in Q)
			for i, x in enumerate(Q):
				l1 = i == 0 and cint(x.get("hs_tech_ok"))
				rows.append({"dt": "Supplier Quotation", "name": x.name, "cells": [{"main": m.name, "sub": m.hs_project} if i == 0 else "", {"main": x.supplier, "sub": x.name},
					{"money": x.base_net_total, "currency": cur, "sub": _("lowest basic") if flt(x.base_net_total) == low_basic else ""},
					{"money": flt(x.get("hs_freight")) + flt(x.get("hs_unloading")), "currency": cur}, {"money": x.get("hs_landed_total") or x.base_net_total, "currency": cur},
					{"pill": _("Compliant") if cint(x.get("hs_tech_ok")) else _("Not compliant"), "tone": "green" if cint(x.get("hs_tech_ok")) else "red"},
					{"pill": "L1", "tone": "green"} if l1 else f"L{i + 1}",
					{"buttons": [_btn(_("PO to L1"), "po_l1", m.name, True)]} if l1 and flt(m.per_ordered) < 100 else ({"link": ["Material Request", m.name]} if l1 else "")]})
		return {"title": _("Comparative statement — landed cost (basic + freight + unloading), technically compliant first"), "cols": [{"label": _("Indent")}, {"label": _("Supplier")},
			{"label": _("Basic"), "cls": "num"}, {"label": _("Freight & unloading"), "cls": "num"}, {"label": _("Landed"), "cls": "num"}, {"label": _("Technical")}, {"label": _("Rank")},
			{"label": ""}], "rows": rows, "nototal": 1, "empty": _("No quotations to compare — record supplier quotations against an approved indent.")}
	if tab == "po":
		chip = chip or "open"
		f = {"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]]} if chip == "open" else {"docstatus": 0} if chip == "draft" else {"docstatus": ["<", 2]}
		rows = []
		for p in _pos(f):
			if not _q(q, p.name, p.supplier, p.hs_project):
				continue
			rows.append({"dt": "Purchase Order", "name": p.name, "cells": [{"main": p.name, "sub": frappe.format(p.transaction_date, {"fieldtype": "Date"})}, {"main": p.supplier},
				_pcell(p.hs_project), {"money": p.base_grand_total, "currency": cur}, _date(p.schedule_date, p.docstatus == 1 and flt(p.per_received) < 100 and getdate(p.schedule_date) < getdate(today())),
				{"bar": flt(p.per_received)}, {"pill": _(p.get("workflow_state") or p.status) if p.docstatus == 0 else _(p.status)}]})
		return {"title": _("Purchase orders"), "cols": [{"label": _("PO")}, {"label": _("Supplier")}, {"label": _("Project")}, {"label": _("Value"), "cls": "num"}, {"label": _("Delivery by")},
			{"label": _("Received")}, {"label": _("Status")}], "rows": rows, "empty": _("No purchase orders here.")}
	if tab == "grn":
		ws = [w for w in (frappe.db.get_value("Project", n, "hs_site_warehouse") for n in names) if w]
		rows = []
		if _perm("Purchase Receipt") and ws:
			for r in frappe.db.sql("""select distinct p.name, p.supplier, p.posting_date, p.base_grand_total, p.per_billed, p.supplier_delivery_note, p.lr_no, i.warehouse,
					p.project from `tabPurchase Receipt` p join `tabPurchase Receipt Item` i on i.parent = p.name where p.docstatus = 1 and i.warehouse in %s
					order by p.posting_date desc""", (tuple(ws),), as_dict=True):
				if (chip or "unbilled") == "unbilled" and flt(r.per_billed) >= 100:
					continue
				if not _q(q, r.name, r.supplier):
					continue
				acc = frappe.db.sql("select sum(received_qty), sum(rejected_qty) from `tabPurchase Receipt Item` where parent = %s", r.name)[0]
				rows.append({"dt": "Purchase Receipt", "name": r.name, "cells": [{"main": r.name, "sub": frappe.format(r.posting_date, {"fieldtype": "Date"})}, r.supplier,
					{"main": r.warehouse.replace(" - " + (r.warehouse.split(" - ")[-1]), ""), "sub": r.lr_no or ""}, {"main": f"{flt(acc[0]):g}", "sub": _("{0:g} rejected").format(flt(acc[1])) if flt(acc[1]) else "",
						"late": 1 if flt(acc[1]) else 0}, {"money": r.base_grand_total, "currency": cur}, {"pill": _("Billed") if flt(r.per_billed) >= 100 else _("Not billed"),
						"tone": "green" if flt(r.per_billed) >= 100 else "orange", "sub": r.supplier_delivery_note or ""},
					{"buttons": [_btn(_("Book bill"), "grn_bill", r.name, True, confirm=_("Book the supplier's bill for {0}?").format(r.name))]} if flt(r.per_billed) < 100 else ""]})
		return {"title": _("Goods received at the site stores"), "cols": [{"label": _("GRN")}, {"label": _("Supplier")}, {"label": _("Store · vehicle")}, {"label": _("Received")},
			{"label": _("Value"), "cls": "num"}, {"label": _("Bill")}, {"label": ""}], "rows": rows, "empty": _("No receipts here.")}
	if tab == "store":
		pj = _pick(chip, names)
		w = frappe.db.get_value("Project", pj, "hs_site_warehouse") if pj else None
		rows = []
		if w:
			for b in frappe.get_all("Bin", filters={"warehouse": w, "actual_qty": ["!=", 0]}, fields=["item_code", "actual_qty", "valuation_rate", "stock_value", "stock_uom"]):
				if not _q(q, b.item_code, _iname(b.item_code)):
					continue
				last = frappe.db.get_value("Stock Ledger Entry", {"item_code": b.item_code, "warehouse": w, "is_cancelled": 0}, "posting_date", order_by="posting_date desc")
				rows.append({"dt": "Item", "name": b.item_code, "cells": [{"main": _iname(b.item_code), "sub": b.item_code}, _qty(b.actual_qty, b.stock_uom), {"money": b.valuation_rate, "currency": cur},
					{"money": b.stock_value, "currency": cur}, _date(last)]})
		return {"title": _("Site store — {0}").format(w or "—"), "cols": [{"label": _("Material")}, {"label": _("In store")}, {"label": _("Rate"), "cls": "num"}, {"label": _("Value"), "cls": "num"},
			{"label": _("Last movement")}], "rows": rows, "empty": _("Nothing in this store.")}
	if tab == "rec":
		ps = names if (chip or "all") == "all" else [chip]
		rows = []
		for n in ps:
			for x in S.material_status(n):
				if not _q(q, n, x.item, x.item_name):
					continue
				rows.append({"dt": "Project", "name": n, "cells": [_pcell(n), {"main": x.item_name, "sub": _("BOQ {0}").format(", ".join(x.lines[:3]))}, _qty(x.theory, x.uom), _qty(x.issued, x.uom),
					{"main": f"{x.excess_pct:+.1f}%" if x.theory else "—", "sub": _("allowed {0:.1f}%").format(x.wastage), "late": 1 if x.excess > 0 else 0},
					{"money": x.excess_value, "currency": cur, "neg": 1 if x.excess_value else 0}, {"money": x.recovery, "currency": cur},
					_qty(x.remaining, x.uom)]})
		return {"title": _("Material reconciliation — theoretical use of the work measured vs issued"), "cols": [{"label": _("Project")}, {"label": _("Material")}, {"label": _("Theory")},
			{"label": _("Issued")}, {"label": _("Variance")}, {"label": _("Excess value"), "cls": "num"}, {"label": _("Recover (×1.5)"), "cls": "num"}, {"label": _("BOQ still needs")}],
			"rows": rows, "empty": _("No material norms match these BOQs — add them under Material Norm.")}
	rows = []
	if _perm("Stock Entry"):
		for e in frappe.get_list("Stock Entry", filters={"purpose": "Material Issue", "docstatus": 1, "project": ["in", names or [""]]}, fields=["name", "project", "posting_date",
				"total_outgoing_value", "remarks"], order_by="posting_date desc", limit_page_length=100):
			items = frappe.get_all("Stock Entry Detail", filters={"parent": e.name}, fields=["item_code", "qty", "uom"])
			if not _q(q, e.name, e.project, e.remarks, *[i.item_code for i in items]):
				continue
			rows.append({"dt": "Stock Entry", "name": e.name, "cells": [_date(e.posting_date), _pcell(e.project), {"lines": [f"{_iname(i.item_code)} — {flt(i.qty):g} {i.uom}" for i in items][:3]},
				(e.remarks or "")[:60], {"money": e.total_outgoing_value, "currency": cur}]})
	return {"title": _("Material issued to the work"), "cols": [{"label": _("Date")}, {"label": _("Project")}, {"label": _("Material")}, {"label": _("To")}, {"label": _("Value"), "cls": "num"}],
		"rows": rows, "empty": _("No issues yet.")}


# ================================================================ Vendors
def _suppliers():
	meta = frappe.get_meta("Supplier")
	fields = ["name", "supplier_name", "supplier_group", "supplier_type"] + [f for f in ("gstin", "pan", "gst_category", "hs_kyc_status", "hs_msme_category", "hs_msme_no",
		"tax_withholding_category") if meta.has_field(f)]
	co = _co()
	used = set(frappe.db.sql_list("select distinct supplier from `tabPurchase Order` where company = %s union select distinct supplier from `tabSubcontractor Work Order` where company = %s",
		(co, co))) if frappe.db.table_exists("Subcontractor Work Order") else set()
	S_ = frappe.get_list("Supplier", fields=fields, limit_page_length=0) if _perm("Supplier") else []
	return [s for s in S_ if s.name in used or (s.get("gstin") or "").startswith(("32", "29", "33", "27"))]


def _score(supplier):
	"""On-time delivery (receipt by the PO's date) and quality (share of the quantity received that was accepted)."""
	r = frappe.db.sql("""select count(distinct p.name), sum(i.received_qty), sum(i.rejected_qty) from `tabPurchase Receipt Item` i join `tabPurchase Receipt` p on p.name = i.parent
		where p.docstatus = 1 and p.supplier = %s""", supplier)[0]
	if not r[0]:
		return None
	pos = frappe.get_all("Purchase Order", filters={"supplier": supplier, "docstatus": 1}, fields=["name", "schedule_date"])
	on, n = 0, 0
	for p in pos:
		d = frappe.db.sql("""select min(pr.posting_date) from `tabPurchase Receipt Item` i join `tabPurchase Receipt` pr on pr.name = i.parent
			where i.purchase_order = %s and pr.docstatus = 1""", p.name)[0][0]
		if d:
			n += 1
			on += 1 if getdate(d) <= getdate(p.schedule_date) else 0
		elif getdate(p.schedule_date) < getdate(today()):
			n += 1  # past its date and nothing received
	ot = on / n * 100 if n else None
	ql = (flt(r[1]) - flt(r[2])) / flt(r[1]) * 100 if flt(r[1]) else None
	score = round((ot if ot is not None else 90) * .4 + (ql if ql is not None else 95) * .6, 0)
	return frappe._dict(pos=len(pos), received=cint(r[0]), ontime=ot, quality=ql, score=score)


def cn_ven_module():
	V = _suppliers()
	cur = _cur()
	kyc = [v for v in V if v.get("hs_kyc_status") not in ("Verified",)]
	msme = [v for v in V if v.get("hs_msme_category") not in (None, "", "Not MSME")]
	BO = frappe.get_list("Blanket Order", filters={"blanket_order_type": "Purchasing", "docstatus": 1}, fields=["name", "to_date"], limit_page_length=0) if _perm("Blanket Order") else []
	exp = [b for b in BO if b.to_date and getdate(b.to_date) <= getdate(add_days(today(), 30))]
	out = frappe.db.sql("""select sum(outstanding_amount) from `tabPurchase Invoice` where docstatus = 1 and company = %s and outstanding_amount > 0""", _co())[0][0]
	return {
		"title": _("Vendors"),
		"desc": _("Suppliers and subcontractors — GSTIN, PAN, MSME, TDS and KYC — their scorecard from real orders and receipts, and the rate contracts."),
		"new": [{"label": _("New vendor"), "doctype": "Supplier", "primary": 1}, {"label": _("New rate contract"), "doctype": "Blanket Order"}],
		"kpis": [
			kpi(_("Vendors"), len(V), _("{0} MSME (45-day payment rule)").format(len(msme)), "navy", "users", tab="ven"),
			kpi(_("KYC not verified"), len(kyc), _("no PO until verified") if kyc else _("all verified"), "orange" if kyc else "green", "shield-check", tab="ven", chip="kyc"),
			kpi(_("Payables"), flt(out), _("purchase invoices outstanding"), "red", "banknote", True, cur),
			kpi(_("Rate contracts"), len(BO), _("{0} expire in 30 days").format(len(exp)), "orange" if exp else "blue", "file-text", tab="rc"),
		],
		"tabs": [
			{"key": "ven", "label": _("Vendors"), "chips": [["all", _("All")], ["kyc", _("KYC pending")], ["msme", _("MSME")]]},
			{"key": "score", "label": _("Scorecard"), "chips": []},
			{"key": "rc", "label": _("Rate contracts"), "chips": []},
		],
	}


def cn_ven_rows(tab, chip, q=None):
	cur = _cur()
	V = _suppliers()
	if tab == "score":
		rows = []
		for v in V:
			s = _score(v.name)
			if not s or not _q(q, v.name):
				continue
			rows.append({"dt": "Supplier", "name": v.name, "cells": [{"main": v.supplier_name, "sub": v.supplier_group}, s.pos, {"main": f"{s.ontime:.0f}%" if s.ontime is not None else "—",
				"sub": _("{0} receipts").format(s.received)}, {"main": f"{s.quality:.1f}%" if s.quality is not None else "—", "sub": _("accepted")},
				{"pill": f"{s.score:.0f}", "tone": "green" if s.score >= 90 else "orange" if s.score >= 75 else "red"}]})
		rows.sort(key=lambda r: -float(r["cells"][4]["pill"]))
		return {"title": _("Vendor scorecard — on-time delivery and quality accepted"), "cols": [{"label": _("Vendor")}, {"label": _("POs")}, {"label": _("On time")}, {"label": _("Quality")},
			{"label": _("Score")}], "rows": rows, "nototal": 1, "empty": _("No orders yet.")}
	if tab == "rc":
		rows = []
		for b in frappe.get_list("Blanket Order", filters={"blanket_order_type": "Purchasing", "docstatus": ["<", 2]}, fields=["name", "supplier", "from_date", "to_date", "docstatus"],
				order_by="to_date asc", limit_page_length=0) if _perm("Blanket Order") else []:
			for it in frappe.get_all("Blanket Order Item", filters={"parent": b.name}, fields=["item_code", "qty", "rate", "ordered_qty"]):
				if not _q(q, b.name, b.supplier, it.item_code):
					continue
				drawn = flt(it.ordered_qty) / flt(it.qty) * 100 if flt(it.qty) else 0
				days = date_diff(b.to_date, today()) if b.to_date else None
				rows.append({"dt": "Blanket Order", "name": b.name, "cells": [{"main": b.supplier, "sub": b.name}, {"main": _iname(it.item_code)}, {"money": it.rate, "currency": cur},
					_qty(it.qty), {"bar": drawn}, _date(b.to_date, days is not None and days <= 30),
					{"pill": _("Active") if b.docstatus == 1 and (days or 0) >= 0 else _("Expired") if b.docstatus == 1 else _("Draft"),
						"tone": "red" if drawn >= 90 or (days is not None and days <= 30) else "green", "sub": _("near cap") if drawn >= 90 else ""}]})
		return {"title": _("Rate contracts — cap, drawn and expiry"), "cols": [{"label": _("Vendor")}, {"label": _("Material")}, {"label": _("Rate"), "cls": "num"}, {"label": _("Cap")},
			{"label": _("Drawn")}, {"label": _("Valid to")}, {"label": _("Status")}], "rows": rows, "nototal": 1, "empty": _("No rate contracts — add a Blanket Order (Purchasing).")}
	chip = chip or "all"
	rows = []
	for v in V:
		if chip == "kyc" and v.get("hs_kyc_status") == "Verified":
			continue
		if chip == "msme" and v.get("hs_msme_category") in (None, "", "Not MSME"):
			continue
		if not _q(q, v.name, v.get("gstin"), v.supplier_group):
			continue
		out = flt(frappe.db.sql("select sum(outstanding_amount) from `tabPurchase Invoice` where docstatus = 1 and supplier = %s", v.name)[0][0])
		rows.append({"dt": "Supplier", "name": v.name, "cells": [{"main": v.supplier_name, "sub": v.supplier_group}, {"main": v.get("gstin") or _("Unregistered"), "sub": v.get("pan") or ""},
			{"main": _(v.get("hs_msme_category") or "Not MSME"), "sub": v.get("hs_msme_no") or ""}, {"main": (v.get("tax_withholding_category") or "—")[:34]},
			{"money": out, "currency": cur}, {"pill": _(v.get("hs_kyc_status") or "Pending"), "tone": "green" if v.get("hs_kyc_status") == "Verified" else "orange"}]})
	return {"title": _("Vendors"), "cols": [{"label": _("Vendor")}, {"label": _("GSTIN · PAN")}, {"label": _("MSME")}, {"label": _("TDS")}, {"label": _("Outstanding"), "cls": "num"},
		{"label": _("KYC")}], "rows": rows, "empty": _("No vendors here.")}


# ================================================================ Central Store & Logistics
def _transfers(f=None):
	if not _perm("Stock Entry") or not frappe.get_meta("Stock Entry").has_field("hs_transfer_status"):
		return []
	return frappe.get_list("Stock Entry", filters=dict({"purpose": "Material Transfer", "hs_transfer_status": ["in", ["Requested", "In transit", "Delivered"]], **_cof()}, **(f or {})),
		fields=["name", "posting_date", "project", "hs_transfer_status", "hs_vehicle", "hs_driver", "hs_driver_mobile", "hs_eway_bill", "hs_destination", "docstatus", "total_outgoing_value",
			"from_warehouse", "modified"], order_by="posting_date desc", limit_page_length=0)


def cn_store_module():
	co = _co()
	cur = _cur()
	cs = S.central_store(co) if co else None
	val = flt(frappe.db.sql("select sum(stock_value) from `tabBin` where warehouse = %s", cs)[0][0]) if cs else 0
	T = _transfers()
	tr = [t for t in T if t.hs_transfer_status == "In transit"]
	late = [t for t in tr if date_diff(today(), t.posting_date) > 1]
	dead = _dead(cs)
	return {
		"title": _("Central Store & Logistics"),
		"desc": _("The central yard's stock, transfers to the sites through Goods In Transit with vehicle, driver and e-way bill, the stock ledger and dead stock."),
		"new": [{"label": _("New transfer"), "doctype": "Stock Entry", "primary": 1}],
		"kpis": [
			kpi(_("Central store"), val, cs or "—", "navy", "warehouse", True, cur, tab="stock"),
			kpi(_("Transfers requested"), len([t for t in T if t.hs_transfer_status == "Requested"]), _("to dispatch"), "blue", "truck", tab="trf", chip="Requested"),
			kpi(_("In transit"), len(tr), _("{0} over a day on the road").format(len(late)), "red" if late else "orange" if tr else "green", "route", tab="trf", chip="In transit"),
			kpi(_("Dead stock"), sum(d[2] for d in dead), _("{0} items, no movement 90 days").format(len(dead)), "amber", "archive", True, cur, tab="dead"),
		],
		"tabs": [
			{"key": "stock", "label": _("Central stock"), "chips": []},
			{"key": "trf", "label": _("Transfers"), "chips": [["open", _("Open")], ["Requested", _("Requested")], ["In transit", _("In transit")], ["Delivered", _("Delivered")]]},
			{"key": "led", "label": _("Stock ledger"), "chips": []},
			{"key": "dead", "label": _("Dead stock"), "chips": []},
		],
	}


def _dead(w):
	if not w:
		return []
	out = []
	for b in frappe.get_all("Bin", filters={"warehouse": w, "actual_qty": [">", 0]}, fields=["item_code", "actual_qty", "stock_value"]):
		last = frappe.db.get_value("Stock Ledger Entry", {"item_code": b.item_code, "warehouse": w, "is_cancelled": 0, "actual_qty": ["<", 0]}, "posting_date", order_by="posting_date desc") \
			or frappe.db.get_value("Stock Ledger Entry", {"item_code": b.item_code, "warehouse": w, "is_cancelled": 0}, "posting_date", order_by="posting_date asc")
		if last and date_diff(today(), last) > 90:
			out.append((b.item_code, flt(b.actual_qty), flt(b.stock_value), last))
	return out


def cn_store_rows(tab, chip, q=None):
	co = _co()
	cur = _cur()
	cs = S.central_store(co) if co else None
	if tab == "trf":
		chip = chip or "open"
		rows = []
		for t in _transfers():
			if chip == "open" and t.hs_transfer_status == "Delivered":
				continue
			if chip not in ("open", "all") and t.hs_transfer_status != chip:
				continue
			items = frappe.get_all("Stock Entry Detail", filters={"parent": t.name}, fields=["item_code", "qty", "uom"])
			if not _q(q, t.name, t.project, t.hs_vehicle, t.hs_driver, *[i.item_code for i in items]):
				continue
			b = {"Requested": [_btn(_("Dispatch"), "trf_dispatch", t.name, True)], "In transit": [_btn(_("Delivered at site"), "trf_deliver", t.name, True)]}.get(t.hs_transfer_status)
			days = date_diff(today(), t.posting_date)
			rows.append({"dt": "Stock Entry", "name": t.name, "cells": [{"main": t.name, "sub": frappe.format(t.posting_date, {"fieldtype": "Date"})}, _pcell(t.project) if t.project else (t.hs_destination or "—"),
				{"lines": [f"{_iname(i.item_code)} — {flt(i.qty):g} {i.uom}" for i in items][:3]}, {"main": t.hs_vehicle or "—", "sub": f"{t.hs_driver or ''} {t.hs_driver_mobile or ''}".strip()},
				t.hs_eway_bill or "—", {"pill": _(t.hs_transfer_status), "tone": {"Delivered": "green", "In transit": "orange"}.get(t.hs_transfer_status, "blue"),
					"sub": _("{0} days on the road").format(days) if t.hs_transfer_status == "In transit" and days else "", "late": 1 if t.hs_transfer_status == "In transit" and days > 1 else 0},
				{"buttons": b} if b else ""]})
		return {"title": _("Transfers — central store to sites"), "cols": [{"label": _("Transfer")}, {"label": _("To")}, {"label": _("Material")}, {"label": _("Vehicle · driver")},
			{"label": _("E-way bill")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No transfers here.")}
	if tab == "led":
		ws = [cs] + [w for w in (frappe.db.get_value("Project", n, "hs_site_warehouse") for n in _names()) if w]
		rows = []
		for s in frappe.get_all("Stock Ledger Entry", filters={"warehouse": ["in", ws], "is_cancelled": 0}, fields=["posting_date", "item_code", "warehouse", "actual_qty", "qty_after_transaction",
				"voucher_type", "voucher_no", "stock_value_difference"], order_by="posting_date desc, creation desc", limit_page_length=150):
			if not _q(q, s.item_code, s.warehouse, s.voucher_no):
				continue
			rows.append({"dt": s.voucher_type, "name": s.voucher_no, "cells": [_date(s.posting_date), {"main": _iname(s.item_code)}, s.warehouse.rsplit(" - ", 1)[0],
				{"main": f"{flt(s.actual_qty):+g}", "late": 1 if flt(s.actual_qty) < 0 else 0}, f"{flt(s.qty_after_transaction):g}", {"main": _(s.voucher_type), "sub": s.voucher_no},
				{"money": s.stock_value_difference, "currency": cur}]})
		return {"title": _("Stock ledger — central and site stores (latest 150)"), "cols": [{"label": _("Date")}, {"label": _("Material")}, {"label": _("Store")}, {"label": _("In / out")},
			{"label": _("Balance")}, {"label": _("Document")}, {"label": _("Value"), "cls": "num"}], "rows": rows, "nototal": 1, "empty": _("No movements.")}
	if tab == "dead":
		rows = [{"dt": "Item", "name": d[0], "cells": [{"main": _iname(d[0]), "sub": d[0]}, f"{d[1]:g}", {"money": d[2], "currency": cur}, _date(d[3]), _("{0} days").format(date_diff(today(), d[3]))]}
			for d in _dead(cs) if _q(q, d[0], _iname(d[0]))]
		return {"title": _("Dead stock — no issue for 90 days"), "cols": [{"label": _("Material")}, {"label": _("Qty")}, {"label": _("Value"), "cls": "num"}, {"label": _("Last movement")},
			{"label": _("Idle")}], "rows": rows, "empty": _("No dead stock.")}
	rows = []
	if cs:
		for b in frappe.get_all("Bin", filters={"warehouse": cs, "actual_qty": ["!=", 0]}, fields=["item_code", "actual_qty", "valuation_rate", "stock_value", "stock_uom", "reserved_qty"]):
			if not _q(q, b.item_code, _iname(b.item_code)):
				continue
			rows.append({"dt": "Item", "name": b.item_code, "cells": [{"main": _iname(b.item_code), "sub": b.item_code}, _qty(b.actual_qty, b.stock_uom), {"money": b.valuation_rate, "currency": cur},
				{"money": b.stock_value, "currency": cur}]})
	return {"title": _("Central store stock — {0}").format(cs or "—"), "cols": [{"label": _("Material")}, {"label": _("Qty")}, {"label": _("Rate"), "cls": "num"}, {"label": _("Value"), "cls": "num"}],
		"rows": rows, "empty": _("The central store is empty.")}


# ================================================================ Subcontractors
def _wos(f=None):
	if not _perm("Subcontractor Work Order"):
		return []
	return frappe.get_list("Subcontractor Work Order", filters=dict({"project": ["in", _names() or [""]]}, **(f or {})), fields=["name", "project", "supplier", "scope", "kind", "status",
		"value", "retention_pct", "tds_pct", "advance", "wo_date"], order_by="wo_date desc", limit_page_length=0)


def _sbs(f=None):
	if not _perm("Subcontractor Bill"):
		return []
	return frappe.get_list("Subcontractor Bill", filters=dict({"project": ["in", _names() or [""]]}, **(f or {})), fields=["name", "project", "supplier", "work_order", "bill_no", "bill_date",
		"status", "gross", "material_recovery", "other_recovery", "gst_amount", "retention", "tds", "net_payable", "compliance_hold", "purchase_invoice"],
		order_by="bill_date desc", limit_page_length=0)


def cn_sub_module():
	cur = _cur()
	W = _wos({"status": ["in", ["Active", "Completed"]]})
	B = _sbs({"status": ["!=", "Cancelled"]})
	done = [b for b in B if b.status in ("Approved", "Paid")]
	hold = [b for b in B if cint(b.compliance_hold) and b.status in ("Certified", "Approved")]
	return {
		"title": _("Subcontractors"),
		"desc": _("Work orders to subcontractors and labour contractors, running bills (QS certifies, PM approves, accounts pay) with GST, TDS 194C, retention and recoveries, and the labour-law documents that release payment."),
		"new": [{"label": _("New work order"), "doctype": "Subcontractor Work Order", "primary": 1}, {"label": _("New running bill"), "doctype": "Subcontractor Bill"},
			{"label": _("Labour documents"), "doctype": "Labour Compliance"}],
		"kpis": [
			kpi(_("Work orders"), sum(flt(w.value) for w in W), _("{0} active").format(len([w for w in W if w.status == "Active"])), "navy", "briefcase", True, cur, tab="wo"),
			kpi(_("Billed to date"), sum(flt(b.gross) for b in done), _("{0} bills approved").format(len(done)), "blue", "receipt", True, cur, tab="bill", chip="all"),
			kpi(_("To certify / approve"), len([b for b in B if b.status in ("Draft", "Certified")]), _m(sum(flt(b.net_payable) for b in B if b.status in ("Draft", "Certified")), cur),
				"orange", "inbox", tab="bill", chip="open"),
			kpi(_("Retention held"), sum(flt(b.retention) for b in done), _("released after DLP"), "amber", "landmark", True, cur, tab="ret"),
			kpi(_("Payments on hold"), len(hold), _("PF / ESI / wage register missing") if hold else _("none"), "red" if hold else "green", "shield", tab="lc"),
		],
		"tabs": [
			{"key": "wo", "label": _("Work orders"), "chips": [["Active", _("Active")], ["Draft", _("Draft")], ["all", _("All")]]},
			{"key": "bill", "label": _("Running bills"), "chips": [["open", _("Open")], ["hold", _("On hold")], ["Paid", _("Paid")], ["all", _("All")]]},
			{"key": "ret", "label": _("Retention"), "chips": []},
			{"key": "lc", "label": _("Labour compliance"), "chips": [["month", _("Last month")], ["all", _("All")]]},
		],
	}


def cn_sub_rows(tab, chip, q=None):
	cur = _cur()
	if tab == "bill":
		chip = chip or "open"
		f = {"status": ["in", ["Draft", "Certified", "Approved"]]} if chip in ("open", "hold") else {"status": "Paid"} if chip == "Paid" else {}
		rows = []
		for b in _sbs(f):
			if chip == "hold" and not cint(b.compliance_hold):
				continue
			if not _q(q, b.name, b.supplier, b.project):
				continue
			btn = {"Draft": [_btn(_("Certify"), "sub_certify", b.name, True)], "Certified": [_btn(_("Approve"), "sub_approve", b.name, True)],
				"Approved": [_btn(_("Pay"), "sub_pay", b.name, True, confirm=_("Pay {0} to {1}?").format(_m(b.net_payable), b.supplier))]}.get(b.status)
			rows.append({"dt": "Subcontractor Bill", "name": b.name, "cells": [{"main": _("RB {0} · {1}").format(b.bill_no, b.supplier), "sub": f"{b.name} · {b.work_order}"}, _pcell(b.project),
				{"money": b.gross, "currency": cur, "sub": _("less {0} recovered").format(_m(flt(b.material_recovery) + flt(b.other_recovery), cur)) if flt(b.material_recovery) + flt(b.other_recovery) else ""},
				{"money": b.gst_amount, "currency": cur}, {"money": flt(b.retention) + flt(b.tds), "currency": cur, "sub": _("retention + TDS")}, {"money": b.net_payable, "currency": cur},
				{"pill": _(b.status), "tone": {"Paid": "green", "Approved": "blue", "Certified": "violet"}.get(b.status, "grey"), "sub": _("on hold — labour documents") if cint(b.compliance_hold) else "",
					"late": cint(b.compliance_hold)}, {"buttons": btn} if btn else ""]})
		return {"title": _("Running bills"), "cols": [{"label": _("Bill")}, {"label": _("Project")}, {"label": _("Work this bill"), "cls": "num"}, {"label": _("GST"), "cls": "num"},
			{"label": _("Deductions"), "cls": "num"}, {"label": _("Net payable"), "cls": "num"}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No bills here.")}
	if tab == "ret":
		by = {}
		for b in _sbs({"status": ["in", ["Approved", "Paid"]]}):
			x = by.setdefault((b.supplier, b.project), [0.0, 0.0, 0])
			x[0] += flt(b.gross)
			x[1] += flt(b.retention)
			x[2] += 1
		rows = [{"cells": [s, _pcell(p), n, {"money": g, "currency": cur}, {"money": r, "currency": cur}, _date(add_days(_proj(p).expected_end_date, 365)) if _proj(p).expected_end_date else "—"]}
			for (s, p), (g, r, n) in sorted(by.items()) if _q(q, s, p)]
		return {"title": _("Retention held from subcontractors"), "cols": [{"label": _("Subcontractor")}, {"label": _("Project")}, {"label": _("Bills")}, {"label": _("Billed"), "cls": "num"},
			{"label": _("Retention"), "cls": "num"}, {"label": _("Release after DLP")}], "rows": rows, "empty": _("No retention yet.")}
	if tab == "lc":
		f = {} if chip == "all" else {"month": get_first_day(frappe.utils.add_months(today(), -1))}
		rows = []
		for c in frappe.get_list("Labour Compliance", filters=dict(_cof(), **f), fields=["name", "supplier", "project", "month", "workers", "clra_licence", "licence_valid_to", "wage_register",
				"pf_ecr", "esi_challan", "status"], order_by="month desc", limit_page_length=0) if _perm("Labour Compliance") else []:
			if not _q(q, c.supplier, c.project):
				continue
			tick = lambda v: {"pill": _("Received") if cint(v) else _("Missing"), "tone": "green" if cint(v) else "red"}
			rows.append({"dt": "Labour Compliance", "name": c.name, "cells": [{"main": c.supplier, "sub": c.clra_licence or ""}, frappe.utils.formatdate(c.month, "MMM yyyy"), c.workers or "—",
				tick(c.wage_register), tick(c.pf_ecr), tick(c.esi_challan), _date(c.licence_valid_to, c.licence_valid_to and getdate(c.licence_valid_to) < getdate(add_days(today(), 45))),
				{"buttons": [_btn(_("All received"), "lc_mark", c.name, True)]} if c.status != "Complete" else ""]})
		return {"title": _("Labour-law documents from contractors — payment is held until they are in"), "cols": [{"label": _("Contractor")}, {"label": _("Month")}, {"label": _("Workers")},
			{"label": _("Wage register")}, {"label": _("PF ECR")}, {"label": _("ESI")}, {"label": _("CLRA licence to")}, {"label": ""}], "rows": rows, "empty": _("No records for this month.")}
	chip = chip or "Active"
	rows = []
	for w in _wos({} if chip == "all" else {"status": chip}):
		if not _q(q, w.name, w.supplier, w.scope, w.project):
			continue
		billed = sum(flt(b.gross) for b in _sbs({"work_order": w.name, "status": ["in", ["Approved", "Paid"]]}))
		rows.append({"dt": "Subcontractor Work Order", "name": w.name, "cells": [{"main": w.scope, "sub": f"{w.name} · {w.supplier}"}, _pcell(w.project),
			{"main": _("Labour only") if (w.kind or "").startswith("Labour") else _("Item rate"), "sub": _("TDS {0:g}% · ret. {1:g}%").format(flt(w.tds_pct), flt(w.retention_pct))},
			{"money": w.value, "currency": cur}, {"money": billed, "currency": cur}, {"bar": billed / flt(w.value) * 100 if flt(w.value) else 0}, {"pill": _(w.status)},
			{"buttons": [_btn(_("Issue"), "swo_activate", w.name, True)]} if w.status == "Draft" else ""]})
	return {"title": _("Work orders"), "cols": [{"label": _("Work order")}, {"label": _("Project")}, {"label": _("Kind")}, {"label": _("Value"), "cls": "num"}, {"label": _("Billed"), "cls": "num"},
		{"label": _("Done")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No work orders here.")}


# ================================================================ Labour & Workers
def _workers(f=None):
	if not _perm("Site Worker"):
		return []
	return frappe.get_list("Site Worker", filters=dict({"project": ["in", _names(False) or [""]], "status": "Active"}, **(f or {})), fields=["name", "worker_name", "project", "contractor",
		"trade", "skill", "state", "daily_rate", "min_wage", "upi_id", "bocw_reg_no", "induction_done", "ppe_issued", "id_expiry", "police_verified", "medical_fit", "home_state"],
		order_by="project asc, contractor asc, worker_name asc", limit_page_length=0)


def cn_lab_module():
	cur = _cur()
	W = _workers()
	own = [w for w in W if not w.contractor]
	iss = [w for w in W if S.worker_issues(w)]
	M = frappe.get_list("Weekly Muster", filters={"project": ["in", _names() or [""]]}, fields=["name", "status", "net", "week_start", "earned"], limit_page_length=0) if _perm("Weekly Muster") else []
	A = frappe.get_list("Worker Advance", filters={"project": ["in", _names() or [""]]}, fields=["status", "amount", "recovered"], limit_page_length=0) if _perm("Worker Advance") else []
	return {
		"title": _("Labour & Workers"),
		"desc": _("Every worker on site — own and contractors' — with state minimum wages and the labour register; the weekly muster and pay (Wednesday → Tuesday, by UPI) and advances."),
		"new": [{"label": _("New worker"), "doctype": "Site Worker", "primary": 1}, {"label": _("Weekly muster"), "doctype": "Weekly Muster"}, {"label": _("Advance"), "doctype": "Worker Advance"}],
		"kpis": [
			kpi(_("Workers on site"), len(W), _("{0} own · {1} contractors'").format(len(own), len(W) - len(own)), "navy", "users", tab="wkr"),
			kpi(_("Wages to approve / pay"), sum(flt(m.net) for m in M if m.status in ("Draft", "Approved")), _("{0} musters").format(len([m for m in M if m.status in ("Draft", "Approved")])),
				"orange", "wallet", True, cur, tab="mus", chip="open"),
			kpi(_("Advances outstanding"), sum(flt(a.amount) - flt(a.recovered) for a in A if a.status == "Paid"), _("{0} requests waiting").format(len([a for a in A if a.status == "Requested"])),
				"amber", "hand-coins", True, cur, tab="adv"),
			kpi(_("Labour-register gaps"), len(iss), _("BOCW, induction, PPE, ID, police"), "red" if iss else "green", "shield-alert", tab="wkr", chip="issues"),
		],
		"tabs": [
			{"key": "wkr", "label": _("Workers"), "chips": [["all", _("All")], ["own", _("Own")], ["con", _("Contractors'")], ["issues", _("With gaps")]]},
			{"key": "mus", "label": _("Weekly muster & pay"), "chips": [["open", _("To approve / pay")], ["Paid", _("Paid")], ["all", _("All")]]},
			{"key": "adv", "label": _("Advances"), "chips": [["open", _("Open")], ["all", _("All")]]},
			{"key": "mw", "label": _("Minimum wages"), "chips": []},
		],
	}


def cn_lab_rows(tab, chip, q=None):
	cur = _cur()
	if tab == "mus":
		chip = chip or "open"
		f = {"status": ["in", ["Draft", "Approved"]]} if chip == "open" else {"status": "Paid"} if chip == "Paid" else {}
		rows = []
		for m in frappe.get_list("Weekly Muster", filters=dict({"project": ["in", _names() or [""]]}, **f), fields=["name", "project", "week_start", "week_end", "status", "workers",
				"man_days", "earned", "pf", "esi", "advance_recovery", "net", "approved_by"], order_by="week_start desc", limit_page_length=0) if _perm("Weekly Muster") else []:
			if not _q(q, m.name, m.project):
				continue
			b = {"Draft": [_btn(_("Approve"), "mus_approve", m.name, True)], "Approved": [_btn(_("Pay by UPI"), "mus_pay", m.name, True, confirm=_("Pay {0} to {1} workers by UPI?").format(_m(m.net), m.workers))]}.get(m.status)
			rows.append({"dt": "Weekly Muster", "name": m.name, "cells": [{"main": f"{frappe.format(m.week_start, {'fieldtype': 'Date'})} → {frappe.format(m.week_end, {'fieldtype': 'Date'})}", "sub": m.name},
				_pcell(m.project), {"main": f"{m.workers} · {flt(m.man_days):g}", "sub": _("workers · man-days")}, {"money": m.earned, "currency": cur},
				{"money": flt(m.pf) + flt(m.esi) + flt(m.advance_recovery), "currency": cur, "sub": _("PF, ESI, advances")}, {"money": m.net, "currency": cur},
				{"pill": _(m.status), "tone": {"Paid": "green", "Approved": "blue"}.get(m.status, "grey"), "sub": m.approved_by or ""}, {"buttons": b} if b else ""]})
		return {"title": _("Weekly muster & pay — Wednesday to Tuesday"), "cols": [{"label": _("Week")}, {"label": _("Project")}, {"label": _("Workers")}, {"label": _("Earned"), "cls": "num"},
			{"label": _("Deductions"), "cls": "num"}, {"label": _("Net (UPI)"), "cls": "num"}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No musters here.")}
	if tab == "adv":
		f = {"status": ["in", ["Requested", "Approved", "Paid"]]} if (chip or "open") == "open" else {}
		rows = []
		for a in frappe.get_list("Worker Advance", filters=dict({"project": ["in", _names() or [""]]}, **f), fields=["name", "worker", "worker_name", "project", "amount", "requested_on",
				"reason", "status", "recovered"], order_by="requested_on desc", limit_page_length=0) if _perm("Worker Advance") else []:
			if not _q(q, a.worker_name, a.project, a.reason):
				continue
			b = {"Requested": [_btn(_("Approve"), "adv_approve", a.name, True), _btn("✕", "adv_reject", a.name)], "Approved": [_btn(_("Pay by UPI"), "adv_pay", a.name, True)]}.get(a.status)
			rows.append({"dt": "Worker Advance", "name": a.name, "cells": [{"main": a.worker_name, "sub": a.worker}, _pcell(a.project), {"money": a.amount, "currency": cur,
				"sub": _("PM approves") if flt(a.amount) > S.limits().wadv and a.status == "Requested" else ""}, _date(a.requested_on), a.reason or "—",
				{"money": flt(a.amount) - flt(a.recovered), "currency": cur} if a.status == "Paid" else "—", {"pill": _(a.status)}, {"buttons": b} if b else ""]})
		return {"title": _("Worker advances — recovered from the weekly pay, at most half the wages"), "cols": [{"label": _("Worker")}, {"label": _("Project")}, {"label": _("Amount"), "cls": "num"},
			{"label": _("Asked on")}, {"label": _("Reason")}, {"label": _("Still owed"), "cls": "num"}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No advances here.")}
	if tab == "mw":
		rows = [{"dt": "Minimum Wage", "name": m.name, "cells": [m.state, _(m.skill), {"money": m.daily_rate, "currency": cur}, _date(m.effective_from)]}
			for m in frappe.get_all("Minimum Wage", fields=["name", "state", "skill", "daily_rate", "effective_from"], order_by="state asc, daily_rate asc")]
		return {"title": _("State minimum wages — construction (basic + VDA, per day)"), "cols": [{"label": _("State")}, {"label": _("Skill")}, {"label": _("Per day"), "cls": "num"},
			{"label": _("From")}], "rows": rows, "nototal": 1, "empty": _("Add the state minimum wages.")}
	chip = chip or "all"
	rows = []
	for w in _workers():
		if chip == "own" and w.contractor:
			continue
		if chip == "con" and not w.contractor:
			continue
		iss = S.worker_issues(w)
		if chip == "issues" and not iss:
			continue
		if not _q(q, w.worker_name, w.project, w.contractor, w.trade):
			continue
		rows.append({"dt": "Site Worker", "name": w.name, "cells": [{"main": w.worker_name, "sub": f"{w.name} · {w.home_state or w.state}"}, _pcell(w.project), {"main": _(w.trade), "sub": _(w.skill)},
			{"main": w.contractor or _("Own"), "sub": w.upi_id or ""}, {"money": w.daily_rate, "currency": cur, "sub": _("min {0}").format(_m(w.min_wage, cur)) if flt(w.min_wage) else ""},
			{"pill": _("{0} gaps").format(len(iss)) if iss else _("Complete"), "tone": "red" if iss else "green", "sub": ", ".join(iss[:2])}]})
	return {"title": _("Workers"), "cols": [{"label": _("Worker")}, {"label": _("Project")}, {"label": _("Trade")}, {"label": _("Employer · UPI")}, {"label": _("Daily wage"), "cls": "num"},
		{"label": _("Labour register")}], "rows": rows, "empty": _("No workers here.")}


# ================================================================ Equipment
def _eqs(f=None):
	if not _perm("Construction Equipment"):
		return []
	return frappe.get_list("Construction Equipment", filters=dict(_cof(), **(f or {})), fields=["name", "equipment_name", "kind", "project", "ownership", "supplier", "hire_rate", "hire_basis",
		"status", "planned_hours_month", "diesel_norm_lph", "last_hmr", "next_service_hmr", "insurance_expiry", "fitness_expiry", "reg_no"], order_by="kind asc", limit_page_length=0)


def cn_eqp_module():
	cur = _cur()
	E = _eqs({"status": ["!=", "Off-hired"]})
	F = {e.name: S.eq_fig(e) for e in E}
	util = [F[e.name].util for e in E if F[e.name].plan]
	alerts = [e for e in E if S.eq_flags(e)]
	return {
		"title": _("Equipment"),
		"desc": _("Plant and equipment — own and hired — where it works, hours and diesel from the log sheets, utilisation against plan, maintenance and downtime, insurance and fitness."),
		"new": [{"label": _("Log sheet"), "doctype": "Equipment Log", "primary": 1}, {"label": _("Maintenance"), "doctype": "Equipment Maintenance"},
			{"label": _("New equipment"), "doctype": "Construction Equipment"}],
		"kpis": [
			kpi(_("Equipment"), len(E), _("{0} hired · {1} broken down").format(len([e for e in E if e.ownership == "Hired"]), len([e for e in E if e.status == "Breakdown"])), "navy", "truck", tab="reg"),
			kpi(_("Utilisation this month"), f"{sum(util) / len(util):.0f}%" if util else "—", _("hours worked vs planned"), "blue", "gauge", tab="reg"),
			kpi(_("Hire cost this month"), sum(F[e].hire for e in F), _("hired machines"), "amber", "receipt", True, cur, tab="reg", chip="Hired"),
			kpi(_("Alerts"), len(alerts), _("service, insurance, fitness") if alerts else _("none"), "red" if alerts else "green", "bell", tab="reg", chip="alerts"),
		],
		"tabs": [
			{"key": "reg", "label": _("Register"), "chips": [["all", _("All")], ["Own", _("Own")], ["Hired", _("Hired")], ["alerts", _("With alerts")]]},
			{"key": "log", "label": _("Log sheets (HMR)"), "chips": [["week", _("Last 7 days")], ["all", _("All")]]},
			{"key": "mnt", "label": _("Maintenance & downtime"), "chips": []},
		],
	}


def cn_eqp_rows(tab, chip, q=None):
	cur = _cur()
	if tab == "log":
		f = dict(_cof())
		if (chip or "week") == "week":
			f["log_date"] = [">=", add_days(today(), -7)]
		rows = []
		for l in frappe.get_list("Equipment Log", filters=f, fields=["name", "equipment", "project", "log_date", "operator", "start_hmr", "end_hmr", "hours", "idle_hours", "diesel_litres", "work_done"],
				order_by="log_date desc, equipment asc", limit_page_length=200) if _perm("Equipment Log") else []:
			en = frappe.get_cached_value("Construction Equipment", l.equipment, "equipment_name")
			if not _q(q, en, l.project, l.operator, l.work_done):
				continue
			norm = flt(frappe.get_cached_value("Construction Equipment", l.equipment, "diesel_norm_lph"))
			rate = flt(l.diesel_litres) / flt(l.hours) if flt(l.hours) else 0
			rows.append({"dt": "Equipment Log", "name": l.name, "cells": [_date(l.log_date), {"main": en, "sub": l.operator or ""}, _pcell(l.project), f"{flt(l.start_hmr):g} → {flt(l.end_hmr):g}",
				{"main": f"{flt(l.hours):g} h", "sub": _("{0:g} h idle").format(flt(l.idle_hours)) if flt(l.idle_hours) else ""},
				{"main": f"{flt(l.diesel_litres):g} L", "sub": f"{rate:.1f} L/h" + (_(" (norm {0:g})").format(norm) if norm else ""), "late": 1 if norm and rate > norm * 1.1 else 0},
				(l.work_done or "")[:50]]})
		return {"title": _("Log sheets"), "cols": [{"label": _("Date")}, {"label": _("Equipment")}, {"label": _("Project")}, {"label": _("HMR")}, {"label": _("Hours")}, {"label": _("Diesel")},
			{"label": _("Work done")}], "rows": rows, "empty": _("No log sheets here.")}
	if tab == "mnt":
		rows = []
		for m in frappe.get_list("Equipment Maintenance", filters=_cof(), fields=["name", "equipment", "job_date", "job_type", "description", "downtime_hours", "cost", "done_by", "hmr"],
				order_by="job_date desc", limit_page_length=0) if _perm("Equipment Maintenance") else []:
			en = frappe.get_cached_value("Construction Equipment", m.equipment, "equipment_name")
			if not _q(q, en, m.job_type, m.description):
				continue
			rows.append({"dt": "Equipment Maintenance", "name": m.name, "cells": [_date(m.job_date), {"main": en, "sub": _("at {0:g} h").format(flt(m.hmr)) if flt(m.hmr) else ""},
				{"pill": _(m.job_type), "tone": "red" if m.job_type == "Breakdown" else "blue"}, (m.description or "")[:60], f"{flt(m.downtime_hours):g} h", {"money": m.cost, "currency": cur}, m.done_by or "—"]})
		return {"title": _("Maintenance & downtime"), "cols": [{"label": _("Date")}, {"label": _("Equipment")}, {"label": _("Job")}, {"label": _("What was done")}, {"label": _("Downtime")},
			{"label": _("Cost"), "cls": "num"}, {"label": _("By")}], "rows": rows, "empty": _("No maintenance yet.")}
	chip = chip or "all"
	rows = []
	for e in _eqs():
		fl = S.eq_flags(e)
		if chip in ("Own", "Hired") and e.ownership != chip:
			continue
		if chip == "alerts" and not fl:
			continue
		if not _q(q, e.equipment_name, e.kind, e.project, e.reg_no, e.supplier):
			continue
		f = S.eq_fig(e)
		b = [_btn(_("Breakdown"), "eq_status", e.name, args={"status": "Breakdown"})] if e.status == "Working" else [_btn(_("Working"), "eq_status", e.name, True, args={"status": "Working"})] \
			if e.status in ("Breakdown", "Idle") else []
		rows.append({"dt": "Construction Equipment", "name": e.name, "cells": [{"main": e.equipment_name, "sub": " · ".join(x for x in (_(e.kind), e.reg_no) if x)},
			_pcell(e.project) if e.project else "—", {"main": _(e.ownership), "sub": (_("{0} · ₹{1:,.0f}/{2}").format(e.supplier, flt(e.hire_rate), _(e.hire_basis).lower()) if e.ownership == "Hired" else "")},
			{"bar": min(100, f.util)}, {"main": f"{f.hours:g} h", "sub": _("diesel {0:g} L").format(f.diesel), "late": 1 if f.over_diesel else 0},
			{"main": f"{flt(e.last_hmr):g}", "sub": _("service at {0:g}").format(flt(e.next_service_hmr)) if flt(e.next_service_hmr) else ""},
			{"pill": _(e.status), "tone": {"Working": "green", "Breakdown": "red", "Idle": "orange"}.get(e.status, "grey"), "sub": "; ".join(fl)[:60], "late": 1 if fl else 0},
			{"buttons": b} if b else ""]})
	return {"title": _("Equipment register — this month"), "cols": [{"label": _("Equipment")}, {"label": _("Site")}, {"label": _("Ownership")}, {"label": _("Utilisation")},
		{"label": _("Hours · diesel")}, {"label": _("HMR")}, {"label": _("Status")}, {"label": ""}], "rows": rows, "empty": _("No equipment here.")}
