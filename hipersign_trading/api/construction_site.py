"""v1.9.0 stage A3 (prototypes C3, C6, C7): Construction (India) — site resources (feature cn_site).

  · procurement & stores on ERPNext: indents (Material Request with the project) checked against what the BOQ still needs
    (Material Norm: material per BOQ unit + allowed wastage, less issued, in the site store and on order) — above it the PM
    approves; supplier quotations compared on landed cost (basic + freight + unloading, technically compliant) and the PO to
    L1; receipts at the site store (accepted / rejected) and the bill booked from the receipt; material issues to the work;
    material reconciliation — theoretical consumption of the work measured vs issued, the excess valued and recovered,
  · vendors: GSTIN, PAN, MSME, KYC; scorecard from real POs and receipts; rate contracts (ERPNext Blanket Order),
  · central store & logistics: transfers central → site through Goods In Transit (vehicle, driver, e-way bill; dispatched →
    delivered when the site confirms), stock ledger and dead stock,
  · subcontractors: work orders (labour-only with free-issue materials, or item rate), running bills — QS certifies, PM
    approves (books the purchase invoice: GST, TDS 194C, retention and recoveries), accounts pay — held while the contractor's
    monthly labour-law documents (wage register, PF ECR, ESI) are missing,
  · own workers: register with state minimum wages and the labour-register checks, the weekly muster (pay week Wednesday →
    Tuesday, OT at double rate, PF 12% / ESI 0.75% with their ceilings, advance recovery up to half the wages) approved by
    the PM and paid by UPI (wage journal), worker advances (up to four weeks' wages, above ₹5,000 the PM approves),
  · plant & equipment: register, log sheets (hour meter never goes back), maintenance with downtime and cost.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, get_first_day, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import projects as P

MD, PM, PMS, QS, SE, SK, HR, PLANT, AM, AU = ("Managing Director", "Project Manager", "Projects Manager", "Quantity Surveyor", "Site Engineer", "Storekeeper",
	"HR & Admin", "Plant Manager", "Accounts Manager", "Accounts User")
BUY = ("Purchase Manager", "Purchase User")
PF_CEILING_DAY = 15000 / 26   # PF on wages up to ₹15,000 a month
ESI_CEILING_DAY = 21000 / 26  # ESI where wages are up to ₹21,000 a month
SUB_ITEM = "CN-SUBCON"


def limits():
	s = frappe.get_cached_doc("Hipersign Settings")
	return frappe._dict(wadv=flt(s.get("cn_worker_advance_limit")) or 5000)


def week_start(d=None):
	"""The pay week runs Wednesday → Tuesday."""
	d = getdate(d or today())
	return add_days(d, -((d.weekday() - 2) % 7))


# ---------------------------------------------------------------- accounts, items, stores
def accounts(company):
	cache = P._local("hs_cn_site_acc")
	if company in cache:
		return cache[company]
	base = P.accounts(company)
	cur_assets = P._group(company, "Asset", ("Loans and Advances (Assets)", "Current Assets"))
	cur_liab = P._group(company, "Liability", ("Duties and Taxes", "Current Liabilities"))
	liab = P._group(company, "Liability", ("Current Liabilities",))
	a = frappe._dict(
		heads=base.heads, retention_payable=base.retention_payable,
		tds_payable=P._account(company, "TDS Payable - 194C", "Liability", cur_liab),
		pf_payable=P._account(company, "PF Payable", "Liability", liab),
		esi_payable=P._account(company, "ESI Payable", "Liability", liab),
		worker_adv=P._account(company, "Advances to Workers", "Asset", cur_assets),
		sub_adv=P._account(company, "Advances to Subcontractors", "Asset", cur_assets),
	)
	cache[company] = a
	return a


def sub_item():
	if not frappe.db.exists("Item", SUB_ITEM):
		it = frappe.get_doc({"doctype": "Item", "item_code": SUB_ITEM, "item_name": _("Subcontract works"), "item_group": "Services" if frappe.db.exists("Item Group", "Services")
			else frappe.db.get_value("Item Group", {"is_group": 0}), "stock_uom": "Nos", "is_stock_item": 0, "is_sales_item": 0, "is_purchase_item": 1})
		if it.meta.has_field("gst_hsn_code") and frappe.db.exists("GST HSN Code", "995411"):
			it.gst_hsn_code = "995411"
		it.flags.ignore_permissions = True
		it.insert()
	return SUB_ITEM


def central_store(company):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = f"Central Store - {abbr}"
	if not frappe.db.exists("Warehouse", name):
		parent = frappe.db.get_value("Warehouse", {"company": company, "is_group": 1}, "name", order_by="lft asc")
		frappe.get_doc({"doctype": "Warehouse", "warehouse_name": "Central Store", "company": company, "parent_warehouse": parent}).insert(ignore_permissions=True)
	return name


def rejected_store(company):
	"""Where rejected material waits for the supplier to take it back."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = f"Rejected Material - {abbr}"
	if not frappe.db.exists("Warehouse", name):
		parent = frappe.db.get_value("Warehouse", {"company": company, "is_group": 1}, "name", order_by="lft asc")
		frappe.get_doc({"doctype": "Warehouse", "warehouse_name": "Rejected Material", "company": company, "parent_warehouse": parent}).insert(ignore_permissions=True)
	return name


def transit_store(company):
	return frappe.db.get_value("Warehouse", {"company": company, "warehouse_type": "Transit", "is_group": 0}) or \
		frappe.db.get_value("Warehouse", {"company": company, "warehouse_name": "Goods In Transit"})


def input_tax_template(company, company_address=None, supplier=None):
	inn = frappe.db.get_value("Purchase Taxes and Charges Template", {"company": company, "name": ["like", "Input GST In-state%"]}, "name")
	out = frappe.db.get_value("Purchase Taxes and Charges Template", {"company": company, "name": ["like", "Input GST Out-state%"]}, "name")
	if not (company_address and supplier and out) or not frappe.get_meta("Address").has_field("gst_state"):
		return inn
	cs = frappe.db.get_value("Address", company_address, "gst_state")
	sa = frappe.db.get_value("Dynamic Link", {"link_doctype": "Supplier", "link_name": supplier, "parenttype": "Address"}, "parent")
	ss = frappe.db.get_value("Address", sa, "gst_state") if sa else None
	return out if cs and ss and cs != ss else inn


