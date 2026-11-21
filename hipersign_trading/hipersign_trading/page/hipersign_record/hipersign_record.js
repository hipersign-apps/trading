// v1.9.2 U3: the Hipersign record page — see public/js/hs_record.js (every Construction (India) record opens here)
frappe.pages["hipersign-record"].on_page_load = function (wrapper) {
	hipersign.record.load(wrapper);
};
frappe.pages["hipersign-record"].on_page_show = function (wrapper) {
	hipersign.record.show(wrapper);
};
