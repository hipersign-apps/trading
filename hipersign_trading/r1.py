import frappe
def run(step):
    frappe.flags.hs_force_demo = True; frappe.flags.hs_skip_doc_rules = True; frappe.flags.mute_emails = True
    from hipersign_trading.demo import cn_india, run as r, LOG
    LOG.clear(); r(getattr(cn_india, step), frappe._dict()); frappe.db.commit(); print(LOG)
    print(frappe.db.sql("select substr(error, -600) from `tabError Log` order by creation desc limit 1") if "✗" in LOG[0] else "")
