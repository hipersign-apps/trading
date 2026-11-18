"""v1.9.0 stage A5 (prototype C8): Construction (India) — finance & tax (feature cn_fin).

On top of ERPNext's books (GL, trial balance, P&L, balance sheet, bank reconciliation) and India Compliance (GST returns,
e-invoice, e-way bill), the construction view of the money:
  · project P&L from the GL (revenue and the cost heads by project), receivables and payables ageing (MSME suppliers past 45
    days flagged — section 43B(h)), an eight-week cash-flow forecast from the documents,
  · GST by registration (GSTIN) and month — output tax, input tax credit, the cash to pay — and its payment (set-off
    journal); TDS both ways (194C deducted by clients vs Form 26AS, 194C deducted from subcontractors, 192 from salaries) and
    its deposit by the 7th; GST-TDS; BOCW labour cess (deducted by government clients, self-paid 1% of the cost on private
    work); the compliance calendar,
  · earned value per project (BAC, PV, EV, AC, CPI, SPI, EAC, VAC, TCPI) and the cost heads (budget, committed, actual, EAC),
  · staff payroll — PF 12% (₹15,000 ceiling), ESI 0.75% (gross up to ₹21,000), professional tax by state, TDS 192 on the
    new regime (₹75,000 standard deduction, rebate up to ₹12 lakh, 4% cess) — posted to the projects the staff work on;
    gratuity provision,
  · the approval matrix: manual journals need the Accounts Manager, and the MD above the limit.
Tax rates and slabs are configured here for FY 2026-27 — verify with the company's tax adviser before relying on them.
"""

import calendar

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, get_first_day, get_last_day, getdate, today

from hipersign_trading.api import construction as CN
from hipersign_trading.api import projects as P

MD, AM, AU, HR, FM = "Managing Director", "Accounts Manager", "Accounts User", "HR & Admin", "Finance Manager"
PT = {"Kerala": 208, "Karnataka": 200, "Tamil Nadu": 208, "Maharashtra": 200}  # monthly professional tax at these salaries (sample)
SLABS = [(400000, 0), (800000, .05), (1200000, .10), (1600000, .15), (2000000, .20), (2400000, .25), (10 ** 12, .30)]  # new regime
STD_DED, REBATE_LIMIT = 75000, 1200000
DUE_DAY = {"GST": 20, "TDS 194C (contractors)": 7, "TDS 192 (salaries)": 7, "PF": 15, "ESI": 15, "Professional tax": 20, "BOCW labour cess": 30}


def limits():
	s = frappe.get_cached_doc("Hipersign Settings")
	return frappe._dict(jv_md=flt(s.get("cn_jv_md_limit")) or 1000000)


def accounts(company):
	cache = P._local("hs_cn_fin_acc")
	if company in cache:
		return cache[company]
	from hipersign_trading.api import construction_site as S

	base = S.accounts(company)
	liab = P._group(company, "Liability", ("Duties and Taxes", "Current Liabilities"))
	a = frappe._dict(base, tds192=P._account(company, "TDS Payable - 192", "Liability", liab), pt=P._account(company, "Professional Tax Payable", "Liability", liab),
		cess=CN.accounts(company).cess)
	cache[company] = a
	return a


def companies():
	return [r[0] for r in frappe.db.sql("select distinct company from `tabProject` where hs_cn = 1")] if frappe.get_meta("Project").has_field("hs_cn") else []


def due_date(kind, month):
	nxt = add_months(get_first_day(month), 1)
	return getdate(nxt).replace(day=min(DUE_DAY.get(kind, 20), 28)) if DUE_DAY.get(kind) != 30 else get_last_day(nxt)


