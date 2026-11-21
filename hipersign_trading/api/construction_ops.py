"""v1.9.1 stage B3 (prototype C12): the site diary and productivity against standard; diesel against the norm and the
monthly hire bills of hired plant; returnable formwork at the sites and scrap sales; mobilisation advances to
subcontractors, free-issue material reconciled against the work billed, and the margin on each subcontracted scope.

Money:
- hire bill → Purchase Invoice to the hirer: Plant & Equipment Hire on the project, input GST, TDS 194I 2% deducted;
- scrap sale → Sales Invoice to the highest bidder: Other Income - Scrap, output GST 18%, TCS 1% (section 206C(1)) collected;
- advance to a subcontractor → Dr Advances to Subcontractors, Cr Bank; each running bill recovers its % (the bill's
  purchase invoice credits Advances to Subcontractors);
- excess free-issue material → the running bill's material recovery (factor × rate, from the material norm)."""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, get_first_day, get_last_day, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import construction_site as S
from hipersign_trading.api import projects as P

MD, PM, PMS, QS, SE, SK, HR, PLANT, AM, AU = S.MD, S.PM, S.PMS, S.QS, S.SE, S.SK, S.HR, S.PLANT, S.AM, S.AU
DIESEL_RATE = 92  # ₹ a litre (HSD, outside GST) — the value of diesel burnt above the norm
RET_HIRE = 4  # % of value a month while returnable formwork stays at a site
HIRE_ITEM, SCRAP_ITEM = "HS-PLANT-HIRE", "HS-SCRAP-SALE"


def _has(dt):
	return frappe.db.exists("DocType", dt)


def _who():
	return S._who()


def _service_item(code, name, sales, purchase, hsn):
	if not frappe.db.exists("Item", code):
		grp = "Services" if frappe.db.exists("Item Group", "Services") else frappe.db.get_value("Item Group", {"is_group": 0})
		it = frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": name, "item_group": grp, "stock_uom": "Nos", "is_stock_item": 0, "is_sales_item": sales,
			"is_purchase_item": purchase})
		if it.meta.has_field("gst_hsn_code") and frappe.db.exists("GST HSN Code", hsn):
			it.gst_hsn_code = hsn
		it.flags.ignore_permissions = True
		it.insert()
	return code


def accounts(company):
	liab = P._group(company, "Liability", ("Duties and Taxes", "Current Liabilities"))
	inc = P._group(company, "Income", ("Indirect Income", "Income"))
	return frappe._dict(tds_hire=P._account(company, "TDS Payable - 194I", "Liability", liab), tcs=P._account(company, "TCS Payable - 206C", "Liability", liab),
		scrap=P._account(company, "Other Income - Scrap", "Income", inc, "Income Account"))


# ================================================================ site diary
def diary_validate(doc):
	if doc.project and not CN.is_cn(doc.project):
		frappe.throw(_("{0} is not a Construction (India) project.").format(doc.project))
	doc.company = frappe.get_cached_value("Project", doc.project, "company")
	if getdate(doc.diary_date) > getdate(today()):
		frappe.throw(_("The diary is written on the day — not for a date ahead."))
	if frappe.db.exists("Site Diary", {"project": doc.project, "diary_date": doc.diary_date, "name": ["!=", doc.name or ""]}):
		frappe.throw(_("{0} already has its diary for {1} — add to that page.").format(doc.project, frappe.format(doc.diary_date, {"fieldtype": "Date"})))
	doc.recorded_by = doc.recorded_by or _who()
	if (doc.instructions or "").strip():
		if doc.instruction_status in (None, "", "None"):
			doc.instruction_status = "To confirm in writing"
	elif doc.instruction_status != "None":
		doc.instruction_status = "None"


def _sd(name):
	d = S._doc("Site Diary", name)
	if d.instruction_status != "To confirm in writing":
		frappe.throw(_("{0} has no instruction waiting ({1}).").format(name, _(d.instruction_status)))
	return d