def _apply_taxes(doc, tpl):
	doc.taxes_and_charges = tpl
	doc.set("taxes", [])
	if tpl:
		for r in frappe.get_doc("Purchase Taxes and Charges Template", tpl).taxes:
			doc.append("taxes", {"charge_type": r.charge_type, "account_head": r.account_head, "rate": r.rate, "description": r.description,
				"category": r.category or "Total", "add_deduct_tax": r.add_deduct_tax or "Add"})


# ---------------------------------------------------------------- material need and reconciliation
def norms():
	return frappe.get_all("Material Norm", fields=["name", "item", "boq_match", "boq_unit", "qty_per_unit", "wastage_pct", "recovery_factor"]) \
		if frappe.db.exists("DocType", "Material Norm") else []


def _issued(project, item):
	return flt(frappe.db.sql("""select sum(d.transfer_qty) from `tabStock Entry Detail` d join `tabStock Entry` e on e.name = d.parent
		where e.docstatus = 1 and e.purpose = 'Material Issue' and d.item_code = %s and ifnull(d.project, e.project) = %s""", (item, project))[0][0])


def _in_store(project, item):
	w = frappe.db.get_value("Project", project, "hs_site_warehouse")
	return flt(frappe.db.get_value("Bin", {"item_code": item, "warehouse": w}, "actual_qty")) if w else 0


def _on_order(project, item, exclude_mr=None):
	mr = flt(frappe.db.sql("""select sum(i.stock_qty - i.ordered_qty) from `tabMaterial Request Item` i join `tabMaterial Request` m on m.name = i.parent
		where m.docstatus < 2 and m.status not in ('Stopped', 'Cancelled', 'Ordered', 'Received') and m.hs_project = %s and i.item_code = %s and m.name != %s""",
		(project, item, exclude_mr or ""))[0][0])
	po = flt(frappe.db.sql("""select sum((i.qty - i.received_qty) * i.conversion_factor) from `tabPurchase Order Item` i join `tabPurchase Order` o on o.name = i.parent
		where o.docstatus = 1 and o.status not in ('Closed', 'Completed') and o.hs_project = %s and i.item_code = %s""", (project, item))[0][0])
	return max(0, mr) + max(0, po)


def material_status(project, exclude_mr=None):
	"""Per material with a norm: the BOQ's full need (with wastage), theoretical use of the work measured, issued, in the site
	store, on order and still needed; the excess beyond the allowed wastage, valued, and what is recovered from the contractor."""
	b = CN.boq(project)
	if not b:
		return []
	out = {}
	for n in norms():
		key = n.boq_match.lower()
		lines = [r for r in b.items if key in (r.description or "").lower() and (not n.boq_unit or (r.unit or "").lower() == n.boq_unit.lower())]
		if not lines:
			continue
		x = out.setdefault(n.item, frappe._dict(item=n.item, need=0.0, theory=0.0, allowed=0.0, factor=flt(n.recovery_factor) or 1.5, lines=[]))
		x.need += sum(flt(r.qty) for r in lines) * flt(n.qty_per_unit) * (1 + flt(n.wastage_pct) / 100)
		th = sum(flt(r.qty) * flt(r.measured_pct) / 100 for r in lines) * flt(n.qty_per_unit)
		x.theory += th
		x.allowed += th * (1 + flt(n.wastage_pct) / 100)
		x.lines += [r.item_no for r in lines]
	for x in out.values():
		x.issued = _issued(project, x.item)
		x.in_store = _in_store(project, x.item)
		x.on_order = _on_order(project, x.item, exclude_mr)
		x.remaining = max(0, x.need - x.issued - x.in_store - x.on_order)
		x.wastage = (x.allowed / x.theory - 1) * 100 if x.theory else 0  # weighted over the norms of this material
		x.excess = max(0, x.issued - x.allowed)
		x.excess_pct = (x.issued / x.theory - 1) * 100 if x.theory else 0
		x.rate = flt(frappe.db.get_value("Bin", {"item_code": x.item, "valuation_rate": [">", 0]}, "valuation_rate")) or \
			flt(frappe.db.get_value("Item", x.item, "valuation_rate")) or flt(frappe.db.get_value("Item Price", {"item_code": x.item, "buying": 1}, "price_list_rate"))
		x.excess_value = x.excess * x.rate
		x.recovery = x.excess_value * x.factor
		x.uom = frappe.get_cached_value("Item", x.item, "stock_uom")
		x.item_name = frappe.get_cached_value("Item", x.item, "item_name")
	return list(out.values())


def mr_validate(doc, method=None):
	"""An indent for a Construction (India) project: above what the BOQ still needs, the PM approves."""
	if not doc.get("hs_project") or not CN.is_cn(doc.hs_project) or doc.material_request_type != "Purchase":
		return
	st = {x.item: x for x in material_status(doc.hs_project, exclude_mr=doc.name)}
	over = []
	for i in doc.items:
		i.project = i.project or doc.hs_project
		x = st.get(i.item_code)
		if x and flt(i.stock_qty or i.qty) > x.remaining + 0.001:
			over.append(_("{0}: {1:g} asked, {2:g} {3} still needed by the BOQ").format(i.item_code, flt(i.stock_qty or i.qty), round(x.remaining, 2), x.uom))
	doc.hs_over_boq = 1 if over else 0
	doc.hs_rejected_lines = "\n".join(over) if over else None


def mr_before_submit(doc, method=None):
	if doc.get("hs_project") and CN.is_cn(doc.hs_project) and cint(doc.get("hs_over_boq")) and not P._has(PM, MD):
		frappe.throw(_("This indent is above what the BOQ still needs — the Project Manager approves it.") + "\n" + (doc.hs_rejected_lines or ""))