# ---------------------------------------------------------------- GST by registration and month
def _gst_raw(company, month):
	start, end = get_first_day(month), get_last_day(month)
	out = {}
	for doctype, child, side in (("Sales Invoice", "Sales Taxes and Charges", "out"), ("Purchase Invoice", "Purchase Taxes and Charges", "in")):
		rows = frappe.db.sql(f"""select d.company_gstin, t.account_head, sum(t.base_tax_amount_after_discount_amount) from `tab{child}` t join `tab{doctype}` d on d.name = t.parent
			where d.docstatus = 1 and d.company = %s and d.posting_date between %s and %s and t.account_head in
			(select name from `tabAccount` where company = %s and account_name like %s and account_name not like '%%RCM%%')
			{"and t.add_deduct_tax = 'Add'" if side == "in" else ""} group by d.company_gstin, t.account_head""",
			(company, start, end, company, "Output Tax%" if side == "out" else "Input Tax%"))
		for gstin, acc, amt in rows:
			x = out.setdefault(gstin or "—", frappe._dict(output={}, input={}))
			x["output" if side == "out" else "input"][acc] = flt(amt, 2)
	return out


def _kind(account):
	for k in ("IGST", "CGST", "SGST", "UTGST"):
		if k in account:
			return "SGST" if k == "UTGST" else k
	return "Cess"


ORDER = {"IGST": ("IGST", "CGST", "SGST"), "CGST": ("CGST", "IGST"), "SGST": ("SGST", "IGST"), "Cess": ("Cess",)}  # sec. 49 / 49A: which credit pays which tax


def _set_off(output, credit):
	"""Input tax credit set against output tax the way the GST law allows: IGST credit first against IGST, then CGST, then
	SGST; CGST credit against CGST, then IGST; SGST credit against SGST, then IGST (never CGST against SGST). Returns the credit
	used per account, the credit left per account and the cash to pay."""
	due = {}
	for a, v in output.items():
		due[_kind(a)] = due.get(_kind(a), 0) + v
	left = dict(credit)
	use = {}
	for ck in ("IGST", "CGST", "SGST", "Cess"):
		for a in sorted(k for k in left if _kind(k) == ck):
			for dk in ORDER[ck]:
				take = min(left[a], due.get(dk, 0))
				if take > 0:
					use[a] = use.get(a, 0) + take
					left[a] -= take
					due[dk] -= take
	return {a: flt(v, 2) for a, v in use.items() if v > .005}, {a: flt(v, 2) for a, v in left.items() if v > .005}, flt(sum(due.values()), 2)


def gst_month(company, month, back=6):
	"""Output tax (sales invoices) and input tax (purchase invoices) by company GSTIN for a month, RCM aside. Input tax credit
	left over from earlier months (output lower than input) is carried forward and used first — per GSTIN and per account."""
	month = get_first_day(month)
	carry = {}
	res = {}
	for k in range(back, -1, -1):
		m = get_first_day(add_months(month, -k))
		res = {}
		raw = _gst_raw(company, m)
		for gstin in set(raw) | set(carry):
			r = raw.get(gstin) or frappe._dict(output={}, input={})
			cin = carry.get(gstin) or {}
			avail = dict(cin)
			for acc, v in r.input.items():
				avail[acc] = avail.get(acc, 0) + v
			outv, inp, cin_total = sum(r.output.values()), sum(r.input.values()), sum(cin.values())
			use, rest, cash = _set_off(r.output, avail)
			used = sum(use.values())
			x = frappe._dict(gstin=gstin, output=r.output, input=r.input, out=outv, inp=inp, carried_in=cin_total, use=use, used=used, cash=cash, carry=sum(rest.values()))
			res[gstin] = x
			carry[gstin] = rest
	for gstin, x in res.items():
		x.paid = frappe.db.get_value("Statutory Deposit", {"kind": "GST", "gstin": gstin, "month": month, "status": "Paid"}, "name") \
			if frappe.db.exists("DocType", "Statutory Deposit") else None
		x.filed = _filed(company, gstin, month)
	return {g: x for g, x in res.items() if x.out or x.inp or x.carried_in}


def _filed(company, gstin, month):
	"""GSTR-1 filed for the period — India Compliance's GST Return Log (filed from the GST portal)."""
	if not frappe.db.exists("DocType", "GST Return Log"):
		return None
	return frappe.db.get_value("GST Return Log", {"return_type": "GSTR1", "gstin": gstin, "return_period": getdate(month).strftime("%m%Y"), "filing_status": "Filed"}, "name")