def _a_sd_confirm(name, a):
	CN._need([SE, PM, QS, MD], _("Recording the written confirmation"))
	d = _sd(name)
	d.instruction_status = "Confirmed in writing"
	if a.get("ref"):
		d.instructions = f"{d.instructions}\n— {_('confirmed')}: {a.get('ref')}"
	d.save()
	return {"message": _("{0}: instruction confirmed in writing").format(name)}


def _a_sd_nocost(name, a):
	CN._need([QS, PM, MD], _("Closing an instruction without cost"))
	d = _sd(name)
	d.instruction_status = "No cost effect"
	d.save()
	return {"message": _("{0}: no cost or time effect").format(name)}


def _a_sd_ei(name, a):
	"""The instruction changes the scope — an extra item is raised to price and send to the client."""
	CN._need([QS, PM, MD], _("Raising an extra item"))
	frappe.has_permission("Extra Item", "create", throw=True)
	d = _sd(name)
	ei = frappe.get_doc({"doctype": "Extra Item", "project": d.project, "title": (a.get("title") or d.instructions.split("\n")[0])[:140], "kind": a.get("kind") or "Extra item",
		"amount": flt(a.get("amount")), "status": "Draft", "raised_on": today(), "raised_by": _who(), "reference": _("Site diary {0} of {1}").format(d.name,
		frappe.format(d.diary_date, {"fieldtype": "Date"})), "notes": _("Instruction by {0}: {1}").format(d.instruction_from or _("client"), d.instructions)})
	ei.insert()
	d.instruction_status, d.extra_item = "Raised as extra item", ei.name
	d.save()
	return {"message": _("{0} raised from {1} — price it and send to the client").format(ei.name, name), "open": ["Extra Item", ei.name]}


def diaries(names, f=None):
	return frappe.get_list("Site Diary", filters=dict({"project": ["in", names or [""]]}, **(f or {})), fields=["name", "project", "diary_date", "recorded_by", "weather", "visitors",
		"instructions", "instruction_from", "instruction_status", "extra_item", "events", "safety"], order_by="diary_date desc", limit_page_length=0) if _has("Site Diary") and frappe.has_permission("Site Diary", "read") else []


# ================================================================ productivity
def productivity(names, days=30):
	"""Per site and standard: the DPR quantities of the matching activities ÷ the man-days spent on them."""
	if not _has("Productivity Norm"):
		return []
	N = frappe.get_all("Productivity Norm", fields=["name", "trade", "activity", "match", "unit", "output_per_manday"])
	D = frappe.get_all("Daily Progress Report", filters={"project": ["in", names or [""]], "report_date": [">=", add_days(today(), -days)], "status": ["!=", "Draft"], "mandays": [">", 0]},
		fields=["project", "activity", "trade", "actual_qty", "mandays", "unit"])
	out = []
	for pj in names:
		for n in N:
			k = (n.match or "").lower()
			R = [d for d in D if d.project == pj and k and k in (d.activity or "").lower()]
			if not R:
				continue
			q, md = sum(flt(d.actual_qty) for d in R), sum(flt(d.mandays) for d in R)
			act = q / md if md else 0
			out.append(frappe._dict(project=pj, trade=n.trade, activity=n.activity, unit=n.unit or R[0].unit, norm=flt(n.output_per_manday), qty=q, mandays=md, actual=act,
				pct=act / flt(n.output_per_manday) * 100 if flt(n.output_per_manday) else 0, reports=len(R)))
	return out


# ================================================================ diesel and hire bills
def month_range(m):
	m = get_first_day(m)
	return m, get_last_day(m)


