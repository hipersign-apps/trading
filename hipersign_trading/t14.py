import frappe
from frappe.utils import flt, add_days, today
def A(action, name, user=None, **args):
    from hipersign_trading.api.construction import act
    if user: frappe.set_user(user)
    try:
        r = act(action, name, frappe.as_json(args)); print(" ", user or "", action, name, "→", r.get("message")); return r
    except Exception as e:
        print(" ", user or "", action, name, "✗", type(e).__name__, frappe.utils.strip_html(str(e))[:150]); frappe.clear_messages(); return None
def U(email, roles):
    if not frappe.db.exists("User", email):
        frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0, "roles": [{"role": r} for r in roles]}).insert(ignore_permissions=True)
def run():
    for e, r in (("pm@hci.test", ["Project Manager"]), ("sk@hci.test", ["Storekeeper"]), ("se@hci.test", ["Site Engineer"]), ("acc@hci.test", ["Accounts User"]), ("md@hci.test", ["Managing Director"])):
        U(e, r)
    frappe.db.commit()
    from hipersign_trading.api import construction_site as S
    over = frappe.get_all("Material Request", filters={"hs_over_boq": 1, "docstatus": 0}, pluck="name")[0]
    print("  over-need indent:", frappe.db.get_value("Material Request", over, "hs_rejected_lines"))
    A("ind_approve", over, "se@hci.test"); A("ind_approve", over, "pm@hci.test")
    mr = frappe.db.get_value("Supplier Quotation Item", {"docstatus": 1}, "material_request")
    print("  comparison:", [(q.supplier[:20], q.base_net_total, q.hs_landed_total, q.hs_tech_ok) for q in S.comparison(mr)])
    A("po_l1", mr, "pm@hci.test")
    pr = frappe.db.sql("select name from `tabPurchase Receipt` where docstatus=1 and per_billed < 100 order by posting_date desc limit 1")[0][0]
    A("grn_bill", pr, "acc@hci.test")
    req = frappe.get_all("Stock Entry", filters={"hs_transfer_status": "Requested", "docstatus": 0}, pluck="name")[0]
    A("trf_dispatch", req, "sk@hci.test")
    frappe.set_user("Administrator"); frappe.db.set_value("Stock Entry", req, {"hs_vehicle": "KL-07-CB-9001", "hs_driver": "Sathyan K"})
    A("trf_dispatch", req, "sk@hci.test"); A("trf_deliver", req, "se@hci.test")
    print("  stock at P-2406 site:", frappe.db.get_value("Bin", {"warehouse": frappe.db.get_value("Project", "P-2406", "hs_site_warehouse"), "item_code": "TMT-FE500D"}, "actual_qty"))
    sw = frappe.get_all("Subcontractor Work Order", filters={"status": "Draft"}, pluck="name")[0]
    A("swo_activate", sw, "pm@hci.test")
    cert = frappe.get_all("Subcontractor Bill", filters={"status": "Certified"}, fields=["name", "project", "compliance_hold"])
    print("  certified bills:", cert)
    for b in cert:
        A("sub_approve", b.name, "pm@hci.test"); A("sub_pay", b.name, "acc@hci.test")
        if b.compliance_hold:
            lc = frappe.get_all("Labour Compliance", filters={"status": "Missing"}, pluck="name")[0]
            A("lc_mark", lc, "acc@hci.test"); A("sub_pay", b.name, "acc@hci.test")
    pi = frappe.get_doc("Purchase Invoice", frappe.db.get_value("Subcontractor Bill", cert[0].name, "purchase_invoice"))
    print("  sub PI:", pi.grand_total, [(t.account_head, t.add_deduct_tax, t.tax_amount) for t in pi.taxes])
    for m in frappe.get_all("Weekly Muster", filters={"status": "Draft"}, pluck="name")[:2]:
        A("mus_approve", m, "se@hci.test"); A("mus_approve", m, "pm@hci.test"); A("mus_pay", m, "acc@hci.test")
    big = frappe.db.get_value("Worker Advance", {"status": "Requested", "amount": [">", 5000]})
    A("adv_approve", big, "se@hci.test"); A("adv_approve", big, "pm@hci.test"); A("adv_pay", big, "acc@hci.test")
    e = frappe.db.get_value("Construction Equipment", {"status": "Breakdown"})
    A("eq_status", e, "se@hci.test", status="Working")
    frappe.set_user("Administrator")
    eq = frappe.db.get_value("Construction Equipment", {"equipment_name": ["like", "Tower crane%"]}, ["name", "last_hmr"], as_dict=True)
    for start in (eq.last_hmr - 5, eq.last_hmr):
        try:
            frappe.get_doc({"doctype": "Equipment Log", "equipment": eq.name, "project": "P-2401", "log_date": today(), "start_hmr": start, "end_hmr": start + 8}).insert(); print("  log ok from", start)
        except Exception as ex: print("  log refused:", str(ex)[:90]); frappe.clear_messages()
    try:
        frappe.get_doc({"doctype": "Site Worker", "worker_name": "Test Low", "project": "P-2401", "trade": "Helper", "skill": "Unskilled", "state": "Kerala", "daily_rate": 500, "upi_id": "x@ok"}).insert()
    except Exception as ex: print("  worker refused:", str(ex)[:110]); frappe.clear_messages()
    for x in S.material_status("P-2401"):
        print("  ", x.item, round(x.theory), round(x.issued), f"{x.excess_pct:+.1f}%", round(x.excess_value), round(x.remaining))
    from hipersign_trading.api import construction as CN
    CN.clear_cache()
    for p in ("P-2401", "P-2405", "P-2403"): print(" ", p, [f["text"] for f in S.flags(p)])
    frappe.db.commit()
