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
