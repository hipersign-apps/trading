import frappe
def run():
    from hipersign_trading.api.module import get_module, get_rows
    for k in ("pj_home", "pj_boq", "pj_bill", "sales", "finance", "stock"):
        m = get_module(k); print(k, "ok", len(m.get("tabs") or []))
    from hipersign_trading.api import projects as P
    print("UAE project list excludes India:", P.project_names())
    from hipersign_trading import features
    s = frappe.get_doc("Hipersign Settings"); print("pack_of:", features.pack_of(s))