def hire_fig(e, month):
	"""The hire bill of a hired machine for a month: logbook hours (or days), the minimum hours, the amount."""
	a, b = month_range(month)
	L = frappe.get_all("Equipment Log", filters={"equipment": e.name, "log_date": ["between", [a, b]]}, fields=["hours", "log_date"])
	h = sum(flt(x.hours) for x in L)
	days = len([x for x in L if flt(x.hours) > 0])
	mn = flt(e.get("min_hours_month"))
	basis = e.hire_basis or "Hour"
	bill = max(h, mn) if basis == "Hour" and L else h if basis == "Hour" else days if basis == "Day" else (1 if L else 0)
	pi = frappe.db.get_value("Purchase Invoice", {"hs_equipment": e.name, "hs_hire_month": a, "docstatus": 1}, ["name", "grand_total"], as_dict=True) \
		if frappe.get_meta("Purchase Invoice").has_field("hs_equipment") else None
	return frappe._dict(month=a, hours=h, days=days, min=mn, basis=basis, billable=bill, rate=flt(e.hire_rate), amount=flt(bill * flt(e.hire_rate), 2), logs=len(L),
		invoice=pi.name if pi else None, short=max(0, mn - h) if basis == "Hour" and L else 0)


def diesel_fig(e, start=None, end=None):
	f = S.eq_fig(e, start, end)
	norm = flt(e.diesel_norm_lph)
	ex = max(0, f.diesel - f.hours * norm) if norm else 0
	return frappe._dict(hours=f.hours, diesel=f.diesel, rate=f.diesel_rate, norm=norm, excess=ex, value=ex * DIESEL_RATE, over=bool(f.over_diesel))


def _a_eq_hire_book(name, a):
	"""Books the month's hire bill of a hired machine: logbook hours (at least the minimum) × rate, GST, TDS 194I 2%."""
	CN._need([AM, AU, PM, MD, PLANT], _("Booking a hire bill"))
	e = frappe.get_doc("Construction Equipment", name)
	if e.ownership != "Hired" or not e.supplier:
		frappe.throw(_("{0} is not hired.").format(e.equipment_name))
	m = getdate(a.get("month") or add_months(get_first_day(today()), -1))
	if get_first_day(m) >= get_first_day(today()):
		frappe.throw(_("The hire bill is booked once the month is over."))
	H = hire_fig(e, m)
	if H.invoice:
		frappe.throw(_("The {0} hire bill of {1} is already booked — {2}.").format(frappe.format(H.month, {"fieldtype": "Date"}), e.equipment_name, H.invoice))
	if not H.logs:
		frappe.throw(_("No logbook entries for {0} in that month.").format(e.equipment_name))
	co = e.company or frappe.get_cached_value("Project", e.project, "company")
	p = frappe.get_cached_doc("Project", e.project) if e.project else None
	cc = (p.cost_center if p else None) or frappe.get_cached_value("Company", co, "cost_center")
	addr = (p.get("hs_cn_address") if p else None) or CN.branch_address(co)
	acc = accounts(co)
	d = a.get("date") or today()
	unit = {"Hour": _("hours"), "Day": _("days"), "Month": _("month")}[H.basis]
	pi = frappe.get_doc({"doctype": "Purchase Invoice", "company": co, "supplier": e.supplier, "posting_date": d, "set_posting_time": 1,
		"bill_no": a.get("bill_no") or f"HIRE/{e.reg_no or e.name}/{H.month.strftime('%m-%Y')}", "bill_date": d, "due_date": add_days(d, 30), "project": e.project, "cost_center": cc,
		"hs_equipment": e.name, "hs_hire_month": H.month,
		"items": [{"item_code": _service_item(HIRE_ITEM, _("Hire of plant & machinery"), 0, 1, "997313"), "qty": 1, "rate": H.amount,
			"expense_account": P.accounts(co).heads["Plant & equipment"], "project": e.project, "cost_center": cc,
			"description": _("{0} ({1}) — {2}: {3:g} {4} × ₹{5:,.2f}{6}").format(e.equipment_name, e.reg_no or "", H.month.strftime("%B %Y"), H.billable, unit, H.rate,
				_(" (logbook {0:g} h, minimum {1:g} h)").format(H.hours, H.min) if H.short else "")}],
		"remarks": _("Hire bill {0} — {1}").format(e.equipment_name, H.month.strftime("%B %Y"))})
	if addr:
		pi.billing_address = pi.shipping_address = addr
	S._apply_taxes(pi, S.input_tax_template(co, addr, e.supplier))
	tds = flt(H.amount * .02, 0)
	pi.append("taxes", {"charge_type": "Actual", "account_head": acc.tds_hire, "tax_amount": tds, "description": _("TDS u/s 194I @ 2%"), "category": "Total",
		"add_deduct_tax": "Deduct", "cost_center": cc})
	pi.flags.ignore_permissions = True
	pi.flags.hs_system_entry = True
	pi.set_missing_values()
	with CN._elevated():
		pi.insert()
		pi.submit()
	return {"message": _("Hire bill {0} booked — {1} + GST, TDS {2}").format(pi.name, CN.inr(H.amount), CN.inr(tds)), "open": ["Purchase Invoice", pi.name]}