# ---------------------------------------------------------------- TDS and cess
def liability_for(company, month, kind):
	start, end = get_first_day(month), get_last_day(month)
	acc = accounts(company)
	a = {"TDS 194C (contractors)": acc.tds_payable, "TDS 192 (salaries)": acc.tds192, "PF": acc.pf_payable, "ESI": acc.esi_payable, "Professional tax": acc.pt}.get(kind)
	if not a:
		return 0
	return flt(frappe.db.sql("""select sum(credit) from `tabGL Entry` where is_cancelled = 0 and account = %s and posting_date between %s and %s and credit > 0""",
		(a, start, end))[0][0])


def cess_due(project):
	"""BOCW cess, 1% of the cost of construction: deducted by government clients from the bills; on private work the builder
	pays it to the state's welfare board. Due = 1% of the cost to date less what has been paid."""
	p = frappe.get_cached_doc("Project", project)
	F = CN.fig(project)
	if cint(p.get("hs_cn_govt")):
		return frappe._dict(mode="Deducted by the client", base=F.billed, due=0, paid=F.cess)
	base = F.cost
	paid = flt(frappe.db.sql("select sum(amount) from `tabStatutory Deposit` where kind = 'BOCW labour cess' and project = %s and status = 'Paid'", project)[0][0]) \
		if frappe.db.exists("DocType", "Statutory Deposit") else 0
	return frappe._dict(mode="Self-paid to the board", base=base, due=max(0, base * .01 - paid), paid=paid)


def deposit_validate(doc):
	doc.month = get_first_day(doc.month)
	doc.due_date = due_date(doc.kind, doc.month)
	if doc.kind == "GST" and not doc.gstin:
		frappe.throw(_("Pick the GSTIN this GST payment is for."))
	if doc.kind == "BOCW labour cess" and not doc.project:
		frappe.throw(_("Pick the project the cess is paid for."))


def pay_deposit(name, posting_date=None):
	d = frappe.get_doc("Statutory Deposit", name)
	acc = accounts(d.company)
	cc = frappe.get_cached_value("Company", d.company, "cost_center")
	bank = CN.bank_account(d.company)
	rows = []
	if d.kind == "GST":
		g = gst_month(d.company, d.month).get(d.gstin)
		if not g:
			frappe.throw(_("No GST for {0} in {1}.").format(d.gstin, frappe.utils.formatdate(d.month, "MMM yyyy")))
		for a, v in g.output.items():
			rows.append({"account": a, "debit_in_account_currency": flt(v, 2), "cost_center": cc})
		for a, v in g.use.items():
			rows.append({"account": a, "credit_in_account_currency": flt(v, 2), "cost_center": cc})
		cash = flt(sum(g.output.values()), 2) - flt(sum(g.use.values()), 2)
		if cash > 0:
			rows.append({"account": bank, "credit_in_account_currency": flt(cash, 2), "cost_center": cc})
		d.amount, d.itc_used = flt(cash, 2), flt(g.used, 2)
	else:
		a = {"TDS 194C (contractors)": acc.tds_payable, "TDS 192 (salaries)": acc.tds192, "PF": acc.pf_payable, "ESI": acc.esi_payable, "Professional tax": acc.pt,
			"BOCW labour cess": acc.cess}[d.kind]
		rows = [{"account": a, "debit_in_account_currency": flt(d.amount, 2), "cost_center": cc, "project": d.project},
			{"account": bank, "credit_in_account_currency": flt(d.amount, 2), "cost_center": cc}]
	if not rows:
		frappe.throw(_("Nothing to pay."))
	je = frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Bank Entry" if any(r["account"] == bank for r in rows) else "Journal Entry", "company": d.company,
		"posting_date": posting_date or d.paid_on or today(), "cheque_no": d.challan_no or f"CHLN/{d.name}", "cheque_date": posting_date or d.paid_on or today(),
		"user_remark": _("{0} for {1}{2} — challan {3}").format(_(d.kind), frappe.utils.formatdate(d.month, "MMMM yyyy"), f" ({d.gstin})" if d.gstin else "", d.challan_no or "—"),
		"accounts": rows})
	if d.kind == "GST" and je.meta.has_field("company_gstin"):
		je.company_gstin = d.gstin
	je.flags.ignore_permissions = True
	je.flags.hs_system_entry = True
	je.insert()
	je.submit()
	d.status, d.journal_entry, d.paid_on = "Paid", je.name, posting_date or d.paid_on or today()
	d.flags.ignore_permissions = True
	d.save()
	return je.name


