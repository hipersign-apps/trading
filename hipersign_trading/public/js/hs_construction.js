// Hipersign ERP v1.9.0 (prototype C11) — Construction (India): the windows behind the Construction page buttons that need
// an answer (the client's certified amount, the rank of a lost tender), and the lists that open the Construction pages.
frappe.provide("hipersign.projects");

hipersign.cn = {
	act(action, name, args, done) {
		return frappe.xcall("hipersign_trading.api.construction.act", { action, name, args }).then((r) => {
			frappe.show_alert({ message: (r && r.message) || __("Done"), indicator: "green" }, 7);
			if (r && r.open && hipersign.panel && hipersign.panel.has && hipersign.panel.has(r.open[0])) hipersign.panel.open(r.open[0], r.open[1]);
			if (done) done(r);
		});
	},
};

// RA bill with the client → the certificate: the amount the client certified (it may cut the claim) and the date
hipersign.projects.cn_ra_certify = function (name, done) {
	frappe.db.get_value("RA Bill", name, ["claimed_amount", "bill_no", "project"]).then(({ message: r }) => {
		const d = new frappe.ui.Dialog({
			title: __("RA bill {0} — the client's certificate", [r.bill_no]),
			fields: [
				{ fieldtype: "HTML", options: `<p class="text-muted">${__("Claimed {0}. Enter what the client's engineer certified — any cut stays on the bill and can be claimed again.",
					[hipersign.ui.money(r.claimed_amount, "INR")])}</p>` },
				{ fieldtype: "Currency", fieldname: "amount", label: __("Certified amount (before GST)"), options: "INR", default: r.claimed_amount, reqd: 1 },
				{ fieldtype: "Date", fieldname: "date", label: __("Certified on"), default: frappe.datetime.get_today(), reqd: 1 },
			],
			primary_action_label: __("Record certificate"),
			primary_action(v) { d.hide(); hipersign.cn.act("ra_certify", name, v, done); },
		});
		d.show();
	});
};

// a lost tender: our rank
hipersign.projects.cn_tnd_lost = function (name, done) {
	frappe.prompt({ fieldtype: "Select", fieldname: "rank", label: __("Our rank"), options: ["L2", "L3", "L4", "L5", "L6+", "Disqualified"].join("\n"), default: "L2", reqd: 1 },
		(v) => hipersign.cn.act("tnd_lost", name, v, done), __("Tender lost"), __("Record"));
};

// the Construction lists open their pages (the UAE Projects pages keep Project and Project BOQ unless only Construction is on)
$(document).on("app_ready", () => {
	const L = (hipersign.nav && hipersign.nav.LIST_PAGE) || null;
	if (!L || !hipersign.feature("construction")) return;
	Object.assign(L, {
		Tender: ["hipersign-cn-tenders", "tnd"], "Measurement Book": ["hipersign-cn-mb", "mb"], "RA Bill": ["hipersign-cn-billing", "ra"],
		"Extra Item": ["hipersign-cn-boq", "ei"], "Daily Progress Report": ["hipersign-cn-site", "dpr"], Hindrance: ["hipersign-cn-site", "hin"],
	});
	if (!hipersign.feature("projects")) Object.assign(L, { Project: ["hipersign-cn-projects", "port"], "Project BOQ": ["hipersign-cn-boq", "boq"],
		"Bank Guarantee": ["hipersign-cn-projects", "bg"] });
});

