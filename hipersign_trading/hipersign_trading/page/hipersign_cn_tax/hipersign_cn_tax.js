// GST & TDS — Construction (India) finance & tax (v1.9.0 A5): see public/js/hs_module.js and api/module_cn_fin.py.
frappe.pages["hipersign-cn-tax"].on_page_load = function (wrapper) {
	hipersign.module.render(wrapper, "cn_tax");
};
frappe.pages["hipersign-cn-tax"].on_page_show = function (wrapper) {
	if (wrapper.hs_reload && wrapper.hs_loaded_once) wrapper.hs_reload();
	wrapper.hs_loaded_once = true;
};