def calendar_items(company, months=2):
	"""What is due: GST (per GSTIN), TDS 194C and 192, PF, ESI, professional tax — this month's and last month's."""
	t = getdate(today())
	out = []
	for k in range(months, 0, -1):
		m = get_first_day(add_months(t, -k))
		for gstin, g in gst_month(company, m).items():
			out.append(frappe._dict(kind="GST", label=_("GSTR-3B & GST payment"), month=m, ref=gstin, due=due_date("GST", m), amount=g.cash, paid=g.paid))
			if g.out:
				out.append(frappe._dict(kind="GSTR-1", label=_("GSTR-1 (outward supplies)"), month=m, ref=gstin, due=getdate(add_months(m, 1)).replace(day=11), amount=g.out, paid=g.filed))
		for kind in ("TDS 194C (contractors)", "TDS 192 (salaries)", "PF", "ESI", "Professional tax"):
			amt = liability_for(company, m, kind)
			if amt:
				paid = frappe.db.get_value("Statutory Deposit", {"kind": kind, "month": m, "company": company, "status": "Paid"}, "name")
				out.append(frappe._dict(kind=kind, label=_(kind), month=m, ref="", due=due_date(kind, m), amount=amt, paid=paid))
	for x in out:
		x.state = ("Filed" if x.kind == "GSTR-1" else "Paid") if x.paid else "Overdue" if getdate(x.due) < t else "Due"
	return out


# ---------------------------------------------------------------- earned value
def evm(project):
	F = CN.fig(project)
	p = frappe.get_cached_doc("Project", project)
	c = P.cost_of(project) if CN.boq(project) else frappe._dict(budget=0, actual=0, committed=0, fac=0, H={})
	bac = flt(c.budget)
	planned = flt(p.get("hs_cn_planned_pct")) or F.pct
	pv, ev, ac = bac * planned / 100, bac * F.pct / 100, flt(c.actual)
	cpi = ev / ac if ac else 0
	spi = ev / pv if pv else 0
	eac = bac / cpi if cpi else bac
	return frappe._dict(bac=bac, planned=planned, done=F.pct, pv=pv, ev=ev, ac=ac, cpi=cpi, spi=spi, eac=eac, vac=bac - eac,
		tcpi=(bac - ev) / (bac - ac) if bac - ac > 0 else 0, heads=c.H, committed=flt(c.committed), revised=F.revised)


# ---------------------------------------------------------------- receivables, payables, cash flow
def receivables(company):
	t = getdate(today())
	return frappe.db.sql("""select customer, name, project, due_date, outstanding_amount, posting_date from `tabSales Invoice` where docstatus = 1 and company = %s
		and outstanding_amount > 0.5""", company, as_dict=True), t


def payables(company):
	return frappe.db.sql("""select pi.supplier, pi.name, pi.project, pi.due_date, pi.outstanding_amount, pi.posting_date, s.hs_msme_category from `tabPurchase Invoice` pi
		left join `tabSupplier` s on s.name = pi.supplier where pi.docstatus = 1 and pi.company = %s and pi.outstanding_amount > 0.5""", company, as_dict=True)


def bucket(days):
	return 0 if days <= 0 else 1 if days <= 30 else 2 if days <= 60 else 3 if days <= 90 else 4