# ================================================================ returnables and scrap
def returnables(names):
	"""Returnable items (formwork, props, scaffolding) lying at each site store, since when, and their hire charge."""
	items = frappe.get_all("Item", filters={"hs_returnable": 1}, pluck="name") if frappe.get_meta("Item").has_field("hs_returnable") else []
	if not items:
		return []
	out = []
	t = getdate(today())
	for pj in names:
		w = frappe.db.get_value("Project", pj, "hs_site_warehouse")
		if not w:
			continue
		for b in frappe.get_all("Bin", filters={"warehouse": w, "item_code": ["in", items], "actual_qty": [">", 0]}, fields=["item_code", "actual_qty", "stock_value", "valuation_rate"]):
			since = frappe.db.get_value("Stock Ledger Entry", {"warehouse": w, "item_code": b.item_code, "is_cancelled": 0, "actual_qty": [">", 0]}, "posting_date",
				order_by="posting_date asc")
			months = max(0, date_diff(t, since) / 30) if since else 0
			pend = flt(frappe.db.sql("""select sum(d.transfer_qty) from `tabStock Entry Detail` d join `tabStock Entry` e on e.name = d.parent where e.docstatus = 0
				and e.purpose = 'Material Transfer' and d.s_warehouse = %s and d.item_code = %s""", (w, b.item_code))[0][0])
			out.append(frappe._dict(project=pj, warehouse=w, item=b.item_code, item_name=frappe.get_cached_value("Item", b.item_code, "item_name"),
				uom=frappe.get_cached_value("Item", b.item_code, "stock_uom"), qty=flt(b.actual_qty), value=flt(b.stock_value), since=since, months=months,
				per_month=flt(b.stock_value) * RET_HIRE / 100, charged=flt(b.stock_value) * RET_HIRE / 100 * months, returning=pend))
	return out


def _a_ret_back(name, a):
	"""Returnable material goes back to the central store: a transfer request from the site store (dispatch and delivery as usual)."""
	CN._need([SK, SE, PM, MD], _("Returning material to the central store"))
	frappe.has_permission("Stock Entry", "create", throw=True)
	item = a.get("item")
	R = [r for r in returnables([name]) if r.item == item]
	if not R:
		frappe.throw(_("No {0} lying at {1}.").format(item, name))
	r = R[0]
	qty = flt(a.get("qty")) or (r.qty - r.returning)
	if qty <= 0 or qty > r.qty - r.returning + 1e-6:
		frappe.throw(_("Only {0:g} {1} can go back ({2:g} already on a return request).").format(r.qty - r.returning, r.uom, r.returning))
	co = frappe.get_cached_value("Project", name, "company")
	cs = S.central_store(co)
	se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Transfer", "purpose": "Material Transfer", "company": co, "project": name,
		"hs_transfer_status": "Requested", "hs_destination": cs, "remarks": _("Return of {0} from {1} to the central store").format(r.item_name, name),
		"items": [{"item_code": item, "qty": qty, "s_warehouse": r.warehouse, "t_warehouse": cs, "project": name}]})
	se.insert()
	return {"message": _("{0} — return of {1:g} {2} {3} requested; dispatch it with the vehicle").format(se.name, qty, r.uom, r.item_name), "open": ["Stock Entry", se.name]}


