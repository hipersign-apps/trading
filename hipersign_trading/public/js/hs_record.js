// Hipersign ERP v1.9.2 U3/U4 — the Hipersign record page. Every Construction (India) record (Tender, RA Bill, Measurement
// Book, DPR, NCR, work orders, workers …) opens here instead of ERPNext's form: a header with the status and its steps, the
// key figures, the filled fields as cards, the line tables, linked records, files and activity — and the same actions as
// the Construction pages (hipersign.cn.FORM_ACTS). Edit and New open the designed form on the same page; it saves through
// frappe.client, so every server rule still runs. Server side: api/record.py.
frappe.provide("hipersign.record");

(function () {
	const R = hipersign.record, esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s)), API = "hipersign_trading.api.record.";
	const ic = (n, s) => frappe.utils.icon(n, s || "sm");
	R.types = () => ((frappe.boot && frappe.boot.hipersign) || {}).record_types || [];
	R.has = (dt) => R.types().includes(dt);
	R.view_only = (dt) => (((frappe.boot && frappe.boot.hipersign) || {}).record_view_only || []).includes(dt);  // made by the pages' actions
	R.open = (dt, name) => frappe.set_route("Form", dt, name);
	R.new = (dt, values) => { frappe.route_options = Object.assign({}, values || {}); frappe.set_route("hipersign-record", dt, "new"); };
	const money = (v, cur) => (hipersign.ui && hipersign.ui.money ? hipersign.ui.money(v, cur, true) : format_currency(v, cur));
	const pill = (t, tone) => (t ? `<span class="hsx-pill ${tone || "grey"}">${esc(t)}</span>` : "");
	const go_link = (dt, name) => { if (R.has(dt)) return R.open(dt, name); if (hipersign.panel && hipersign.panel.has && hipersign.panel.has(dt)) return hipersign.panel.open(dt, name); };

	// ---------------------------------------------------------------- the page
	R.load = function (wrapper) {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Record"), single_column: true });
		wrapper.hr = { page, $body: $(`<div class="hr-wrap"></div>`).appendTo(page.main) };
		$(wrapper).find(".page-head").addClass("hr-hidden-head");
	};
	R.show = function (wrapper) {
		const route = frappe.get_route(), dt = route[1], name = route.slice(2).join("/");
		const st = wrapper.hr;
		if (!dt) return frappe.set_route("hipersign-home");
		const opts = frappe.route_options; frappe.route_options = null;
		if (!name || name === "new") return R.form(st, dt, null, opts || {});
		if (String(name).startsWith("new-")) return R.form(st, dt, null, Object.assign({}, (locals[dt] || {})[name] || {}, opts || {}));
		if (opts && opts.__edit) return R.form(st, dt, name, {});
		R.view(st, dt, name);
	};

	R.view = function (st, dt, name) {
		st.$body.html(`<div class="hsx-loading">${__("Loading…")}</div>`);
		frappe.xcall(API + "get", { doctype: dt, name }).then((r) => { st.r = r; st.page.set_title(r.title); document.title = `${r.title} · ${r.label}`; render_view(st); })
			.catch(() => st.$body.html(`<div class="hr-empty">${ic("alert-triangle", "lg")}<p>${__("This record could not be opened.")}</p><button class="btn btn-default" data-hr="back">${__("Back")}</button></div>`));
	};

	function actions(r) {
		const A = (hipersign.cn && hipersign.cn.FORM_ACTS && hipersign.cn.FORM_ACTS[r.doctype]) || {};
		const list = r.docstatus === 2 ? [] : (A[r.raw_status] || A[r.doc.instruction_status] || A["*"] || []);
		return list.map(([label, act, primary]) => ({ label: __(label), act, primary }));
	}

	function render_view(st) {
		const r = st.r, acts = actions(r), can = r.can;
		const head = `<div class="hr-head">
			<button class="hr-back" data-hr="back" title="${__("Back")}">${ic("left")}</button>
			<div class="hr-h">
				<div class="hr-kick">${esc(r.label)}${r.title !== r.name ? ` · ${esc(r.name)}` : ""}</div>
				<h2>${esc(r.title)} ${pill(r.status, r.tone)}</h2>
				${r.sub.length ? `<div class="hr-sub">${r.sub.map((s) => `<span>${esc(s.label)}: ${s.open ? `<a data-hr="link" data-dt="${esc(s.dt)}" data-name="${esc(s.name)}">${esc(s.value)}</a>` : `<b>${esc(s.value)}</b>`}</span>`).join("")}</div>` : ""}
			</div>
			<div class="hr-acts">
				${acts.map((a, i) => `<button class="btn btn-sm ${a.primary ? "btn-primary" : "btn-default"}" data-hr="act" data-i="${i}">${esc(a.label)}</button>`).join("")}
				${can.write ? `<button class="btn btn-sm btn-default" data-hr="edit">${ic("edit")} ${__("Edit")}</button>` : ""}
				${can.submit ? `<button class="btn btn-sm btn-default" data-hr="submit">${__("Submit")}</button>` : ""}
				<div class="dropdown hr-more"><button class="btn btn-sm btn-default" data-toggle="dropdown" title="${__("More")}">${ic("dot-horizontal")}</button>
					<div class="dropdown-menu dropdown-menu-right">
						<a class="dropdown-item" data-hr="print">${__("Print")}</a><a class="dropdown-item" data-hr="copy">${__("Copy link")}</a>
						${can.create ? `<a class="dropdown-item" data-hr="dup">${__("Duplicate")}</a>` : ""}
						${can.cancel ? `<a class="dropdown-item text-danger" data-hr="cancel">${__("Cancel")}</a>` : ""}
						${can.delete ? `<a class="dropdown-item text-danger" data-hr="delete">${__("Delete")}</a>` : ""}</div></div>
			</div></div>`;
		const steps = r.steps ? `<div class="hsx-card hr-steps"><div class="hsx-steps">${r.steps.steps.map((s, i) => `<div class="hsx-step ${i <= r.steps.at ? "on" : ""} ${i === r.steps.at ? "cur" : ""}"><i>${i < r.steps.at ? "✓" : i + 1}</i><span>${esc(s)}</span></div>`).join("")}</div></div>` : "";
		const figs = r.figures.length ? `<div class="hr-figs">${r.figures.map((f) => `<div class="hr-fig"><small>${esc(f.label)}</small><b>${f.kind === "money" ? esc(money(f.value, f.currency)) : esc(flt(f.value, 1) + "%")}</b></div>`).join("")}</div>` : "";
		const field = (f) => `<div class="hr-f ${f.wide ? "wide" : ""}"><span>${esc(f.label)}</span><div>${f.file ? (f.image ? `<a href="${esc(f.file)}" target="_blank" rel="noopener"><img src="${esc(f.file)}" alt=""></a>` : `<a href="${esc(f.file)}" target="_blank" rel="noopener">${ic("file")} ${esc(f.file.split("/").pop())}</a>`)
			: f.dt && f.open ? `<a data-hr="link" data-dt="${esc(f.dt)}" data-name="${esc(f.name)}">${esc(f.title)}</a>${f.title !== f.name ? ` <small>${esc(f.name)}</small>` : ""}`
			: f.dt ? `${esc(f.title)}${f.title !== f.name ? ` <small>${esc(f.name)}</small>` : ""}` : f.html}</div></div>`;
		const table = (t, solo) => `<div class="hr-tbl">${solo ? "" : `<div class="hr-tbl-h">${esc(t.label)} <small>${t.rows.length}</small></div>`}<div class="hsx-tw"><table class="hsx-t"><thead><tr><th class="hr-n">#</th>${t.cols.map((c) => `<th class="${c.num ? "text-right" : ""}">${esc(c.label)}</th>`).join("")}</tr></thead>
			<tbody>${t.rows.map((row, i) => `<tr><td class="hr-n">${i + 1}</td>${row.map((c, j) => `<td class="${t.cols[j].num ? "text-right" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody>
			${t.totals ? `<tfoot><tr><td></td>${t.totals.map((c, j) => `<td class="${t.cols[j].num ? "text-right" : ""}">${c}</td>`).join("")}</tr></tfoot>` : ""}</table></div></div>`;
		const sections = r.sections.map((s) => { const solo = !s.fields.length && s.tables.length === 1;
			return hipersign.ui.card(solo ? `${s.tables[0].label}` : s.label || __("Details"), `${s.fields.length ? `<div class="hr-grid">${s.fields.map(field).join("")}</div>` : ""}${s.tables.map((t) => table(t, solo)).join("")}`, solo ? { sub: String(s.tables[0].rows.length) } : {}); }).join("");
		const linked = r.linked.length ? hipersign.ui.card(__("Linked records"), r.linked.map((g) => `<div class="hr-lg"><div class="hr-lg-h">${esc(g.label)} <small>${g.count}</small></div>
			${g.items.map((i) => `<${g.open ? "a" : "div"} class="hr-li" ${g.open ? `data-hr="link" data-dt="${esc(g.doctype)}" data-name="${esc(i.name)}"` : ""}><span>${esc(i.title || i.name)}${i.title && i.title !== i.name ? `<small>${esc(i.name)}</small>` : ""}</span>${pill(i.status, i.tone)}</${g.open ? "a" : "div"}>`).join("")}</div>`).join(""), { icon: "link" }) : "";
		const files = hipersign.ui.card(__("Files"), `${r.files.map((f) => `<a class="hr-file" href="${esc(f.file_url)}" target="_blank" rel="noopener">${ic("file")}<span>${esc(f.file_name || f.file_url)}</span></a>`).join("") || `<p class="hr-muted">${__("No files yet.")}</p>`}
			<button class="btn btn-xs btn-default" data-hr="attach">${ic("upload")} ${__("Add a file")}</button>`, { icon: "attachment" });
		const actv = hipersign.ui.card(__("Activity"), `<div class="hr-cmt"><textarea class="form-control" rows="2" placeholder="${__("Add a comment — @name to notify a colleague")}"></textarea><button class="btn btn-xs btn-primary" data-hr="comment">${__("Comment")}</button></div>
			${r.activity.map((a) => `<div class="hr-act"><i class="k-${esc(a.kind)}"></i><div><b>${esc(a.by)}</b> ${a.kind === "created" ? __("created this") : a.kind === "changed" ? __("last changed it") : ""} <small>${frappe.datetime.comment_when(a.on)}</small>${a.text ? `<div class="hr-act-t">${a.text}</div>` : ""}</div></div>`).join("")}`, { icon: "message" });
		st.$body.html(`${head}${steps}${figs}<div class="hr-cols"><div class="hr-main">${sections || hipersign.ui.card("", `<p class="hr-muted">${__("Nothing filled in yet.")}</p>`)}</div><div class="hr-side">${linked}${files}${actv}</div></div>`);
		wire(st);
	}

	function wire(st) {
		const r = st.r;
		st.$body.off("click.hr").on("click.hr", "[data-hr]", function (e) {
			const k = $(this).attr("data-hr");
			if (k !== "link") e.preventDefault();
			if (k === "back") return window.history.length > 2 ? window.history.back() : frappe.set_route("hipersign-home");
			if (k === "link") { e.preventDefault(); return go_link($(this).attr("data-dt"), $(this).attr("data-name")); }
			if (k === "edit") return R.form(st, r.doctype, r.name, {});
			if (k === "act") { const a = actions(r)[+$(this).attr("data-i")];
				if (a.act.startsWith("js:")) return hipersign.projects[a.act.slice(3)](r.name, () => R.view(st, r.doctype, r.name));
				return hipersign.cn.act(a.act, r.name, {}, (x) => (x && x.open && x.open[0] !== r.doctype ? go_link(x.open[0], x.open[1]) || R.view(st, r.doctype, r.name) : R.view(st, r.doctype, r.name))); }
			if (k === "submit") return frappe.confirm(__("Submit {0}? It can then only be changed by cancelling it.", [r.title]), () =>
				frappe.xcall("frappe.client.submit", { doc: r.doc }).then(() => { frappe.show_alert({ message: __("Submitted"), indicator: "green" }); R.view(st, r.doctype, r.name); }));
			if (k === "cancel") return frappe.confirm(__("Cancel {0}?", [r.title]), () => frappe.xcall("frappe.client.cancel", { doctype: r.doctype, name: r.name }).then(() => R.view(st, r.doctype, r.name)));
			if (k === "delete") return frappe.confirm(__("Delete {0}? This cannot be undone.", [r.title]), () => frappe.xcall("frappe.client.delete", { doctype: r.doctype, name: r.name })
				.then(() => { frappe.show_alert({ message: __("Deleted"), indicator: "orange" }); window.history.back(); }));
			if (k === "print") return window.open(`/printview?doctype=${encodeURIComponent(r.doctype)}&name=${encodeURIComponent(r.name)}&trigger_print=1`, "_blank");
			if (k === "copy") return frappe.utils.copy_to_clipboard(`${location.origin}/app/${frappe.router.slug(r.doctype)}/${encodeURIComponent(r.name)}`);
			if (k === "dup") { const v = Object.assign({}, r.doc); ["name", "owner", "creation", "modified", "modified_by", "docstatus", "status", "amended_from", "idx"].forEach((x) => delete v[x]);
				return R.form(st, r.doctype, null, v); }
			if (k === "attach") return new frappe.ui.FileUploader({ doctype: r.doctype, docname: r.name, on_success: () => R.view(st, r.doctype, r.name) });
			if (k === "comment") { const t = st.$body.find(".hr-cmt textarea").val(); if (!t.trim()) return;
				return frappe.xcall("frappe.desk.form.utils.add_comment", { reference_doctype: r.doctype, reference_name: r.name, content: frappe.utils.escape_html(t).replace(/\n/g, "<br>"),
					comment_email: frappe.session.user, comment_by: frappe.session.user_fullname }).then(() => R.view(st, r.doctype, r.name)); }
		});
	}

	// ---------------------------------------------------------------- the designed form (edit and new)
	const NUM = ["Int", "Float", "Currency", "Percent"];
	const dep = (expr, doc, parent) => { if (!expr) return true; try { if (String(expr).startsWith("eval:")) return !!new Function("doc", "parent", "frappe", `return (${String(expr).slice(5)});`)(doc, parent || doc, frappe); return !!doc[expr]; } catch (e) { return true; } };
	const show = (f, doc, parent) => !f.hidden && dep(f.depends_on, doc, parent);
	const req = (f, doc, parent) => (f.reqd || (f.mandatory_depends_on && dep(f.mandatory_depends_on, doc, parent)));
	const ro = (f, doc, parent) => (f.read_only || (f.read_only_depends_on && dep(f.read_only_depends_on, doc, parent)) || !!f.fetch_from);

	function input(f, v, doc, parent, path) {
		const a = `data-f="${esc(f.fieldname)}" data-path="${esc(path)}"`;
		if (ro(f, doc, parent)) return `<div class="hr-ro">${v == null || v === "" ? "—" : NUM.includes(f.fieldtype) ? esc(format_number(v, null, f.fieldtype === "Int" ? 0 : 2))
			: f.fieldtype === "Check" ? (cint(v) ? __("Yes") : __("No")) : f.fieldtype === "Date" ? esc(frappe.datetime.str_to_user(v)) : f.fieldtype === "Datetime" ? esc(frappe.datetime.str_to_user(v))
			: f.fieldtype === "Select" ? esc(__(v)) : esc(v)}</div>`;
		switch (f.fieldtype) {
			case "Check": return `<label class="hr-switch"><input type="checkbox" ${a} ${cint(v) ? "checked" : ""}><span></span></label>`;
			case "Select": return `<select class="form-control" ${a}>${(f.opts || []).map((o) => `<option value="${esc(o)}" ${o === (v || "") ? "selected" : ""}>${esc(o ? __(o) : "—")}</option>`).join("")}</select>`;
			case "Small Text": case "Text": case "Long Text": case "Text Editor": return `<textarea class="form-control" rows="${f.fieldtype === "Small Text" ? 2 : 4}" ${a}>${esc(f.fieldtype === "Text Editor" ? $("<div>").html(v || "").text() : v || "")}</textarea>`;
			case "Date": return `<input type="date" class="form-control" ${a} value="${esc(v || "")}">`;
			case "Datetime": return `<input type="datetime-local" class="form-control" ${a} value="${esc((v || "").replace(" ", "T").slice(0, 16))}">`;
			case "Time": return `<input type="time" class="form-control" ${a} value="${esc((v || "").slice(0, 5))}">`;
			case "Int": case "Float": case "Currency": case "Percent": return `<input type="number" step="any" class="form-control text-right" ${a} value="${v == null ? "" : esc(v)}" ${f.non_negative ? 'min="0"' : ""}>`;
			case "Link": return `<div class="hr-link"><input class="form-control" ${a} data-link="${esc(f.options)}" value="${esc(v || "")}" autocomplete="off"><div class="hr-sug"></div></div>`;
			case "Dynamic Link": return `<div class="hr-link"><input class="form-control" ${a} data-dlink="${esc(f.options)}" value="${esc(v || "")}" autocomplete="off"><div class="hr-sug"></div></div>`;
			case "Attach": case "Attach Image": return `<div class="hr-att">${v ? `<a href="${esc(v)}" target="_blank" rel="noopener">${esc(String(v).split("/").pop())}</a>` : `<span class="hr-muted">${__("No file")}</span>`}<button class="btn btn-xs btn-default" data-up="${esc(f.fieldname)}" data-path="${esc(path)}">${v ? __("Replace") : __("Upload")}</button></div>`;
			case "Password": return `<input type="password" class="form-control" ${a} value="">`;
			default: return `<input class="form-control" ${a} value="${esc(v == null ? "" : v)}" ${f.length ? `maxlength="${f.length}"` : ""}>`;
		}
	}

	R.form = function (st, dt, name, values) {
		st.$body.html(`<div class="hsx-loading">${__("Loading…")}</div>`);
		const vals = Object.assign({}, values || {}); delete vals.__edit;
		frappe.xcall(API + "form", { doctype: dt, name: name || null, values: vals }).then((F) => {
			st.F = F; st.doc = F.doc; st.page.set_title(F.title); document.title = `${F.title} · ${F.label}`;
			render_form(st);
		});
	};

	function sections(fields) {
		const out = []; let cur = { label: "", cols: [[]] };
		out.push(cur);
		fields.forEach((f) => {
			if (f.fieldtype === "Section Break" || f.fieldtype === "Tab Break") { cur = { label: f.label || "", cols: [[]], f }; out.push(cur); return; }
			if (f.fieldtype === "Column Break") { cur.cols.push([]); return; }
			cur.cols[cur.cols.length - 1].push(f);
		});
		return out;
	}

	function render_form(st) {
		const F = st.F, doc = st.doc;
		const field_html = (f) => {
			if (!show(f, doc)) return "";
			if (f.fieldtype === "Table" || f.fieldtype === "Table MultiSelect") return grid(f, doc[f.fieldname] || []);
			const r = req(f, doc);
			return `<div class="hr-in ${["Small Text", "Text", "Long Text", "Text Editor"].includes(f.fieldtype) ? "wide" : ""} ${f.fieldtype === "Check" ? "chk" : ""}" data-wrap="${esc(f.fieldname)}">
				<label>${esc(f.label || f.fieldname)}${r ? ' <i class="hr-req">*</i>' : ""}</label>${input(f, doc[f.fieldname], doc, null, f.fieldname)}${f.description ? `<small>${esc(__(f.description))}</small>` : ""}</div>`;
		};
		const secs = sections(F.fields).map((s) => {
			const body = s.cols.map((c) => c.map(field_html).join("")).join("");
			if (!body.trim() || (s.f && !show(s.f, doc))) return "";
			const tables = /class="hr-grid-t/.test(body);
			return hipersign.ui.card(s.label || (tables ? "" : __("Details")), `<div class="hr-fgrid">${body}</div>`);
		}).join("");
		st.$body.html(`<div class="hr-head"><button class="hr-back" data-hf="back" title="${__("Back")}">${ic("left")}</button><div class="hr-h"><div class="hr-kick">${esc(F.label)}${F.name ? " · " + esc(F.name) : ""}</div>
			<h2>${esc(F.title)} ${F.is_new ? pill(__("Not saved"), "orange") : pill(__("Editing"), "blue")}</h2></div></div>
			<div class="hr-form">${secs}</div>
			<div class="hr-bar"><span class="hr-muted">${F.is_new ? __("Fill in the fields with * and save.") : __("Changes are saved when you press Save.")}</span>
				<button class="btn btn-default" data-hf="discard">${__("Discard")}</button>${F.submittable ? `<button class="btn btn-default" data-hf="save_submit">${__("Save & submit")}</button>` : ""}<button class="btn btn-primary" data-hf="save">${__("Save")}</button></div>`);
		wire_form(st);
	}

	function grid(f, rows) {
		const cols = (f.cols || []).map((c) => f.child.find((x) => x.fieldname === c)).filter(Boolean);
		return `<div class="hr-in wide hr-grid-t" data-wrap="${esc(f.fieldname)}"><label>${esc(f.label)} <small>${rows.length}</small></label><div class="hsx-tw"><table class="hsx-t hr-et"><thead><tr><th class="hr-n">#</th>
			${cols.map((c) => `<th class="${NUM.includes(c.fieldtype) ? "text-right" : ""}">${esc(c.label)}${c.reqd ? ' <i class="hr-req">*</i>' : ""}</th>`).join("")}<th></th></tr></thead>
			<tbody>${rows.map((row, i) => `<tr><td class="hr-n">${i + 1}</td>${cols.map((c) => `<td>${input(c, row[c.fieldname], row, row, `${f.fieldname}.${i}.${c.fieldname}`)}</td>`).join("")}
				<td class="hr-ra"><button class="btn btn-xs btn-default" data-row="${esc(f.fieldname)}" data-i="${i}" title="${__("All fields")}">${ic("edit")}</button><button class="btn btn-xs btn-default" data-del="${esc(f.fieldname)}" data-i="${i}" title="${__("Remove")}">${ic("delete")}</button></td></tr>`).join("")}</tbody></table></div>
			<button class="btn btn-xs btn-default hr-add" data-add="${esc(f.fieldname)}">${ic("add")} ${__("Add a line")}</button></div>`;
	}

	function setv(st, path, v) {
		const p = path.split(".");
		if (p.length === 1) st.doc[p[0]] = v; else st.doc[p[0]][+p[1]][p[2]] = v;
	}
	const field_of = (st, path) => { const p = path.split("."), f = st.F.fields.find((x) => x.fieldname === p[0]); return p.length === 1 ? f : f.child.find((x) => x.fieldname === p[2]); };

	function wire_form(st) {
		const $b = st.$body, F = st.F;
		const rerender = frappe.utils.debounce(() => { const y = window.scrollY; render_form(st); window.scrollTo(0, y); }, 50);
		$b.off("change.hf input.hf click.hf focusin.hf");
		$b.on("change.hf", "[data-path]", function () {
			const path = $(this).attr("data-path"), f = field_of(st, path);
			let v = this.type === "checkbox" ? (this.checked ? 1 : 0) : $(this).val();
			if (f && NUM.includes(f.fieldtype)) v = v === "" ? null : f.fieldtype === "Int" ? cint(v) : flt(v);
			if (f && f.fieldtype === "Datetime" && v) v = v.replace("T", " ") + ":00";
			setv(st, path, v);
			// fields shown only for some values: draw again when a field others depend on changes
			if (F.fields.some((x) => (x.depends_on || x.mandatory_depends_on || x.read_only_depends_on || "").includes(path.split(".").pop()))) rerender();
		});
		// link search
		let timer = null;
		$b.on("input.hf focusin.hf", "[data-link],[data-dlink]", function () {
			const $i = $(this), $s = $i.siblings(".hr-sug");
			const dt = $i.attr("data-link") || st.doc[$i.attr("data-dlink")];
			if (!dt) return;
			clearTimeout(timer);
			const fd = field_of(st, $i.attr("data-path")), filters = fd && fd.filters ? JSON.stringify(fd.filters) : undefined;
			timer = setTimeout(() => frappe.xcall("frappe.desk.search.search_link", { doctype: dt, txt: $i.val() || "", page_length: 10, filters }).then((res) => {
				$s.html((res || []).map((o) => `<a data-v="${esc(o.value)}"><b>${esc(o.label || o.value)}</b>${o.description ? `<small>${esc(o.description)}</small>` : ""}</a>`).join("") || `<span>${__("Nothing found")}</span>`).addClass("on");
			}), 180);
		});
		$b.on("click.hf", ".hr-sug a", function () { const $i = $(this).closest(".hr-link").find("input"); $i.val($(this).attr("data-v")).trigger("change"); $(this).parent().removeClass("on"); });
		$(document).off("click.hrsug").on("click.hrsug", (e) => { if (!$(e.target).closest(".hr-link").length) $b.find(".hr-sug").removeClass("on"); });
		$b.on("click.hf", "[data-add]", function () { const k = $(this).attr("data-add"); st.doc[k] = st.doc[k] || []; st.doc[k].push({ doctype: F.fields.find((x) => x.fieldname === k).options, __islocal: 1 }); rerender(); });
		$b.on("click.hf", "[data-del]", function () { st.doc[$(this).attr("data-del")].splice(+$(this).attr("data-i"), 1); rerender(); });
		$b.on("click.hf", "[data-row]", function () { row_sheet(st, $(this).attr("data-row"), +$(this).attr("data-i"), rerender); });
		$b.on("click.hf", "[data-up]", function () { const path = $(this).attr("data-path");
			new frappe.ui.FileUploader({ doctype: F.doctype, docname: F.name || undefined, allow_multiple: false, on_success: (file) => { setv(st, path, file.file_url); rerender(); } }); });
		$b.on("click.hf", "[data-hf]", function () {
			const k = $(this).attr("data-hf");
			if (k === "back" || k === "discard") return F.name ? R.view(st, F.doctype, F.name) : (window.history.length > 2 ? window.history.back() : frappe.set_route("hipersign-home"));
			if (k === "save" || k === "save_submit") save(st, k === "save_submit");
		});
	}

	function row_sheet(st, table, i, done) {
		const f = st.F.fields.find((x) => x.fieldname === table), row = st.doc[table][i];
		const d = new frappe.ui.Dialog({ title: `${f.label} — ${__("line {0}", [i + 1])}`, size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "b" }], primary_action_label: __("Done"), primary_action() { d.hide(); done(); } });
		d.fields_dict.b.$wrapper.html(`<div class="hr-fgrid hr-rowform">${f.child.filter((c) => !["Section Break", "Column Break", "Tab Break"].includes(c.fieldtype) && show(c, row, st.doc)).map((c) =>
			`<div class="hr-in ${["Small Text", "Text", "Long Text"].includes(c.fieldtype) ? "wide" : ""}"><label>${esc(c.label || c.fieldname)}${req(c, row, st.doc) ? ' <i class="hr-req">*</i>' : ""}</label>${input(c, row[c.fieldname], row, st.doc, `${table}.${i}.${c.fieldname}`)}</div>`).join("")}</div>`);
		d.$wrapper.on("change", "[data-path]", function () { const path = $(this).attr("data-path"), c = field_of(st, path);
			let v = this.type === "checkbox" ? (this.checked ? 1 : 0) : $(this).val(); if (c && NUM.includes(c.fieldtype)) v = v === "" ? null : flt(v); setv(st, path, v); });
		d.show();
	}

	function missing(st) {
		const out = [];
		st.F.fields.forEach((f) => {
			if (["Section Break", "Column Break", "Tab Break"].includes(f.fieldtype) || !show(f, st.doc) || ro(f, st.doc)) return;
			if (f.fieldtype === "Table") (st.doc[f.fieldname] || []).forEach((row, i) => f.child.forEach((c) => { if (req(c, row, st.doc) && !ro(c, row, st.doc) && (row[c.fieldname] == null || row[c.fieldname] === "")) out.push(`${f.label} ${i + 1}: ${c.label}`); }));
			else if (req(f, st.doc) && (st.doc[f.fieldname] == null || st.doc[f.fieldname] === "")) out.push(f.label);
		});
		return out;
	}

	function save(st, submit) {
		const miss = missing(st);
		if (miss.length) return frappe.msgprint({ title: __("Fill these in first"), message: `<ul>${miss.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>`, indicator: "orange" });
		const doc = Object.assign({}, st.doc, { doctype: st.F.doctype });
		const call = st.F.is_new ? frappe.xcall("frappe.client.insert", { doc }) : frappe.xcall("frappe.client.save", { doc });
		call.then((saved) => (submit ? frappe.xcall("frappe.client.submit", { doc: saved }) : saved)).then((saved) => {
			frappe.show_alert({ message: submit ? __("Saved and submitted") : __("Saved"), indicator: "green" });
			if (st.F.is_new) frappe.set_route("Form", st.F.doctype, saved.name); else R.view(st, st.F.doctype, saved.name);
		});
	}

	// ---------------------------------------------------------------- every way into a construction record lands here
	// The router turns /app/ra-bill/RA-26-0090 (from a button, a link, a list row, a typed address or the back button) into
	// ["Form", "RA Bill", "RA-26-0090"]; for these record types it shows the record page instead — the address stays the same.
	const patch = () => {
		if (frappe.router && frappe.router.parse && !frappe.router.parse.__hr) {
			const parse = frappe.router.parse;
			frappe.router.parse = async function () {
				const r = await parse.apply(this, arguments);
				if (r && r[0] === "Form" && r[1] && r[2] && R.has(r[1]) && !(R.view_only(r[1]) && String(r[2]).startsWith("new-"))) return ["hipersign-record", r[1], r.slice(2).join("/")];
				return r;
			};
			frappe.router.parse.__hr = true;
		}
		if (frappe.new_doc && !frappe.new_doc.__hr) {
			const nd = frappe.new_doc;
			frappe.new_doc = function (dt, opts) { if (R.has(dt) && !R.view_only(dt)) return R.new(dt, opts && typeof opts === "object" ? opts : {}); return nd.apply(this, arguments); };
			frappe.new_doc.__hr = true;
		}
		if (hipersign.fm && hipersign.fm.new && !hipersign.fm.new.__hr) {
			const fn = hipersign.fm.new;
			hipersign.fm.new = function (dt, v) { if (R.has(dt) && !R.view_only(dt)) return R.new(dt, v || {}); return fn.apply(this, arguments); };
			hipersign.fm.new.__hr = true;
		}
	};
	patch();
	$(document).on("app_ready", patch);
})();
