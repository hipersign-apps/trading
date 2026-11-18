"""v1.9.0 stage A6 (prototype C9): Construction (India) — project controls (feature cn_ctl) and the portals and apps
(feature cn_portal).

  · Project Controls: RAG on eleven dimensions computed from the live records (with the reasons), the constraints
    look-ahead, milestones and deliverables (planned / forecast / actual, slip), the portfolio timeline and the weekly review.
  · Publishing: photos, weekly progress reports and GFC drawings wait for the PM before the client sees them.
  · Client portal (/cn-client): progress, published photos, RA bills (certified online by private clients), documents,
    variations (approved online), snags — switched per client.
  · Subcontractor portal (/cn-partner): work orders, running bills (submitted online), payments, labour documents, photos —
    everything the partner sends waits in the verification queue.
  · Site app (/cn-site) for site engineers: check-in with GPS, gang check-in of workers, DPR from today's attendance,
    geo-tagged photos, site cash (approval limit), deliveries (site OTP for the driver), site chat.
  · Worker app (/cn-worker) by mobile number and PIN, in English, Malayalam, Tamil and Hindi: attendance, pay slip,
    advance request, report a danger.
"""

import base64
import hashlib
import hmac
import json

import frappe
from frappe import _
from frappe.utils import (add_days, cint, date_diff, flt, get_datetime, getdate, now_datetime, nowtime, today)

from hipersign_trading.api import construction as CN
from hipersign_trading.api import projects as P

MD, PM, PMS, QS, SE, AM, AU = "Managing Director", "Project Manager", "Projects Manager", "Quantity Surveyor", "Site Engineer", "Accounts Manager", "Accounts User"
QA, SO, DC, SK, HR = "QA/QC Engineer", "Safety Officer", "Document Controller", "Storekeeper", "HR & Admin"

DIMS = [("schedule", "Schedule"), ("cost", "Cost"), ("cash", "Cash"), ("billing", "Billing"), ("quality", "Quality"), ("safety", "Safety"), ("labour", "Labour"),
	("materials", "Materials"), ("design", "Design & RFIs"), ("client", "Client"), ("compliance", "Compliance")]
# a red flag's words decide the dimension it counts against (lower case; first match wins)
WORDS = [("schedule", ("behind the extended", "ld exposure", "hindrance", "eot ", "milestone", "spi ")), ("cost", ("margin", "cpi ", "overrun", "budget")),
	("safety", ("lti", "incident", "permit", "safety audit", "ppe", "danger")), ("quality", ("ncr", "cube", "inspection", "itp ")), ("design", ("rfi", "drawing", "gfc")),
	("materials", ("over theory", "material", "indent", "wastage", "dead stock")), ("compliance", ("labour cess", "gst", "tds 194", "guarantee", "insurance", "fitness", "licence", "bond",
		"service due")), ("labour", ("worker", "wage", "muster", "labour", "esi", "on hold")), ("billing", ("ra bill", "not certified", "extra item", "26as", "unbilled", "claim")),
	("cash", ("overdue", "receipt", "retention", "advance")), ("client", ("client", "snag", "dlp", "defect", "variation")), ("schedule", ("late", "delay", "constraint"))]
TONE = {"Red": 3, "Amber": 2, "Green": 1}


def limits():
	s = frappe.get_cached_doc("Hipersign Settings")
	return frappe._dict(cash=flt(s.get("cn_site_cash_limit")) or 5000)


def _who():
	return frappe.utils.get_fullname(frappe.session.user)


def log(party_type, party, action, project=None, ref=None):
	frappe.get_doc({"doctype": "Portal Activity", "user": frappe.session.user if frappe.session.user != "Guest" else None, "party_type": party_type, "party": party,
		"project": project, "action": action[:140], "reference_doctype": ref[0] if ref else None, "reference_name": ref[1] if ref else None}).insert(ignore_permissions=True)


# ================================================================ project controls
def rag(project):
	"""Eleven dimensions, each Green / Amber / Red with the reasons — from the project's red flags (every module) and the
	earned-value, billing, cash and look-ahead figures."""
	out = {k: frappe._dict(key=k, label=l, state="Green", why=[]) for k, l in DIMS}

	def put(k, state, why):
		d = out[k]
		if TONE[state] > TONE[d.state]:
			d.state = state
		if why and why not in d.why:
			d.why.append(why)

	for f in CN.flags(project):
		txt = f.get("text") or ""
		low = txt.lower()
		k = next((k for k, words in WORDS if any(w in low for w in words)), "schedule")
		put(k, "Red" if f.get("lvl") == "High" else "Amber", txt)
	F = CN.fig(project)
	from hipersign_trading.api import construction_fin as FN

	x = FN.evm(project)
	if x.pv and F.step < 22:
		if x.spi < .85:
			put("schedule", "Red", _("SPI {0:.2f} — {1:.0f}% done against {2:.0f}% planned").format(x.spi, x.done, x.planned))
		elif x.spi < .95:
			put("schedule", "Amber", _("SPI {0:.2f} — {1:.0f}% done against {2:.0f}% planned").format(x.spi, x.done, x.planned))
	if x.ac and F.step < 22:
		if x.cpi < .92:
			put("cost", "Red", _("CPI {0:.2f} — forecast overrun {1}").format(x.cpi, CN.inr(-x.vac)))
		elif x.cpi < .97:
			put("cost", "Amber", _("CPI {0:.2f} — forecast overrun {1}").format(x.cpi, CN.inr(-x.vac)))
	if F.overdue > 1:
		put("cash", "Red" if F.overdue > .1 * max(F.billed, 1) else "Amber", _("{0} overdue from the client").format(CN.inr(F.overdue)))
	unbilled = F.work - F.billed - F.pending_cert
	if F.revised and F.step < 24 and unbilled > .05 * F.revised:
		put("billing", "Red" if unbilled > .1 * F.revised else "Amber", _("{0} of work done not yet billed").format(CN.inr(unbilled)))
	t = getdate(today())
	for c in frappe.get_all("Project Constraint", filters={"project": project, "status": "Open"}, fields=["description", "need_by", "owner_name"]):
		if getdate(c.need_by) < t:
			put("schedule", "Red", _("Constraint past need-by: {0} ({1})").format(c.description, c.owner_name or "—"))
		elif date_diff(c.need_by, t) <= 7:
			put("schedule", "Amber", _("Constraint due in {0} days: {1}").format(date_diff(c.need_by, t), c.description))
	for m in frappe.get_all("Construction Milestone", filters={"project": project, "status": ["in", ["Late", "At risk"]]}, fields=["title", "slip_days", "status"]):
		put("schedule", "Red" if m.status == "Late" else "Amber", _("{0} — {1} days slip").format(m.title, m.slip_days))
	ei = frappe.db.count("Extra Item", {"project": project, "status": "Pending client"})
	if ei:
		put("client", "Amber", _("{0} variations waiting for the client").format(ei))
	return [out[k] for k, _l in DIMS]