// the same actions on the forms: what the record's status allows, as on the Construction pages
hipersign.cn.FORM_ACTS = {
	Tender: { "Bid / no-bid": [["Bid", "tnd_bid", 1], ["No bid", "tnd_nobid"]], "Being priced": [["Submit bid", "tnd_submit", 1]],
		Submitted: [["Next: technical evaluation", "tnd_next", 1], ["Lost…", "js:cn_tnd_lost"]], "Technical evaluation": [["Next: financial evaluation", "tnd_next", 1], ["Lost…", "js:cn_tnd_lost"]],
		"Financial evaluation": [["Next: L1 — LOA awaited", "tnd_next", 1], ["Lost…", "js:cn_tnd_lost"]], "L1 — LOA awaited": [["LOA received — award", "tnd_award", 1], ["Lost…", "js:cn_tnd_lost"]] },
	"Measurement Book": { Draft: [["QS checked", "mb_qs", 1], ["Reject", "mb_reject"]], "Checked by QS": [["Client checked", "mb_client", 1], ["Reject", "mb_reject"]] },
	"RA Bill": { Draft: [["Submit to client", "ra_submit", 1], ["Cancel bill", "ra_cancel"]], "Submitted to client": [["Record certificate…", "js:cn_ra_certify", 1], ["Cancel bill", "ra_cancel"]],
		Certified: [["Raise tax invoice", "ra_invoice", 1]], Invoiced: [["Payment received", "ra_receive", 1]], "Part paid": [["Payment received", "ra_receive", 1]] },
	"Extra Item": { Draft: [["Send to client", "ei_send", 1]], "Pending client": [["Client approved", "ei_approve", 1], ["Client rejected", "ei_reject"]] },
	"Daily Progress Report": { Draft: [["Submit", "dpr_submit", 1]], Submitted: [["Approve", "dpr_approve", 1]] },
};
Object.keys(hipersign.cn.FORM_ACTS).forEach((dt) => frappe.ui.form.on(dt, {
	refresh(frm) {
		if (frm.is_new()) return;
		(hipersign.cn.FORM_ACTS[dt][frm.doc.status] || []).forEach(([label, act, primary]) => {
			const go = () => (act.startsWith("js:") ? hipersign.projects[act.slice(3)](frm.doc.name, () => frm.reload_doc())
				: (frm.is_dirty() ? frm.save() : Promise.resolve()).then(() => hipersign.cn.act(act, frm.doc.name, {}, (r) => (r && r.open && r.open[0] !== dt ? frappe.set_route("Form", r.open[0], r.open[1]) : frm.reload_doc()))));
			const b = frm.add_custom_button(__(label), go);
			if (primary) b.removeClass("btn-default").addClass("btn-primary");
		});
	},
}));
frappe.ui.form.on("Hindrance", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (!frm.doc.to_date) frm.add_custom_button(__("Ended today"), () => hipersign.cn.act("hin_close", frm.doc.name, {}, () => frm.reload_doc()));
		if (frm.doc.eot_status === "Not applied") frm.add_custom_button(__("Apply EOT"), () => hipersign.cn.act("hin_eot", frm.doc.name, {}, () => frm.reload_doc()));
	},
});
// a project marked Construction (India): the button that prepares the next RA bill from the checked measurements
frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.hs_cn || !hipersign.feature("construction")) return;
		frm.add_custom_button(__("Prepare RA bill"), () => hipersign.cn.act("ra_new", frm.doc.name, {}, (r) => r && r.open && frappe.set_route("Form", r.open[0], r.open[1])), __("Construction"));
		frm.add_custom_button(__("Construction page"), () => frappe.set_route("hipersign-cn-projects"), __("Construction"));
	},
});

