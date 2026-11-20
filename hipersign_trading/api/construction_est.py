"""v1.9.1 stage B1 (prototype C12, BOQ & Rate Analysis and Tenders): Construction (India) — estimating.

  · Rate Analysis: an item of work analysed per unit — material, labour and plant from DSR coefficients and current rates
    (the latest purchase order of the company for linked items), plus water charges, contractor overheads and profit. It is
    also the rate library: our rate against the state schedule of rates (SOR) and the rates we quoted in the last tenders.
  · BOQ lines linked to a rate analysis take their cost build-up (material, labour and plant shares of the rate) from it —
    the build-up becomes the project budget.
  · BOQ versions: tender BOQ → contract BOQ (after negotiation) → revised BOQ (with the approved variations). The
    measurement book and the RA bills always work on the current version; earlier versions are kept, superseded.
  · Tender price: direct cost from the build-up, site and head-office overheads, contingency, target margin → bid price
    against the client's estimate; bids above ₹20 crore need the MD.
  · BOQ templates: a new tender or project BOQ from a standard BOQ, quantities following the value.
  · Tender submission checklist (a bid is not submitted with items missing) and the bids opened — L1, our rank, vs estimate.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from hipersign_trading.api import construction as CN

MD, PM, PMS, QS, BD = "Managing Director", "Project Manager", "Projects Manager", "Quantity Surveyor", "BD Manager"
CHECKLIST = ["Tender documents & corrigenda downloaded", "Pre-bid queries submitted", "Site visit report", "Estimate & rate analysis approved",
	"PAN, GST and contractor registration", "Turnover — CA certificate, last 3 years", "Similar works — completion certificates", "Solvency certificate",
	"EMD paid / BG uploaded", "Financial bid (BOQ) filled", "Signed with the digital signature (DSC) and uploaded"]
MD_BID_LIMIT = 200000000  # ₹20 crore — the default; Hipersign Settings › cn_bid_md_limit (v1.9.1 B4: the approval matrix)


def bid_limit():
	return flt(frappe.get_cached_doc("Hipersign Settings").get("cn_bid_md_limit")) or MD_BID_LIMIT
SHARE_OF = {"Material": "mat_share", "Labour": "lab_share", "Plant": "plant_share"}
COST_OF = {"Material": "material_cost", "Labour": "labour_cost", "Plant": "plant_cost"}


def _who():
	return frappe.utils.get_fullname(frappe.session.user)


# ================================================================ rate analysis
def ra_validate(doc):
	for k in COST_OF.values():
		doc.set(k, 0)
	for r in doc.resources:
		r.amount = flt(flt(r.coefficient) * flt(r.rate), 2)
		f = COST_OF.get(r.resource_type)
		doc.set(f, flt(doc.get(f)) + r.amount)
	doc.base_cost = flt(flt(doc.material_cost) + flt(doc.labour_cost) + flt(doc.plant_cost), 2)
	doc.water = flt(doc.base_cost * flt(doc.water_pct) / 100, 2)
	doc.overheads = flt((doc.base_cost + doc.water) * flt(doc.overhead_pct) / 100, 2)
	doc.profit = flt((doc.base_cost + doc.water + doc.overheads) * flt(doc.profit_pct) / 100, 2)
	doc.analysed_rate = flt(doc.base_cost + doc.water + doc.overheads + doc.profit, 2)
	if not doc.resources:
		frappe.throw(_("Add the material, labour and plant per {0}.").format(doc.unit or _("unit")))


def last_po_rate(company, item):
	"""The latest rate the company bought the item at — purchase order, receipt or invoice, whichever is the latest."""
	best = None
	for dt, child, d in (("Purchase Order", "Purchase Order Item", "transaction_date"), ("Purchase Receipt", "Purchase Receipt Item", "posting_date"),
			("Purchase Invoice", "Purchase Invoice Item", "posting_date")):
		r = frappe.db.sql(f"""select i.base_rate, p.name, p.{d} as dt from `tab{child}` i join `tab{dt}` p on p.name = i.parent
			where p.docstatus = 1 and p.company = %s and i.item_code = %s and i.base_rate > 0 order by p.{d} desc, p.creation desc limit 1""", (company, item), as_dict=True)
		if r and (not best or getdate(r[0].dt) > getdate(best.dt)):
			best = r[0]
	if best:
		best.transaction_date = best.dt
	return best


def refresh_rates(doc):
	n = 0
	for r in doc.resources:
		if r.item:
			x = last_po_rate(doc.company, r.item)
			if x and flt(x.base_rate):
				if abs(flt(x.base_rate) - flt(r.rate)) > .005:
					n += 1
				r.rate, r.rate_source = flt(x.base_rate, 2), f"{x.name} · {frappe.format(x.transaction_date, {'fieldtype': 'Date'})}"
			elif not r.rate_source:
				r.rate_source = _("Entered")
		elif not r.rate_source:
			r.rate_source = _("Entered")
	doc.rates_as_of = today()
	return n


def quoted_history(name, limit=3):
	"""The rates we quoted against this analysis in the latest BOQs (tenders and contracts)."""
	return frappe.db.sql("""select i.rate, b.name, b.title, b.version_type, b.status from `tabProject BOQ Item` i join `tabProject BOQ` b on b.name = i.parent
		where i.rate_analysis = %s and b.version_type in ('Tender BOQ', 'Contract BOQ') order by b.creation desc limit %s""", (name, limit), as_dict=True)


# ================================================================ BOQ: build-up, price and versions
def boq_validate(doc):
	doc.version_type = doc.version_type or ("Tender BOQ" if doc.tender and not doc.project else "Contract BOQ")
	cache = {}
	changed = False
	for r in doc.items:
		if not r.rate_analysis:
			continue
		a = cache.get(r.rate_analysis) or cache.setdefault(r.rate_analysis, frappe.db.get_value("Rate Analysis", r.rate_analysis,
			["analysed_rate", "material_cost", "labour_cost", "plant_cost", "water_pct", "unit"], as_dict=True))
		if not a:
			continue
		r.analysed_rate = a.analysed_rate
		has = any(flt(r.get(f)) for f in ("mat_share", "lab_share", "plant_share", "sub_share"))
		# the build-up follows the analysis while the tender is priced; after award it is the budget and stays put
		if flt(r.rate) and ((doc.version_type or "") == "Tender BOQ" or not has):
			w = 1 + flt(a.water_pct) / 100
			for t, f in SHARE_OF.items():
				r.set(f, flt(flt(a.get(COST_OF[t])) * w / flt(r.rate) * 100, 2))
			changed = True
	if changed:  # the controller computed the totals before the shares changed
		SH = ("mat_share", "lab_share", "sub_share", "plant_share", "ovh_share")
		for r in doc.items:
			r.cost_rate = flt(flt(r.rate) * sum(flt(r.get(s)) for s in SH) / 100, 2)
		doc.direct_cost = flt(sum(flt(r.cost_rate) * flt(r.qty) for r in doc.items), 2)
		if doc.total_amount:
			doc.margin_pct = flt((doc.total_amount - doc.direct_cost - flt(doc.overheads)) / doc.total_amount * 100, 2)
	adds = flt(doc.site_oh_pct) + flt(doc.ho_oh_pct) + flt(doc.contingency_pct)
	doc.total_cost = flt(flt(doc.direct_cost) * (1 + adds / 100), 2)
	m = flt(doc.target_margin)
	doc.bid_price = flt(doc.total_cost / (1 - m / 100), 0) if 0 <= m < 90 and doc.total_cost else 0
	doc.approved_variations = flt(sum(flt(e.amount) for e in frappe.get_all("Extra Item", filters={"project": doc.project, "status": "Approved"}, fields=["amount"]))) \
		if doc.project and doc.version_type == "Revised BOQ" else 0
	doc.revised_value = flt(flt(doc.total_amount) + flt(doc.approved_variations), 2)


def price(boq):
	b = frappe.get_doc("Project BOQ", boq) if isinstance(boq, str) else boq
	d = flt(b.direct_cost)
	return frappe._dict(direct=d, site=d * flt(b.site_oh_pct) / 100, ho=d * flt(b.ho_oh_pct) / 100, cont=d * flt(b.contingency_pct) / 100, total=flt(b.total_cost),
		margin=flt(b.target_margin), bid=flt(b.bid_price))


def new_version(name, kind, discount_pct=0):
	"""A new version of the current BOQ: Contract (after negotiation — rates less the discount) or Revised (with the approved
	variations). The old version is kept, superseded."""
	old = frappe.get_doc("Project BOQ", name)
	if old.status == "Superseded":
		frappe.throw(_("{0} is superseded — revise the current version.").format(old.name))
	kind = {"Contract": "Contract BOQ", "Revised": "Revised BOQ"}.get(kind, kind)
	if kind == "Contract BOQ" and old.version_type != "Tender BOQ":
		frappe.throw(_("The contract BOQ is made from the tender BOQ."))
	if kind == "Contract BOQ" and old.tender and frappe.db.get_value("Tender", old.tender, "status") not in ("Awarded", "L1 — LOA awaited"):
		frappe.throw(_("{0} is not awarded yet — the contract BOQ follows the award.").format(old.tender))
	if kind == "Revised BOQ" and not old.project:
		frappe.throw(_("A revised BOQ needs the project."))
	new = frappe.copy_doc(old)
	new.version_type, new.version_of, new.revision = kind, old.name, cint(old.revision) + 1
	new.status = "Awarded" if old.project or kind != "Tender BOQ" else old.status
	if kind == "Contract BOQ":
		t = frappe.get_cached_doc("Tender", old.tender) if old.tender else None
		new.project = new.project or (t.project if t else None)
		f = 1 - flt(discount_pct) / 100
		for r in new.items:
			r.rate = flt(flt(r.rate) * f, 2)
	for r_new, r_old in zip(new.items, old.items):
		r_new.measured_pct, r_new.certified_pct = r_old.measured_pct, r_old.certified_pct
	new.flags.ignore_permissions = True
	new.insert()
	old.db_set("status", "Superseded")
	frappe.clear_document_cache("Project BOQ", old.name)
	try:
		from hipersign_trading.api import projects as P

		P._c().pop("boq", None)
	except Exception:
		pass
	return new


def from_template(template, value, title=None, project=None, tender=None, company=None):
	T = frappe.get_doc("BOQ Template", template)
	value = flt(value)
	if value <= 0:
		frappe.throw(_("Enter the value the BOQ is priced for."))
	items = []
	for l in T.items:
		amt = value * flt(l.weight_pct) / 100
		if (l.unit or "").upper() == "LS" or not flt(l.rate):
			qty, rate = 1, round(amt)
		else:
			rate = flt(l.rate)
			qty = max(1, round(amt / rate)) if (l.unit or "") in ("Nos", "Set") else round(amt / rate * 10) / 10
		items.append({"section": (l.section_name or "A")[:1].upper(), "section_name": l.section_name, "item_no": l.item_no, "description": l.description, "unit": l.unit,
			"qty": qty, "rate": rate, "rate_analysis": l.rate_analysis, "mat_share": l.mat_share, "lab_share": l.lab_share, "sub_share": l.sub_share, "plant_share": l.plant_share,
			"ovh_share": l.ovh_share})
	t = frappe.get_cached_doc("Tender", tender) if tender else None
	b = frappe.get_doc({"doctype": "Project BOQ", "title": title or (t.tender_name if t else T.title), "project": project, "tender": tender, "template": T.name,
		"company": company or (t.company if t else frappe.defaults.get_user_default("Company")), "customer": t.customer if t else None, "client_name": t.client_name if t else None,
		"status": "Being priced" if tender and not project else "Awarded", "version_type": "Tender BOQ" if tender and not project else "Contract BOQ", "revision": 1,
		"received_on": t.published_on if t else today(), "due_date": t.due_date if t else None, "target_margin": flt(t.our_margin_pct) if t else 12, "items": items})
	b.flags.ignore_permissions = True
	b.insert()
	if t:
		frappe.db.set_value("Tender", t.name, "boq", b.name)
	return b


def template_validate(doc):
	doc.total_weight = flt(sum(flt(l.weight_pct) for l in doc.items), 2)
	if doc.items and abs(doc.total_weight - 100) > .5:
		frappe.msgprint(_("The shares add up to {0}% — a BOQ made from this template is priced for that share of the value.").format(doc.total_weight), alert=True)


# ================================================================ tenders: checklist and bids
def tender_validate(doc):
	if doc.is_new() and not doc.checklist:
		for x in CHECKLIST:
			doc.append("checklist", {"item": x})
	for r in doc.checklist:
		if cint(r.done) and not r.done_on:
			r.done_on, r.done_by = today(), _who()
		if not cint(r.done):
			r.done_on = r.done_by = None
	doc.checklist_total = len(doc.checklist)
	doc.checklist_done = len([r for r in doc.checklist if cint(r.done)])
	B = sorted([r for r in doc.bidders if flt(r.bid_amount)], key=lambda r: flt(r.bid_amount))
	for i, r in enumerate(B, 1):
		r.rank = i
	doc.l1_amount = flt(B[0].bid_amount) if B else 0
	us = next((r for r in B if cint(r.is_us)), None)
	if us:
		doc.rank = f"L{us.rank}" if us.rank <= 5 else "L6+"
		if not flt(doc.our_bid):
			doc.our_bid = us.bid_amount


def check_ready(t):
	if t.checklist and t.checklist_done < t.checklist_total:
		miss = [r.item for r in t.checklist if not cint(r.done)]
		frappe.throw(_("{0} items of the submission checklist are not ready: {1}").format(len(miss), "; ".join(miss)))


# ================================================================ actions
def _doc(dt, name, perm="read"):
	d = frappe.get_doc(dt, name)
	d.check_permission(perm)
	return d


def _a_ran_refresh(name, a):
	CN._need([QS, PM, MD, PMS, BD], _("Refreshing the rates"))
	d = _doc("Rate Analysis", name)
	n = refresh_rates(d)
	d.save(ignore_permissions=True)
	return {"message": _("{0} rate(s) updated from the latest purchases — analysed rate {1}").format(n, CN.inr(d.analysed_rate))}


def _a_ran_approve(name, a):
	CN._need([QS, PM, MD, PMS], _("Approving a rate analysis"))
	d = _doc("Rate Analysis", name)
	d.db_set({"status": "Approved", "approved_by": _who()})
	return {"message": _("{0} approved at {1} per {2}").format(d.title, CN.inr(d.analysed_rate), d.unit)}


def _a_boq_ver(name, a):
	CN._need([QS, PM, MD, PMS], _("Making a new BOQ version"))
	_doc("Project BOQ", name)
	with CN._elevated():
		b = new_version(name, a.get("kind") or "Revised", flt(a.get("discount")))
	return {"message": _("{0} {1} (rev {2}) is now current — {3}").format(_(b.version_type), b.name, b.revision, CN.inr(b.revised_value or b.total_amount)),
		"open": ["Project BOQ", b.name]}


def _a_boq_price(name, a):
	"""name: a Project BOQ; args: margin — sets the target margin and the bid price, and the tender's quoted value."""
	CN._need([QS, PM, MD, PMS, BD], _("Pricing the tender"))
	b = _doc("Project BOQ", name)
	m = flt(a.get("margin"))
	if not 0 <= m < 40:
		frappe.throw(_("A margin between 0 and 40%."))
	b.target_margin = m
	b.flags.ignore_permissions = True
	b.save()
	if b.tender:
		t = frappe.get_doc("Tender", b.tender)
		if t.status not in ("Bid / no-bid", "Being priced"):
			frappe.throw(_("{0} is already {1} — the price cannot change.").format(t.name, _(t.status)))
		if flt(b.bid_price) > bid_limit() and not frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": MD}) and frappe.session.user != "Administrator":
			frappe.throw(_("A bid of {0} is above ₹20 crore — the Managing Director sets it.").format(CN.inr(b.bid_price)), frappe.PermissionError)
		t.our_bid, t.our_margin_pct = b.bid_price, m
		t.flags.ignore_permissions = True
		t.save()
	return {"message": _("Bid price {0} at {1}% margin").format(CN.inr(b.bid_price), m)}