def cash_forecast(company, weeks=8):
	"""Eight weeks from the documents: client receipts (invoiced by due date, certified and with-the-client bills at 30 days
	from expected certification), supplier and subcontractor bills by due date, weekly wages, staff salaries at month end and
	the statutory payments when due."""
	t = getdate(today())
	wk = [frappe._dict(start=add_days(t, 7 * i), inflow=0.0, outflow=0.0, lines=[]) for i in range(weeks)]

	def put(d, amt, inflow, what):
		i = max(0, date_diff(d, t) // 7) if d else 0
		if i < weeks:
			w = wk[i]
			if inflow:
				w.inflow += amt
			else:
				w.outflow += amt
			w.lines.append((what, amt, inflow))

	names = [n for n in CN.project_names() if frappe.get_cached_value("Project", n, "company") == company]
	for r in frappe.get_all("RA Bill", filters={"project": ["in", names or [""]], "status": ["in", ["Submitted to client", "Certified", "Invoiced", "Part paid"]]},
			fields=["status", "net_receivable", "received_amount", "due_date", "submitted_on", "certified_on"]):
		if r.status in ("Invoiced", "Part paid"):
			put(r.due_date, flt(r.net_receivable) - flt(r.received_amount), True, _("Client receipts (invoiced)"))
		elif r.status == "Certified":
			put(add_days(r.certified_on or t, 32), flt(r.net_receivable), True, _("Client receipts (certified, to invoice)"))
		else:
			put(add_days(r.submitted_on or t, 55), flt(r.net_receivable) * .98, True, _("Client receipts (bills with the client)"))
	for p in payables(company):
		put(p.due_date, flt(p.outstanding_amount), False, _("Suppliers & subcontractors"))
	if frappe.db.exists("DocType", "Weekly Muster"):
		recent = flt(frappe.db.sql("""select sum(net) from `tabWeekly Muster` where company = %s and status = 'Paid' and week_start >= %s""", (company, add_days(t, -35)))[0][0])
		for i in range(weeks):
			put(add_days(t, 7 * i + 6), recent / 4, False, _("Site wages"))
	last = frappe.get_all("Staff Payroll", filters={"company": company, "status": ["in", ["Approved", "Paid"]]}, fields=["net", "month"], order_by="month desc", limit=1) \
		if frappe.db.exists("DocType", "Staff Payroll") else []
	if last:
		for k in range(0, 3):
			d = get_last_day(add_months(t, k))
			put(d, flt(last[0].net), False, _("Staff salaries"))
	for x in calendar_items(company, 1):
		if x.state != "Paid" and x.kind != "GSTR-1":
			put(max(t, getdate(x.due)), flt(x.amount), False, _("Statutory — {0}").format(_(x.kind)))
	bal = flt(frappe.db.sql("""select sum(debit - credit) from `tabGL Entry` where is_cancelled = 0 and account in (select name from `tabAccount` where company = %s
		and account_type = 'Bank' and is_group = 0)""", company)[0][0])
	for w in wk:
		w.opening = bal
		bal += w.inflow - w.outflow
		w.closing = bal
	return wk


# ---------------------------------------------------------------- staff payroll
def income_tax_annual(annual_gross):
	taxable = max(0, annual_gross - STD_DED)
	if taxable <= REBATE_LIMIT:
		return 0
	tax, low = 0.0, 0
	for top, rate in SLABS:
		if taxable > low:
			tax += (min(taxable, top) - low) * rate
		low = top
	tax = min(tax, taxable - REBATE_LIMIT) if taxable - REBATE_LIMIT < tax else tax  # marginal relief just above the rebate limit
	return round(tax * 1.04)


def payroll_validate(doc):
	doc.month = get_first_day(doc.month)
	days_in = calendar.monthrange(getdate(doc.month).year, getdate(doc.month).month)[1]
	for r in doc.rows:
		e = frappe.get_cached_doc("Employee", r.employee)
		r.project = r.project or e.get("hs_cn_project")
		r.state = r.state or e.get("hs_cn_state") or "Kerala"
		f = min(1, flt(r.days or days_in) / days_in)
		r.basic = flt(r.basic) or flt(flt(e.get("hs_cn_basic")) * f, 0)
		r.hra = flt(r.hra) or flt(flt(e.get("hs_cn_hra")) * f, 0)
		r.special = flt(r.special) or flt(flt(e.get("hs_cn_special")) * f, 0)
		r.gross = flt(r.basic + r.hra + r.special, 2)
		r.pf = flt(min(r.basic, 15000) * .12, 0)
		r.esi = flt(r.gross * .0075, 0) if r.gross <= 21000 else 0
		r.pt = PT.get(r.state, 200) if r.gross > 12000 else 0
		full = flt(e.get("hs_cn_basic")) + flt(e.get("hs_cn_hra")) + flt(e.get("hs_cn_special"))
		r.tds = flt(income_tax_annual(full * 12) / 12, 0)
		r.net = flt(r.gross - r.pf - r.esi - r.pt - r.tds, 2)
	doc.employees = len(doc.rows)
	for f in ("gross", "pf", "esi", "pt", "tds", "net"):
		doc.set(f, flt(sum(flt(r.get(f)) for r in doc.rows), 2))
	doc.employer_pf = flt(doc.pf * 13 / 12, 2)
	doc.employer_esi = flt(sum(flt(r.gross) * .0325 for r in doc.rows if flt(r.esi)), 2)
	if frappe.db.exists("Staff Payroll", {"company": doc.company, "month": doc.month, "name": ["!=", doc.name or ""]}):
		frappe.throw(_("The payroll for {0} already exists.").format(frappe.utils.formatdate(doc.month, "MMMM yyyy")))


def pay_payroll(name, posting_date=None):
	s = frappe.get_doc("Staff Payroll", name)
	acc = accounts(s.company)
	cc = frappe.get_cached_value("Company", s.company, "cost_center")
	by = {}
	for r in s.rows:
		k = r.project or ""
		by[k] = by.get(k, 0) + flt(r.gross) + flt(r.gross and r.pf * 13 / 12) + (flt(r.gross) * .0325 if flt(r.esi) else 0)
	sal = acc.heads["Site overheads"]
	ho = P._account(s.company, "Salaries — head office", "Expense", P._group(s.company, "Expense", ("Indirect Expenses", "Expenses")), "Expense Account")
	rows = [{"account": sal if k else ho, "debit_in_account_currency": flt(v, 2), "cost_center": cc, "project": k or None} for k, v in by.items()]
	diff = flt(s.gross + s.employer_pf + s.employer_esi, 2) - flt(sum(r["debit_in_account_currency"] for r in rows), 2)
	if abs(diff) >= .01:
		rows[0]["debit_in_account_currency"] = flt(rows[0]["debit_in_account_currency"] + diff, 2)
	rows += [{"account": CN.bank_account(s.company), "credit_in_account_currency": flt(s.net, 2), "cost_center": cc},
		{"account": acc.pf_payable, "credit_in_account_currency": flt(s.pf + s.employer_pf, 2), "cost_center": cc}]
	for a, v in ((acc.esi_payable, flt(s.esi + s.employer_esi, 2)), (acc.pt, s.pt), (acc.tds192, s.tds)):
		if flt(v):
			rows.append({"account": a, "credit_in_account_currency": flt(v, 2), "cost_center": cc})
	d = posting_date or get_last_day(s.month)
	je = frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Bank Entry", "company": s.company, "posting_date": d, "cheque_no": f"SAL/{s.name}", "cheque_date": d,
		"user_remark": _("Staff salaries {0} — {1} employees").format(frappe.utils.formatdate(s.month, "MMMM yyyy"), s.employees), "accounts": rows})
	je.flags.ignore_permissions = True
	je.flags.hs_system_entry = True
	je.insert()
	je.submit()
	s.db_set({"status": "Paid", "journal_entry": je.name, "paid_on": d})
	return je.name


