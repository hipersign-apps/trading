import frappe
def run():
    from hipersign_trading.api.construction import act
    t = frappe.get_doc({"doctype": "Tender", "tender_name": "Test road", "company": "Hipersign Construction & Infrastructure Pvt. Ltd.", "customer": "Kochi Water Metro Ltd. (fictional)",
        "status": "L1 — LOA awaited", "bid_decision": "Bid", "our_bid": 5e7, "portal": "CPPP"}).insert()
    r = act("tnd_award", t.name, "{}"); pj = r["open"][1]
    print(r["message"], frappe.db.get_value("Construction Contract", {"project": pj}, ["loa_no", "original_value", "revised_value", "price_escalation"]))
    frappe.db.rollback()
