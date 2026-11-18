import frappe
USERS = [("qs@hci.test", "Deepa", ["Quantity Surveyor", "Projects User"]), ("se@hci.test", "Vishnu", ["Site Engineer", "Projects User"]),
    ("acc@hci.test", "Accounts", ["Accounts User"]), ("md@hci.test", "Arjun", ["Managing Director"]), ("view@hci.test", "Viewer", ["Demo Viewer"]), ("bd@hci.test", "Arjun", ["BD Manager"]), ("qa@hci.test", "Ancy", ["QA/QC Engineer"]), ("so@hci.test", "Sajith", ["Safety Officer"]), ("dc@hci.test", "Doc", ["Document Controller"]), ("sk@hci.test", "Biju", ["Storekeeper"]), ("hr@hci.test", "Reshma", ["HR & Admin"]), ("pl@hci.test", "Plant", ["Plant Manager"])]
def setup():
    for email, first, roles in USERS:
        if not frappe.db.exists("User", email):
            u = frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "send_welcome_email": 0, "roles": [{"role": r} for r in roles]})
            u.insert(ignore_permissions=True)
    frappe.db.commit()
def check():
    from hipersign_trading.api.module import get_module, get_rows
    from hipersign_trading.api import module_cn
    from hipersign_trading.api.construction import act
    for email, first, roles in USERS:
        frappe.set_user(email); bad = []
        for key in module_cn.KEYS:
            try:
                m = get_module(key)
                for t in m["tabs"]:
                    get_rows(key, t["key"], (t["chips"] or [[None]])[0][0])
            except Exception as e:
                bad.append(f"{key}: {e!r}"[:160])
        # actions each role should / should not do
        res = {}
        mb = frappe.db.get_value("Measurement Book", {"status": "Draft"})
        for a, n in (("mb_qs", mb), ("ra_26as", frappe.db.get_value("RA Bill", {"status": "Paid", "tds_in_26as": 1})), ("tnd_bid", frappe.db.get_value("Tender", {"status": "Bid / no-bid"})),
                     ("qt_approve", frappe.db.get_value("Quotation", {"hs_cn_approval": "Pending"})), ("fup_log", frappe.db.get_value("RA Bill", {"status": "Invoiced"}))):
            frappe.db.savepoint("x")
            try:
                act(a, n, "{}"); res[a] = "ok"
            except Exception as e:
                res[a] = type(e).__name__
            frappe.db.rollback(save_point="x")
        print(email, roles, "pages:", "OK" if not bad else bad, res)
    frappe.set_user("Administrator")