def overall(R):
	reds = len([d for d in R if d.state == "Red"])
	ambers = len([d for d in R if d.state == "Amber"])
	return ("Red" if reds >= 3 else "Amber" if reds or ambers >= 3 else "Green"), reds, ambers


def week_monday(d=None):
	d = getdate(d or today())
	return add_days(d, -d.weekday())


def milestone_validate(doc):
	t = getdate(today())
	doc.forecast = doc.forecast or doc.planned
	ref = doc.actual or doc.forecast
	doc.slip_days = max(0, date_diff(ref, doc.planned)) if ref and doc.planned else 0
	if doc.actual:
		doc.status = "Done"
	elif getdate(doc.forecast) < t or doc.slip_days > 14:
		doc.status = "Late"
	elif doc.slip_days > 0:
		doc.status = "At risk"
	else:
		doc.status = "On track"


def constraint_validate(doc):
	doc.raised_by = doc.raised_by or _who()


def review_validate(doc):
	doc.week_start = week_monday(doc.week_start)
	if frappe.db.exists("Project Review", {"project": doc.project, "week_start": doc.week_start, "name": ["!=", doc.name or ""]}):
		frappe.throw(_("{0} is already reviewed for the week of {1}.").format(doc.project, frappe.format(doc.week_start, {"fieldtype": "Date"})))
	if not doc.rag_json:
		R = rag(doc.project)
		doc.rag_json = json.dumps({d.key: [d.state, d.why[:3]] for d in R})
		doc.overall, doc.reds, doc.ambers = overall(R)
	doc.reviewed_by = doc.reviewed_by or _who()


def last_review(project, before=None):
	f = {"project": project}
	if before:
		f["week_start"] = ["<", before]
	r = frappe.get_all("Project Review", filters=f, fields=["name", "week_start", "rag_json", "overall", "notes", "decisions", "reviewed_by"], order_by="week_start desc", limit=1)
	if not r:
		return None
	r = r[0]
	r.rag = json.loads(r.rag_json or "{}")
	return r


# ================================================================ photos and publishing
def photo_validate(doc):
	doc.taken_by = doc.taken_by or _who()
	if doc.source == "Subcontractor portal" and doc.is_new():
		doc.status = "To verify"


def expense_validate(doc):
	doc.requested_by = doc.requested_by or _who()
	if flt(doc.amount) <= 0:
		frappe.throw(_("Enter the amount spent."))


def attendance_validate(doc):
	doc.marked_by = doc.marked_by or _who()
	doc.time_in = doc.time_in or nowtime()
	w = frappe.get_cached_doc("Site Worker", doc.worker)
	if w.status != "Active":
		frappe.throw(_("{0} has left.").format(w.worker_name))
	if frappe.db.exists("Site Attendance", {"worker": doc.worker, "attendance_date": doc.attendance_date, "name": ["!=", doc.name or ""]}):
		frappe.throw(_("{0} is already marked present on {1}.").format(w.worker_name, frappe.format(doc.attendance_date, {"fieldtype": "Date"})))


def attendance_days(worker, start, end):
	return frappe.db.count("Site Attendance", {"worker": worker, "attendance_date": ["between", [start, end]]})


def weekly_report(project, monday):
	"""The weekly progress report from the DPRs of the week — work done, labour, weather, hindrances and progress."""
	end = add_days(monday, 6)
	D = frappe.get_all("Daily Progress Report", filters={"project": project, "report_date": ["between", [monday, end]], "status": ["!=", "Draft"]},
		fields=["report_date", "activity", "actual_qty", "unit", "own_labour", "sub_labour", "weather", "hours_lost", "remarks"], order_by="report_date asc")
	if not D:
		return None
	F = CN.fig(project)
	acts = {}
	for d in D:
		k = (d.activity or _("General works"), d.unit or "")
		acts[k] = acts.get(k, 0) + flt(d.actual_qty)
	labour = sum(cint(d.own_labour) + cint(d.sub_labour) for d in D)
	lost = sum(flt(d.hours_lost) for d in D)
	rows = "".join(f"<li>{frappe.utils.escape_html(a)} — {q:,.1f} {frappe.utils.escape_html(u)}</li>" for (a, u), q in acts.items())
	hin = frappe.get_all("Hindrance", filters={"project": project, "from_date": ["<=", end], "to_date": ["is", "not set"]}, pluck="cause")
	return (f"<p><b>{_('Progress')}:</b> {F.pct:.1f}% {_('of the revised contract')} ({CN.inr(F.work)} {_('of')} {CN.inr(F.revised)}).</p>"
		f"<p><b>{_('Work done this week')}:</b></p><ul>{rows}</ul>"
		f"<p><b>{_('Labour')}:</b> {labour:,} {_('man-days')} · <b>{_('Weather')}:</b> {', '.join(sorted({d.weather for d in D if d.weather})) or '—'}"
		+ (f" · {lost:g} {_('hours lost')}" if lost else "") + "</p>"
		+ (f"<p><b>{_('Hindrances')}:</b> {', '.join(frappe.utils.escape_html(h) for h in hin)}</p>" if hin else ""))


def sync_publications(projects=None):
	"""Puts in the publishing queue what the client could see and has not been decided: site photos in the project log,
	drawings issued GFC, and last week's progress report."""
	names = projects or CN.project_names()
	have = {(r.kind, r.photo or r.drawing or str(r.week_start), r.project) for r in frappe.get_all("Client Publication", filters={"project": ["in", names or [""]]},
		fields=["kind", "photo", "drawing", "week_start", "project"])}
	for p in frappe.get_all("Site Photo", filters={"project": ["in", names or [""]], "status": "In the project log"}, fields=["name", "project", "caption", "taken_on"]):
		if ("Photo", p.name, p.project) not in have:
			frappe.get_doc({"doctype": "Client Publication", "project": p.project, "kind": "Photo", "photo": p.name, "title": p.caption or _("Site photo")}).insert(ignore_permissions=True)
	for d in frappe.get_all("Construction Drawing", filters={"project": ["in", names or [""]], "status": "GFC"}, fields=["name", "project", "drawing_no", "revision", "title"]):
		if ("Drawing", d.name, d.project) not in have:
			frappe.get_doc({"doctype": "Client Publication", "project": d.project, "kind": "Drawing", "drawing": d.name,
				"title": f"{d.drawing_no} {d.revision} — {d.title}"}).insert(ignore_permissions=True)
	mon = add_days(week_monday(), -7)
	for n in names:
		if ("Weekly report", str(mon), n) in have or CN.fig(n).step >= 26:
			continue
		html = weekly_report(n, mon)
		if html:
			frappe.get_doc({"doctype": "Client Publication", "project": n, "kind": "Weekly report", "week_start": mon,
				"title": _("Weekly progress report — week of {0}").format(frappe.format(mon, {"fieldtype": "Date"})), "content": html}).insert(ignore_permissions=True)


