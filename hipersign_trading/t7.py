import frappe
def run():
    co = "Hipersign Construction & Infrastructure Pvt. Ltd."
    print("GL balanced:", frappe.db.sql("select round(sum(debit)-sum(credit),2) from `tabGL Entry` where is_cancelled=0 and company=%s", co))
    for a in ("State Bank of India - HCI", "Debtors - HCI", "TDS Receivable - 194C - HCI", "Retention Receivable - HCI", "Mobilisation Advance Received - HCI", "Output Tax CGST - HCI", "Contract Revenue - HCI", "Accrued Site Costs - HCI"):
        print(" ", a, frappe.db.sql("select round(sum(debit)-sum(credit)) from `tabGL Entry` where is_cancelled=0 and account=%s", a)[0][0])
    print(frappe.db.sql("select name, account_type from tabAccount where account_type='Bank' and company=%s", co))
    print("negative bank days:", frappe.db.sql("""select count(*) from (select posting_date, sum(sum(debit-credit)) over (order by posting_date) bal from `tabGL Entry`
        where is_cancelled=0 and account in (select name from tabAccount where account_type='Bank' and company=%s) group by posting_date) x where bal < 0""", co))
