// Quotations & Sales — Construction (India) business (v1.9.0 A2, prototype C5): see public/js/hs_module.js and api/module_cn_biz.py.
frappe.pages["hipersign-cn-sales"].on_page_load = function (wrapper) {
	hipersign.module.render(wrapper, "cn_sales");
};
frappe.pages["hipersign-cn-sales"].on_page_show = function (wrapper) {
	if (wrapper.hs_reload && wrapper.hs_loaded_once) wrapper.hs_reload();
	wrapper.hs_loaded_once = true;
};