def sq_validate(doc, method=None):
	"""Supplier quotation: landed cost = basic + freight + unloading (the comparison's basis)."""
	if doc.meta.has_field("hs_landed_total"):
		doc.hs_landed_total = flt(doc.base_net_total) + flt(doc.get("hs_freight")) + flt(doc.get("hs_unloading"))


def comparison(mr):
	rows = frappe.get_all("Supplier Quotation Item", filters={"material_request": mr, "docstatus": 1}, fields=["parent"], distinct=True)
	q = [frappe.get_doc("Supplier Quotation", r.parent) for r in rows]
	q = [x for x in q if x.status not in ("Expired", "Stopped")]
	q.sort(key=lambda x: (0 if cint(x.get("hs_tech_ok")) else 1, flt(x.get("hs_landed_total")) or flt(x.base_net_total)))
	return q


# ---------------------------------------------------------------- subcontractors
def sub_wo_validate(doc):
	for r in doc.items:
		r.amount = flt(flt(r.qty) * flt(r.rate), 2)
	doc.value = sum(flt(r.amount) for r in doc.items)
	if doc.supplier and not cint(doc.tds_pct):
		doc.tds_pct = 1 if frappe.db.get_value("Supplier", doc.supplier, "supplier_type") == "Individual" else 2


def compliance_ok(supplier, month=None):
	"""The contractor's wage register, PF ECR and ESI challan of the month before the bill are in (labour-only and labour
	contractors: the principal employer pays if they do not)."""
	m = get_first_day(add_months(month or today(), -1))
	r = frappe.db.get_value("Labour Compliance", {"supplier": supplier, "month": m}, ["wage_register", "pf_ecr", "esi_challan"], as_dict=True)
	return bool(r and r.wage_register and r.pf_ecr and r.esi_challan), m


def _labour_contractor(wo):
	return (frappe.db.get_value("Subcontractor Work Order", wo, "kind") or "").startswith("Labour")


def sub_bill_validate(doc):
	w = frappe.get_doc("Subcontractor Work Order", doc.work_order)
	doc.project, doc.supplier = w.project, w.supplier
	if doc.is_new():
		doc.gst_rate = doc.gst_rate if doc.gst_rate is not None and doc.gst_rate != "" else w.gst_rate
		doc.retention_pct = doc.retention_pct or w.retention_pct
		doc.tds_pct = doc.tds_pct or w.tds_pct
		if not cint(doc.bill_no):
			doc.bill_no = cint(frappe.db.count("Subcontractor Bill", {"work_order": w.name, "status": ["!=", "Cancelled"]})) + 1
	wol = {r.item_no: r for r in w.items}
	prev = {}
	for b in frappe.get_all("Subcontractor Bill", filters={"work_order": w.name, "status": ["!=", "Cancelled"], "name": ["!=", doc.name or ""], "bill_no": ["<", cint(doc.bill_no)]},
			pluck="name"):
		for it in frappe.get_all("Subcontractor Bill Item", filters={"parent": b}, fields=["item_no", "this_qty"]):
			prev[it.item_no] = prev.get(it.item_no, 0) + flt(it.this_qty)
	for it in doc.items:
		r = wol.get(it.item_no)
		if r:
			it.description, it.unit, it.wo_qty = it.description or r.description, it.unit or r.unit, r.qty
			it.rate = it.rate or r.rate
		it.prev_qty = flt(prev.get(it.item_no), 3)
		it.cum_qty = flt(it.prev_qty + flt(it.this_qty), 3)
		it.amount = flt(flt(it.this_qty) * flt(it.rate), 2)
		if r and flt(r.qty) and it.cum_qty > flt(r.qty) * 1.10 + 0.001:
			frappe.throw(_("Item {0}: {1:g} up to date is more than the work order quantity {2:g} + 10%.").format(it.item_no, it.cum_qty, flt(r.qty)))
	doc.gross = flt(sum(flt(i.amount) for i in doc.items), 2)
	doc.taxable = flt(doc.gross - flt(doc.material_recovery) - flt(doc.other_recovery), 2)
	doc.gst_amount = flt(doc.taxable * flt(doc.gst_rate) / 100, 2)
	doc.retention = flt(doc.gross * flt(doc.retention_pct) / 100, 2)
	doc.tds = flt(doc.taxable * flt(doc.tds_pct) / 100, 2)
	doc.net_payable = flt(doc.taxable + doc.gst_amount - doc.retention - doc.tds - flt(doc.advance_recovery), 2)
	if _labour_contractor(w.name) and doc.status not in ("Paid", "Cancelled"):
		ok, _m = compliance_ok(w.supplier)  # last month's documents, as of today
		doc.compliance_hold = 0 if ok else 1
	if not doc.is_new() and doc.status in ("Approved", "Paid"):
		before = doc.get_doc_before_save()
		if before and before.status == doc.status and flt(before.net_payable) != flt(doc.net_payable):
			frappe.throw(_("{0} is {1} — it cannot change.").format(doc.name, _(doc.status)))


