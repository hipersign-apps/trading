"""v1.5 — Approvals: every document waiting for a decision, the rule that routed it and who must act.

Sources: documents in a workflow state that has a decision to take (any active workflow), document exceptions, tax
returns waiting for the Finance Manager, and — with Frappe HR — leave applications and expense claims. Approving here
moves the source document to its next state, exactly as the button on the form would.
"""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, today

from hipersign_trading.utils import can_read

VALUE_FIELDS = ("base_grand_total", "grand_total", "base_paid_amount", "paid_amount", "total_amount", "amount", "requested_limit",
	"total_sanctioned_amount", "total_claimed_amount", "advance_amount", "output_vat")
DESC_FIELDS = ("customer_name", "supplier_name", "party_name", "title", "employee_name", "customer", "supplier", "party")


def _value(doc):
	for f in VALUE_FIELDS:
		if doc.get(f):
			return flt(doc.get(f))
	return 0.0


def _desc(doc):
	for f in DESC_FIELDS:
		if doc.get(f):
			return doc.get(f)
	return ""


def _workflow_items(company=None):
	out = []
	for wf in frappe.get_all("Workflow", filters={"is_active": 1}, fields=["name", "document_type", "workflow_state_field"]):
		w = frappe.get_doc("Workflow", wf.name)
		first = w.states[0].state if w.states else None
		final_docstatus = {s.state: int(s.doc_status or 0) for s in w.states}
		decisions = {}
		for t in w.transitions:
			# a decision: out of a state that is not the starting draft, and not a cancellation
			if t.state == first or final_docstatus.get(t.next_state, 0) == 2 or (t.action or "").lower().startswith("cancel"):
				continue
			decisions.setdefault(t.state, []).append(t)
		if not decisions:
			continue
		field = wf.workflow_state_field or "workflow_state"
		meta = frappe.get_meta(wf.document_type)
		filters = {field: ["in", list(decisions)], "docstatus": ["<", 2]}
		if company and meta.has_field("company"):
			filters["company"] = company
		fields = ["name", field, "owner", "modified", "creation", "docstatus"] + [f for f in VALUE_FIELDS + DESC_FIELDS if meta.has_field(f)]
		if meta.has_field("hs_approval_reason"):
			fields.append("hs_approval_reason")
		for d in frappe.get_all(wf.document_type, filters=filters, fields=fields, limit=200):
			ts = decisions[d.get(field)]
			roles = sorted({t.allowed for t in ts})
			out.append({
				"kind": "workflow", "type": _(wf.document_type), "doctype": wf.document_type, "name": d.name,
				"description": _desc(d), "reason": d.get("hs_approval_reason") or _("Workflow {0} — {1}").format(wf.name, _(d.get(field))),
				"value": _value(d), "waiting_for": roles, "state": d.get(field), "actions": sorted({t.action for t in ts}),
				"by": d.owner, "since": str(d.modified)[:10],
			})
	return out


def _waivers():
	if not frappe.db.table_exists("Document Waiver"):
		return []
	return [{"kind": "waiver", "type": _("Document exception"), "doctype": "Document Waiver", "name": w.name,
		"description": _("{0} for {1} {2}").format(_(w.document_type), _(w.reference_doctype), w.reference_name),
		"reason": w.reason or "", "value": 0, "waiting_for": [w.approver_role], "actions": ["Approve", "Reject"],
		"by": w.requested_by or w.owner, "since": str(w.creation)[:10]}
		for w in frappe.get_all("Document Waiver", filters={"status": "Pending"},
			fields=["name", "document_type", "reference_doctype", "reference_name", "reason", "approver_role", "requested_by", "owner", "creation"])
		if waiver_open(w)]


def waiver_open(w):
	"""v1.5.6: an exception for a record that has already moved on (submitted, cancelled or deleted) is no longer waiting."""
	if not w.reference_doctype or not w.reference_name or not frappe.db.exists(w.reference_doctype, w.reference_name):
		return False
	if frappe.get_meta(w.reference_doctype).is_submittable:
		return frappe.db.get_value(w.reference_doctype, w.reference_name, "docstatus") == 0
	return True


def _tax_returns(company=None):
	if not frappe.db.table_exists("Tax Return"):
		return []
	f = {"status": "Pending Finance Manager"}
	if company:
		f["company"] = company
	return [{"kind": "tax", "type": _(t.tax_type), "doctype": "Tax Return", "name": t.name, "description": t.title or t.name,
		"reason": _("Approve & lock before filing on EmaraTax · due {0}").format(frappe.format(t.due_date, "Date")),
		"value": flt(t.output_vat), "waiting_for": ["Accounts Manager"], "actions": ["Approve", "Reject"], "by": t.owner, "since": str(t.modified)[:10]}
		for t in frappe.get_all("Tax Return", filters=f, fields=["name", "title", "tax_type", "due_date", "output_vat", "owner", "modified"])]


