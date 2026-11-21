"""v1.9.2 U3/U4: the Hipersign record page — every Construction (India) record opens here instead of ERPNext's form.

get(doctype, name)      the record as the page shows it: header, status steps, key figures, sections of filled fields,
                        line tables with totals, files, linked records and activity
form(doctype, name)     what the designed form needs to edit or create it: the fields in order (sections, columns),
                        their rules (mandatory, depends on, read only) and the line tables' fields
The page saves through frappe.client (insert / save / submit / cancel), so every server rule and validation still runs."""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from hipersign_trading.features import FEATURES

CN_FEATURES = ("construction", "cn_biz", "cn_site", "cn_qhse", "cn_fin", "cn_ctl", "cn_portal")
# construction records that are not in a feature's list (masters and records the pages create)
EXTRA = ("Project BOQ", "Rate Analysis", "BOQ Template", "Bank Guarantee", "Material Norm", "Development Unit", "Scrap Bid", "Site Diary",
	"Productivity Norm", "Project Review", "Construction Milestone", "Client Visit", "Project", "Task")
LAYOUT = ("Section Break", "Column Break", "Tab Break", "Fold")
SKIP = ("HTML", "Button", "Heading", "Image", "Geolocation", "Signature", "Barcode", "HTML Editor", "Code", "Markdown Editor", "JSON")
NUMBER = ("Currency", "Float", "Int", "Percent")
TONE = (("green", ("paid", "approved", "completed", "complete", "closed", "certified", "verified", "done", "won", "awarded", "active", "issued", "current",
	"accepted", "rectified", "published", "booked", "gfc", "submitted to client")),
	("red", ("rejected", "cancelled", "lost", "overdue", "late", "open ncr", "expired", "failed", "disqualified", "hold")),
	("amber", ("draft", "pending", "requested", "waiting", "open", "under", "being", "at risk", "reported", "new", "no bid", "for approval")),
	("blue", ("submitted", "in progress", "invoiced", "part", "responded", "running", "evaluation", "priced", "checked", "on track")))


def types():
	"""The record types that open the Hipersign record page (worked out once per request)."""
	got = getattr(frappe.local, "hs_record_types", None)
	if got is not None:
		return got
	out = []
	for key in CN_FEATURES:
		f = FEATURES.get(key)
		if f:
			out += f[4]
	out += EXTRA
	seen, res = set(), []
	for dt in out:
		if dt not in seen and frappe.db.exists("DocType", dt) and not frappe.get_meta(dt).istable:
			seen.add(dt)
			res.append(dt)
	frappe.local.hs_record_types = res
	return res


@frappe.whitelist()
def record_types():
	return types()


def tone(status):
	s = (status or "").lower()
	for t, words in TONE:
		if any(w in s for w in words):
			return t
	return "grey"


def _title(dt, name):
	if not name:
		return ""
	try:
		m = frappe.get_meta(dt)
		tf = m.title_field or ("project_name" if dt == "Project" else None)
		if tf and tf != "name":
			return frappe.db.get_value(dt, name, tf) or name
	except Exception:
		pass
	return name


def _fmt(df, v, doc):
	if df.fieldtype == "Check":
		return _("Yes") if cint(v) else ""
	if df.fieldtype in ("Text Editor",):
		from frappe.utils.html_utils import clean_html

		return clean_html(v or "")
	try:
		return frappe.format(v, df, doc)
	except Exception:
		return frappe.utils.escape_html(str(v))


def _cur(doc):
	co = doc.get("company")
	return (frappe.get_cached_value("Company", co, "default_currency") if co else None) or frappe.db.get_default("currency") or "INR"


def _openable(dt):
	return dt in types()


def _steps(meta, doc):
	df = meta.get_field("status")
	if not df or df.fieldtype != "Select":
		return None
	opts = [o for o in (df.options or "").split("\n") if o and o.lower() not in ("cancelled", "rejected", "lost", "no bid", "disqualified", "closed", "superseded", "withdrawn")]
	if not 3 <= len(opts) <= 9 or doc.get("status") not in opts:
		return None
	return {"steps": [_(o) for o in opts], "at": opts.index(doc.get("status"))}


def _figures(meta, doc, cur):
	cand = [df for df in meta.fields if df.fieldtype in ("Currency", "Percent") and not df.hidden and flt(doc.get(df.fieldname))]
	cand.sort(key=lambda d: (0 if d.fieldtype == "Currency" else 1, 0 if d.bold else 1, 0 if d.in_list_view else 1))
	out = []
	for df in cand[:4]:
		out.append({"label": _(df.label), "value": flt(doc.get(df.fieldname)), "kind": "money" if df.fieldtype == "Currency" else "pct", "currency": cur})
	return out


