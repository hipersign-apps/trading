// Safety (HSE) — Construction (India) quality, safety & handover (v1.9.0 A4): see public/js/hs_module.js and api/module_cn_qhse.py.
frappe.pages["hipersign-cn-safety"].on_page_load = function (wrapper) {
	hipersign.module.render(wrapper, "cn_hse");
};
frappe.pages["hipersign-cn-safety"].on_page_show = function (wrapper) {
	if (wrapper.hs_reload && wrapper.hs_loaded_once) wrapper.hs_reload();
	wrapper.hs_loaded_once = true;
};
