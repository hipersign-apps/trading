import frappe, traceback
def run():
    frappe.set_user("pm@hci.test")
    from hipersign_trading.api.construction import act
    mr = frappe.db.get_value("Supplier Quotation Item", {"docstatus": 1}, "material_request")
    try:
        print(act("po_l1", mr, "{}"))
    except Exception:
        print(traceback.format_exc()[-1500:])
    frappe.db.rollback()