# ================================================================ site cash
def imprest_account(company):
	return P._account(company, "Site Imprest", "Asset", P._group(company, "Asset", ("Cash In Hand", "Current Assets")), "Cash")


def book_expense(name):
	x = frappe.get_doc("Site Expense", name)
	p = frappe.get_cached_doc("Project", x.project)
	from hipersign_trading.api import construction_site as S

	acc = S.accounts(p.company)
	cc = p.cost_center or frappe.get_cached_value("Company", p.company, "cost_center")
	je = frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Cash Entry", "company": p.company, "posting_date": x.expense_date,
		"user_remark": _("Site cash {0}: {1} — {2}").format(x.project, x.description, x.paid_to or ""), "accounts": [
			{"account": acc.heads[x.head], "debit_in_account_currency": flt(x.amount, 2), "project": x.project, "cost_center": cc},
			{"account": imprest_account(p.company), "credit_in_account_currency": flt(x.amount, 2), "cost_center": cc}]})
	je.flags.ignore_permissions = True
	je.flags.hs_system_entry = True
	je.insert()
	je.submit()
	x.db_set({"status": "Booked", "journal_entry": je.name, "approved_by": x.approved_by or _("Within the site limit")})
	return je.name


def imprest_balance(company):
	return flt(frappe.db.sql("select sum(debit - credit) from `tabGL Entry` where is_cancelled = 0 and account = %s", imprest_account(company))[0][0])


# ================================================================ delivery OTP
def otp_for(stock_entry):
	key = (frappe.local.conf.get("encryption_key") or frappe.local.conf.get("db_password") or "hipersign").encode()
	return str(int(hmac.new(key, stock_entry.encode(), hashlib.sha256).hexdigest()[:8], 16) % 9000 + 1000)


def deliver_with_otp(stock_entry, otp, by):
	if str(otp).strip() != otp_for(stock_entry):
		frappe.throw(_("Wrong OTP — ask the site engineer for the delivery OTP."))
	from hipersign_trading.api import construction_site as S

	with CN._elevated():
		frappe.flags.hs_cn_skip_role = True
		try:
			S._a_trf_deliver(stock_entry, frappe._dict())
		finally:
			frappe.flags.hs_cn_skip_role = False
	frappe.get_doc("Stock Entry", stock_entry).add_comment("Comment", _("Delivered at site — OTP confirmed by {0}").format(by))


# ================================================================ flags
def flags(name):
	out = []
	if not frappe.db.exists("DocType", "Project Constraint"):
		return out
	t = getdate(today())
	for c in frappe.get_all("Project Constraint", filters={"project": name, "status": "Open", "need_by": ["<", t]}, fields=["name", "description", "need_by", "owner_name"]):
		out.append({"lvl": "High", "text": _("Constraint past need-by ({0} days): {1} — {2}").format(date_diff(t, c.need_by), c.description, c.owner_name or "—"),
			"open": ["Project Constraint", c.name]})
	for m in frappe.get_all("Construction Milestone", filters={"project": name, "status": "Late"}, fields=["name", "title", "slip_days"]):
		out.append({"lvl": "Medium", "text": _("Milestone late: {0} — {1} days slip").format(m.title, m.slip_days), "open": ["Construction Milestone", m.name]})
	return out


# ================================================================ desk actions
def _doc(dt, name, perm="read"):
	d = frappe.get_doc(dt, name)
	d.check_permission(perm)
	return d


def _a_con_remove(name, a):
	CN._need([PM, MD, PMS, SE, QS], _("Removing a constraint"))
	c = _doc("Project Constraint", name)
	if c.status != "Open":
		frappe.throw(_("{0} is already removed.").format(c.name))
	c.status, c.removed_on, c.notes = "Removed", today(), a.get("notes") or c.notes
	c.save(ignore_permissions=True)
	return {"message": _("Constraint removed: {0}").format(c.description)}


def _a_ms_done(name, a):
	CN._need([PM, MD, PMS], _("Recording a milestone"))
	m = _doc("Construction Milestone", name)
	m.actual = a.get("date") or today()
	m.save(ignore_permissions=True)
	return {"message": _("{0} done — {1} days slip").format(m.title, m.slip_days)}


def _a_ms_forecast(name, a):
	CN._need([PM, MD, PMS], _("Re-forecasting a milestone"))
	m = _doc("Construction Milestone", name)
	if not a.get("date"):
		frappe.throw(_("Pick the new forecast date."))
	m.forecast = a.get("date")
	m.save(ignore_permissions=True)
	return {"message": _("{0} forecast {1} — {2}").format(m.title, frappe.format(m.forecast, {"fieldtype": "Date"}), _(m.status))}


def _a_review(name, a):
	CN._need([PM, MD, PMS], _("Recording the weekly review"))
	r = frappe.get_doc({"doctype": "Project Review", "project": name, "week_start": week_monday(), "notes": a.get("notes"), "decisions": a.get("decisions")})
	r.insert(ignore_permissions=True)
	return {"message": _("{0} reviewed — {1}").format(name, _(r.overall))}


def _a_pub(name, a):
	CN._need([PM, MD, PMS], _("Publishing to the client"))
	keep = a.get("keep")
	names = [name] if name != "all" else frappe.get_all("Client Publication", filters={"status": "Waiting", "project": ["in", CN.project_names()]}, pluck="name")
	for n in names:
		frappe.db.set_value("Client Publication", n, {"status": "Kept internal" if keep else "Published", "published_on": None if keep else now_datetime(), "published_by": _who()})
	return {"message": _("{0} kept internal").format(len(names)) if keep else _("{0} published to the client").format(len(names))}


def _a_ver_bill(name, a):
	CN._need([QS, PM, MD, PMS], _("Verifying a partner's bill"))
	b = _doc("Subcontractor Bill", name)
	b.db_set({"partner_verified": 1, "verified_by": _who()})
	return {"message": _("{0} verified — with the QS to certify").format(b.name)}