def make_sub_invoice(name, posting_date=None):
	b = frappe.get_doc("Subcontractor Bill", name)
	if b.purchase_invoice:
		return b.purchase_invoice
	p = frappe.get_cached_doc("Project", b.project)
	acc = accounts(p.company)
	posting_date = posting_date or today()
	cc = p.cost_center or frappe.get_cached_value("Company", p.company, "cost_center")
	addr = p.get("hs_cn_address") or CN.branch_address(p.company)
	pi = frappe.get_doc({"doctype": "Purchase Invoice", "company": p.company, "supplier": b.supplier, "posting_date": posting_date, "set_posting_time": 1,
		"bill_no": b.supplier_invoice_no or f"RB-{b.bill_no}/{b.work_order}", "bill_date": b.bill_date or posting_date, "due_date": add_days(posting_date, 15),
		"project": p.name, "cost_center": cc, "hs_sub_bill": b.name,
		"items": [{"item_code": sub_item(), "qty": 1, "rate": flt(b.taxable), "expense_account": acc.heads["Subcontract"], "project": p.name, "cost_center": cc,
			"description": _("Running bill {0} — {1}, work up to {2}").format(b.bill_no, frappe.db.get_value("Subcontractor Work Order", b.work_order, "scope"),
				frappe.format(b.period_to or b.bill_date, {"fieldtype": "Date"}))}],
		"remarks": _("Subcontractor bill {0} — gross {1}, recoveries {2}").format(b.name, CN.inr(b.gross), CN.inr(flt(b.material_recovery) + flt(b.other_recovery)))})
	if addr:
		pi.billing_address = addr
		pi.shipping_address = addr
	if flt(b.gst_rate):
		_apply_taxes(pi, input_tax_template(p.company, addr, b.supplier))
	for acct, amt, desc in ((acc.tds_payable, b.tds, _("TDS u/s 194C @ {0:g}%").format(flt(b.tds_pct))), (acc.retention_payable, b.retention, _("Retention @ {0:g}%").format(flt(b.retention_pct))),
			(acc.sub_adv, b.advance_recovery, _("Mobilisation advance recovered"))):
		if flt(amt):
			pi.append("taxes", {"charge_type": "Actual", "account_head": acct, "tax_amount": flt(amt), "description": desc, "category": "Total", "add_deduct_tax": "Deduct",
				"cost_center": cc})
	pi.flags.ignore_permissions = True
	pi.flags.hs_system_entry = True  # made from the certified and approved running bill (the contractor's invoice is on the bill)
	pi.set_missing_values()
	pi.insert()
	pi.submit()
	b.db_set({"purchase_invoice": pi.name, "status": "Approved"})
	return pi.name


def pay_sub(name, posting_date=None, reference=None):
	b = frappe.get_doc("Subcontractor Bill", name)
	pi = frappe.get_doc("Purchase Invoice", b.purchase_invoice)
	if flt(pi.outstanding_amount) <= 0.5:
		return None
	posting_date = posting_date or today()
	amt = flt(pi.outstanding_amount, 2)
	pe = frappe.get_doc({"doctype": "Payment Entry", "payment_type": "Pay", "company": pi.company, "posting_date": posting_date, "party_type": "Supplier", "party": pi.supplier,
		"paid_from": CN.bank_account(pi.company), "paid_to": pi.credit_to, "paid_amount": amt, "received_amount": amt, "project": b.project,
		"reference_no": reference or f"NEFT/{b.name}", "reference_date": posting_date,
		"references": [{"reference_doctype": "Purchase Invoice", "reference_name": pi.name, "allocated_amount": amt}]})
	pe.flags.ignore_permissions = True
	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.insert()
	pe.submit()
	b.db_set({"payment_entry": pe.name, "status": "Paid"})
	return pe.name


def compliance_validate(doc):
	doc.month = get_first_day(doc.month)
	doc.status = "Complete" if doc.wage_register and doc.pf_ecr and doc.esi_challan else "Missing"


# ---------------------------------------------------------------- workers and wages
def min_wage(state, skill, on=None):
	r = frappe.get_all("Minimum Wage", filters={"state": state, "skill": skill, "effective_from": ["<=", on or today()]}, fields=["daily_rate"],
		order_by="effective_from desc", limit=1)
	return flt(r[0].daily_rate) if r else 0


def worker_validate(doc):
	doc.min_wage = min_wage(doc.state, doc.skill)
	if doc.min_wage and flt(doc.daily_rate) < doc.min_wage:
		frappe.throw(_("{0}: ₹{1:,.0f} a day is below the {2} minimum wage for {3} workers (₹{4:,.0f}).").format(doc.worker_name, flt(doc.daily_rate), doc.state,
			_(doc.skill).lower(), doc.min_wage))
	if not doc.contractor and doc.status == "Active" and not doc.upi_id:
		frappe.throw(_("Own workers are paid by UPI — enter the UPI ID of {0}.").format(doc.worker_name))
	if doc.aadhaar_last4 and (len(doc.aadhaar_last4) != 4 or not doc.aadhaar_last4.isdigit()):
		frappe.throw(_("Aadhaar: only the last four digits are kept."))


def worker_issues(w):
	t = getdate(today())
	out = []
	if not w.get("bocw_reg_no"):
		out.append(_("No BOCW registration"))
	if not cint(w.get("induction_done")):
		out.append(_("Induction pending"))
	if not cint(w.get("ppe_issued")):
		out.append(_("PPE not issued"))
	if w.get("id_expiry") and getdate(w.id_expiry) < add_days(t, 30):
		out.append(_("ID expires {0}").format(frappe.format(w.id_expiry, {"fieldtype": "Date"})))
	if not cint(w.get("police_verified")):
		out.append(_("Police verification pending"))
	return out


def _open_advance(worker):
	return frappe.get_all("Worker Advance", filters={"worker": worker, "status": "Paid"}, fields=["name", "amount", "recovered"], order_by="requested_on asc")


