import frappe
def wizard():
    from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
    print(setup_complete({"language":"English","country":"India","timezone":"Asia/Kolkata","currency":"INR","full_name":"Administrator","email":"admin@example.com",
        "company_name":"Hipersign Construction & Infrastructure Pvt. Ltd.","company_abbr":"HCI","chart_of_accounts":"Standard","fy_start_date":"2026-04-01","fy_end_date":"2027-03-31",
        "setup_demo":0,"domains":["Services"],"company_tagline":"","bank_account":"State Bank of India"}))
    frappe.db.commit()
def demo():
    from hipersign_trading import demo
    demo.load_from_button("Administrator", "Construction (India)")
    print("\n".join(demo.LOG))
    print(frappe.db.get_single_value("Hipersign Settings", "feature_pack"), frappe.db.get_single_value("Hipersign Settings", "feat_construction"))