// ---------------------------------------------------------------- v1.9.0 A2: business windows (CRM, quotations, claims, collections)
const hs_cn_dialog = (title, fields, label, action, name, done) => {
	const d = new frappe.ui.Dialog({ title, fields, primary_action_label: label, primary_action(v) { d.hide(); hipersign.cn.act(action, name, v, done); } });
	d.show();
	return d;
};
hipersign.projects.cn_opp_followed = (name, done) => hs_cn_dialog(__("Follow-up done"), [
	{ fieldtype: "Small Text", fieldname: "note", label: __("What was discussed") },
	{ fieldtype: "Date", fieldname: "date", label: __("Next follow-up"), reqd: 1, default: frappe.datetime.add_days(frappe.datetime.get_today(), 7) },
], __("Save"), "opp_followed", name, done);
hipersign.projects.cn_opp_lost = (name, done) => hs_cn_dialog(__("Enquiry lost"), [
	{ fieldtype: "Select", fieldname: "reason", label: __("Reason"), reqd: 1, options: ["Price too high", "Lost to competitor", "Project shelved by client", "Client chose design-build", "Scope or terms not acceptable", "Other"].join("\n") },
	{ fieldtype: "Data", fieldname: "competitor", label: __("Won by (competitor)") },
	{ fieldtype: "Small Text", fieldname: "note", label: __("Detail") },
], __("Record lost"), "opp_lost", name, done);
hipersign.projects.cn_qt_lost = (name, done) => hs_cn_dialog(__("Quotation lost"), [
	{ fieldtype: "Select", fieldname: "reason", label: __("Reason"), reqd: 1, options: ["Price too high", "Lost to competitor", "Project shelved by client", "Scope or terms not acceptable", "Other"].join("\n") },
	{ fieldtype: "Small Text", fieldname: "note", label: __("Detail") },
], __("Record lost"), "qt_lost", name, done);
hipersign.projects.cn_qt_revise = (name, done) => hs_cn_dialog(__("Revise {0}", [name]), [
	{ fieldtype: "HTML", options: `<p class="text-muted">${__("A sent quotation is never changed: a new revision is drafted with your reason, and this one is withdrawn.")}</p>` },
	{ fieldtype: "Small Text", fieldname: "reason", label: __("Reason for the revision"), reqd: 1 },
], __("Draft revision"), "qt_revise", name, (r) => { if (r && r.open) frappe.set_route("Form", r.open[0], r.open[1]); else if (done) done(r); });
hipersign.projects.cn_qt_accept = (name, done) => hs_cn_dialog(__("Client accepted {0}", [name]), [
	{ fieldtype: "HTML", options: `<p class="text-muted">${__("Creates the project (Construction India), its BOQ from the quotation lines and the contract with the LOA.")}</p>` },
	{ fieldtype: "Data", fieldname: "loa_no", label: __("LOA / work order no."), reqd: 1 },
	{ fieldtype: "Date", fieldname: "loa_date", label: __("LOA date"), reqd: 1, default: frappe.datetime.get_today() },
	{ fieldtype: "Date", fieldname: "start", label: __("Site handover / start"), reqd: 1, default: frappe.datetime.add_days(frappe.datetime.get_today(), 21) },
	{ fieldtype: "Int", fieldname: "months", label: __("Duration (months)"), reqd: 1, default: 18 },
], __("Create project & contract"), "qt_accept", name, done);
hipersign.projects.cn_clm_award = (name, done) => frappe.db.get_value("Contract Claim", name, ["claimed_days", "claimed_amount", "title"]).then(({ message: c }) => hs_cn_dialog(__("Award — {0}", [c.title]), [
	{ fieldtype: "Int", fieldname: "days", label: __("Days awarded (of {0})", [c.claimed_days || 0]), default: c.claimed_days || 0 },
	{ fieldtype: "Currency", fieldname: "amount", options: "INR", label: __("Amount awarded (of {0})", [hipersign.ui.money(c.claimed_amount, "INR")]), default: c.claimed_amount || 0 },
], __("Record award"), "clm_award", name, done));
hipersign.projects.cn_fup_log = (name, done) => frappe.db.get_value("RA Bill", name, ["bill_no", "due_date", "net_receivable", "received_amount"]).then(({ message: r }) => {
	const days = frappe.datetime.get_day_diff(frappe.datetime.get_today(), r.due_date);
	const lv = ["L1 — e-mail reminder", "L2 — PM call", "L3 — MD letter", "L4 — legal notice"];
	const due = days <= 15 ? lv[0] : days <= 30 ? lv[1] : days <= 60 ? lv[2] : lv[3];
	hs_cn_dialog(__("RA bill {0} — {1} days overdue", [r.bill_no, Math.max(0, days)]), [
		{ fieldtype: "Select", fieldname: "level", label: __("Level"), options: lv.join("\n"), default: due, reqd: 1 },
		{ fieldtype: "Small Text", fieldname: "note", label: __("What was said / sent"), reqd: 1 },
		{ fieldtype: "Date", fieldname: "promised_date", label: __("Client promised to pay by") },
		{ fieldtype: "Currency", fieldname: "promised_amount", options: "INR", label: __("Amount promised"), default: flt(r.net_receivable) - flt(r.received_amount) },
	], __("Log"), "fup_log", name, done);
});

