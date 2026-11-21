// Subcontractors — Construction (India) site resources (v1.9.0 A3): see public/js/hs_module.js and api/module_cn_site.py.
frappe.pages["hipersign-cn-subcon"].on_page_load = function (wrapper) {
	hipersign.module.render(wrapper, "cn_sub");
};
frappe.pages["hipersign-cn-subcon"].on_page_show = function (wrapper) {
	if (wrapper.hs_reload && wrapper.hs_loaded_once) wrapper.hs_reload();
	wrapper.hs_loaded_once = true;
};