def _a_boq_tpl(name, a):
	"""name: a BOQ Template; args: tender or project, value."""
	CN._need([QS, PM, MD, PMS, BD], _("Starting a BOQ from a template"))
	tender, project = a.get("tender"), a.get("project")
	if not (tender or project):
		frappe.throw(_("Pick the tender or the project."))
	if tender and frappe.db.get_value("Tender", tender, "boq"):
		frappe.throw(_("{0} already has a priced BOQ ({1}).").format(tender, frappe.db.get_value("Tender", tender, "boq")))
	if project and CN.boq(project):
		frappe.throw(_("{0} already has a BOQ — make a new version instead.").format(project))
	value = flt(a.get("value")) or (flt(frappe.db.get_value("Tender", tender, "estimated_value")) if tender else flt(frappe.db.get_value("Project", project, "hs_contract_value")))
	with CN._elevated():
		b = from_template(name, value, project=project, tender=tender, company=frappe.db.get_value("Project", project, "company") if project else None)
	return {"message": _("{0} made from {1}: {2} items, {3}").format(b.name, name, len(b.items), CN.inr(b.total_amount)), "open": ["Project BOQ", b.name]}


def _a_tnd_chk(name, a):
	"""args: done — the list of checklist rows (idx) that are ready."""
	CN._need([QS, PM, MD, PMS, BD], _("Updating the submission checklist"))
	t = _doc("Tender", name, "write")
	done = {cint(x) for x in (frappe.parse_json(a.get("done")) if isinstance(a.get("done"), str) else a.get("done") or [])}
	for r in t.checklist:
		r.done = 1 if r.idx in done else 0
	t.save()
	return {"message": _("{0}: {1} of {2} ready").format(t.name, t.checklist_done, t.checklist_total)}


ACTIONS = {"ran_refresh": _a_ran_refresh, "ran_approve": _a_ran_approve, "boq_ver": _a_boq_ver, "boq_price": _a_boq_price, "boq_tpl": _a_boq_tpl, "tnd_chk": _a_tnd_chk}
VALIDATE = {"Rate Analysis": ra_validate, "BOQ Template": template_validate}