Object.assign(hipersign.cn.FORM_ACTS, {
	"Contract Claim": { Draft: [["Submit to client", "clm_submit", 1]], Submitted: [["Under negotiation", "clm_negotiate"], ["Awarded…", "js:cn_clm_award", 1]],
		"Under negotiation": [["Awarded…", "js:cn_clm_award", 1], ["Rejected", "clm_reject"]] },
});
frappe.ui.form.on("Contract Claim", {
	refresh(frm) {
		if (frm.is_new()) return;
		(hipersign.cn.FORM_ACTS["Contract Claim"][frm.doc.status] || []).forEach(([label, act, primary]) => {
			const b = frm.add_custom_button(__(label), () => (act.startsWith("js:") ? hipersign.projects[act.slice(3)](frm.doc.name, () => frm.reload_doc())
				: hipersign.cn.act(act, frm.doc.name, {}, () => frm.reload_doc())));
			if (primary) b.removeClass("btn-default").addClass("btn-primary");
		});
	},
});
// a construction quotation: MD approval, revise, won, lost — what its state allows
frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.hs_cn || !hipersign.feature("cn_biz")) return;
		const add = (label, fn, primary) => { const b = frm.add_custom_button(label, fn, __("Construction")); if (primary) b.addClass("btn-primary"); };
		const reload = () => frm.reload_doc();
		if (frm.doc.hs_cn_approval === "Pending") {
			add(__("Approve (MD)"), () => hipersign.cn.act("qt_approve", frm.doc.name, {}, reload));
			add(__("Send back (MD)"), () => hipersign.cn.act("qt_reject", frm.doc.name, {}, reload));
			frm.dashboard.set_headline_alert(__("Needs the Managing Director's approval before it is sent — discount {0}%, margin {1}%.",
				[flt(frm.doc.hs_cn_discount_pct, 1), flt(frm.doc.hs_estimated_margin, 1)]), "orange");
		}
		if (frm.doc.docstatus === 1 && (frm.doc.hs_cn_outcome || "Open") === "Open") {
			add(__("Client accepted…"), () => hipersign.projects.cn_qt_accept(frm.doc.name, reload));
			add(__("Revise…"), () => hipersign.projects.cn_qt_revise(frm.doc.name, reload));
			add(__("Lost…"), () => hipersign.projects.cn_qt_lost(frm.doc.name, reload));
		}
	},
});
frappe.ui.form.on("Opportunity", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.hs_cn || !hipersign.feature("cn_biz") || !["Open", "Quotation", "Replied"].includes(frm.doc.status)) return;
		frm.add_custom_button(__("Construction quotation"), () => hipersign.cn.act("opp_quote", frm.doc.name, {}, (r) => r && r.open && frappe.set_route("Form", r.open[0], r.open[1])), __("Construction"));
		frm.add_custom_button(__("Followed up…"), () => hipersign.projects.cn_opp_followed(frm.doc.name, () => frm.reload_doc()), __("Construction"));
	},
});
// the business lists open their pages
$(document).on("app_ready", () => {
	const L = (hipersign.nav && hipersign.nav.LIST_PAGE) || null;
	if (!L || !hipersign.feature("cn_biz")) return;
	Object.assign(L, { "Client Visit": ["hipersign-cn-crm", "visit"], "Construction Contract": ["hipersign-cn-contracts", "reg"], "Contract Claim": ["hipersign-cn-contracts", "clm"],
		"Collection Follow-up": ["hipersign-cn-sales", "fup"] });
});