def _a_ver_photo(name, a):
	CN._need([SE, QS, PM, MD, PMS, QA], _("Verifying a partner's photo"))
	p = _doc("Site Photo", name)
	p.db_set("status", "In the project log")
	return {"message": _("Photo added to the project log")}


def _a_ver_lc(name, a):
	from hipersign_trading.api import construction_site as S

	r = S._a_lc_mark(name, a)
	frappe.db.set_value("Labour Compliance", name, "verified_by", _who())
	return r


def _a_exp_approve(name, a):
	x = _doc("Site Expense", name)
	CN._need([PM, MD, PMS], _("Approving site cash"))
	if x.status != "Waiting for approval":
		frappe.throw(_("{0} is {1}.").format(x.name, _(x.status)))
	x.db_set("approved_by", _who())
	with CN._elevated():
		je = book_expense(x.name)
	return {"message": _("{0} booked — {1}").format(x.name, je)}


def _a_exp_reject(name, a):
	x = _doc("Site Expense", name)
	CN._need([PM, MD, PMS], _("Rejecting site cash"))
	x.db_set({"status": "Rejected", "approved_by": _who()})
	return {"message": _("{0} rejected").format(x.name)}


def _a_cp_features(name, a):
	"""name: a Customer; args: the switches."""
	CN._need([PM, MD, PMS], _("Changing what a client sees"))
	vals = {f"hs_cnp_{k}": cint(a.get(k)) for k in FEATURES if k in a}
	frappe.db.set_value("Customer", name, vals)
	return {"message": _("{0}: portal updated").format(name)}


def _a_invite(name, a):
	"""name: 'Customer::<customer>' or 'Supplier::<supplier>'; args: email, first_name."""
	CN._need([PM, MD, PMS], _("Inviting a portal user"))
	kind, party = name.split("::", 1)
	email = (a.get("email") or "").strip().lower()
	if not frappe.utils.validate_email_address(email):
		frappe.throw(_("Enter a valid e-mail address."))
	if frappe.db.exists("User", email) and frappe.db.get_value("User", email, "user_type") == "System User":
		frappe.throw(_("{0} is a staff login — use another e-mail for the portal.").format(email))
	with CN._elevated():
		u = frappe.get_doc("User", email) if frappe.db.exists("User", email) else frappe.get_doc({"doctype": "User", "email": email,
			"first_name": a.get("first_name") or email.split("@")[0], "user_type": "Website User", "send_welcome_email": cint(not frappe.flags.hs_demo_loading)})
		if u.is_new():
			u.flags.ignore_permissions = True
			u.insert()
		u.add_roles("Customer" if kind == "Customer" else "Supplier")
		c = frappe.db.get_value("Contact", {"user": email}) or frappe.db.get_value("Contact", {"email_id": email})
		c = frappe.get_doc("Contact", c) if c else frappe.get_doc({"doctype": "Contact", "first_name": a.get("first_name") or email.split("@")[0], "email_ids": [{"email_id": email, "is_primary": 1}]})
		c.user = email
		if not any(l.link_doctype == kind and l.link_name == party for l in c.links):
			c.append("links", {"link_doctype": kind, "link_name": party})
		c.flags.ignore_permissions = True
		c.save()
	log(kind, party, _("User invited: {0}").format(email))
	return {"message": _("{0} invited to the {1} portal").format(email, _("client") if kind == "Customer" else _("subcontractor"))}


def _a_user_enable(name, a):
	CN._need([PM, MD, PMS], _("Changing a portal user"))
	if frappe.db.get_value("User", name, "user_type") != "Website User":
		frappe.throw(_("Only portal logins are changed here."))
	frappe.db.set_value("User", name, "enabled", cint(a.get("enabled")))
	return {"message": _("{0} {1}").format(name, _("enabled") if cint(a.get("enabled")) else _("disabled"))}


def _a_user_resend(name, a):
	CN._need([PM, MD, PMS], _("Re-sending a portal invitation"))
	u = frappe.get_doc("User", name)
	if u.user_type != "Website User":
		frappe.throw(_("Only portal logins are changed here."))
	with CN._elevated():
		u.reset_password(send_email=True)
	return {"message": _("Password link sent to {0}").format(name)}


def _a_wpin(name, a):
	"""name: a Site Worker; sets or resets the worker app PIN (args: pin, language)."""
	CN._need([SE, PM, MD, PMS, HR], _("Setting a worker's app PIN"))
	pin = str(a.get("pin") or "").strip()
	if not (pin.isdigit() and len(pin) == 4):
		frappe.throw(_("The PIN is four digits."))
	w = frappe.get_doc("Site Worker", name)
	if not w.mobile:
		frappe.throw(_("Enter {0}'s mobile number first.").format(w.worker_name))
	w.app_pin = pin
	if a.get("language"):
		w.app_language = a.get("language")
	w.flags.ignore_permissions = True
	w.save()
	return {"message": _("{0} can log in to the worker app with {1} and the PIN").format(w.worker_name, w.mobile)}


ACTIONS = {"con_remove": _a_con_remove, "ms_done": _a_ms_done, "ms_forecast": _a_ms_forecast, "review": _a_review, "pub": _a_pub, "ver_bill": _a_ver_bill,
	"ver_photo": _a_ver_photo, "ver_lc": _a_ver_lc, "exp_approve": _a_exp_approve, "exp_reject": _a_exp_reject, "cp_features": _a_cp_features, "invite": _a_invite,
	"user_enable": _a_user_enable, "user_resend": _a_user_resend, "wpin": _a_wpin}
VALIDATE = {"Construction Milestone": milestone_validate, "Project Constraint": constraint_validate, "Project Review": review_validate, "Site Photo": photo_validate,
	"Site Expense": expense_validate, "Site Attendance": attendance_validate}

# ================================================================ client portal
FEATURES = {"progress": ("Progress & milestones", 1), "photos": ("Published photos", 1), "bills": ("RA bills & invoices", 1), "documents": ("Documents & weekly reports", 1),
	"certify": ("Certify RA bills online (private clients)", 1), "vo": ("Approve variations online", 1), "snags": ("Raise snags", 1), "whatsapp": ("WhatsApp updates", 0),
	"cost": ("Cost & margin (off unless agreed)", 0)}


def client_features(customer):
	c = frappe.db.get_value("Customer", customer, [f"hs_cnp_{k}" for k in FEATURES], as_dict=True) or {}
	return frappe._dict({k: cint(c.get(f"hs_cnp_{k}")) for k in FEATURES})


def _contact_parties(kind):
	contact, link = frappe.qb.DocType("Contact"), frappe.qb.DocType("Dynamic Link")
	return (frappe.qb.from_(contact).join(link).on(link.parent == contact.name).select(link.link_name).distinct()
		.where(contact.user == frappe.session.user).where(link.parenttype == "Contact").where(link.link_doctype == kind)).run(pluck=True)


