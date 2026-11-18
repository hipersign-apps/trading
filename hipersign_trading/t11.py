import frappe
def run():
    frappe.set_user("bd@hci.test")
    from hipersign_trading.api.construction import act
    opp = frappe.get_all("Opportunity", filters={"title": ["like", "Skyline Residency Phase 2%"]}, pluck="name")[0]
    r = act("opp_quote", opp, "{}"); q = frappe.get_doc("Quotation", r["open"][1])
    print(q.company_address, q.taxes_and_charges, [(t.account_head, t.tax_amount) for t in q.taxes])
    print(frappe.db.get_value("Project", "PRJ-2026-001", "hs_cn_address"))
    frappe.db.rollback()