def muster_validate(doc):
	doc.week_start = week_start(doc.week_start)
	doc.week_end = add_days(doc.week_start, 6)
	for r in doc.rows:
		w = frappe.get_cached_doc("Site Worker", r.worker)
		if w.contractor:
			frappe.throw(_("{0} is a worker of {1} — contractors pay their own workers.").format(w.worker_name, w.contractor))
		r.rate = r.rate or w.daily_rate
		if flt(r.days) > 7:
			frappe.throw(_("{0}: at most 7 days in a pay week.").format(w.worker_name))
		r.earned = flt(flt(r.rate) * flt(r.days) + flt(r.rate) / 8 * 2 * flt(r.ot_hours), 2)  # OT at double the hourly rate
		r.pf = flt(min(flt(r.rate), PF_CEILING_DAY) * flt(r.days) * .12, 0)
		r.esi = flt(r.earned * .0075, 0) if flt(r.rate) <= ESI_CEILING_DAY else 0
		owed = sum(flt(a.amount) - flt(a.recovered) for a in _open_advance(r.worker))
		if r.advance_recovery is None or (doc.status == "Draft" and not flt(r.advance_recovery)):
			r.advance_recovery = 0
		r.advance_recovery = flt(min(flt(r.advance_recovery) or owed, owed, (r.earned - r.pf - r.esi) * .5), 0)
		r.net = flt(r.earned - r.pf - r.esi - r.advance_recovery, 2)
	doc.workers = len(doc.rows)
	doc.man_days = sum(flt(r.days) for r in doc.rows)
	for f in ("earned", "pf", "esi", "advance_recovery", "net"):
		doc.set(f, flt(sum(flt(r.get(f)) for r in doc.rows), 2))
	if frappe.db.exists("Weekly Muster", {"project": doc.project, "week_start": doc.week_start, "name": ["!=", doc.name or ""]}):
		frappe.throw(_("{0} already has the muster for the week from {1}.").format(doc.project, frappe.format(doc.week_start, {"fieldtype": "Date"})))


def pay_muster(name, posting_date=None):
	m = frappe.get_doc("Weekly Muster", name)
	p = frappe.get_cached_doc("Project", m.project)
	acc = accounts(p.company)
	cc = p.cost_center or frappe.get_cached_value("Company", p.company, "cost_center")
	er_pf = flt(m.pf * 13 / 12, 2)  # employer 13% (EPF 3.67 + EPS 8.33 + EDLI/admin 1)
	er_esi = flt(sum(flt(r.earned) * .0325 for r in m.rows if flt(r.esi)), 2)
	rows = [{"account": acc.heads["Labour"], "debit_in_account_currency": flt(m.earned + er_pf + er_esi, 2), "project": m.project, "cost_center": cc},
		{"account": CN.bank_account(p.company), "credit_in_account_currency": flt(m.net, 2), "cost_center": cc},
		{"account": acc.pf_payable, "credit_in_account_currency": flt(m.pf + er_pf, 2), "cost_center": cc}]
	if flt(m.esi) + er_esi:
		rows.append({"account": acc.esi_payable, "credit_in_account_currency": flt(m.esi + er_esi, 2), "cost_center": cc})
	if flt(m.advance_recovery):
		rows.append({"account": acc.worker_adv, "credit_in_account_currency": flt(m.advance_recovery, 2), "cost_center": cc})
	je = frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Bank Entry", "company": p.company, "posting_date": posting_date or today(), "cheque_no": f"UPI/{m.name}",
		"cheque_date": posting_date or today(), "user_remark": _("Wages {0} — week {1} to {2}, {3} workers, {4:g} man-days, paid by UPI").format(m.project,
			frappe.format(m.week_start, {"fieldtype": "Date"}), frappe.format(m.week_end, {"fieldtype": "Date"}), m.workers, m.man_days), "accounts": rows})
	je.flags.ignore_permissions = True
	je.flags.hs_system_entry = True
	je.insert()
	je.submit()
	for r in m.rows:
		left = flt(r.advance_recovery)
		for a in _open_advance(r.worker):
			if left <= 0:
				break
			take = min(left, flt(a.amount) - flt(a.recovered))
			rec = flt(a.recovered) + take
			frappe.db.set_value("Worker Advance", a.name, {"recovered": rec, "status": "Recovered" if rec >= flt(a.amount) - 0.5 else "Paid"})
			left -= take
	m.db_set({"journal_entry": je.name, "status": "Paid", "paid_on": posting_date or today()})
	return je.name


def advance_validate(doc):
	w = frappe.get_cached_doc("Site Worker", doc.worker)
	if w.contractor:
		frappe.throw(_("{0} is a worker of {1} — advances go through the contractor.").format(w.worker_name, w.contractor))
	cap = flt(w.daily_rate) * 6 * 4
	if flt(doc.amount) > cap:
		frappe.throw(_("An advance is at most four weeks' wages — ₹{0:,.0f} for {1}.").format(cap, w.worker_name))
	if doc.is_new() and flt(doc.amount) + sum(flt(a.amount) - flt(a.recovered) for a in _open_advance(doc.worker)) > cap:
		frappe.throw(_("{0} still owes earlier advances — the total would be above four weeks' wages.").format(w.worker_name))


def pay_advance(name, posting_date=None):
	a = frappe.get_doc("Worker Advance", name)
	p = frappe.get_cached_doc("Project", a.project)
	acc = accounts(p.company)
	cc = p.cost_center or frappe.get_cached_value("Company", p.company, "cost_center")
	je = frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Bank Entry", "company": p.company, "posting_date": posting_date or today(), "cheque_no": f"UPI/{a.name}",
		"cheque_date": posting_date or today(), "user_remark": _("Advance to {0} ({1})").format(a.worker_name, a.project),
		"accounts": [{"account": acc.worker_adv, "debit_in_account_currency": flt(a.amount), "cost_center": cc, "project": a.project},
			{"account": CN.bank_account(p.company), "credit_in_account_currency": flt(a.amount), "cost_center": cc}]})
	je.flags.ignore_permissions = True
	je.flags.hs_system_entry = True
	je.insert()
	je.submit()
	a.db_set({"journal_entry": je.name, "status": "Paid"})
	return je.name


# ---------------------------------------------------------------- equipment
def eq_log_validate(doc):
	if flt(doc.end_hmr) < flt(doc.start_hmr):
		frappe.throw(_("The end hour meter is below the start."))
	last = frappe.db.sql("""select max(end_hmr) from `tabEquipment Log` where equipment = %s and name != %s and log_date <= %s""",
		(doc.equipment, doc.name or "", doc.log_date))[0][0]
	if last is not None and flt(doc.start_hmr) < flt(last) - 0.01:
		frappe.throw(_("The start hour meter {0:g} is below the last reading {1:g} — a meter never goes back.").format(flt(doc.start_hmr), flt(last)))
	doc.hours = flt(flt(doc.end_hmr) - flt(doc.start_hmr) - flt(doc.idle_hours), 2)
	if doc.hours < 0:
		frappe.throw(_("Idle hours are more than the hours on the meter."))
	top = flt(frappe.db.sql("select max(end_hmr) from `tabEquipment Log` where equipment = %s and name != %s", (doc.equipment, doc.name or ""))[0][0])
	frappe.db.set_value("Construction Equipment", doc.equipment, "last_hmr", max(top, flt(doc.end_hmr)), update_modified=False)