def portal_party(kind):
	"""(party, parties, preview) — the client or subcontractor of the login; staff open any party as a preview."""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.local.request.path
		raise frappe.Redirect
	staff = frappe.session.user == "Administrator" or frappe.get_cached_value("User", frappe.session.user, "user_type") == "System User"
	if kind == "Customer":
		with_projects = sorted({r[0] for r in frappe.db.sql("select distinct customer from `tabProject` where hs_cn = 1 and ifnull(customer, '') != ''")})
	else:
		with_projects = sorted({r[0] for r in frappe.db.sql("select distinct supplier from `tabSubcontractor Work Order` where status != 'Draft'")})
	if staff:
		if not (P._has(PM, MD, PMS, QS, SE, AM) and frappe.has_permission("Project", "read")):
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		parties = with_projects
		preview = True
	else:
		parties = [p for p in _contact_parties(kind) if p in with_projects]
		preview = False
	if not parties:
		frappe.throw(_("Your login is not linked to a {0} with construction projects. Please contact us.").format(_("client") if kind == "Customer" else _("subcontractor")),
			frappe.PermissionError)
	name = frappe.form_dict.get("party")
	return (name if name in parties else parties[0]), parties, preview


def _client_check(project, feature=None):
	customer, customers, preview = portal_party("Customer")
	pj = frappe.db.get_value("Project", project, ["customer", "hs_cn", "hs_cn_govt", "project_name"], as_dict=True)
	if not pj or not cint(pj.hs_cn) or pj.customer not in customers:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if preview:
		frappe.throw(_("This is a preview — the client does this on their own login."))
	if feature and not client_features(pj.customer).get(feature):
		frappe.throw(_("This is not switched on for your account."), frappe.PermissionError)
	return pj


def _contact_name():
	return frappe.utils.get_fullname(frappe.session.user)


@frappe.whitelist()
def cp_certify(ra_bill, amount=None, note=None):
	ra = frappe.get_doc("RA Bill", ra_bill)
	pj = _client_check(ra.project, "certify")
	if cint(pj.hs_cn_govt):
		frappe.throw(_("Government works are certified by the engineer-in-charge on the measurement book, not online."))
	if ra.status != "Submitted to client":
		frappe.throw(_("{0} is {1}.").format(ra.bill_no, _(ra.status)))
	amt = flt(amount) or flt(ra.claimed_amount)
	if amt <= 0:
		frappe.throw(_("Enter the amount you certify."))
	if flt(ra.claimed_amount) - amt > max(1, flt(ra.claimed_amount) * .001) and not (note or "").strip():
		frappe.throw(_("You certify less than claimed — say why in the note, so the site team can answer it."))
	with CN._elevated():
		frappe.flags.hs_cn_skip_role = True
		try:
			r = CN._a_ra_certify(ra.name, frappe._dict(amount=amt))
		finally:
			frappe.flags.hs_cn_skip_role = False
		frappe.get_doc("RA Bill", ra.name).add_comment("Comment", _("Certified online by {0} (client portal){1}").format(_contact_name(), f" — {note}" if note else ""))
	log("Customer", pj.customer, _("Certified RA bill {0}").format(ra.bill_no), ra.project, ["RA Bill", ra.name])
	return r


@frappe.whitelist()
def cp_variation(extra_item, approve=1, note=None):
	e = frappe.get_doc("Extra Item", extra_item)
	pj = _client_check(e.project, "vo")
	if e.status != "Pending client":
		frappe.throw(_("{0} is {1}.").format(e.title, _(e.status)))
	with CN._elevated():
		frappe.flags.hs_cn_skip_role = True
		try:
			r = (CN._a_ei_approve if cint(approve) else CN._a_ei_reject)(e.name, frappe._dict())
		finally:
			frappe.flags.hs_cn_skip_role = False
		if cint(approve):
			frappe.db.set_value("Extra Item", e.name, "approved_by", _contact_name())
		frappe.get_doc("Extra Item", e.name).add_comment("Comment", _("{0} online by {1}{2}").format(_("Approved") if cint(approve) else _("Rejected"), _contact_name(),
			f" — {note}" if note else ""))
	log("Customer", pj.customer, _("{0} variation {1}").format(_("Approved") if cint(approve) else _("Rejected"), e.title), e.project, ["Extra Item", e.name])
	return r


@frappe.whitelist()
def cp_snag(project, location, description, trade=None):
	pj = _client_check(project, "snags")
	if not (location and description):
		frappe.throw(_("Say where and what."))
	s = frappe.get_doc({"doctype": "Snag", "project": project, "location": location[:140], "description": description[:500], "trade": trade or "Civil", "raised_on": today(),
		"target": add_days(today(), 7)})
	s.insert(ignore_permissions=True)
	s.add_comment("Comment", _("Raised by {0} on the client portal").format(_contact_name()))
	log("Customer", pj.customer, _("Raised a snag: {0}").format(location), project, ["Snag", s.name])
	return {"message": _("Snag {0} raised — the site team will fix it by {1}").format(s.name, frappe.format(s.target, {"fieldtype": "Date"}))}


# ================================================================ subcontractor portal
def _partner_check(work_order=None, project=None):
	supplier, suppliers, preview = portal_party("Supplier")
	if preview:
		frappe.throw(_("This is a preview — the subcontractor does this on their own login."))
	if work_order:
		w = frappe.db.get_value("Subcontractor Work Order", work_order, ["supplier", "project", "status"], as_dict=True)
		if not w or w.supplier not in suppliers:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		return w.supplier, w
	if project:
		ok = frappe.db.exists("Subcontractor Work Order", {"project": project, "supplier": ["in", suppliers], "status": ["!=", "Draft"]})
		if not ok:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		return frappe.db.get_value("Subcontractor Work Order", ok, "supplier"), None
	return supplier, None