def scrap_validate(doc):
	if doc.project:
		doc.company = frappe.get_cached_value("Project", doc.project, "company")
	for b in doc.bids:
		if flt(b.amount) <= 0:
			frappe.throw(_("Row {0}: enter the bid amount.").format(b.idx))
	if len({b.bidder for b in doc.bids}) < len(doc.bids):
		frappe.throw(_("One bid per bidder."))
	if doc.status == "Sold" and not doc.sales_invoice:
		frappe.throw(_("A lot is sold through the sale action."))


def _a_scrap_invite(name, a):
	CN._need([MD, PM, SK, AM, "Stock Manager"], _("Inviting bids for scrap"))
	d = S._doc("Scrap Lot", name)
	if d.status != "Identified":
		frappe.throw(_("{0} is {1}.").format(name, _(d.status)))
	d.status = "Bids invited"
	d.save()
	return {"message": _("{0}: sealed bids invited — enter them on the lot as they come").format(name)}


def _a_scrap_sell(name, a):
	"""Sells the lot to the highest bidder (a PCB-authorised one for hazardous waste): Sales Invoice with GST 18% and TCS 1%."""
	CN._need([MD, PM, AM], _("Selling scrap"))
	d = S._doc("Scrap Lot", name)
	if d.status != "Bids invited":
		frappe.throw(_("{0} is {1} — invite bids first.").format(name, _(d.status)))
	B = [b for b in d.bids if not cint(d.hazardous) or cint(b.pcb_authorised)]
	if not B:
		frappe.throw(_("No eligible bid on {0}{1}.").format(name, _(" — hazardous waste goes only to a PCB-authorised buyer") if cint(d.hazardous) else ""))
	h1 = sorted(B, key=lambda b: -flt(b.amount))[0]
	if flt(d.estimate) and flt(h1.amount) < flt(d.estimate) * .9 and MD not in frappe.get_roles() and frappe.session.user != "Administrator":
		frappe.throw(_("The best bid {0} is more than 10% below the estimate {1} — the MD decides.").format(CN.inr(h1.amount), CN.inr(d.estimate)))
	co = d.company
	acc = accounts(co)
	addr = (frappe.get_cached_value("Project", d.project, "hs_cn_address") if d.project else None) or CN.branch_address(co, h1.bidder)
	tpl = CN._tax_template(co, addr, h1.bidder)
	cc = (frappe.get_cached_value("Project", d.project, "cost_center") if d.project else None) or frappe.get_cached_value("Company", co, "cost_center")
	dt = a.get("date") or today()
	si = frappe.get_doc({"doctype": "Sales Invoice", "company": co, "customer": h1.bidder, "posting_date": dt, "set_posting_time": 1, "due_date": dt,
		"cost_center": cc,  # the site goes on the line (the invoice's project must be the project's own client) "remarks": _("Scrap lot {0} — {1}").format(d.name, d.description),
		"items": [{"item_code": _service_item(SCRAP_ITEM, _("Sale of scrap"), 1, 0, "72044900"), "qty": 1, "rate": flt(h1.amount), "income_account": acc.scrap, "cost_center": cc,
			"project": d.project, "description": _("{0} — {1:g} {2} (lot {3})").format(d.description, flt(d.qty), d.uom or "", d.name)}], "taxes_and_charges": tpl})
	if addr:
		si.company_address = addr
	ca = CN._customer_address(h1.bidder)
	if ca:
		si.customer_address = ca
	if tpl:
		for r in frappe.get_doc("Sales Taxes and Charges Template", tpl).taxes:
			si.append("taxes", {"charge_type": r.charge_type, "account_head": r.account_head, "rate": r.rate, "description": r.description, "cost_center": cc})
	si.append("taxes", {"charge_type": "On Previous Row Total", "row_id": len(si.taxes), "account_head": acc.tcs, "rate": 1, "description": _("TCS u/s 206C(1) @ 1% — scrap"),
		"cost_center": cc})
	si.flags.ignore_permissions = True
	with CN._elevated():
		si.insert()
		si.submit()
	d.db_set({"status": "Sold", "buyer": h1.bidder, "sale_amount": flt(h1.amount), "sold_on": dt, "sales_invoice": si.name})
	return {"message": _("{0} sold to {1} — {2} + GST + TCS = {3}").format(name, h1.bidder, CN.inr(h1.amount), CN.inr(si.grand_total)), "open": ["Sales Invoice", si.name]}