def eq_log_after(doc, method=None):
	last = frappe.db.sql("select max(end_hmr) from `tabEquipment Log` where equipment = %s", doc.equipment)[0][0]
	frappe.db.set_value("Construction Equipment", doc.equipment, "last_hmr", flt(last), update_modified=False)


def eq_fig(e, start=None, end=None):
	"""Hours, diesel, utilisation against plan, downtime and cost of a machine in a period (default: this month)."""
	start = start or get_first_day(today())
	end = end or today()
	L = frappe.get_all("Equipment Log", filters={"equipment": e.name, "log_date": ["between", [start, end]]}, fields=["hours", "idle_hours", "diesel_litres"])
	M = frappe.get_all("Equipment Maintenance", filters={"equipment": e.name, "job_date": ["between", [start, end]]}, fields=["downtime_hours", "cost"])
	h = sum(flt(x.hours) for x in L)
	days = max(1, date_diff(end, start) + 1)
	plan = flt(e.planned_hours_month) * days / 30
	d = sum(flt(x.diesel_litres) for x in L)
	f = frappe._dict(hours=h, idle=sum(flt(x.idle_hours) for x in L), diesel=d, plan=plan, util=h / plan * 100 if plan else 0,
		diesel_rate=d / h if h else 0, downtime=sum(flt(x.downtime_hours) for x in M), maint_cost=sum(flt(x.cost) for x in M))
	f.hire = (flt(e.hire_rate) * (h if e.hire_basis == "Hour" else len(L) if e.hire_basis == "Day" else days / 30)) if e.ownership == "Hired" else 0
	f.over_diesel = flt(e.diesel_norm_lph) and h and f.diesel_rate > flt(e.diesel_norm_lph) * 1.1
	return f


def eq_flags(e):
	t = getdate(today())
	out = []
	for f, label in (("insurance_expiry", _("Insurance")), ("fitness_expiry", _("Fitness / RTO"))):
		if e.get(f) and getdate(e.get(f)) <= add_days(t, 30):
			out.append(_("{0} {1} on {2}").format(label, _("expired") if getdate(e.get(f)) < t else _("expires"), frappe.format(e.get(f), {"fieldtype": "Date"})))
	if flt(e.next_service_hmr) and flt(e.last_hmr) >= flt(e.next_service_hmr) - 10:
		out.append(_("Service due at {0:g} h (now {1:g} h)").format(flt(e.next_service_hmr), flt(e.last_hmr)))
	return out


# ---------------------------------------------------------------- validation hub and flags
VALIDATE = {"Subcontractor Work Order": sub_wo_validate, "Subcontractor Bill": sub_bill_validate, "Labour Compliance": compliance_validate,
	"Site Worker": worker_validate, "Weekly Muster": muster_validate, "Worker Advance": advance_validate, "Equipment Log": eq_log_validate}


def flags(name):
	out = []
	if not frappe.db.exists("DocType", "Material Norm"):
		return out
	for x in material_status(name):
		if x.excess > 0 and x.excess_value > 1000:
			out.append({"lvl": "High" if x.excess_pct - x.wastage > 2 else "Medium", "text": _("{0} used {1:.1f}% over theory (allowed {2:.1f}%) — {3} excess, recover {4}").format(
				x.item_name, x.excess_pct, x.wastage, CN.inr(x.excess_value), CN.inr(x.recovery)), "open": ["Project", name]})
	for b in frappe.get_all("Subcontractor Bill", filters={"project": name, "status": ["in", ["Certified", "Approved"]], "compliance_hold": 1}, fields=["name", "supplier", "net_payable"]):
		out.append({"lvl": "Medium", "text": _("{0}: bill {1} on hold — PF / ESI / wage register missing").format(b.supplier, CN.inr(b.net_payable)), "open": ["Subcontractor Bill", b.name]})
	n = frappe.db.count("Material Request", {"hs_project": name, "docstatus": 0, "hs_over_boq": 1})
	if n:
		out.append({"lvl": "Medium", "text": _("{0} indents above the BOQ need wait for the PM").format(n), "open": ["Project", name]})
	for e in frappe.get_all("Construction Equipment", filters={"project": name, "status": ["!=", "Off-hired"]}, fields=["name", "equipment_name", "insurance_expiry", "fitness_expiry",
			"next_service_hmr", "last_hmr"]):
		for t in eq_flags(e):
			out.append({"lvl": "Medium", "text": f"{e.equipment_name}: {t}", "open": ["Construction Equipment", e.name]})
	return out


# ---------------------------------------------------------------- actions
def _who():
	return frappe.utils.get_fullname(frappe.session.user)


def _doc(dt, name, perm="write"):
	d = frappe.get_doc(dt, name)
	d.check_permission(perm)
	return d


def _a_ind_approve(name, a):
	m = _doc("Material Request", name, "read")
	CN._need([PM, MD] if cint(m.hs_over_boq) else [PM, MD, PMS, SK, QS], _("Approving this indent"))
	if m.docstatus != 0:
		frappe.throw(_("{0} is already approved.").format(m.name))
	with CN._elevated():
		m = frappe.get_doc("Material Request", name)
		m.submit()
		m.add_comment("Comment", _("Approved by {0}").format(_who()))
	return {"message": _("{0} approved — get quotations or order").format(m.name)}


def _a_ind_reject(name, a):
	CN._need([PM, MD], _("Rejecting an indent"))
	m = _doc("Material Request", name, "read")
	with CN._elevated():
		frappe.get_doc("Material Request", name).add_comment("Comment", _("Rejected by {0}: {1}").format(_who(), a.get("note") or ""))
		frappe.delete_doc("Material Request", name, ignore_permissions=True) if m.docstatus == 0 else None
	return {"message": _("{0} rejected").format(name)}