@frappe.whitelist()
def sp_bill(work_order, quantities, invoice_no=None, period_to=None):
	"""quantities: {item_no: quantity this bill}."""
	supplier, w = _partner_check(work_order)
	if w.status != "Active":
		frappe.throw(_("The work order is {0}.").format(_(w.status)))
	q = frappe.parse_json(quantities) if isinstance(quantities, str) else quantities
	wo = frappe.get_doc("Subcontractor Work Order", work_order)
	prev = {}
	for b in frappe.get_all("Subcontractor Bill", filters={"work_order": work_order, "status": ["!=", "Cancelled"]}, pluck="name"):
		for i in frappe.get_doc("Subcontractor Bill", b).items:
			prev[i.item_no] = max(prev.get(i.item_no, 0), flt(i.cum_qty))
	items = []
	for it in wo.items:
		this = flt((q or {}).get(it.item_no))
		if this < 0:
			frappe.throw(_("Quantities cannot be negative."))
		if this:
			items.append({"item_no": it.item_no, "description": it.description, "unit": it.unit, "rate": it.rate, "wo_qty": it.qty, "prev_qty": prev.get(it.item_no, 0),
				"this_qty": this, "cum_qty": prev.get(it.item_no, 0) + this})
	if not items:
		frappe.throw(_("Enter the quantity done this bill on at least one item."))
	b = frappe.get_doc({"doctype": "Subcontractor Bill", "work_order": work_order, "project": w.project, "supplier": supplier, "supplier_invoice_no": invoice_no,
		"bill_date": today(), "period_to": period_to or today(), "items": items, "partner_submitted": 1})
	with CN._elevated():
		b.insert(ignore_permissions=True)
	log("Supplier", supplier, _("Submitted running bill {0} — {1}").format(b.bill_no, CN.inr(b.net_payable)), w.project, ["Subcontractor Bill", b.name])
	return {"message": _("Running bill {0} submitted — {1} net. The site team verifies it for the QS.").format(b.bill_no, CN.inr(b.net_payable))}


def _file(doctype, name, field, data_url, filename):
	if not data_url:
		return None
	head, _sep, body = data_url.partition(",")
	content = base64.b64decode(body)
	if len(content) > 8 * 1024 * 1024:
		frappe.throw(_("The file is larger than 8 MB."))
	f = frappe.get_doc({"doctype": "File", "file_name": filename, "attached_to_doctype": doctype, "attached_to_name": name, "attached_to_field": field,
		"content": content, "is_private": 1})
	f.flags.ignore_permissions = True
	f.insert()
	return f.file_url


@frappe.whitelist()
def sp_compliance(project, month, workers=None, wage_register=None, pf_ecr=None, esi=None):
	supplier, _w = _partner_check(project=project)
	m = getdate(month).replace(day=1)
	n = frappe.db.get_value("Labour Compliance", {"supplier": supplier, "project": project, "month": m})
	c = frappe.get_doc("Labour Compliance", n) if n else frappe.get_doc({"doctype": "Labour Compliance", "supplier": supplier, "project": project, "month": m})
	c.workers = cint(workers) or c.workers
	c.partner_submitted = 1
	with CN._elevated():
		c.flags.ignore_permissions = True
		c.save() if n else c.insert()
		for field, data, label in (("wage_register_file", wage_register, "wage-register"), ("pf_ecr_file", pf_ecr, "pf-ecr"), ("esi_file", esi, "esi-challan")):
			if data:
				ext = "pdf" if "pdf" in data[:40] else "jpg"
				c.db_set(field, _file("Labour Compliance", c.name, field, data, f"{supplier[:20]}-{label}-{m.strftime('%Y-%m')}.{ext}"))
	log("Supplier", supplier, _("Uploaded labour documents for {0}").format(m.strftime("%b %Y")), project, ["Labour Compliance", c.name])
	return {"message": _("Documents for {0} uploaded — the HR team verifies them and releases any held bill.").format(m.strftime("%B %Y"))}


@frappe.whitelist()
def sp_photo(project, image, caption=None, location=None):
	supplier, _w = _partner_check(project=project)
	p = frappe.get_doc({"doctype": "Site Photo", "project": project, "image": "/files/placeholder.png", "caption": (caption or _("Progress photo"))[:140], "location": location,
		"source": "Subcontractor portal", "supplier": supplier, "taken_by": _contact_name()})
	with CN._elevated():
		p.insert(ignore_permissions=True)
		url = _file("Site Photo", p.name, "image", image, f"{p.name}.jpg")
		p.db_set("image", url)
	log("Supplier", supplier, _("Uploaded a progress photo"), project, ["Site Photo", p.name])
	return {"message": _("Photo sent — the site team verifies it.")}


# ================================================================ site app
def _site_user():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in"), frappe.PermissionError)
	if not P._has(SE, PM, PMS, MD, SK, QS):
		frappe.throw(_("The site app is for site engineers, project managers and storekeepers."), frappe.PermissionError)


def _site_project(project):
	_site_user()
	if not CN.is_cn(project) or not frappe.has_permission("Project", "read", project):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return frappe.get_cached_doc("Project", project)


@frappe.whitelist()
def sa_home(project=None):
	_site_user()
	names = [n for n in CN.project_names(None, False) if CN.fig(n).step < 26]
	emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, ["name", "hs_cn_project"], as_dict=True)
	if project not in names:
		project = (emp or {}).get("hs_cn_project") if (emp or {}).get("hs_cn_project") in names else (names[0] if names else None)
	if not project:
		return {"projects": []}
	p = frappe.get_cached_doc("Project", project)
	t = today()
	workers = frappe.get_all("Site Worker", filters={"project": project, "status": "Active"}, fields=["name", "worker_name", "trade", "contractor"], order_by="worker_name asc")
	present = set(frappe.get_all("Site Attendance", filters={"project": project, "attendance_date": t}, pluck="worker"))
	me_in = frappe.get_all("Employee Checkin", filters={"employee": emp.name, "time": [">=", t]}, fields=["time"], order_by="time asc", limit=1) if emp else []
	dpr = frappe.get_all("Daily Progress Report", filters={"project": project, "report_date": t}, fields=["name", "status", "activity", "actual_qty", "unit"])
	trips = frappe.get_all("Stock Entry", filters={"docstatus": 1, "hs_transfer_status": "In transit", "project": project},
		fields=["name", "hs_vehicle", "hs_driver", "hs_driver_mobile", "hs_eway_bill", "posting_date", "from_warehouse"], order_by="posting_date desc")
	for x in trips:
		x.otp = otp_for(x.name)
		x.items = frappe.get_all("Stock Entry Detail", filters={"parent": x.name}, fields=["item_name", "qty", "uom"])
	pos = frappe.get_all("Purchase Order", filters={"docstatus": 1, "hs_project": project, "per_received": ["<", 100], "status": ["not in", ["Closed", "Completed"]]},
		fields=["name", "supplier", "schedule_date", "per_received"], order_by="schedule_date asc", limit=8) if frappe.get_meta("Purchase Order").has_field("hs_project") else []
	photos = frappe.get_all("Site Photo", filters={"project": project}, fields=["name", "image", "caption", "taken_on", "status"], order_by="taken_on desc", limit=6)
	chat = frappe.get_all("Comment", filters={"reference_doctype": "Project", "reference_name": project, "comment_type": "Comment"}, fields=["owner", "content", "creation"],
		order_by="creation desc", limit=15)
	for c in chat:
		c.who = frappe.utils.get_fullname(c.owner)
		c.content = frappe.utils.strip_html_tags(c.content or "")
	exp = frappe.get_all("Site Expense", filters={"project": project, "expense_date": [">=", add_days(t, -14)]}, fields=["name", "description", "amount", "status", "expense_date"],
		order_by="expense_date desc", limit=10)
	acts = sorted({(r.item_no, r.description[:60], r.unit) for r in (CN.boq(project).items if CN.boq(project) else [])})[:60]
	return {"projects": [{"name": n, "label": frappe.get_cached_value("Project", n, "project_name")} for n in names], "project": project, "project_name": p.project_name,
		"me": _who(), "employee": emp.name if emp else None, "checked_in": str(me_in[0].time)[11:16] if me_in else None,
		"workers": [dict(w, present=w.name in present) for w in workers], "present": len(present), "dpr": dpr, "trips": trips, "pos": pos, "photos": photos,
		"chat": chat, "expenses": exp, "cash_limit": limits().cash, "imprest": imprest_balance(p.company), "boq": acts,
		"permits": frappe.get_all("Work Permit", filters={"project": project, "status": "Issued", "valid_to": [">=", t]}, fields=["kind", "location", "valid_to"])}