def _sub(meta, doc):
	bits = []
	for df in meta.fields:
		if df.fieldtype == "Link" and doc.get(df.fieldname) and df.options in ("Project", "Customer", "Supplier", "Tender", "Subcontractor Work Order", "Site Worker",
				"Construction Equipment", "Employee") and df.fieldname != "name":
			bits.append({"label": _(df.label), "value": _title(df.options, doc.get(df.fieldname)), "dt": df.options, "name": doc.get(df.fieldname),
				"open": _openable(df.options)})
		if len(bits) >= 3:
			break
	return bits


def _table(df, doc, cur):
	cm = frappe.get_meta(df.options)
	cols = [c for c in cm.fields if c.in_list_view and not c.hidden and c.fieldtype not in LAYOUT + SKIP] or \
		[c for c in cm.fields if not c.hidden and c.fieldtype not in LAYOUT + SKIP + ("Table",)][:6]
	cols = cols[:8]
	rows, tot = [], {}
	for r in doc.get(df.fieldname) or []:
		cells = []
		for c in cols:
			v = r.get(c.fieldname)
			cells.append(_fmt(c, v, r) if v not in (None, "") else "")
			if c.fieldtype == "Currency":
				tot[c.fieldname] = tot.get(c.fieldname, 0) + flt(v)
		rows.append(cells)
	return {"label": _(df.label), "fieldname": df.fieldname, "cols": [{"label": _(c.label), "num": c.fieldtype in NUMBER} for c in cols], "rows": rows,
		"totals": [(frappe.format(tot[c.fieldname], c, None) if c.fieldname in tot else "") for c in cols] if tot else None}


def _linked(doctype, name):
	out = []
	for dt in types() + ["Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry", "Stock Entry", "Material Request", "Purchase Order"]:
		if dt == doctype or not frappe.db.exists("DocType", dt) or not frappe.has_permission(dt, "read"):
			continue
		m = frappe.get_meta(dt)
		for df in m.fields:
			if df.fieldtype == "Link" and df.options == doctype:
				n = frappe.db.count(dt, {df.fieldname: name})
				if n:
					title = m.title_field if m.title_field and m.title_field != "name" else None
					fields = ["name"] + ([title] if title else []) + (["status"] if m.has_field("status") else [])
					items = frappe.get_all(dt, filters={df.fieldname: name}, fields=fields, order_by="modified desc", limit=5)
					out.append({"doctype": dt, "label": _(dt), "count": n, "open": _openable(dt) or dt in ("Sales Invoice", "Purchase Order"),
						"items": [{"name": i.name, "title": (i.get(title) if title else "") or "", "status": i.get("status") or "", "tone": tone(i.get("status"))} for i in items]})
				break
		if len(out) >= 10:
			break
	return out


def _activity(doctype, name, doc):
	act = [{"kind": "created", "by": frappe.utils.get_fullname(doc.owner), "on": str(doc.creation)}]
	if str(doc.modified) != str(doc.creation):
		act.append({"kind": "changed", "by": frappe.utils.get_fullname(doc.modified_by), "on": str(doc.modified)})
	for c in frappe.get_all("Comment", filters={"reference_doctype": doctype, "reference_name": name, "comment_type": ["in", ["Comment", "Info", "Workflow"]]},
			fields=["comment_type", "content", "comment_email", "creation", "owner"], order_by="creation desc", limit=20):
		from frappe.utils.html_utils import clean_html

		act.append({"kind": c.comment_type.lower(), "by": frappe.utils.get_fullname(c.owner), "on": str(c.creation), "text": clean_html(c.content or "")})
	act.sort(key=lambda a: a["on"], reverse=True)
	return act