def _hr(company=None):
	out = []
	if frappe.db.table_exists("Leave Application") and frappe.db.exists("DocType", "Leave Application"):
		f = {"status": "Open", "docstatus": 0}
		if company:
			f["company"] = company
		for la in frappe.get_all("Leave Application", filters=f, fields=["name", "employee_name", "leave_type", "total_leave_days", "from_date", "owner", "creation"]):
			out.append({"kind": "leave", "type": _("Leave Application"), "doctype": "Leave Application", "name": la.name,
				"description": _("{0} · {1} · {2} days from {3}").format(la.employee_name, _(la.leave_type), flt(la.total_leave_days), frappe.format(la.from_date, "Date")),
				"reason": "", "value": 0, "waiting_for": ["HR Manager", "Leave Approver"], "actions": ["Approve", "Reject"], "by": la.owner, "since": str(la.creation)[:10]})
	if frappe.db.table_exists("Expense Claim") and frappe.db.exists("DocType", "Expense Claim"):
		f = {"approval_status": "Draft", "docstatus": 0}
		if company:
			f["company"] = company
		for ec in frappe.get_all("Expense Claim", filters=f, fields=["name", "employee_name", "total_claimed_amount", "owner", "creation"]):
			out.append({"kind": "expense", "type": _("Expense Claim"), "doctype": "Expense Claim", "name": ec.name, "description": ec.employee_name,
				"reason": "", "value": flt(ec.total_claimed_amount), "waiting_for": ["Expense Approver", "HR Manager"], "actions": ["Approve", "Reject"],
				"by": ec.owner, "since": str(ec.creation)[:10]})
	return out


def _construction(company=None):
	"""v1.9.0 A2: construction quotations waiting for the MD (discount above the limit or margin below the floor)."""
	if not frappe.get_meta("Quotation").has_field("hs_cn_approval"):
		return []
	f = {"hs_cn": 1, "hs_cn_approval": "Pending", "docstatus": 0}
	if company:
		f["company"] = company
	return [{"kind": "cn_quote", "type": _("Construction quotation"), "doctype": "Quotation", "name": q.name,
		"description": _("{0} — {1}").format(q.hs_subject or q.customer_name, q.customer_name),
		"reason": _("Discount {0:.1f}% · margin {1:.1f}%").format(flt(q.hs_cn_discount_pct), flt(q.hs_estimated_margin)),
		"value": flt(q.base_net_total), "waiting_for": ["Managing Director"], "actions": ["Approve", "Reject"], "by": q.owner, "since": str(q.modified)[:10]}
		for q in frappe.get_all("Quotation", filters=f, fields=["name", "hs_subject", "customer_name", "hs_cn_discount_pct", "hs_estimated_margin", "base_net_total", "owner", "modified"])]


def _permits(company=None):
	"""v1.9.0 A4: permits to work waiting for the safety officer."""
	if not frappe.db.exists("DocType", "Work Permit"):
		return []
	f = {"status": "Requested"}
	if company:
		f["company"] = company
	return [{"kind": "cn_permit", "type": _("Permit to work"), "doctype": "Work Permit", "name": w.name,
		"description": _("{0} — {1} ({2})").format(_(w.kind), w.location, w.project), "reason": (w.work or "")[:120], "value": 0,
		"waiting_for": ["Safety Officer"], "actions": ["Approve", "Reject"], "by": w.owner, "since": str(w.creation)[:10]}
		for w in frappe.get_all("Work Permit", filters=f, fields=["name", "kind", "location", "project", "work", "owner", "creation"])]


def _journals(company=None):
	"""v1.9.0 A5: manual journals of a construction company waiting for the Accounts Manager (the MD above the limit)."""
	from hipersign_trading.api import construction_fin as FN

	cos = FN.companies()
	if not cos or not frappe.db.exists("DocType", "Staff Payroll"):
		return []
	lim = FN.limits().jv_md
	f = {"docstatus": 0, "voucher_type": "Journal Entry", "company": ["in", [company] if company in cos else cos]}
	return [{"kind": "cn_jv", "type": _("Manual journal"), "doctype": "Journal Entry", "name": j.name, "description": (j.user_remark or j.title or j.name)[:120],
		"reason": _("{0} — the MD approves above {1}").format(frappe.format(j.total_debit, {"fieldtype": "Currency", "options": "INR"}), frappe.format(lim, {"fieldtype": "Currency", "options": "INR"}))
		if flt(j.total_debit) > lim else _("Accounts Manager approves"), "value": flt(j.total_debit), "waiting_for": ["Managing Director"] if flt(j.total_debit) > lim else ["Accounts Manager", "Managing Director"],
		"actions": ["Approve"], "by": j.owner, "since": str(j.creation)[:10]}
		for j in frappe.get_all("Journal Entry", filters=f, fields=["name", "user_remark", "title", "total_debit", "owner", "creation"])]


