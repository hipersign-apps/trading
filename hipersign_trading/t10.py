import frappe
from frappe.utils import flt
def A(action, name, **args):
    from hipersign_trading.api.construction import act
    r = act(action, name, frappe.as_json(args)); print(" ", action, name, "→", r.get("message")); return r
def run():
    if not frappe.db.exists("User", "bd@hci.test"):
        frappe.get_doc({"doctype": "User", "email": "bd@hci.test", "first_name": "Arjun", "send_welcome_email": 0, "roles": [{"role": "BD Manager"}]}).insert(ignore_permissions=True)
    if not frappe.db.exists("User", "md@hci.test"):
        frappe.get_doc({"doctype": "User", "email": "md@hci.test", "first_name": "Shihab", "send_welcome_email": 0, "roles": [{"role": "Managing Director"}]}).insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.set_user("bd@hci.test")
    opp = frappe.get_all("Opportunity", filters={"title": ["like", "Karaikudi%"]}, pluck="name")[0]
    A("opp_stage", opp)
    q = A("opp_quote", opp)["open"][1]
    d = frappe.get_doc("Quotation", q); print("  quote", d.base_net_total, d.hs_cn_cost, round(d.hs_estimated_margin, 1), d.hs_cn_approval, d.company_address)
    A("qt_send", q)
    r = A("qt_revise", q, reason="Client wants marble in the lobby — price up, 7% special discount")
    q2 = r["open"][1]
    d = frappe.get_doc("Quotation", q2); d.items[0].rate = flt(d.items[0].rate) * 1.05; d.hs_cn_list_value = flt(d.items[0].rate) / 0.93; d.save()
    print("  rev", d.name, d.hs_cn_revision, d.hs_cn_revision_of, round(d.hs_cn_discount_pct, 1), d.hs_cn_approval)
    try:
        A("qt_send", q2)
    except Exception as e:
        print("  send refused:", str(e)[:120])
    try:
        A("qt_approve", q2)
    except Exception as e:
        print("  BD cannot approve:", type(e).__name__)
    frappe.set_user("md@hci.test")
    A("qt_approve", q2)
    aluva = frappe.get_all("Quotation", filters={"hs_cn_approval": "Pending"}, pluck="name")
    for x in aluva: A("qt_reject", x, note="Margin under 10% — rework steel rates")
    frappe.set_user("bd@hci.test")
    A("qt_send", q2)
    r = A("qt_accept", q2, loa_no="LOA/CHR/2026/04", start="2026-12-10", months=14)
    pj = r["open"][1]
    print("  project", frappe.db.get_value("Project", pj, ["hs_cn", "hs_contract_value", "hs_step"]), frappe.db.count("Project BOQ", {"project": pj}),
          frappe.db.get_value("Construction Contract", {"project": pj}, ["loa_no", "original_value", "completion_date"]),
          frappe.db.get_value("Opportunity", opp, ["status", "hs_cn_project"]))
    o2 = frappe.get_all("Opportunity", filters={"title": ["like", "Technopark Phase IV — Food%"]}, pluck="name")[0]
    A("opp_lost", o2, reason="Project shelved by client", note="Budget moved to next year")
    A("opp_followed", frappe.get_all("Opportunity", filters={"title": ["like", "Skyline Residency Phase 2%"]}, pluck="name")[0], note="Call fixed", date="2026-12-01")
    frappe.set_user("md@hci.test")
    from hipersign_trading.api import construction_biz as B
    before = B.ld("P-2401")
    c = frappe.get_all("Contract Claim", filters={"status": "Under negotiation", "project": "P-2401"}, pluck="name")[0]
    A("clm_award", c, days=14, amount=0)
    after = B.ld("P-2401")
    print("  P-2401 LD", round(before.amount), before.delay, "→", round(after.amount), after.delay, frappe.db.get_value("Construction Contract", {"project": "P-2401"}, ["eot_days", "extended_completion"]))
    d = frappe.get_all("Contract Claim", filters={"status": "Draft"}, pluck="name")[0]
    A("clm_submit", d); A("clm_negotiate", d); A("clm_award", d, days=0, amount=300000)
    print("  revised P-2401", frappe.db.get_value("Project", "P-2401", "hs_revised_contract"), frappe.db.get_value("Construction Contract", {"project": "P-2401"}, ["claims_awarded", "revised_value"]))
    rb = frappe.get_all("RA Bill", filters={"project": "P-2403", "status": "Invoiced"}, pluck="name", order_by="bill_no desc")[0]
    A("fup_log", rb, note="MD letter sent to the Chief Engineer", promised_date="2026-11-28")
    from hipersign_trading.api import construction as CN
    CN.clear_cache()
    for p in ("P-2401", "P-2402", "P-2403"):
        print(" ", p, [f["text"] for f in CN.flags(p)])
    frappe.db.commit()