def gratuity(e):
	"""Payment of Gratuity Act: 15/26 × last basic × completed years (5 years to be payable), capped at ₹20 lakh."""
	if not e.get("date_of_joining"):
		return frappe._dict(years=0, amount=0, eligible=False)
	yrs = date_diff(today(), e.date_of_joining) / 365.25
	return frappe._dict(years=yrs, amount=min(2000000, 15 / 26 * flt(e.get("hs_cn_basic")) * int(yrs + (1 if yrs % 1 >= .5 else 0))), eligible=yrs >= 5)


# ---------------------------------------------------------------- manual journals: the approval matrix
def je_before_submit(doc, method=None):
	if doc.flags.get("hs_system_entry") or frappe.flags.hs_demo_loading or frappe.flags.in_import or frappe.flags.in_install:
		return
	if doc.voucher_type != "Journal Entry" or doc.company not in companies():
		return
	from hipersign_trading.features import feature_on

	if not feature_on("cn_fin"):
		return
	amt = flt(doc.total_debit)
	need = [MD] if amt > limits().jv_md else [AM, MD]
	if not P._has(*need):
		frappe.throw(_("A manual journal of {0} needs the {1} — save it as a draft; it waits in Approvals.").format(CN.inr(amt), " / ".join(_(r) for r in need)),
			frappe.PermissionError)


