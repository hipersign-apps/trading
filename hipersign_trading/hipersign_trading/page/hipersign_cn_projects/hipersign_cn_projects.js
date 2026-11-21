// Construction Projects — Construction (India) (v1.9.0, prototype C11): see public/js/hs_module.js and api/module_cn.py.
frappe.pages["hipersign-cn-projects"].on_page_load = function (wrapper) {
	hipersign.module.render(wrapper, "cn_home");
};
frappe.pages["hipersign-cn-projects"].on_page_show = function (wrapper) {
	if (wrapper.hs_reload && wrapper.hs_loaded_once) wrapper.hs_reload();
	wrapper.hs_loaded_once = true;
};
