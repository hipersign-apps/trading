import frappe
from frappe.utils import today, add_days
def A(_action, name, user=None, **args):
    action = _action
    from hipersign_trading.api.construction import act
    if user: frappe.set_user(user)
    try:
        r = act(action, name, frappe.as_json(args)); print(" ", user or "", action, name, "→", r.get("message")); return r
    except Exception as e:
        print(" ", user or "", action, name, "✗", type(e).__name__, frappe.utils.strip_html(str(e))[:140]); frappe.clear_messages(); return None
def U(email, roles):
    if not frappe.db.exists("User", email):
        frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0, "roles": [{"role": r} for r in roles]}).insert(ignore_permissions=True)
def run():
    for e, r in (("qa@hci.test", ["QA/QC Engineer"]), ("so@hci.test", ["Safety Officer"]), ("dc@hci.test", ["Document Controller"]), ("pm@hci.test", ["Project Manager"]),
                 ("se@hci.test", ["Site Engineer"]), ("acc@hci.test", ["Accounts User"])):
        U(e, r)
    frappe.db.commit()
    ir = frappe.get_all("Inspection Request", filters={"status": "Requested"}, pluck="name")
    A("ir_approve", ir[0], "se@hci.test"); A("ir_approve", ir[0], "qa@hci.test")
    r = A("ir_reject", ir[1], "qa@hci.test", note="Shuttering props not braced")
    nc = frappe.get_all("NCR", filters={"status": "Open"}, pluck="name")[0]
    A("ncr_close", nc, "qa@hci.test")
    A("ncr_close", nc, "qa@hci.test", root_cause="Vibrator not used at the wall base", corrective_action="Two vibrators per pour; QA witness", rework_cost=42000)
    frappe.set_user("Administrator")
    try:
        frappe.get_doc({"doctype": "Cube Test", "project": "P-2401", "pour": "Test", "grade": "M25", "cast_on": add_days(today(), -3), "s7_1": 20}).insert(); print("  cube accepted?!")
    except Exception as ex: print("  cube refused:", str(ex)[:80]); frappe.clear_messages()
    c = frappe.get_doc({"doctype": "Cube Test", "project": "P-2401", "pour": "Test 2", "grade": "M25", "cast_on": add_days(today(), -30), "s28_1": 29, "s28_2": 30, "s28_3": 27}); c.insert()
    print("  cube result:", c.avg28, c.result)
    p = frappe.get_all("Work Permit", filters={"status": "Requested"}, pluck="name")[0]
    A("ptw_issue", p, "pm@hci.test"); A("ptw_issue", p, "so@hci.test"); A("ptw_close", p, "se@hci.test")
    frappe.set_user("so@hci.test")
    from hipersign_trading.api import approvals
    print("  approvals for SO:", [(i["type"], i["name"]) for i in approvals.pending(mine=True)])
    inc = frappe.get_all("Safety Incident", filters={"status": "Open", "kind": "Property damage"}, pluck="name")[0]
    A("inc_close", inc, "so@hci.test"); A("inc_close", inc, "so@hci.test", root_cause="No banksman while reversing", action="Banksman for every reversing tipper")
    d = frappe.get_all("Construction Drawing", filters={"status": "For approval", "project": "P-2401"}, fields=["name", "drawing_no"])[0]
    frappe.set_user("Administrator")
    n = frappe.get_doc({"doctype": "Construction Drawing", "project": "P-2401", "drawing_no": d.drawing_no, "revision": "R1", "title": "rev", "discipline": "Structural"}); n.insert()
    try:
        frappe.get_doc({"doctype": "Construction Drawing", "project": "P-2401", "drawing_no": d.drawing_no.lower(), "revision": "r1", "title": "dup"}).insert(); print("  dup accepted?!")
    except Exception as ex: print("  duplicate refused:", str(ex)[:70]); frappe.clear_messages()
    A("drg_gfc", n.name, "dc@hci.test")
    print("  old rev:", frappe.db.get_value("Construction Drawing", d.name, ["status", "superseded_by"]))
    rf = frappe.get_all("RFI", filters={"status": "Open"}, pluck="name")[0]
    A("rfi_answer", rf, "dc@hci.test", answer="Use couplers instead of laps at C-4"); A("rfi_close", rf, "dc@hci.test")
    t = frappe.get_all("Transmittal", filters={"status": "Sent"}, pluck="name")[0]; A("trn_ack", t, "dc@hci.test")
    s = frappe.get_all("Snag", filters={"status": "Open"}, pluck="name")[0]
    A("snag_verify", s, "pm@hci.test"); A("snag_fixed", s, "se@hci.test"); A("snag_verify", s, "pm@hci.test")
    h = frappe.get_all("Handover Document", filters={"status": "Applied"}, pluck="name")[0]; A("hdoc", h, "pm@hci.test")
    df = frappe.get_all("DLP Defect", filters={"status": "Reported"}, pluck="name", order_by="reported_on asc")[0]
    A("def_respond", df, "se@hci.test"); A("def_rectify", df, "se@hci.test", cost=6500)
    from hipersign_trading.api import construction_qhse as Q
    x = Q.dlp("P-2408"); print("  P-2408 DLP:", x.end, round(x.retention), round(x.release_now), x.pbg_ok)
    A("ret_release", "P-2408", "se@hci.test"); A("ret_release", "P-2408", "acc@hci.test"); A("ret_release", "P-2408", "acc@hci.test", amount=99999999)
    x = Q.dlp("P-2408"); print("  after:", round(x.released), round(x.held), round(x.release_now))
    for p in ("P-2401", "P-2402", "P-2403", "P-2406", "P-2408"):
        print(" ", p, [f["text"] for f in Q.flags(p)])
    frappe.db.commit()