def _a_po_l1(name, a):
	CN._need([PM, MD, *BUY, QS], _("Ordering from the L1 supplier"))
	frappe.has_permission("Purchase Order", "create", throw=True)
	q = comparison(name)
	if not q:
		frappe.throw(_("No submitted supplier quotations against {0}.").format(name))
	l1 = q[0]
	if not cint(l1.get("hs_tech_ok")):
		frappe.throw(_("No technically compliant quotation."))
	from erpnext.buying.doctype.supplier_quotation.supplier_quotation import make_purchase_order

	m = frappe.get_doc("Material Request", name)
	with CN._elevated():
		return _po_from(l1, m, name)


def _po_from(l1, m, name):
	from erpnext.buying.doctype.supplier_quotation.supplier_quotation import make_purchase_order

	po = make_purchase_order(l1.name)
	po.hs_project = m.get("hs_project")
	po.schedule_date = m.schedule_date if getdate(m.schedule_date) >= getdate(today()) else add_days(today(), 7)
	w = P.site_warehouse(m.hs_project) if m.get("hs_project") else None
	for i in po.items:
		i.schedule_date = po.schedule_date
		i.material_request = name
		i.material_request_item = next((r.name for r in m.items if r.item_code == i.item_code), None)
		if w:
			i.warehouse = w
		i.project = m.get("hs_project")
	if flt(l1.get("hs_freight")) or flt(l1.get("hs_unloading")):
		po.append("taxes", {"charge_type": "Actual", "account_head": frappe.db.get_value("Account", {"company": po.company, "account_name": ["like", "Freight%"], "is_group": 0})
			or P.accounts(po.company).heads["Materials"], "tax_amount": flt(l1.get("hs_freight")) + flt(l1.get("hs_unloading")), "description": _("Freight & unloading"),
			"category": "Valuation and Total", "add_deduct_tax": "Add"})
	po.flags.ignore_permissions = True
	po.insert()
	return {"message": _("{0} drafted to {1} (L1 on landed cost {2})").format(po.name, l1.supplier, CN.inr(l1.get("hs_landed_total") or l1.base_net_total)),
		"open": ["Purchase Order", po.name]}


def _a_grn_bill(name, a):
	CN._need([AM, AU, PM, MD, *BUY], _("Booking the supplier's bill"))
	pr = _doc("Purchase Receipt", name, "read")
	if pr.docstatus != 1:
		frappe.throw(_("{0} is not submitted.").format(pr.name))
	if frappe.db.exists("Purchase Invoice Item", {"purchase_receipt": pr.name, "docstatus": 1}):
		frappe.throw(_("{0} is already billed.").format(pr.name))
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice

	with CN._elevated():
		pi = make_purchase_invoice(pr.name)
		pi.bill_no = a.get("bill_no") or pr.get("supplier_delivery_note") or f"INV/{pr.name}"
		pi.bill_date = a.get("bill_date") or pr.posting_date
		pi.posting_date, pi.set_posting_time = a.get("date") or today(), 1
		pi.flags.ignore_permissions = True
		pi.insert()
		frappe.db.savepoint("hs_grn_bill")
		try:
			pi.submit()
		except frappe.ValidationError as e:  # a document rule (the supplier's tax invoice on file) — the bill waits as a draft
			frappe.db.rollback(save_point="hs_grn_bill")
			frappe.clear_messages()
			return {"message": _("Bill {0} drafted — {1}").format(pi.name, frappe.utils.strip_html(str(e))[:160]), "open": ["Purchase Invoice", pi.name]}
	return {"message": _("Bill {0} booked — {1}").format(pi.name, CN.inr(pi.grand_total)), "open": ["Purchase Invoice", pi.name]}


def _a_trf_dispatch(name, a):
	CN._need([SK, PM, MD, SE], _("Dispatching a transfer"))
	se = _doc("Stock Entry", name)
	if se.docstatus != 0:
		frappe.throw(_("{0} is already dispatched.").format(se.name))
	if not (se.get("hs_vehicle") and se.get("hs_driver")):
		frappe.throw(_("Enter the vehicle and the driver first."))
	tr = transit_store(se.company)
	for d in se.items:
		d.t_warehouse = tr
	se.add_to_transit = 1
	se.hs_transfer_status = "In transit"
	se.submit()
	return {"message": _("{0} dispatched — {1}, driver {2}").format(se.name, se.hs_vehicle, se.hs_driver)}


def _a_trf_deliver(name, a):
	CN._need([SK, SE, PM, MD], _("Confirming a delivery at site"))
	se = _doc("Stock Entry", name, "read")
	if se.docstatus != 1 or se.get("hs_transfer_status") != "In transit":
		frappe.throw(_("{0} is not in transit.").format(se.name))
	from erpnext.stock.doctype.stock_entry.stock_entry import make_stock_in_entry

	with CN._elevated():
		n = make_stock_in_entry(se.name)
		dest = se.get("hs_destination") or (P.site_warehouse(se.project) if se.project else None)
		for d in n.items:
			d.t_warehouse = dest or d.t_warehouse
		n.posting_date, n.set_posting_time = a.get("date") or today(), 1
		n.project = se.project
		n.hs_transfer_status = "Delivered"
		n.flags.ignore_permissions = True
		n.insert()
		n.submit()
		frappe.db.set_value("Stock Entry", se.name, "hs_transfer_status", "Delivered")
	return {"message": _("{0} delivered at {1}").format(se.name, dest or _("site"))}


def _a_swo_activate(name, a):
	CN._need([PM, MD], _("Issuing a work order"))
	w = _doc("Subcontractor Work Order", name)
	if w.status != "Draft":
		frappe.throw(_("{0} is {1}.").format(w.name, _(w.status)))
	if not w.items:
		frappe.throw(_("Add the work order items."))
	w.status = "Active"
	w.save()
	return {"message": _("{0} issued to {1} — {2}").format(w.name, w.supplier, CN.inr(w.value))}