# ================================================================ subcontractors: advances, free issue, margin
def sub_adv(w):
	"""Advance given to a work order, what the running bills recovered and the balance."""
	paid = flt(frappe.db.get_value("Subcontractor Work Order", w, "advance_paid"))
	B = frappe.get_all("Subcontractor Bill", filters={"work_order": w, "status": ["!=", "Cancelled"], "advance_recovery": [">", 0]}, fields=["name", "bill_no", "advance_recovery"],
		order_by="bill_no asc")
	rec = sum(flt(b.advance_recovery) for b in B)
	return frappe._dict(paid=paid, recovered=rec, balance=max(0, paid - rec), bills=B)


def wo_validate(doc):
	if flt(doc.advance) > flt(doc.value) * .2 + 1 and flt(doc.value):
		frappe.throw(_("A mobilisation advance is at most 20% of the work order ({0}).").format(CN.inr(flt(doc.value) * .2)))
	if flt(doc.advance) and not flt(doc.advance_recovery_pct):
		doc.advance_recovery_pct = 10
	if flt(doc.advance_paid) and flt(doc.advance) < flt(doc.advance_paid):
		frappe.throw(_("{0} is already paid as advance.").format(CN.inr(doc.advance_paid)))


def bill_advance(doc, w):
	"""A draft running bill recovers the work order's advance at its % until nil."""
	if doc.status != "Draft" or not flt(w.get("advance_paid")) or flt(doc.advance_recovery):
		return
	A = sub_adv(w.name)
	left = A.balance + (flt(doc.get_db_value("advance_recovery")) if not doc.is_new() else 0)
	doc.advance_recovery = flt(min(flt(doc.gross) * flt(w.advance_recovery_pct or 10) / 100, left), 0)


def _a_swo_adv_pay(name, a):
	CN._need([AM, AU, MD], _("Paying a subcontractor's advance"))
	w = S._doc("Subcontractor Work Order", name, "read")
	if w.status != "Active":
		frappe.throw(_("{0} is {1} — the advance is paid on an issued work order.").format(name, _(w.status)))
	amt = flt(a.get("amount")) or flt(w.advance) - flt(w.advance_paid)
	if amt <= 0:
		frappe.throw(_("No advance due on {0}.").format(name))
	if amt > flt(w.advance) - flt(w.advance_paid) + 1:
		frappe.throw(_("{0} is more than the advance still due ({1}).").format(CN.inr(amt), CN.inr(flt(w.advance) - flt(w.advance_paid))))
	co = w.company
	cc = frappe.get_cached_value("Project", w.project, "cost_center") or frappe.get_cached_value("Company", co, "cost_center")
	d = a.get("date") or today()
	je = frappe.get_doc({"doctype": "Journal Entry", "company": co, "posting_date": d, "voucher_type": "Bank Entry", "cheque_no": a.get("ref") or f"ADV/{name}", "cheque_date": d,
		"user_remark": _("Mobilisation advance to {0} — {1}, recovered at {2:g}% of each bill").format(w.supplier, name, flt(w.advance_recovery_pct)),
		"accounts": [{"account": S.accounts(co).sub_adv, "debit_in_account_currency": amt, "project": w.project, "cost_center": cc},
			{"account": CN.bank_account(co), "credit_in_account_currency": amt, "project": w.project, "cost_center": cc}]})
	je.flags.hs_system_entry = True
	with CN._elevated():
		je.insert()
		je.submit()
	w.db_set({"advance_paid": flt(w.advance_paid) + amt, "advance_paid_on": d, "advance_entry": je.name})
	return {"message": _("Advance {0} paid to {1} — {2}").format(CN.inr(amt), w.supplier, je.name), "open": ["Journal Entry", je.name]}