def _site_cash(company=None):
	"""v1.9.0 A6: site cash above the site engineer's limit, waiting for the PM."""
	if not frappe.db.exists("DocType", "Site Expense"):
		return []
	from hipersign_trading.api.construction import project_names

	names = project_names([company] if company else None)
	return [{"kind": "cn_exp", "type": _("Site cash"), "doctype": "Site Expense", "name": x.name, "description": f"{x.project} — {x.description}"[:120],
		"reason": _("{0} spent by {1} — above the site limit").format(frappe.format(x.amount, {"fieldtype": "Currency", "options": "INR"}), x.requested_by or x.owner),
		"value": flt(x.amount), "waiting_for": ["Project Manager", "Managing Director"], "actions": ["Approve", "Reject"], "by": x.owner, "since": str(x.creation)[:10]}
		for x in frappe.get_all("Site Expense", filters={"status": "Waiting for approval", "project": ["in", names or [""]]},
			fields=["name", "project", "description", "amount", "requested_by", "owner", "creation"])]


def pending(company=None, mine=False):
	items = []
	for src in (_workflow_items, _tax_returns, _hr, _construction, _permits, _journals, _site_cash):
		try:
			items.extend(src(company))
		except Exception:
			frappe.log_error(title=f"Hipersign approvals {src.__name__}")
	items.extend(_waivers())
	roles = set(frappe.get_roles())
	items = [i for i in items if can_read(i["doctype"], i["name"])]
	for i in items:
		i["can_act"] = bool(roles & set(i["waiting_for"])) or "System Manager" in roles and i["kind"] != "workflow"
		i["days"] = date_diff(today(), i["since"]) if i.get("since") else 0
		i["by_name"] = frappe.get_cached_value("User", i["by"], "full_name") or i["by"] if i.get("by") else ""
	if mine:
		items = [i for i in items if i["can_act"]]
	items.sort(key=lambda i: (-i["days"], i["type"]))
	return items


@frappe.whitelist()
def get_approvals(company=None, mine=0):
	items = pending(company or None, mine=int(mine or 0))
	return {"items": items, "types": sorted({i["type"] for i in items})}


@frappe.whitelist()
def act(kind, doctype, name, action, note=None):
	"""Take the decision on the source document, as its own form would."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	approve = action in ("Approve", "Approved")
	if kind == "workflow":
		from frappe.model.workflow import apply_workflow

		doc = apply_workflow(doc, action)
		if note:
			doc.add_comment("Comment", note)
		return {"state": doc.get("workflow_state"), "docstatus": doc.docstatus}
	if kind == "waiver":
		(doc.approve if approve else doc.reject)(note=note)
		return {"state": doc.status}
	if kind == "tax":
		doc.approve() if approve else doc.reject(reason=note)
		return {"state": doc.status}
	if kind == "leave":
		doc.status = "Approved" if approve else "Rejected"
		doc.save()
		doc.submit()
		return {"state": doc.status}
	if kind == "cn_quote":  # v1.9.0 A2
		from hipersign_trading.api.construction import act as cn_act

		cn_act("qt_approve" if approve else "qt_reject", name, frappe.as_json({"note": note}))
		return {"state": frappe.db.get_value("Quotation", name, "hs_cn_approval")}
	if kind == "cn_permit":  # v1.9.0 A4
		from hipersign_trading.api.construction import act as cn_act

		cn_act("ptw_issue" if approve else "ptw_reject", name, frappe.as_json({"note": note}))
		return {"state": frappe.db.get_value("Work Permit", name, "status")}
	if kind == "cn_exp":  # v1.9.0 A6
		from hipersign_trading.api.construction import act as cn_act

		cn_act("exp_approve" if approve else "exp_reject", name, "{}")
		return {"state": "Booked" if approve else "Rejected"}
	if kind == "cn_jv":  # v1.9.0 A5
		from hipersign_trading.api.construction import act as cn_act

		if not approve:
			doc.add_comment("Comment", _("Sent back: {0}").format(note or ""))
			return {"state": "Draft"}
		cn_act("jv_approve", name, "{}")
		return {"state": "Posted"}
	if kind == "expense":
		doc.approval_status = "Approved" if approve else "Rejected"
		doc.save()
		if approve:
			doc.submit()
		return {"state": doc.approval_status}
	frappe.throw(_("Unknown approval"))
