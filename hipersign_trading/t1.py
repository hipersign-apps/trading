import frappe
def run():
    frappe.flags.hs_force_demo = True
    from hipersign_trading.demo import cn_india, run as r, LOG
    LOG.clear(); r(cn_india.cn_bonds, frappe._dict()); frappe.db.commit(); print(LOG, frappe.db.count("Bank Guarantee"))