def free_issue(w):
	"""Free-issue material of a labour-only work order: issued less returned against the theoretical for the work billed
	(work order lines × the material norms) plus wastage; the excess at the recovery factor × rate."""
	w = frappe.get_doc("Subcontractor Work Order", w) if isinstance(w, str) else w
	cum = {}
	for b in frappe.get_all("Subcontractor Bill", filters={"work_order": w.name, "status": ["!=", "Cancelled"]}, pluck="name"):
		for it in frappe.get_all("Subcontractor Bill Item", filters={"parent": b}, fields=["item_no", "this_qty"]):
			cum[it.item_no] = cum.get(it.item_no, 0) + flt(it.this_qty)
	out = {}
	for n in S.norms():
		key = (n.boq_match or "").lower()
		for r in w.items:
			if key and key in (r.description or "").lower() and (not n.boq_unit or (r.unit or "").lower() == n.boq_unit.lower()):
				x = out.setdefault(n.item, frappe._dict(item=n.item, theory=0.0, allowed=0.0, factor=flt(n.recovery_factor) or 1.5))
				th = flt(cum.get(r.item_no)) * flt(n.qty_per_unit)
				x.theory += th
				x.allowed += th * (1 + flt(n.wastage_pct) / 100)
	mv = frappe.db.sql("""select d.item_code, e.purpose, sum(d.transfer_qty) q from `tabStock Entry Detail` d join `tabStock Entry` e on e.name = d.parent
		where e.docstatus = 1 and e.hs_sub_wo = %s and e.purpose in ('Material Issue', 'Material Receipt') group by d.item_code, e.purpose""", w.name, as_dict=True) \
		if frappe.get_meta("Stock Entry").has_field("hs_sub_wo") else []
	for m in mv:
		x = out.setdefault(m.item_code, frappe._dict(item=m.item_code, theory=0.0, allowed=0.0, factor=1.5))
		x["issued" if m.purpose == "Material Issue" else "returned"] = flt(x.get("issued" if m.purpose == "Material Issue" else "returned")) + flt(m.q)
	res = []
	for x in out.values():
		x.issued, x.returned = flt(x.get("issued")), flt(x.get("returned"))
		if not x.issued:
			continue
		x.net = x.issued - x.returned
		x.excess = max(0, x.net - x.allowed)
		x.rate = flt(frappe.db.get_value("Bin", {"item_code": x.item, "valuation_rate": [">", 0]}, "valuation_rate")) or flt(frappe.db.get_value("Item", x.item, "valuation_rate"))
		x.recover = flt(x.excess * x.rate * x.factor, 0)
		x.uom = frappe.get_cached_value("Item", x.item, "stock_uom")
		x.item_name = frappe.get_cached_value("Item", x.item, "item_name")
		res.append(x)
	return res


def _a_swo_matrec(name, a):
	"""Puts the excess free-issue material not yet recovered on the work order's draft running bill."""
	CN._need([QS, PM, MD], _("Recovering excess material"))
	w = frappe.get_doc("Subcontractor Work Order", name)
	X = free_issue(w)
	due = sum(x.recover for x in X)
	b = frappe.db.get_value("Subcontractor Bill", {"work_order": name, "status": "Draft"}, "name", order_by="bill_no desc")
	if not b:
		frappe.throw(_("No draft running bill on {0} — the recovery goes on the next bill.").format(name))
	done = flt(frappe.db.sql("""select sum(material_recovery) from `tabSubcontractor Bill` where work_order = %s and status != 'Cancelled' and name != %s""", (name, b))[0][0])
	amt = max(0, flt(due - done, 0))
	if amt <= 0:
		frappe.throw(_("Nothing more to recover on {0} — {1} due, {2} recovered in earlier bills.").format(name, CN.inr(due), CN.inr(done)))
	sb = S._doc("Subcontractor Bill", b)
	sb.material_recovery = amt
	sb.save()
	return {"message": _("{0}: excess material {1} recovered on bill {2}").format(name, CN.inr(amt), b), "open": ["Subcontractor Bill", b]}


