import frappe, json, time
def run(user="Administrator"):
    frappe.set_user(user)
    from hipersign_trading.api.module import get_module, get_rows
    from hipersign_trading.api import module_cn
    bad = 0
    for key in module_cn.KEYS:
        t0 = time.time()
        m = get_module(key)
        print(f"== {key} {m['title']} ({time.time()-t0:.2f}s) kpis:", " | ".join(f"{k['label']}={k['value'] if not k.get('money') else round(k['value'])}" for k in m["kpis"]))
        for tab in m["tabs"]:
            chips = [c[0] for c in tab["chips"]] or [None]
            for ch in chips:
                try:
                    r = get_rows(key, tab["key"], ch)
                    n = len(r.get("rows") or []) if "rows" in r else ("blocks" if r.get("blocks") else 0)
                    # every row's cells match the columns
                    for row in r.get("rows") or []:
                        if len(row["cells"]) != len(r["cols"]): bad += 1; print("  !! cell count", key, tab["key"], row["name"])
                    json.dumps(r, default=str)
                    print(f"   {tab['key']}/{ch}: {n}")
                except Exception as e:
                    bad += 1; print("  !! ERROR", key, tab["key"], ch, repr(e)[:300])
    print("problems:", bad)