@frappe.whitelist()
def sa_checkin(project, latitude=None, longitude=None, selfie=None):
	p = _site_project(project)
	emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"})
	if not emp:
		frappe.throw(_("Your login is not linked to an employee — ask HR to set the user on your employee record."))
	c = frappe.get_doc({"doctype": "Employee Checkin", "employee": emp, "log_type": "IN", "time": now_datetime(), "device_id": f"Site app — {project}",
		"latitude": flt(latitude) or None, "longitude": flt(longitude) or None})
	c.flags.ignore_permissions = True
	c.insert()
	if selfie:
		_file("Employee Checkin", c.name, None, selfie, f"checkin-{c.name}.jpg")
	return {"message": _("Checked in at {0} — {1}").format(p.project_name, str(c.time)[11:16])}


@frappe.whitelist()
def sa_gang(project, workers, latitude=None, longitude=None):
	_site_project(project)
	W = frappe.parse_json(workers) if isinstance(workers, str) else workers
	n = 0
	for w in W or []:
		if frappe.db.exists("Site Attendance", {"worker": w, "attendance_date": today()}):
			continue
		if frappe.db.get_value("Site Worker", w, "project") != project:
			continue
		frappe.get_doc({"doctype": "Site Attendance", "project": project, "worker": w, "attendance_date": today(), "method": "Gang check-in",
			"latitude": flt(latitude) or None, "longitude": flt(longitude) or None}).insert(ignore_permissions=True)
		n += 1
	return {"message": _("{0} workers checked in").format(n)}


@frappe.whitelist()
def sa_dpr(project, activity, qty=0, unit=None, boq_item=None, weather="Fair", sub_labour=0, hours_lost=0, remarks=None):
	_site_project(project)
	if frappe.db.exists("Daily Progress Report", {"project": project, "report_date": today(), "activity": activity}):
		frappe.throw(_("Today's DPR for {0} is already in.").format(activity))
	own = frappe.db.count("Site Attendance", {"project": project, "attendance_date": today()})
	d = frappe.get_doc({"doctype": "Daily Progress Report", "project": project, "report_date": today(), "activity": activity, "boq_item": boq_item, "unit": unit,
		"actual_qty": flt(qty), "planned_qty": flt(qty), "weather": weather, "own_labour": own, "sub_labour": cint(sub_labour), "hours_lost": flt(hours_lost),
		"remarks": remarks, "reported_by": _who(), "status": "Submitted"})
	d.insert(ignore_permissions=True)
	return {"message": _("DPR {0} sent — {1} own workers from today's check-ins").format(d.name, own)}


@frappe.whitelist()
def sa_photo(project, image, caption=None, location=None, latitude=None, longitude=None):
	_site_project(project)
	p = frappe.get_doc({"doctype": "Site Photo", "project": project, "image": "/files/placeholder.png", "caption": (caption or _("Site photo"))[:140], "location": location,
		"source": "Site app", "latitude": flt(latitude) or None, "longitude": flt(longitude) or None, "taken_on": now_datetime()})
	p.insert(ignore_permissions=True)
	url = _file("Site Photo", p.name, "image", image, f"{p.name}.jpg")
	p.db_set("image", url)
	sync_publications([project])
	return {"message": _("Photo saved to the project log — it waits for the PM before the client sees it")}


@frappe.whitelist()
def sa_expense(project, description, amount, head="Site overheads", paid_to=None, receipt=None):
	pj = _site_project(project)
	x = frappe.get_doc({"doctype": "Site Expense", "project": project, "description": description, "amount": flt(amount), "head": head, "paid_to": paid_to})
	x.insert(ignore_permissions=True)
	if receipt:
		x.db_set("receipt", _file("Site Expense", x.name, "receipt", receipt, f"{x.name}.jpg"))
	if flt(amount) <= limits().cash:
		with CN._elevated():
			book_expense(x.name)
		return {"message": _("{0} booked — within your limit of {1}").format(CN.inr(amount), CN.inr(limits().cash))}
	return {"message": _("{0} is above your limit of {1} — it waits for the PM").format(CN.inr(amount), CN.inr(limits().cash))}


@frappe.whitelist()
def sa_chat(project, text):
	_site_project(project)
	if not (text or "").strip():
		return
	from hipersign_trading.api import messages

	return messages.post("Project", project, text)


# ================================================================ worker app (mobile number + PIN, no Frappe login)
TOKEN_TTL = 12 * 3600


def _worker(token):
	name = frappe.cache.get_value(f"hs_wa:{token}") if token else None
	if not name:
		frappe.throw(_("Please log in again."), frappe.AuthenticationError)
	return frappe.get_doc("Site Worker", name)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def wa_login(mobile, pin):
	mobile = "".join(ch for ch in str(mobile or "") if ch.isdigit())[-10:]
	key = f"hs_wa_try:{mobile}"
	tries = cint(frappe.cache.get_value(key))
	if tries >= 5:
		frappe.throw(_("Too many tries — wait 15 minutes or ask the site engineer to reset your PIN."))
	from frappe.utils.password import get_decrypted_password

	for w in frappe.get_all("Site Worker", filters={"status": "Active", "mobile": ["like", f"%{mobile[-10:]}"]}, pluck="name") if len(mobile) == 10 else []:
		if get_decrypted_password("Site Worker", w, "app_pin", raise_exception=False) == str(pin):
			token = frappe.generate_hash(length=32)
			frappe.cache.set_value(f"hs_wa:{token}", w, expires_in_sec=TOKEN_TTL)
			frappe.cache.delete_value(key)
			frappe.db.set_value("Site Worker", w, "app_last_login", now_datetime(), update_modified=False)
			return {"token": token}
	frappe.cache.set_value(key, tries + 1, expires_in_sec=900)
	frappe.throw(_("Mobile number or PIN is wrong."))