// ---------------------------------------------------------------- v1.9.0 A3: site resources — the same actions on the forms
Object.assign(hipersign.cn.FORM_ACTS, {
	"Subcontractor Work Order": { Draft: [["Issue work order", "swo_activate", 1]] },
	"Subcontractor Bill": { Draft: [["Certify (QS)", "sub_certify", 1]], Certified: [["Approve & book (PM)", "sub_approve", 1]], Approved: [["Pay", "sub_pay", 1]] },
	"Weekly Muster": { Draft: [["Approve wages (PM)", "mus_approve", 1]], Approved: [["Pay by UPI", "mus_pay", 1]] },
	"Worker Advance": { Requested: [["Approve", "adv_approve", 1], ["Reject", "adv_reject"]], Approved: [["Pay by UPI", "adv_pay", 1]] },
});
["Subcontractor Work Order", "Subcontractor Bill", "Weekly Muster", "Worker Advance"].forEach((dt) => frappe.ui.form.on(dt, {
	refresh(frm) {
		if (frm.is_new()) return;
		(hipersign.cn.FORM_ACTS[dt][frm.doc.status] || []).forEach(([label, act, primary]) => {
			const b = frm.add_custom_button(__(label), () => (frm.is_dirty() ? frm.save() : Promise.resolve()).then(() =>
				hipersign.cn.act(act, frm.doc.name, {}, (r) => (r && r.open && r.open[0] !== dt ? frappe.set_route("Form", r.open[0], r.open[1]) : frm.reload_doc()))));
			if (primary) b.removeClass("btn-default").addClass("btn-primary");
		});
		if (dt === "Subcontractor Bill" && frm.doc.compliance_hold) frm.dashboard.set_headline_alert(__("On hold: the contractor's wage register, PF ECR or ESI challan for last month is missing."), "red");
	},
}));
// a weekly muster fills its workers: every own worker of the project
frappe.ui.form.on("Weekly Muster", {
	project(frm) {
		if (!frm.doc.project || (frm.doc.rows || []).length) return;
		frappe.db.get_list("Site Worker", { filters: { project: frm.doc.project, status: "Active", contractor: ["is", "not set"] }, fields: ["name", "daily_rate"], limit: 500 }).then((ws) => {
			ws.forEach((w) => frm.add_child("rows", { worker: w.name, rate: w.daily_rate, days: 6 }));
			frm.refresh_field("rows");
		});
	},
});
$(document).on("app_ready", () => {
	const L = (hipersign.nav && hipersign.nav.LIST_PAGE) || null;
	if (!L || !hipersign.feature("cn_site")) return;
	Object.assign(L, { "Subcontractor Work Order": ["hipersign-cn-subcon", "wo"], "Subcontractor Bill": ["hipersign-cn-subcon", "bill"], "Labour Compliance": ["hipersign-cn-subcon", "lc"],
		"Site Worker": ["hipersign-cn-labour", "wkr"], "Weekly Muster": ["hipersign-cn-labour", "mus"], "Worker Advance": ["hipersign-cn-labour", "adv"], "Minimum Wage": ["hipersign-cn-labour", "mw"],
		"Construction Equipment": ["hipersign-cn-equipment", "reg"], "Equipment Log": ["hipersign-cn-equipment", "log"], "Equipment Maintenance": ["hipersign-cn-equipment", "mnt"] });
});

