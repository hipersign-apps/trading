import frappe
def run():
    frappe.flags.hs_force_demo = True
    from hipersign_trading.demo import cn_india, run as r, LOG
    LOG.clear(); r(cn_india.cn_measurements, frappe._dict()); frappe.db.commit(); print(LOG)
    print(frappe.db.sql("select name, qty, status, over_boq from `tabMeasurement Book` where project='P-2401' and item_no='1.1'"))
