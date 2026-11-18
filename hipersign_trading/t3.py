import frappe
from frappe.utils import flt
def A(action, name, **args):
    from hipersign_trading.api.construction import act
    r = act(action, name, frappe.as_json(args)); print(" ", action, name, "→", r.get("message")); return r
def run():
    frappe.set_user("Administrator")
    # tender to award
    t = "TND-2611-024"
    A("tnd_bid", t)
    frappe.db.set_value("Tender", t, {"our_bid": 12.3e7, "customer": "Kochi Water Metro Ltd. (fictional)"})
    A("tnd_submit", t); A("tnd_next", t); A("tnd_next", t); A("tnd_next", t)
    r = A("tnd_award", t); pj = r["open"][1]
    print("  project", pj, frappe.db.get_value("Project", pj, ["hs_cn", "hs_contract_value", "hs_step", "hs_cn_govt"]))
    # measurement: draft -> qs -> client
    m = frappe.get_all("Measurement Book", filters={"status": "Draft"}, pluck="name", limit=1)[0]
    A("mb_qs", m); A("mb_client", m)
    # P-2406: certify with a cut, invoice, receive, 26AS
    ra = frappe.get_all("RA Bill", filters={"project": "P-2406", "status": "Submitted to client"}, pluck="name")[0]
    c = frappe.db.get_value("RA Bill", ra, "claimed_amount")
    A("ra_certify", ra, amount=flt(c) - 50000)
    r = A("ra_invoice", ra); si = frappe.get_doc("Sales Invoice", r["open"][1])
    print("  SI", si.name, si.grand_total, si.company_gstin, si.place_of_supply, [(x.account_head, x.tax_amount) for x in si.taxes])
    r = A("ra_receive", ra); pe = frappe.get_doc("Payment Entry", r["open"][1])
    print("  PE", pe.paid_amount, [(d.account, d.amount) for d in pe.deductions], pe.unallocated_amount, frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount"))
    A("ra_26as", ra)
    # P-2405 (Karnataka branch) bill
    ra = frappe.get_all("RA Bill", filters={"project": "P-2405", "status": "Invoiced"}, pluck="name")[0]
    si = frappe.get_doc("Sales Invoice", frappe.db.get_value("RA Bill", ra, "sales_invoice"))
    print("  KA SI", si.company_gstin, si.billing_address_gstin, si.place_of_supply, [(x.account_head, x.tax_amount) for x in si.taxes])
    # new RA from checked measurements
    for p in ("P-2402", "P-2401"):
        if frappe.db.exists("Measurement Book", {"project": p, "status": "Client checked", "ra_bill": ["is", "not set"]}):
            r = A("ra_new", p); ra = r["open"][1]
            d = frappe.get_doc("RA Bill", ra); print("  new", ra, d.bill_no, d.claimed_amount, d.net_receivable, len(d.items))
            A("ra_submit", ra); A("ra_certify", ra); A("ra_invoice", ra)
            break
    e = frappe.get_all("Extra Item", filters={"status": "Draft"}, pluck="name")[0]
    A("ei_send", e); A("ei_approve", e)
    h = frappe.get_all("Hindrance", filters={"to_date": ["is", "not set"]}, pluck="name")[0]
    A("hin_eot", h); A("hin_close", h)
    d = frappe.get_all("Daily Progress Report", filters={"status": "Submitted"}, pluck="name")[0]
    A("dpr_approve", d)
    from hipersign_trading.api import construction as CN
    CN.clear_cache()
    for p in ("P-2401", "P-2403", "P-2406"):
        F = CN.fig(p); print(" ", p, {k: round(F[k], 1) if isinstance(F[k], float) else F[k] for k in ("pct", "billed", "received", "outstanding", "overdue", "retention", "margin", "bud_margin", "cost")})
        print("   flags:", [f["text"] for f in CN.flags(p)])
    frappe.db.commit()