// ---------------------------------------------------------------- v1.9.0 A4: quality, safety, drawings, handover — windows and form buttons
hipersign.projects.cn_ir_reject = (name, done) => hs_cn_dialog(__("Inspection not accepted"), [
	{ fieldtype: "Small Text", fieldname: "note", label: __("Inspector's remarks — what to correct"), reqd: 1 },
	{ fieldtype: "HTML", options: `<p class="text-muted">${__("A re-inspection request is raised for two days from today.")}</p>` },
], __("Reject"), "ir_reject", name, done);
hipersign.projects.cn_ncr_close = (name, done) => frappe.db.get_value("NCR", name, ["root_cause", "corrective_action", "rework_cost"]).then(({ message: n }) => hs_cn_dialog(__("Close {0}", [name]), [
	{ fieldtype: "Small Text", fieldname: "root_cause", label: __("Root cause"), reqd: 1, default: n.root_cause },
	{ fieldtype: "Small Text", fieldname: "corrective_action", label: __("Corrective & preventive action"), reqd: 1, default: n.corrective_action },
	{ fieldtype: "Currency", fieldname: "rework_cost", options: "INR", label: __("Rework cost"), default: n.rework_cost },
], __("Close NCR"), "ncr_close", name, done));
hipersign.projects.cn_inc_close = (name, done) => frappe.db.get_value("Safety Incident", name, ["root_cause", "action"]).then(({ message: n }) => hs_cn_dialog(__("Close {0}", [name]), [
	{ fieldtype: "Small Text", fieldname: "root_cause", label: __("Root cause"), default: n.root_cause },
	{ fieldtype: "Small Text", fieldname: "action", label: __("Corrective action"), default: n.action },
], __("Close incident"), "inc_close", name, done));
hipersign.projects.cn_rfi_answer = (name, done) => hs_cn_dialog(__("Answer to {0}", [name]), [
	{ fieldtype: "Small Text", fieldname: "answer", label: __("Consultant's answer"), reqd: 1 },
	{ fieldtype: "Date", fieldname: "date", label: __("Answered on"), default: frappe.datetime.get_today(), reqd: 1 },
], __("Save answer"), "rfi_answer", name, done);
hipersign.projects.cn_def_rectify = (name, done) => hs_cn_dialog(__("Defect rectified"), [
	{ fieldtype: "Currency", fieldname: "cost", options: "INR", label: __("Cost to rectify") },
], __("Rectified"), "def_rectify", name, done);
hipersign.projects.cn_ret_release = (name, done) => frappe.xcall("frappe.client.get_value", { doctype: "Project", filters: name, fieldname: ["project_name"] }).then((p) => hs_cn_dialog(
	__("Retention received — {0}", [p.project_name]), [
	{ fieldtype: "Currency", fieldname: "amount", options: "INR", label: __("Amount received (blank: half at completion)") },
	{ fieldtype: "Date", fieldname: "date", label: __("Received on"), default: frappe.datetime.get_today(), reqd: 1 },
], __("Record receipt"), "ret_release", name, done));

Object.assign(hipersign.cn.FORM_ACTS, {
	"Inspection Request": { Requested: [["Approved", "ir_approve", 1], ["Rejected…", "js:cn_ir_reject"]] },
	NCR: { Open: [["Close NCR…", "js:cn_ncr_close", 1]] },
	"Safety Incident": { Open: [["Close…", "js:cn_inc_close", 1]] },
	"Work Permit": { Requested: [["Issue (safety officer)", "ptw_issue", 1], ["Refuse", "ptw_reject"]], Issued: [["Close permit", "ptw_close", 1]] },
	"Construction Drawing": { "For approval": [["Issue GFC", "drg_gfc", 1]] },
	RFI: { Open: [["Answered…", "js:cn_rfi_answer", 1]], Answered: [["Close", "rfi_close", 1]] },
	Transmittal: { Sent: [["Acknowledged", "trn_ack", 1]] },
	Snag: { Open: [["Fixed", "snag_fixed", 1]], Fixed: [["Client verified", "snag_verify", 1]] },
	"Handover Document": { "Not started": [["Applied", "hdoc", 1]], Applied: [["Received", "hdoc", 1]] },
	"DLP Defect": { Reported: [["Responded", "def_respond", 1]], Responded: [["Rectified…", "js:cn_def_rectify", 1]] },
});
["Inspection Request", "NCR", "Safety Incident", "Work Permit", "Construction Drawing", "RFI", "Transmittal", "Snag", "Handover Document", "DLP Defect"].forEach((dt) => frappe.ui.form.on(dt, {
	refresh(frm) {
		if (frm.is_new()) return;
		(hipersign.cn.FORM_ACTS[dt][frm.doc.status] || []).forEach(([label, act, primary]) => {
			const b = frm.add_custom_button(__(label), () => (act.startsWith("js:") ? hipersign.projects[act.slice(3)](frm.doc.name, () => frm.reload_doc())
				: (frm.is_dirty() ? frm.save() : Promise.resolve()).then(() => hipersign.cn.act(act, frm.doc.name, {}, (r) => (r && r.open && r.open[0] !== dt ? frappe.set_route("Form", r.open[0], r.open[1]) : frm.reload_doc())))));
			if (primary) b.removeClass("btn-default").addClass("btn-primary");
		});
	},
}));
$(document).on("app_ready", () => {
	const L = (hipersign.nav && hipersign.nav.LIST_PAGE) || null;
	if (!L || !hipersign.feature("cn_qhse")) return;
	Object.assign(L, { "Inspection Request": ["hipersign-cn-quality", "ir"], "Cube Test": ["hipersign-cn-quality", "cube"], NCR: ["hipersign-cn-quality", "ncr"], "ITP Item": ["hipersign-cn-quality", "itp"],
		"Safety Incident": ["hipersign-cn-safety", "inc"], "Work Permit": ["hipersign-cn-safety", "ptw"], "Toolbox Talk": ["hipersign-cn-safety", "tbt"], "Safety Audit": ["hipersign-cn-safety", "site"],
		"Construction Drawing": ["hipersign-cn-drawings", "dwg"], RFI: ["hipersign-cn-drawings", "rfi"], Transmittal: ["hipersign-cn-drawings", "trn"], Snag: ["hipersign-cn-handover", "snag"],
		"Handover Document": ["hipersign-cn-handover", "docs"], "DLP Defect": ["hipersign-cn-handover", "def"], "Construction Warranty": ["hipersign-cn-handover", "wty"] });
});