def margin(w):
	"""Our BOQ rate against the subcontract rate per line (the labour share of the BOQ rate for labour-only work)."""
	w = frappe.get_doc("Subcontractor Work Order", w) if isinstance(w, str) else w
	b = CN.boq(w.project)
	L = {r.item_no: r for r in (b.items if b else [])}
	lab = (w.kind or "").startswith("Labour")
	out = []
	for r in w.items:
		x = L.get(r.item_no)
		if not x:
			continue
		ours = flt(x.rate) * (flt(x.lab_share) / 100 if lab and flt(x.lab_share) else 1)
		out.append(frappe._dict(item_no=r.item_no, description=r.description, unit=r.unit, qty=flt(r.qty), ours=ours, theirs=flt(r.rate), share=flt(x.lab_share) if lab else 100,
			margin=(ours - flt(r.rate)) / ours * 100 if ours else 0, value=(ours - flt(r.rate)) * flt(r.qty)))
	return out


# ================================================================ flags, validation, actions
def flags(name):
	out = []
	t = getdate(today())
	if _has("Site Diary"):
		for d in frappe.get_all("Site Diary", filters={"project": name, "instruction_status": "To confirm in writing", "diary_date": ["<", add_days(t, -7)]},
				fields=["name", "diary_date", "instructions"], order_by="diary_date asc"):
			out.append({"lvl": "Medium", "text": _("Verbal instruction of {0} not confirmed in writing — {1}").format(frappe.format(d.diary_date, {"fieldtype": "Date"}),
				(d.instructions or "")[:60]), "open": ["Site Diary", d.name]})
	for e in frappe.get_all("Construction Equipment", filters={"project": name, "status": ["!=", "Off-hired"], "diesel_norm_lph": [">", 0]},
			fields=["name", "equipment_name", "diesel_norm_lph", "planned_hours_month", "hire_rate", "hire_basis", "ownership", "supplier", "min_hours_month"]):
		D = diesel_fig(e)
		if D.over and D.value > 5000:
			out.append({"lvl": "Medium", "text": _("{0}: diesel {1:.1f} L/h against the norm {2:g} — {3} excess this month").format(e.equipment_name, D.rate, D.norm, CN.inr(D.value)),
				"open": ["Construction Equipment", e.name]})
	last = add_months(get_first_day(t), -1)
	for e in frappe.get_all("Construction Equipment", filters={"project": name, "ownership": "Hired"}, fields=["name", "equipment_name", "hire_rate", "hire_basis", "min_hours_month"]):
		H = hire_fig(e, last)
		if H.logs and not H.invoice and t.day > 7:
			out.append({"lvl": "Medium", "text": _("{0}: {1} hire bill not booked — {2}").format(e.equipment_name, last.strftime("%B"), CN.inr(H.amount)),
				"open": ["Construction Equipment", e.name]})
	return out


VALIDATE = {"Site Diary": diary_validate, "Scrap Lot": scrap_validate}
ACTIONS = {"sd_confirm": _a_sd_confirm, "sd_nocost": _a_sd_nocost, "sd_ei": _a_sd_ei, "eq_hire_book": _a_eq_hire_book, "ret_back": _a_ret_back, "scrap_invite": _a_scrap_invite,
	"scrap_sell": _a_scrap_sell, "swo_adv_pay": _a_swo_adv_pay, "swo_matrec": _a_swo_matrec}
