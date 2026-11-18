import frappe
def run():
    from hipersign_trading.api import approvals
    frappe.set_user("md@hci.test")
    q = frappe.get_all("Quotation", filters={"hs_cn_approval": "Rejected", "docstatus": 0}, pluck="name")[0]
    frappe.set_user("Administrator")
    d = frappe.get_doc("Quotation", q); d.items[0].rate = d.items[0].rate * 1.005; d.save(); print("after rework:", d.hs_cn_approval)
    frappe.set_user("md@hci.test")
    it = [i for i in approvals.pending(mine=True) if i["kind"] == "cn_quote"]; print(it)
    print(approvals.act("cn_quote", "Quotation", q, "Approve"))
    frappe.db.rollback()