@frappe.whitelist()
def get(doctype, name):
	if doctype not in types():
		frappe.throw(_("This record type has no Hipersign record page."))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	meta = frappe.get_meta(doctype)
	cur = _cur(doc)
	status = doc.get("status") or (_("Cancelled") if doc.docstatus == 2 else _("Submitted") if doc.docstatus == 1 else (_("Draft") if meta.is_submittable else ""))
	sections, cur_sec = [], None

	def new_section(label):
		nonlocal cur_sec
		cur_sec = {"label": _(label) if label else "", "fields": [], "tables": []}
		sections.append(cur_sec)

	new_section(_("Details"))
	for df in meta.fields:
		if df.fieldtype in ("Section Break", "Tab Break"):
			if df.label or df.fieldtype == "Tab Break":
				new_section(df.label or "")
			continue
		if df.fieldtype in LAYOUT or df.fieldtype in SKIP or df.hidden or df.fieldname in ("naming_series", "amended_from", "status"):
			continue
		v = doc.get(df.fieldname)
		if df.fieldtype in ("Table", "Table MultiSelect"):
			if v:
				cur_sec["tables"].append(_table(df, doc, cur))
			continue
		if v in (None, "", 0, 0.0) and df.fieldtype not in ("Int", "Float", "Currency", "Percent"):
			continue
		if df.fieldtype in NUMBER and not flt(v):
			continue
		if df.fieldtype == "Check" and not cint(v):
			continue
		f = {"label": _(df.label or df.fieldname), "html": _fmt(df, v, doc), "type": df.fieldtype, "wide": df.fieldtype in ("Text", "Small Text", "Long Text", "Text Editor")}
		if df.fieldtype == "Link" and v:
			f.update({"dt": df.options, "name": v, "title": _title(df.options, v) if df.options not in ("User", "Company", "UOM", "Currency") else v, "open": _openable(df.options)})
		if df.fieldtype in ("Attach", "Attach Image") and v:
			f.update({"file": v, "image": df.fieldtype == "Attach Image" or str(v).lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))})
		cur_sec["fields"].append(f)
	sections = [s for s in sections if s["fields"] or s["tables"]]
	can = {"write": doc.docstatus == 0 and frappe.has_permission(doctype, "write", doc), "submit": bool(meta.is_submittable) and doc.docstatus == 0 and frappe.has_permission(doctype, "submit", doc),
		"cancel": doc.docstatus == 1 and frappe.has_permission(doctype, "cancel", doc), "delete": doc.docstatus != 1 and frappe.has_permission(doctype, "delete", doc),
		"create": frappe.has_permission(doctype, "create")}
	files = frappe.get_all("File", filters={"attached_to_doctype": doctype, "attached_to_name": name}, fields=["name", "file_name", "file_url", "is_private", "creation"],
		order_by="creation desc", limit=30)
	return {
		"doctype": doctype, "label": _(doctype), "name": doc.name, "title": _title(doctype, doc.name) if meta.title_field else doc.name, "status": _(status) if status else "",
		"raw_status": doc.get("status") or "", "tone": tone(doc.get("status") or status), "docstatus": doc.docstatus, "sub": _sub(meta, doc), "steps": _steps(meta, doc),
		"figures": _figures(meta, doc, cur), "currency": cur, "sections": sections, "files": files, "linked": _linked(doctype, doc.name), "activity": _activity(doctype, doc.name, doc),
		"can": can, "submittable": bool(meta.is_submittable), "modified": str(doc.modified), "doc": doc.as_dict(convert_dates_to_str=True)}


def _schema(meta):
	out = []
	for df in meta.fields:
		if df.fieldtype in SKIP and df.fieldtype not in ("Code", "JSON"):
			continue
		if df.hidden and df.fieldtype not in ("Section Break", "Tab Break", "Column Break"):
			continue
		if df.fieldname in ("amended_from",):
			continue
		f = {k: df.get(k) for k in ("fieldname", "label", "fieldtype", "options", "reqd", "read_only", "depends_on", "mandatory_depends_on", "read_only_depends_on",
			"default", "description", "fetch_from", "in_list_view", "bold", "non_negative", "collapsible", "hidden", "length", "precision", "allow_on_submit")}
		f["label"] = _(f["label"]) if f["label"] else f["label"]
		if df.fieldtype == "Select":
			f["opts"] = [o for o in (df.options or "").split("\n")]
		if df.fieldtype == "Link":
			flt_ = None
			if df.get("link_filters"):
				try:
					flt_ = json.loads(df.link_filters)
				except Exception:
					flt_ = None
			if df.options == "Project" and frappe.get_meta("Project").has_field("hs_cn"):
				flt_ = (flt_ or []) + [["Project", "hs_cn", "=", 1]]  # construction records belong to construction projects
			f["filters"] = flt_
		if df.fieldtype in ("Table", "Table MultiSelect"):
			cm = frappe.get_meta(df.options)
			f["child"] = _schema(cm)
			f["cols"] = [c.fieldname for c in cm.fields if c.in_list_view and not c.hidden and c.fieldtype not in LAYOUT + SKIP][:6] or \
				[c.fieldname for c in cm.fields if not c.hidden and c.fieldtype not in LAYOUT + SKIP][:4]
		out.append(f)
	return out


@frappe.whitelist()
def form(doctype, name=None, values=None):
	if doctype not in types():
		frappe.throw(_("This record type has no Hipersign form."))
	meta = frappe.get_meta(doctype)
	if name:
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("write")
	else:
		if not frappe.has_permission(doctype, "create"):
			frappe.throw(_("You may not create a {0}.").format(_(doctype)), frappe.PermissionError)
		doc = frappe.new_doc(doctype)
		vals = json.loads(values) if isinstance(values, str) else (values or {})
		for k, v in vals.items():
			if meta.has_field(k) and v not in (None, ""):
				doc.set(k, v)
	return {"doctype": doctype, "label": _(doctype), "name": doc.name if name else None, "submittable": bool(meta.is_submittable),
		"title": _title(doctype, doc.name) if name else _("New {0}").format(_(doctype)), "fields": _schema(meta),
		"doc": doc.as_dict(convert_dates_to_str=True, no_default_fields=False), "is_new": not name}