def _a_sub_certify(name, a):
	CN._need([QS, PM, MD], _("Certifying a subcontractor bill"))
	b = _doc("Subcontractor Bill", name)
	if b.status != "Draft":
		frappe.throw(_("{0} is {1}.").format(b.name, _(b.status)))
	b.status, b.certified_by = "Certified", _who()
	b.save()
	return {"message": _("{0} certified — {1} net").format(b.name, CN.inr(b.net_payable))}


def _a_sub_approve(name, a):
	CN._need([PM, MD], _("Approving a subcontractor bill"))
	b = _doc("Subcontractor Bill", name, "read")
	if b.status != "Certified":
		frappe.throw(_("{0} is {1} — the QS certifies it first.").format(b.name, _(b.status)))
	frappe.db.set_value("Subcontractor Bill", b.name, "approved_by", _who())
	with CN._elevated():
		pi = make_sub_invoice(b.name, a.get("date"))
	return {"message": _("{0} approved — purchase invoice {1}").format(b.name, pi), "open": ["Purchase Invoice", pi]}


def _a_sub_pay(name, a):
	CN._need([AM, AU, MD], _("Paying a subcontractor"))
	b = _doc("Subcontractor Bill", name, "read")
	if b.status != "Approved":
		frappe.throw(_("{0} is {1}.").format(b.name, _(b.status)))
	if _labour_contractor(b.work_order):
		ok, m = compliance_ok(b.supplier)
		if not ok:
			frappe.db.set_value("Subcontractor Bill", b.name, "compliance_hold", 1)
			frappe.throw(_("{0}: the wage register, PF ECR and ESI challan for {1} are not all in — as principal employer we hold the payment.").format(
				b.supplier, frappe.utils.formatdate(m, "MMMM yyyy")))
		frappe.db.set_value("Subcontractor Bill", b.name, "compliance_hold", 0)
	with CN._elevated():
		pe = pay_sub(b.name, a.get("date"))
	return {"message": _("{0} paid").format(b.name), "open": ["Payment Entry", pe] if pe else None}


def _a_lc_mark(name, a):
	CN._need([HR, PM, MD, AM, AU], _("Recording labour documents"))
	c = _doc("Labour Compliance", name)
	c.wage_register = c.pf_ecr = c.esi_challan = 1
	c.save()
	for b in frappe.get_all("Subcontractor Bill", filters={"supplier": c.supplier, "compliance_hold": 1, "status": ["in", ["Draft", "Certified", "Approved"]]}, pluck="name"):
		frappe.get_doc("Subcontractor Bill", b).save(ignore_permissions=True)
	return {"message": _("{0}: documents for {1} received").format(c.supplier, frappe.utils.formatdate(c.month, "MMMM yyyy"))}


def _a_mus_approve(name, a):
	CN._need([PM, MD], _("Approving the wages"))
	m = _doc("Weekly Muster", name)
	if m.status != "Draft":
		frappe.throw(_("{0} is {1}.").format(m.name, _(m.status)))
	m.status, m.approved_by = "Approved", _who()
	m.save()
	return {"message": _("{0} approved — {1} to pay").format(m.name, CN.inr(m.net))}


def _a_mus_pay(name, a):
	CN._need([AM, AU, MD], _("Paying the wages"))
	m = _doc("Weekly Muster", name, "read")
	if m.status != "Approved":
		frappe.throw(_("{0} is {1} — the PM approves it first.").format(m.name, _(m.status)))
	with CN._elevated():
		je = pay_muster(m.name, a.get("date"))
	return {"message": _("Wages paid by UPI — {0}").format(je), "open": ["Journal Entry", je]}


def _a_adv_approve(name, a):
	adv = _doc("Worker Advance", name, "read")
	CN._need([PM, MD] if flt(adv.amount) > limits().wadv else [PM, MD, SE, HR], _("Approving this advance"))
	if adv.status != "Requested":
		frappe.throw(_("{0} is {1}.").format(adv.name, _(adv.status)))
	frappe.db.set_value("Worker Advance", adv.name, "status", "Approved")
	return {"message": _("Advance {0} approved").format(CN.inr(adv.amount))}


def _a_adv_pay(name, a):
	CN._need([AM, AU, MD, PM], _("Paying an advance"))
	adv = _doc("Worker Advance", name, "read")
	if adv.status != "Approved":
		frappe.throw(_("{0} is {1}.").format(adv.name, _(adv.status)))
	with CN._elevated():
		je = pay_advance(adv.name, a.get("date"))
	return {"message": _("Advance paid by UPI — {0}").format(je)}


def _a_adv_reject(name, a):
	CN._need([PM, MD, SE, HR], _("Rejecting an advance"))
	adv = _doc("Worker Advance", name, "read")
	frappe.db.set_value("Worker Advance", adv.name, "status", "Rejected")
	return {"message": _("Advance rejected")}


def _a_eq_status(name, a):
	CN._need([PLANT, PM, SE, MD], _("Changing the equipment status"))
	e = _doc("Construction Equipment", name)
	e.status = a.get("status") or "Working"
	e.save()
	return {"message": _("{0}: {1}").format(e.equipment_name, _(e.status))}


ACTIONS = {
	"ind_approve": _a_ind_approve, "ind_reject": _a_ind_reject, "po_l1": _a_po_l1, "grn_bill": _a_grn_bill, "trf_dispatch": _a_trf_dispatch, "trf_deliver": _a_trf_deliver,
	"swo_activate": _a_swo_activate, "sub_certify": _a_sub_certify, "sub_approve": _a_sub_approve, "sub_pay": _a_sub_pay, "lc_mark": _a_lc_mark,
	"mus_approve": _a_mus_approve, "mus_pay": _a_mus_pay, "adv_approve": _a_adv_approve, "adv_pay": _a_adv_pay, "adv_reject": _a_adv_reject, "eq_status": _a_eq_status,
}