def flags(name):
	out = []
	if not frappe.db.exists("DocType", "Staff Payroll"):
		return out
	x = evm(name)
	F = CN.fig(name)
	if x.ac and x.cpi and x.cpi < .92 and F.step < 22:
		out.append({"lvl": "High" if x.cpi < .85 else "Medium", "text": _("CPI {0:.2f} — every ₹100 spent earns ₹{1:.0f} of work; forecast overrun {2}").format(x.cpi, x.cpi * 100,
			CN.inr(-x.vac)), "open": ["Project", name]})
	c = cess_due(name)
	if c.due > 500000 and F.step >= 10:
		out.append({"lvl": "Medium", "text": _("BOCW labour cess {0} not paid to the welfare board").format(CN.inr(c.due)), "open": ["Project", name]})
	return out


# ---------------------------------------------------------------- actions
def _doc(dt, name, perm="read"):
	d = frappe.get_doc(dt, name)
	d.check_permission(perm)
	return d


def _who():
	return frappe.utils.get_fullname(frappe.session.user)


def _a_pay_approve(name, a):
	CN._need([AM, MD, FM], _("Approving the payroll"))
	s = _doc("Staff Payroll", name)
	if s.status != "Draft":
		frappe.throw(_("{0} is {1}.").format(s.name, _(s.status)))
	s.db_set({"status": "Approved", "approved_by": _who()})
	return {"message": _("Payroll {0} approved — {1} to pay").format(frappe.utils.formatdate(s.month, "MMM yyyy"), CN.inr(s.net))}


def _a_pay_pay(name, a):
	CN._need([AM, AU, MD], _("Paying the salaries"))
	s = _doc("Staff Payroll", name)
	if s.status != "Approved":
		frappe.throw(_("{0} is {1} — it is approved first.").format(s.name, _(s.status)))
	with CN._elevated():
		je = pay_payroll(s.name, a.get("date"))
	return {"message": _("Salaries paid — {0}").format(je), "open": ["Journal Entry", je]}


def _a_dep_pay(name, a):
	"""name: a Statutory Deposit, or 'new' with args kind / month / gstin / project / amount."""
	CN._need([AM, AU, MD], _("Paying a statutory due"))
	with CN._elevated():
		if name == "new":
			d = frappe.get_doc({"doctype": "Statutory Deposit", "company": a.get("company") or (companies() or [None])[0],
				"kind": a.get("kind"), "month": a.get("month"), "gstin": a.get("gstin"), "project": a.get("project"), "state": a.get("state"), "amount": flt(a.get("amount")) or 0.01,
				"challan_no": a.get("challan_no"), "paid_on": a.get("date") or today()})
			d.insert(ignore_permissions=True)
			name = d.name
		je = pay_deposit(name, a.get("date"))
	return {"message": _("Paid — {0}").format(je), "open": ["Journal Entry", je]}


def _a_jv_approve(name, a):
	je = frappe.get_doc("Journal Entry", name)
	CN._need([MD] if flt(je.total_debit) > limits().jv_md else [AM, MD], _("Approving this journal"))
	je.flags.ignore_permissions = True
	if je.docstatus != 0:
		frappe.throw(_("{0} is already posted.").format(je.name))
	je.flags.hs_system_entry = True  # the approver posts it
	je.add_comment("Comment", _("Approved by {0}").format(_who()))
	je.submit()
	return {"message": _("{0} posted").format(je.name)}


ACTIONS = {"pay_approve": _a_pay_approve, "pay_pay": _a_pay_pay, "dep_pay": _a_dep_pay, "jv_approve": _a_jv_approve}
VALIDATE = {"Staff Payroll": payroll_validate, "Statutory Deposit": deposit_validate}