@frappe.whitelist(allow_guest=True, methods=["POST"])
def wa_me(token):
	w = _worker(token)
	from hipersign_trading.api import construction_site as S

	ws = S.week_start(today())
	att = frappe.get_all("Site Attendance", filters={"worker": w.name, "attendance_date": ["between", [ws, add_days(ws, 6)]]}, pluck="attendance_date")
	last = frappe.db.sql("""select m.name, m.week_start, m.week_end, m.status, m.paid_on, r.days, r.ot_hours, r.rate, r.earned, r.pf, r.esi, r.advance_recovery, r.net
		from `tabWeekly Muster Row` r join `tabWeekly Muster` m on m.name = r.parent where r.worker = %s and m.status in ('Approved', 'Paid') order by m.week_start desc limit 1""",
		w.name, as_dict=True)
	advs = frappe.get_all("Worker Advance", filters={"worker": w.name, "status": ["in", ["Requested", "Approved", "Paid"]]}, fields=["amount", "recovered", "status", "requested_on"],
		order_by="requested_on desc", limit=5)
	pay_day = add_days(ws, 7)  # Wednesday after the week
	return {"name": w.worker_name, "trade": _(w.trade), "project": frappe.get_cached_value("Project", w.project, "project_name") if w.project else "",
		"language": w.app_language or "English", "rate": flt(w.daily_rate), "week_start": str(ws), "days": [str(d) for d in att],
		"today_in": getdate(today()) in [getdate(d) for d in att], "slip": last[0] if last else None, "advances": advs, "pay_day": str(pay_day), "upi": w.upi_id or "",
		"max_advance": flt(w.daily_rate) * 6 * 4, "contractor": w.contractor or ""}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def wa_checkin(token, latitude=None, longitude=None):
	w = _worker(token)
	if frappe.db.exists("Site Attendance", {"worker": w.name, "attendance_date": today()}):
		return {"message": "already"}
	frappe.get_doc({"doctype": "Site Attendance", "project": w.project, "worker": w.name, "attendance_date": today(), "method": "Worker app",
		"latitude": flt(latitude) or None, "longitude": flt(longitude) or None, "marked_by": w.worker_name}).insert(ignore_permissions=True)
	return {"message": "ok"}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def wa_advance(token, amount, reason=None):
	w = _worker(token)
	if w.contractor:
		frappe.throw(_("Your contractor pays your wages — ask the contractor for an advance."))
	if frappe.db.exists("Worker Advance", {"worker": w.name, "status": "Requested"}):
		frappe.throw(_("You already have an advance request waiting."))
	a = frappe.get_doc({"doctype": "Worker Advance", "worker": w.name, "amount": flt(amount), "reason": (reason or _("Asked on the worker app"))[:140], "requested_on": today()})
	a.insert(ignore_permissions=True)
	log("Site Worker", w.name, _("Asked for an advance of {0}").format(CN.inr(amount)), w.project, ["Worker Advance", a.name])
	return {"message": "ok", "name": a.name}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def wa_danger(token, text, location=None, photo=None):
	w = _worker(token)
	if not (text or "").strip():
		frappe.throw(_("Say what the danger is."))
	i = frappe.get_doc({"doctype": "Safety Incident", "project": w.project, "incident_date": today(), "kind": "Near miss", "location": (location or "")[:140],
		"description": _("Danger reported on the worker app: {0}").format(text[:400]), "reported_by": w.worker_name})
	i.insert(ignore_permissions=True)
	if photo:
		_file("Safety Incident", i.name, None, photo, f"{i.name}.jpg")
	log("Site Worker", w.name, _("Reported a danger"), w.project, ["Safety Incident", i.name])
	return {"message": "ok"}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def wa_language(token, language):
	w = _worker(token)
	if language in ("English", "മലയാളം", "தமிழ்", "हिन्दी"):
		frappe.db.set_value("Site Worker", w.name, "app_language", language, update_modified=False)
	return {"message": "ok"}


# ================================================================ driver app (construction transfers)
def driver_trips(driver):
	"""Transfers in transit given to this driver (by name or mobile)."""
	d = frappe.db.get_value("Driver", driver.name, ["full_name", "cell_number"], as_dict=True) if driver else None
	if not d:
		return []
	f = [["docstatus", "=", 1], ["hs_transfer_status", "=", "In transit"]]
	rows = frappe.get_all("Stock Entry", filters=f, or_filters=[["hs_driver", "=", d.full_name], ["hs_driver_mobile", "=", d.cell_number or "—"]],
		fields=["name", "project", "hs_vehicle", "hs_eway_bill", "from_warehouse", "hs_destination", "posting_date"])
	for r in rows:
		r.project_name = frappe.get_cached_value("Project", r.project, "project_name") if r.project else ""
		addr = frappe.get_cached_value("Project", r.project, "hs_cn_address") if r.project else None
		r.address = (frappe.db.get_value("Address", addr, ["address_line1", "city"], as_dict=True) or {}) if addr else {}
		r.items = frappe.get_all("Stock Entry Detail", filters={"parent": r.name}, fields=["item_name", "qty", "uom"])
	return rows


@frappe.whitelist()
def cp_file(publication):
	"""A published photo or drawing for the client — photos and drawings are private files; the client sees one only once
	the PM has published it, and only for their own project."""
	c = frappe.db.get_value("Client Publication", publication, ["project", "status", "photo", "drawing"], as_dict=True)
	if not c or c.status != "Published":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	customer, customers, preview = portal_party("Customer")
	if frappe.db.get_value("Project", c.project, "customer") not in customers:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	url = frappe.db.get_value("Site Photo", c.photo, "image") if c.photo else frappe.db.get_value("Construction Drawing", c.drawing, "file")
	f = frappe.db.get_value("File", {"file_url": url}, "name") if url else None
	if not f:
		frappe.throw(_("The file is not there."))
	doc = frappe.get_doc("File", f)
	frappe.local.response.filename = doc.file_name
	frappe.local.response.filecontent = doc.get_content()
	frappe.local.response.type = "binary"
	frappe.local.response.display_content_as = "inline"
