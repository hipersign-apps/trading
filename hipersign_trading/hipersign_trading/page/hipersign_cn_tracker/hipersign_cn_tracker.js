// Construction Tracker — every Construction (India) contract through the 26 steps (v1.9.1 B2): see public/js/hs_construction.js.
frappe.pages["hipersign-cn-tracker"].on_page_load = function (wrapper) {
	hipersign.cn.tracker(wrapper);
};
frappe.pages["hipersign-cn-tracker"].on_page_show = function (wrapper) {
	if (wrapper.hs_reload && wrapper.hs_loaded_once) wrapper.hs_reload();
	wrapper.hs_loaded_once = true;
	$(".popover").remove();
};
