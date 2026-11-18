import frappe
def run():
    from frappe.utils.password import update_password
    update_password("se@hci.test", "Hci#Site2026x")
    frappe.set_user("se@hci.test")
    m = frappe.get_doc({"doctype": "Measurement Book", "project": "P-2401", "item_no": "2.2", "location": "Block B — 4th floor slab", "nos": 1, "length": 10, "breadth": 6, "depth": .15})
    m.insert(); print("MB", m.name, m.qty, m.amount, m.unit, m.status, m.over_boq)
    d = frappe.get_doc({"doctype": "Daily Progress Report", "project": "P-2401", "activity": "Slab casting", "planned_qty": 40, "actual_qty": 36, "own_labour": 30, "sub_labour": 50})
    d.insert(); print("DPR", d.name, d.achievement_pct)
    h = frappe.get_doc({"doctype": "Hindrance", "project": "P-2401", "cause": "Cement supply strike", "attributable_to": "Contractor", "from_date": frappe.utils.add_days(frappe.utils.today(), -3)})
    h.insert(); print("HIN", h.name, h.days)
    frappe.db.commit()