// v1.9.0 A5 (prototype C8): finance & tax — statutory payments from the GST & TDS page, payroll buttons on the form
$(document).on("app_ready", () => {
	const L = (hipersign.nav && hipersign.nav.LIST_PAGE) || null;
	if (!L || !hipersign.feature("cn_fin")) return;
	Object.assign(L, { "Staff Payroll": ["hipersign-cn-payroll", "run"], "Statutory Deposit": ["hipersign-cn-payroll", "dep"] });
});
Object.assign(hipersign.cn.FORM_ACTS, { "Staff Payroll": { Draft: [["Approve", "pay_approve", 1]], Approved: [["Pay", "pay_pay", 1]] } });
Object.assign(hipersign.projects, {
	_cn_dep(title, args, fields, done) {
		const d = new frappe.ui.Dialog({ title, fields: [...fields,
			{ fieldname: "challan_no", fieldtype: "Data", label: __("Challan / CIN"), reqd: 1 },
			{ fieldname: "date", fieldtype: "Date", label: __("Paid on"), default: frappe.datetime.get_today(), reqd: 1 }],
			primary_action_label: __("Pay"),
			primary_action(v) { d.hide(); hipersign.cn.act("dep_pay", "new", Object.assign({}, args, v), done); } });
		d.show();
	},
	cn_gst_pay(code, done) {
		const [gstin, month] = code.split("|");
		hipersign.projects._cn_dep(__("Pay GST — {0}", [gstin]), { kind: "GST", gstin, month }, [
			{ fieldtype: "HTML", options: `<p class="text-muted">${__("Output tax is set off against the input tax credit first; the balance is paid in cash from the bank.")}</p>` }], done);
	},
	cn_dep_pay(code, done) {
		const [kind, month, amount] = code.split("|");
		hipersign.projects._cn_dep(__("Deposit {0}", [__(kind)]), { kind, month }, [
			{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), options: "INR", default: flt(amount), reqd: 1 }], done);
	},
	cn_cess_pay(code, done) {
		const [project, amount] = code.split("|");
		hipersign.projects._cn_dep(__("Pay BOCW cess to the welfare board"), { kind: "BOCW labour cess", project, month: frappe.datetime.get_today() }, [
			{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), options: "INR", default: flt(amount), reqd: 1 }], done);
	},
});
