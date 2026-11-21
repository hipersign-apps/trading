// Subcontractor Portal — Construction (India) controls, portals & apps (v1.9.0 A6): see public/js/hs_module.js and api/module_cn_portal.py.
frappe.pages["hipersign-cn-partner-portal"].on_page_load = function (wrapper) {
	hipersign.module.render(wrapper, "cn_spo");
};
frappe.pages["hipersign-cn-partner-portal"].on_page_show = function (wrapper) {
	if (wrapper.hs_reload && wrapper.hs_loaded_once) wrapper.hs_reload();
	wrapper.hs_loaded_once = true;
};
