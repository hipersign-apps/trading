"""v1.9.0 demo data (prototype C11): Hipersign Construction & Infrastructure Pvt. Ltd. — a contractor with its head office in
Kochi and regional offices in Bengaluru, Chennai and Pune — with six projects at different stages and a tender pipeline, so the
Construction (India) pages open as on the prototype:

  P-2401  Skyline Residency — G+5 Apartments (Kochi)                 ₹18.6 Cr  execution, RA bill with the PMC
  P-2402  Technopark Phase IV — IT Block B (Thiruvananthapuram)      ₹42.8 Cr  execution, TDS not yet in 26AS
  P-2403  Coastal Highway Service Road & Culverts — Pkg 3 (govt)     ₹27.4 Cr  execution, bill overdue, open hindrance
  P-2405  Hosur Road Logistics Warehouse (PEB) (Bengaluru)            ₹14.2 Cr  nearly complete, no mobilisation advance
  P-2406  OMR Business Hotel — Interior Fit-out (Chennai)            ₹9.75 Cr  execution, extra item drafted
  P-2408  Govt. Polytechnic Hostel Block (PWD, govt)                  ₹8.9 Cr   complete, in DLP

Every figure is a real document: GST tax invoices from the branch GSTIN of each project (India Compliance templates), receipts
net of retention, mobilisation advance recovery, TDS 194C, GST-TDS and BOCW labour cess, the mobilisation advance, BOQs,
extra items, measurement book entries, the current RA bills, tenders with EMD, bank guarantees, DPRs, hindrances and the
cost brought forward per cost head. Every step skips what is already there.

Load it with Hipersign Settings → Set-up → Load demo data → Construction (India)."""

import frappe
from frappe.utils import add_days, add_months, cint, date_diff, flt, get_first_day, get_last_day, getdate, today

CO, ABBR = "Hipersign Construction & Infrastructure Pvt. Ltd.", "HCI"
PAN = "AAHCH4821K"
BASE = "2026-11-17"  # the prototype's "today"; demo dates keep their distance from it
CR = 1e7
SHARE = {"mat": "mat_share", "lab": "lab_share", "sub": "sub_share", "plant": "plant_share", "ovh": "ovh_share"}
HEAD = {"mat": "Materials", "lab": "Labour", "sub": "Subcontract", "plant": "Plant & equipment", "ovh": "Site overheads"}

BRANCHES = {  # key: (title, state, city, line 1, pincode)
	"HO": ("Corporate HO — Kochi", "Kerala", "Kochi", "Infopark Road, Kakkanad", "682030"),
	"KA": ("Regional Office — Bengaluru", "Karnataka", "Bengaluru", "Outer Ring Road, Marathahalli", "560037"),
	"TN": ("Regional Office — Chennai", "Tamil Nadu", "Chennai", "OMR, Thoraipakkam", "600097"),
	"MH": ("Regional Office — Pune", "Maharashtra", "Pune", "Baner Road", "411045"),
}
STATE_CODE = {"Kerala": "32", "Karnataka": "29", "Tamil Nadu": "33", "Maharashtra": "27"}

CUSTOMERS = [  # name, state, city, line 1, pincode, PAN, government
	("Malabar Habitat Developers Pvt. Ltd.", "Kerala", "Kochi", "MG Road, Ravipuram", "682016", "AAJCM5521P", 0),
	("Ananthapuri Tech Parks Ltd.", "Kerala", "Thiruvananthapuram", "Technopark Campus, Kazhakoottam", "695582", "AAHCA7319Q", 0),
	("Kerala State Road Development Board (fictional)", "Kerala", "Thiruvananthapuram", "PWD Complex, Vazhuthacaud", "695014", "AAAGK1188M", 1),
	("Deccan Warehousing LLP", "Karnataka", "Bengaluru", "Bommasandra Industrial Area", "560099", "AAQFD6612L", 0),
	("Coromandel Hospitality Pvt. Ltd.", "Tamil Nadu", "Chennai", "Rajiv Gandhi Salai, Thoraipakkam", "600097", "AAJCC4410H", 0),
	("Public Works Department — Building Division (fictional)", "Kerala", "Palakkad", "Civil Station", "678001", "AAAGP0567D", 1),
	("Kochi Water Metro Ltd. (fictional)", "Kerala", "Kochi", "Vyttila Mobility Hub", "682019", "AAHCK3307E", 1),
]

# BOQ templates: [item, chapter, description, unit, rate, weight, sequence 0–1, cost shares]
TPL = {
	"bld": [
		("1.1", "Earthwork", "Earthwork excavation in all soils incl. disposal up to 1 km", "Cum", 385, .025, .02, {"lab": .25, "plant": .55}),
		("1.2", "Earthwork", "Anti-termite treatment to foundation & plinth", "Sqm", 62, .004, .05, {"mat": .5, "lab": .3}),
		("2.1", "Concrete", "PCC M10 (1:3:6) in foundation bed", "Cum", 6250, .018, .06, {"mat": .62, "lab": .18, "plant": .08}),
		("2.2", "Concrete", "RCC M25 in footings, columns, beams & slabs (excl. steel)", "Cum", 8650, .26, .35, {"mat": .6, "lab": .18, "plant": .1}),
		("2.3", "Concrete", "Reinforcement Fe500D — cutting, bending & placing", "MT", 74500, .21, .35, {"mat": .82, "lab": .1}),
		("2.4", "Concrete", "Centering & shuttering incl. propping", "Sqm", 640, .07, .35, {"mat": .3, "lab": .5}),
		("3.1", "Masonry", "AAC block masonry 200 mm in CM 1:6", "Cum", 6900, .06, .55, {"mat": .55, "lab": .3}),
		("4.1", "Finishes", "Cement plaster 12 mm internal in CM 1:4", "Sqm", 395, .05, .7, {"mat": .38, "lab": .5}),
		("4.2", "Finishes", "Vitrified tile flooring 800 × 800 incl. bedding", "Sqm", 1480, .07, .8, {"mat": .62, "lab": .25}),
		("4.3", "Finishes", "Acrylic emulsion paint, 2 coats over putty", "Sqm", 235, .03, .9, {"mat": .45, "lab": .45}),
		("5.1", "Doors & windows", "uPVC windows & flush doors with fittings", "Nos", 26500, .045, .82, {"mat": .7, "lab": .15}),
		("6.1", "MEP", "Internal plumbing & sanitary (subcontract)", "LS", 0, .06, .75, {"sub": .85}),
		("6.2", "MEP", "Internal electrification (subcontract)", "LS", 0, .06, .72, {"sub": .85}),
	],
	"road": [
		("1.1", "Site clearance", "Clearing & grubbing incl. tree cutting", "Ha", 48000, .004, 0, {"lab": .4, "plant": .45}),
		("1.2", "Earthwork", "Embankment with approved earth, compacted in layers", "Cum", 420, .12, .15, {"mat": .3, "lab": .1, "plant": .5}),
		("2.1", "Pavement", "Granular sub-base (GSB) Grade I", "Cum", 2150, .13, .35, {"mat": .6, "plant": .25}),
		("2.2", "Pavement", "Wet mix macadam (WMM)", "Cum", 2680, .14, .5, {"mat": .62, "plant": .25}),
		("2.3", "Pavement", "Dense bituminous macadam (DBM) 60 mm", "Cum", 9650, .17, .68, {"mat": .68, "plant": .22}),
		("2.4", "Pavement", "Bituminous concrete (BC) 40 mm", "Cum", 11200, .12, .85, {"mat": .7, "plant": .2}),
		("3.1", "Culverts", "RCC M30 box culverts (excl. steel)", "Cum", 9400, .12, .3, {"mat": .58, "lab": .2, "plant": .1}),
		("3.2", "Culverts", "Reinforcement Fe500D for culverts", "MT", 75500, .07, .3, {"mat": .82, "lab": .1}),
		("4.1", "Drainage", "Precast kerb & RCC lined drain", "Rmt", 3150, .05, .6, {"mat": .55, "lab": .3}),
		("5.1", "Road furniture", "Thermoplastic road marking & signage (subcontract)", "Sqm", 780, .015, .95, {"sub": .85}),
	],
	"peb": [
		("1.1", "Earthwork", "Excavation for foundations", "Cum", 395, .02, .02, {"lab": .25, "plant": .55}),
		("2.1", "Foundations", "PCC M15 & RCC M25 pedestals and footings", "Cum", 8400, .12, .12, {"mat": .6, "lab": .18, "plant": .1}),
		("2.2", "Foundations", "Reinforcement Fe500D", "MT", 74500, .07, .12, {"mat": .82, "lab": .1}),
		("2.3", "Foundations", "Anchor bolts with templates", "Nos", 2850, .006, .15, {"mat": .7, "lab": .2}),
		("3.1", "PEB structure", "Pre-engineered steel building — supply, fabrication & erection", "MT", 112000, .38, .45, {"sub": .86}),
		("3.2", "Roofing", "Roof & wall sheeting 0.5 mm with insulation", "Sqm", 1240, .12, .6, {"mat": .7, "lab": .15}),
		("4.1", "Flooring", "FM2 trimix industrial floor 200 mm", "Sqm", 1380, .1, .75, {"mat": .6, "lab": .2, "plant": .1}),
		("5.1", "Services", "Electrical, lighting & fire fighting (subcontract)", "LS", 0, .1, .8, {"sub": .85}),
	],
	"fit": [
		("1.1", "Ceilings", "Gypsum false ceiling with cove lighting", "Sqm", 1180, .12, .4, {"mat": .45, "lab": .35}),
		("1.2", "Partitions", "Gypsum & glass partitions", "Sqm", 3650, .14, .3, {"mat": .5, "lab": .3}),
		("2.1", "Flooring", "Engineered wood & carpet flooring", "Sqm", 2950, .14, .6, {"mat": .62, "lab": .2}),
		("2.2", "Flooring", "Italian marble — lobby", "Sqm", 5400, .06, .65, {"mat": .65, "lab": .2}),
		("3.1", "Joinery", "Wardrobes, headboards & vanities (subcontract)", "Set", 185000, .2, .55, {"sub": .8}),
		("4.1", "Finishes", "Wall cladding & paint", "Sqm", 890, .07, .8, {"mat": .45, "lab": .4}),
		("5.1", "MEP", "HVAC & electrical modifications (subcontract)", "LS", 0, .16, .5, {"sub": .85}),
		("6.1", "Loose furniture", "Loose furniture & soft furnishings", "LS", 0, .06, .9, {"mat": .85}),
	],
}
CATEGORY = {"bld": "Commercial buildings", "road": "Roads and highways", "peb": "Industrial buildings", "fit": "Interior fit-out"}

# id, name, category, template, client, branch, location, PM, SE, QS, [contract Cr, approved extras Cr, budget Cr, forecast Cr, planned %, progress %, start, end],
# step, government, engineer-in-charge, advance %
PROJECTS = [
	("P-2401", "Skyline Residency — G+5 Apartments", "Apartment complexes", "bld", "Malabar Habitat Developers Pvt. Ltd.", "HO", "Kakkanad, Kochi", "Rahul Nair", "Vishnu Prasad",
		"Deepa Krishnan", [18.6, 1.24, 15.9, 16.8, 66, 62, "2025-06-02", "2027-03-31"], 16, 0, "Arch. Suresh Menon (PMC)", 10),
	("P-2402", "Technopark Phase IV — IT Block B", "Commercial buildings", "bld", "Ananthapuri Tech Parks Ltd.", "HO", "Kazhakoottam, Thiruvananthapuram", "Meera Pillai", "Aswin Raj",
		"Deepa Krishnan", [42.8, .85, 37.2, 37.9, 41, 38, "2025-11-10", "2027-12-31"], 15, 0, "CBRE Project Management", 10),
	("P-2403", "Coastal Highway Service Road & Culverts — Pkg 3", "Roads and highways", "road", "Kerala State Road Development Board (fictional)", "HO", "Kanhangad, Kasaragod",
		"Rahul Nair", "Nikhil Varghese", "Joseph Mathew", [27.4, 1.9, 23.8, 25.6, 63, 55, "2025-04-15", "2027-01-31"], 16, 1, "Executive Engineer, Roads Division Kasaragod", 10),
	("P-2405", "Hosur Road Logistics Warehouse (PEB)", "Industrial buildings", "peb", "Deccan Warehousing LLP", "KA", "Bommasandra, Bengaluru", "Karthik Rao", "Manjunath S",
		"Anitha Shetty", [14.2, .45, 12.1, 12.4, 84, 81, "2025-09-01", "2026-12-31"], 17, 0, "Client project team", 0),
	("P-2406", "OMR Business Hotel — Interior Fit-out", "Interior fit-out", "fit", "Coromandel Hospitality Pvt. Ltd.", "TN", "Thoraipakkam, Chennai", "Senthil Kumar", "Divya R",
		"Balaji V", [9.75, .62, 8.3, 8.85, 54, 46, "2026-03-02", "2027-02-28"], 16, 0, "Studio Ardete (design consultant)", 10),
	("P-2408", "Govt. Polytechnic Hostel Block", "Institutional buildings", "bld", "Public Works Department — Building Division (fictional)", "HO", "Kalladikode, Palakkad",
		"Meera Pillai", "Anand K", "Joseph Mathew", [8.9, .22, 7.7, 7.8, 100, 100, "2025-01-06", "2026-10-31"], 24, 1, "Executive Engineer, PWD Buildings Palakkad", 10),
]

EIS = [  # project, title, kind, share of the approved extras (or ₹), status, days from today, reference
	("P-2401", "Additional terrace waterproofing — APP membrane", "Extra item", .42, "Approved", -160, "Client letter MHD/SR/114"),
	("P-2401", "Upgrade lobby flooring to granite", "Substituted item", .58, "Approved", -90, "PMC instruction 22"),
	("P-2401", "Excess excavation — soft strata at Block A (8% over BOQ)", "Deviation (excess quantity)", 412000, "Pending client", -12, "MB-2401 p. 41"),
	("P-2402", "Additional basement retaining wall waterproofing", "Extra item", 1, "Approved", -60, "CBRE/TP4/EI-01"),
	("P-2403", "Additional box culvert at Ch. 4+150", "Extra item", .7, "Approved", -210, "EE letter RD/KSD/2025/318"),
	("P-2403", "Shift of utility poles — extra work", "Extra item", .3, "Approved", -120, "SI-19"),
	("P-2403", "Raising embankment by 300 mm — flood level revision", "Extra item", 6850000, "Pending client", -46, "Site instruction SI-27"),
	("P-2405", "Additional dock levellers (4 nos)", "Extra item", 1, "Approved", -75, "DWL/PO-A2"),
	("P-2406", "Change to imported wallcovering — guest corridors", "Substituted item", 1, "Approved", -50, "Design brief rev B"),
	("P-2406", "Acoustic panelling to banquet hall", "Extra item", 1860000, "Draft", -4, "Design brief rev C"),
	("P-2408", "Rain water harvesting sump", "Extra item", 1, "Approved", -300, "EE letter PWD/PKD/77"),
]

TENDERS = [  # id suffix, project, name, client, source, value Cr, EMD share, published (days), due (days), status, rank, margin
	("TND-2611-021", None, "Kochi Water Metro Terminal — Civil & Structural Works", "Kochi Water Metro Ltd. (fictional)", "Kerala e-Tenders", 21.5, .02, -24, 5, "Being priced", "", 11.8),
	("TND-2611-024", None, "Kakkanad Smart City Road — Phase 2", "Kochi Metropolitan Authority (fictional)", "Kerala e-Tenders", 12.6, .02, -6, 18, "Bid / no-bid", "", 10.5),
	("TND-2610-017", None, "Kannur Airport Cargo Shed — PEB", "Kannur International Airport Ltd. (fictional)", "CPPP", 9.4, .01, -48, -12, "Technical evaluation", "", 12.5),
	("TND-2610-014", None, "Mangalore SEZ Boundary Road — 6.2 km", "MSEZ Ltd. (fictional)", "CPPP", 15.8, .02, -60, -26, "L1 — LOA awaited", "L1", 10.4),
	("TND-2609-009", None, "Thrissur Medical College — Hostel G+7", "Kerala Health Infrastructure Board (fictional)", "Kerala e-Tenders", 31.2, .02, -92, -61, "Lost", "L2", 9.8),
	("TND-2608-006", None, "Coimbatore IT Park — Interior Fit-out Floors 3–5", "Kovai Tech Spaces Pvt. Ltd. (fictional)", "Private enquiry", 6.8, .01, -110, -95, "Lost", "L3", 13.1),
	("TND-2505-011", "P-2403", "Coastal Highway Service Road & Culverts — Pkg 3", "Kerala State Road Development Board (fictional)", "Kerala e-Tenders", 27.4, .02, -620, -590, "Awarded", "L1", 11.2),
	("TND-2507-019", "P-2401", "Skyline Residency — G+5 Apartments", "Malabar Habitat Developers Pvt. Ltd.", "Private enquiry", 18.6, .01, -570, -548, "Awarded", "L1", 14.6),
]

HINDRANCES = [  # project, cause, attributable, from (days), to (days or None), EOT, ref
	("P-2401", "Revised structural drawings for Block B transfer beams awaited from the architect", "Client", -38, -17, "Not applied", ""),
	("P-2403", "Monsoon — continuous rain, bituminous work suspended", "Weather", -70, -41, "Applied", "EOT-03"),
	("P-2403", "KSEB utility poles at Ch. 3+400 not yet shifted", "Authority", -14, None, "Not applied", ""),
	("P-2406", "Hotel operator changed the guest-room joinery design", "Client", -30, -12, "Not applied", ""),
]
WORK = {"bld": [("RCC M25 slab casting", "2.2", "Cum"), ("Reinforcement tying", "2.3", "MT"), ("AAC block masonry", "3.1", "Cum"), ("Internal plaster", "4.1", "Sqm")],
	"road": [("GSB laying & compaction", "2.1", "Cum"), ("WMM laying", "2.2", "Cum"), ("DBM paving", "2.3", "Cum"), ("Culvert raft & walls", "3.1", "Cum")],
	"peb": [("Roof sheeting", "3.2", "Sqm"), ("FM2 floor pour", "4.1", "Sqm")], "fit": [("Gypsum ceiling", "1.1", "Sqm"), ("Partitions", "1.2", "Sqm"), ("Flooring", "2.1", "Sqm")]}
LOC = {"bld": ["Block A — 4th floor slab", "Block A — 5th floor columns", "Block B — 3rd floor slab", "Block B — staircase core", "Podium — grid C/4–C/9"],
	"road": ["Ch. 2+400 to 2+650 LHS", "Ch. 2+650 to 2+900 RHS", "Ch. 3+100 to 3+350 both sides", "Culvert C-7 at Ch. 3+820"],
	"peb": ["Bay 1–4, grid A–D", "Bay 5–8, grid A–D", "Dock area — north"], "fit": ["Guest floors 5–6", "Guest floor 7", "Lobby & lounge"]}


def D(n):
	return add_days(today(), n)


def R(iso):
	"""A prototype date, kept at its distance from the prototype's today."""
	return add_days(today(), date_diff(iso, BASE))


def gstin(state_code, pan, entity="1"):
	chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
	g = f"{state_code}{pan}{entity}Z"
	s = 0
	for i, ch in enumerate(g):
		v = chars.index(ch) * (2 if i % 2 else 1)
		s += v // 36 + v % 36
	return g + chars[(36 - s % 36) % 36]


def _cc():
	return frappe.get_cached_value("Company", CO, "cost_center")


def _clamp(x):
	return max(0.0, min(1.0, x))


def _fy(dates):
	from erpnext.accounts.utils import get_fiscal_year

	for dt in dates:
		try:
			get_fiscal_year(dt, company=CO)
			continue
		except Exception:
			pass
		d = getdate(dt)
		y = d.year if d.month >= 4 else d.year - 1
		name = f"{y}-{y + 1}"
		if frappe.db.exists("Fiscal Year", name):
			fy = frappe.get_doc("Fiscal Year", name)
			if fy.companies and CO not in [r.company for r in fy.companies]:
				fy.append("companies", {"company": CO})
				fy.save(ignore_permissions=True)
			continue
		try:
			frappe.get_doc({"doctype": "Fiscal Year", "year": name, "year_start_date": f"{y}-04-01", "year_end_date": f"{y + 1}-03-31",
				"companies": [{"company": CO}]}).insert(ignore_permissions=True)
		except Exception:
			frappe.get_doc({"doctype": "Fiscal Year", "year": str(d.year), "year_start_date": f"{d.year}-01-01", "year_end_date": f"{d.year}-12-31"}).insert(ignore_permissions=True)


def _address(title, link_dt, link_name, state, city, line1, pin, gst, company_address=False, atype="Billing"):
	if frappe.db.exists("Address", {"address_title": title, "address_type": atype}):
		return frappe.db.get_value("Address", {"address_title": title, "address_type": atype})
	a = frappe.get_doc({"doctype": "Address", "address_title": title, "address_type": atype, "address_line1": line1, "city": city, "state": state, "pincode": pin,
		"country": "India", "is_your_company_address": 1 if company_address else 0, "is_primary_address": 1, "links": [{"link_doctype": link_dt, "link_name": link_name}]})
	if a.meta.has_field("gstin"):
		a.gstin, a.gst_category = gst, "Registered Regular"
	a.insert(ignore_permissions=True)
	return a.name


# ---------------------------------------------------------------- 1. company, GST registrations, accounts
def cn_company(c):
	if not frappe.db.exists("Company", CO):
		frappe.get_doc({"doctype": "Company", "company_name": CO, "abbr": ABBR, "default_currency": "INR", "country": "India",
			"create_chart_of_accounts_based_on": "Standard Template", "chart_of_accounts": "Standard"}).insert(ignore_permissions=True)
	_fy(["2024-12-01", "2025-06-01", "2026-06-01", D(0), D(120)])
	co = frappe.get_doc("Company", CO)
	vals = {"tax_id": PAN}
	if co.meta.has_field("pan"):
		vals["pan"] = PAN
	if co.meta.has_field("gstin"):
		vals.update(gstin=gstin("32", PAN), gst_category="Registered Regular")
	frappe.db.set_value("Company", CO, vals)
	for key, (title, state, city, line1, pin) in BRANCHES.items():
		_address(f"{CO} — {title}", "Company", CO, state, city, line1, pin, gstin(STATE_CODE[state], PAN), company_address=True)
	from hipersign_trading.api import construction as CN

	CN.accounts(CO)
	for cat in set(CATEGORY.values()) | {"Apartment complexes", "Institutional buildings"}:
		CN.works_item(cat)
	bank = CN.bank_account(CO)
	eq = frappe.db.get_value("Account", {"company": CO, "root_type": "Equity", "is_group": 0, "account_name": ["like", "%Capital%"]}) \
		or frappe.db.get_value("Account", {"company": CO, "root_type": "Equity", "is_group": 0})
	if bank and eq and not frappe.db.exists("Journal Entry", {"company": CO, "user_remark": "Hipersign demo — HCI opening capital"}):
		je = frappe.get_doc({"doctype": "Journal Entry", "company": CO, "posting_date": "2024-12-02", "voucher_type": "Journal Entry",
			"user_remark": "Hipersign demo — HCI opening capital", "accounts": [{"account": bank, "debit_in_account_currency": 25 * CR, "cost_center": _cc()},
				{"account": eq, "credit_in_account_currency": 25 * CR, "cost_center": _cc()}]})
		je.flags.hs_system_entry = True
		je.insert(ignore_permissions=True)
		je.submit()
	frappe.db.set_single_value("Hipersign Settings", "feat_construction", 1)
	if not frappe.db.get_single_value("Global Defaults", "default_company"):
		frappe.db.set_single_value("Global Defaults", "default_company", CO)


def cn_customers(c):
	grp = "Commercial" if frappe.db.exists("Customer Group", "Commercial") else frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	terr = "India" if frappe.db.exists("Territory", "India") else frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
	for name, state, city, line1, pin, pan, govt in CUSTOMERS:
		if not frappe.db.exists("Customer", name):
			cu = frappe.get_doc({"doctype": "Customer", "customer_name": name, "customer_type": "Company", "customer_group": grp, "territory": terr})
			if cu.meta.has_field("gstin"):
				cu.gstin, cu.gst_category = gstin(STATE_CODE[state], pan), "Registered Regular"
			if cu.meta.has_field("pan"):
				cu.pan = pan
			cu.insert(ignore_permissions=True)
		_address(name, "Customer", name, state, city, line1, pin, gstin(STATE_CODE[state], pan))


# ---------------------------------------------------------------- 2. projects and BOQs
def _spread(lines, P1, el, contract):
	"""The prototype's cnSpread: early items (sequence 0) further along than late ones, adding up to P1 of the BOQ value."""
	tot = sum(l["amt"] for l in lines)
	if P1 >= .999:
		return [100.0] * len(lines)
	if P1 <= 0:
		return [0.0] * len(lines)

	def pct(l, k):
		return min(1, el * 1.1) if l["s"] < 0 else _clamp(k * (1.25 - l["s"] * 1.1))

	lo, hi = 0.0, 6.0
	for _i in range(40):
		mid = (lo + hi) / 2
		if sum(l["amt"] * pct(l, mid) for l in lines) / tot < P1:
			lo = mid
		else:
			hi = mid
	return [round(pct(l, lo) * 1000) / 10 for l in lines]


def _boq_lines(p):
	pid, tpl, f, step = p[0], p[3], p[10], p[11]
	contract = f[0] * CR
	out = []
	for code, ch, d, unit, rate, w, s, sh in TPL[tpl]:
		amt = contract * w
		if unit == "LS":
			qty, r = 1, round(amt)
		else:
			r = rate
			qty = max(1, round(amt / rate)) if unit in ("Nos", "Set") else round(amt / rate * 10) / 10
		out.append({"item_no": code, "section": ch[:1], "section_name": ch, "description": d, "unit": unit, "qty": qty, "rate": r, "amt": qty * r, "s": s, "sh": sh})
	pre = contract - sum(l["amt"] for l in out)
	out.insert(0, {"item_no": "0.1", "section": "P", "section_name": "Preliminaries", "description": "Preliminaries, site establishment, insurance & statutory registrations",
		"unit": "LS", "qty": 1, "rate": round(pre), "amt": round(pre), "s": -1, "sh": {"ovh": .85}})
	start, end = getdate(R(f[6])), getdate(R(f[7]))
	el = _clamp(date_diff(today(), start) / max(1, date_diff(end, start)))
	P1 = f[5] / 100
	m = max(1, date_diff(today(), start) / 30)
	P0 = max(0, P1 - min(P1, P1 / m * 1.05))
	now = _spread(out, P1, el, contract)
	cert = _spread(out, 1 if step >= 22 else P0, 1 if step >= 22 else max(0, el - .04), contract)
	for l, a, b in zip(out, now, cert):
		l["now"], l["cert"] = a, min(a, b)
	if pid == "P-2401":  # Block A excavation fully billed; the soft-strata excess is measured beyond the BOQ (deviation EI-03)
		ex = next(l for l in out if l["item_no"] == "1.1")
		ex["now"] = ex["cert"] = 100
	return out


def cn_projects(c):
	from hipersign_trading.api import construction as CN

	addr = {k: frappe.db.get_value("Address", {"address_title": f"{CO} — {t[0]}"}) for k, t in BRANCHES.items()}
	for p in PROJECTS:
		pid, name, cat, tpl, client, br, loc, pm, se, qs, f, step, govt, eic, adv = p
		if not frappe.db.exists("Project", pid):
			pj = frappe.get_doc({"doctype": "Project", "project_name": name, "company": CO, "customer": client, "status": "Open", "expected_start_date": R(f[6]),
				"expected_end_date": R(f[7]), "percent_complete_method": "Manual", "cost_center": _cc(), "estimated_costing": f[2] * CR,
				"hs_contract_value": f[0] * CR, "hs_retention_pct": 5, "hs_advance_pct": adv, "hs_dlp_months": 12, "hs_step": step, "hs_consultant": eic, "hs_location": loc,
				"hs_project_manager": pm, "hs_quantity_surveyor": qs, "hs_site_engineer": se, "hs_award_date": add_days(R(f[6]), -60), "hs_enquiry_date": add_days(R(f[6]), -110),
				"hs_cn": 1, "hs_cn_category": cat, "hs_cn_govt": govt, "hs_cn_eic": eic, "hs_cn_address": addr[br], "hs_cn_tds_pct": 2, "hs_cn_template": tpl,
				"hs_payment_terms": f"Monthly RA bills on measurement · {adv}% mobilisation advance against BG, recovered pro rata · 5% retention, half at completion, half after 12-month DLP"
					if adv else "Monthly RA bills on measurement · 5% retention, half at completion, half after 12-month DLP"})
			pj.insert(ignore_permissions=True, set_name=pid)
		if not frappe.db.exists("Project BOQ", {"project": pid}):
			ls = _boq_lines(p)
			b = frappe.get_doc({"doctype": "Project BOQ", "title": name, "project": pid, "customer": client, "client_name": client, "company": CO, "status": "Awarded", "revision": 1,
				"tender_value": f[0] * CR, "margin_pct": round((f[0] - f[2]) / f[0] * 100, 1), "target_margin": 14, "overhead_pct": 0,
				"items": [{"section": l["section"], "section_name": l["section_name"], "item_no": l["item_no"], "description": l["description"], "unit": l["unit"], "qty": l["qty"],
					"rate": l["rate"], "measured_pct": l["now"], "certified_pct": l["cert"], **{SHARE[k]: v * 100 for k, v in l["sh"].items()}} for l in ls]})
			b.insert(ignore_permissions=True)
	for (pj, title, kind, frac, status, d, ref) in EIS:
		if frappe.db.exists("Extra Item", {"project": pj, "title": title}):
			continue
		p = next(x for x in PROJECTS if x[0] == pj)
		amt = round(p[10][1] * CR * frac / 1000) * 1000 if frac <= 1 else frac
		e = frappe.get_doc({"doctype": "Extra Item", "project": pj, "title": title, "kind": kind, "amount": amt, "status": status, "raised_on": D(d), "raised_by": p[9],
			"reference": ref, "sent_on": D(d + 2) if status in ("Pending client", "Approved") else None, "approved_on": D(d + 18) if status == "Approved" else None,
			"approved_by": p[13] if status == "Approved" else None})
		e.insert(ignore_permissions=True)
	for p in PROJECTS:
		CN._ei_update_project(p[0])


# ---------------------------------------------------------------- 3. tenders, EMD and bank guarantees
def cn_tenders(c):
	for (tid, pj, name, client, portal, val, emd_pct, pub, due, status, rank, margin) in TENDERS:
		if frappe.db.exists("Tender", tid):
			continue
		emd = round(val * CR * emd_pct / 1000) * 1000
		t = frappe.get_doc({"doctype": "Tender", "tender_name": name, "company": CO, "customer": client if frappe.db.exists("Customer", client) else None, "client_name": client,
			"portal": portal, "tender_ref": f"{'KL' if 'Kerala' in portal else 'CP' if portal == 'CPPP' else 'PE'}/{tid[4:]}", "estimated_value": val * CR,
			"our_bid": round(val * CR * (1 - margin / 400)) if status not in ("Bid / no-bid", "Being priced") else 0, "our_margin_pct": margin, "published_on": D(pub), "due_date": D(due),
			"status": status, "bid_decision": "Pending" if status == "Bid / no-bid" else "Bid", "decided_by": None if status == "Bid / no-bid" else "Arjun Menon", "rank": rank,
			"project": pj, "emd_amount": emd, "emd_mode": "Bank guarantee" if emd_pct >= .02 else "Online",
			"emd_status": "Not paid" if status in ("Bid / no-bid", "Being priced") else "Refund pending" if status == "Lost" else "Adjusted in PBG" if status == "Awarded" else "Held by client",
			"result_note": "Rate quoted 3.4% above L1" if tid == "TND-2609-009" else None})
		t.insert(ignore_permissions=True, set_name=tid)


def cn_bonds(c):
	if not frappe.db.exists("DocType", "Bank Guarantee") or frappe.db.exists("Bank Guarantee", {"project": "P-2401"}):
		return
	banks = ["State Bank of India", "Federal Bank", "HDFC Bank", "Canara Bank"]
	for b in banks:
		if not frappe.db.exists("Bank", b):
			frappe.get_doc({"doctype": "Bank", "bank_name": b}).insert(ignore_permissions=True)
	has_type = frappe.get_meta("Bank Guarantee").has_field("hs_bond_type")
	for i, p in enumerate(PROJECTS):
		pid, name, cat, tpl, client, br, loc, pm, se, qs, f, step, govt, eic, adv = p
		start, end = R(f[6]), R(f[7])
		rows = [("Performance bond", f"PBG/{pid[2:]}", f[0] * CR * (.05 if govt else .03), add_days(start, -40), D(41) if pid == "P-2405" else add_days(end, 30 * 12 + 60), "Active")]
		if adv:
			rows.append(("Advance payment guarantee", f"MABG/{pid[2:]}", f[0] * CR * adv / 100 * (1 - min(.9, f[5] / 100)), add_days(start, -25),
				D(18) if pid == "P-2403" else add_days(end, -20) if step >= 22 else D(120 + i * 30), "Returned" if step >= 22 else "Active"))
		for kind, no, amt, issued, exp, state in rows:
			bg = frappe.get_doc({"doctype": "Bank Guarantee", "bg_type": "Providing", "customer": client, "project": pid, "amount": round(amt), "start_date": issued,
				"validity": date_diff(exp, issued), "end_date": exp, "bank": banks[i % 4], "bank_guarantee_number": f"{no}/{['SBI', 'FED', 'HDFC', 'CAN'][i % 4]}",
				"name_of_beneficiary": client, "more_information": f"{kind} for {pid} — {name}"})
			if has_type:
				bg.hs_bond_type, bg.hs_bond_status = kind, state
			bg.insert(ignore_permissions=True)
			bg.submit()
			frappe.db.set_value("Bank Guarantee", bg.name, "end_date", exp, update_modified=False)


# ---------------------------------------------------------------- 4. mobilisation advance, RA bills, invoices and receipts
def cn_billing(c):
	from hipersign_trading.api import construction as CN

	acc = CN.accounts(CO)
	bank = CN.bank_account(CO)
	for p in PROJECTS:
		pid, name, cat, tpl, client, br, loc, pm, se, qs, f, step, govt, eic, adv = p
		if frappe.db.exists("RA Bill", {"project": pid}):
			continue
		start, end = getdate(R(f[6])), getdate(R(f[7]))
		contract = f[0] * CR
		if adv and not frappe.db.exists("Journal Entry", {"company": CO, "user_remark": f"Hipersign demo — mobilisation advance {pid}"}):
			je = frappe.get_doc({"doctype": "Journal Entry", "company": CO, "posting_date": add_days(start, -20), "voucher_type": "Bank Entry", "cheque_no": f"NEFT/MOB/{pid}",
				"cheque_date": add_days(start, -20), "user_remark": f"Hipersign demo — mobilisation advance {pid}",
				"accounts": [{"account": bank, "debit_in_account_currency": contract * adv / 100, "cost_center": _cc(), "project": pid},
					{"account": acc.advance, "credit_in_account_currency": contract * adv / 100, "cost_center": _cc(), "project": pid}]})
			je.flags.hs_system_entry = True
			je.insert(ignore_permissions=True)
			je.submit()
		b = CN.boq(pid)
		lines = {r.item_no: r for r in b.items}
		E = [e for e in CN.eis(pid) if e.status == "Approved" and not e.kind.startswith("Deviation")]
		ei_total = sum(flt(e.amount) for e in E)
		work_cert = sum(flt(r.amount) * flt(r.certified_pct) / 100 for r in b.items)
		ei_cert = ei_total * min(1, work_cert / contract)
		months = max(1, date_diff(today(), start) // 30)
		n = months + 1 if step >= 22 else max(1, months - (1 if step >= 16 else 0))
		span = min(date_diff(today(), start) - 22, date_diff(end, start) + 30)
		prev_frac = 0
		for k in range(1, n + 1):
			frac = 1 if k == n else (k / n) ** 1.12
			d = add_days(start, round(40 + (k - 1) * (span - 40) / max(1, n - 1)))
			items = []
			for r in b.items:
				cq = flt(r.qty) * flt(r.certified_pct) / 100
				this = flt(cq * frac, 3) - flt(cq * prev_frac, 3)
				if this > 0.0005:
					items.append({"item_no": r.item_no, "prev_qty": flt(cq * prev_frac, 3), "this_qty": flt(this, 3)})
			ei_this = flt(ei_cert * (frac - prev_frac), 2)
			prev_frac = frac
			if not items and not ei_this:
				continue
			ra = frappe.get_doc({"doctype": "RA Bill", "project": pid, "bill_no": k, "is_final": 1 if step >= 22 and k == n else 0, "bill_date": add_days(d, -8),
				"period_to": add_days(d, -10), "status": "Draft", "items": items, "extra_items_amount": ei_this})
			ra.insert(ignore_permissions=True)
			cut = flt(ra.claimed_amount * .012, 0) if k % 4 == 2 else 0
			ra.status, ra.submitted_on = "Submitted to client", add_days(d, -6)
			ra.save(ignore_permissions=True)
			ra.status, ra.certified_amount, ra.certified_on = "Certified", flt(ra.claimed_amount - cut, 2), d
			ra.save(ignore_permissions=True)
			CN.make_invoice(ra.name, add_days(d, 2))
			due = add_days(d, 32)
			paid = getdate(due) <= getdate(D(-6))
			if (pid == "P-2403" and k == n) or (pid == "P-2405" and k == n):
				paid = False
			if paid:
				CN.receive(ra.name, add_days(due, -3), f"NEFT/{pid[2:]}/{k:02d}")
				frappe.db.set_value("RA Bill", ra.name, {"tds_in_26as": 0 if (pid == "P-2402" and k == n) else 1, "gst_tds_ok": 1 if govt else 0}, update_modified=False)
		if pid in ("P-2402", "P-2403"):  # the client's TDS on the latest receipt is not in Form 26AS yet
			paid_last = frappe.get_all("RA Bill", filters={"project": pid, "status": "Paid"}, pluck="name", order_by="bill_no desc", limit=1)
			if paid_last:
				frappe.db.set_value("RA Bill", paid_last[0], {"tds_in_26as": 0, "gst_tds_ok": 0}, update_modified=False)
		if pid == "P-2403":  # the last bill: certified seven weeks ago, invoiced, overdue
			last = frappe.get_all("RA Bill", filters={"project": pid}, fields=["name", "sales_invoice"], order_by="bill_no desc", limit=1)[0]
			frappe.db.set_value("RA Bill", last.name, {"due_date": D(-20)}, update_modified=False)
			frappe.db.set_value("Sales Invoice", last.sales_invoice, "due_date", D(-20), update_modified=False)
		CN.clear_cache()
	# the bills with the client now (step 16–17): the work measured since the last certificate
	for p in PROJECTS:
		pid, step = p[0], p[11]
		if step not in (16, 17) or frappe.db.exists("RA Bill", {"project": pid, "status": "Submitted to client"}):
			continue
		_open_bill(p)


def _open_bill(p):
	"""The current RA bill: the client-checked measurements since the last certified bill, sent to the client."""
	from hipersign_trading.api import construction as CN

	pid, tpl, step, se, qs, eic = p[0], p[3], p[11], p[8], p[9], p[13]
	_mb(p, open_bill=True)
	try:
		n = CN.new_ra(pid)
	except frappe.ValidationError:
		return
	ra = frappe.get_doc("RA Bill", n)
	ra.bill_date, ra.period_to = D(-9), D(-10)
	ra.status, ra.submitted_on = "Submitted to client", D(-26) if step == 17 else D(-7)
	ra.save(ignore_permissions=True)


def _mb(p, open_bill=False):
	"""Measurement book entries for the work done since the last certificate (measured % − certified % of each line)."""
	from hipersign_trading.api import construction as CN

	pid, tpl, se, qs, eic = p[0], p[3], p[8], p[9], p[13]
	b = CN.boq(pid)
	locs = LOC[tpl]
	page = 30 + int(pid[-1]) * 3
	i = 0
	for r in b.items:
		if (r.unit or "").upper() == "LS" or flt(r.measured_pct) <= flt(r.certified_pct):
			continue
		q = flt(r.qty) * (flt(r.measured_pct) - flt(r.certified_pct)) / 100
		parts = 2 if q > 50 else 1
		for j in range(parts):
			qq = flt(q * (.55 if parts == 2 and j == 0 else .45 if parts == 2 else 1), 3)
			age = 2 + ((i * 3 + j * 5) % 24)
			st = "Client checked" if open_bill else "Draft" if age <= 4 else "Checked by QS" if age <= 9 else "Client checked"
			dims = {}
			if r.unit == "Cum":
				dd, bb = (.45, 12) if qq > 300 else (.15, 6)
				dims = {"nos": 1, "length": flt(qq / (bb * dd), 3), "breadth": bb, "depth": dd}
			elif r.unit == "Sqm":
				bb = 18 if qq > 500 else 6
				dims = {"nos": 1, "length": flt(qq / bb, 3), "breadth": bb}
			elif r.unit == "Rmt":
				dims = {"nos": 1, "length": qq}
			m = frappe.get_doc(dict({"doctype": "Measurement Book", "project": pid, "item_no": r.item_no, "location": locs[(i + j) % len(locs)], "measured_on": D(-age),
				"mb_page": page, "measured_by": se, "status": st, "qs_checked_by": qs if st != "Draft" else None, "client_checked_by": eic if st == "Client checked" else None,
				"manual_qty": 0 if dims else 1, "qty": qq, "bbs_ref": "As per bar bending schedule" if r.unit == "MT" else None}, **dims))
			m.insert(ignore_permissions=True)
			page += 1
		i += 1


def cn_measurements(c):
	"""Projects without a bill at the client measure for the next one: drafts, QS-checked and client-checked entries; and
	Skyline's excess excavation in soft strata — measured beyond the BOQ, behind the deviation statement with the PMC."""
	from hipersign_trading.api import construction as CN

	if not frappe.db.exists("Measurement Book", {"project": "P-2401", "item_no": "1.1"}):
		_b, r = CN.boq_line("P-2401", "1.1")
		if r:
			frappe.get_doc({"doctype": "Measurement Book", "project": "P-2401", "item_no": "1.1", "location": "Block A — soft strata pocket, grid A/1–A/6",
				"measured_on": D(-12), "mb_page": 41, "measured_by": "Vishnu Prasad", "status": "Checked by QS", "qs_checked_by": "Deepa Krishnan", "manual_qty": 1,
				"qty": flt(flt(r.qty) * .08, 1), "remarks": "Excess over BOQ — deviation statement EI sent to the PMC"}).insert(ignore_permissions=True)
	for p in PROJECTS:
		pid, step = p[0], p[11]
		if step >= 22 or step in (16, 17) or frappe.db.exists("Measurement Book", {"project": pid}):
			continue
		_mb(p)


# ---------------------------------------------------------------- 5. site: hindrances and daily progress reports
def cn_site(c):
	from hipersign_trading.api import construction as CN

	for (pid, cause, by, frm, to, eot, ref) in HINDRANCES:
		if frappe.db.exists("Hindrance", {"project": pid, "cause": cause}):
			continue
		frappe.get_doc({"doctype": "Hindrance", "project": pid, "cause": cause, "attributable_to": by, "from_date": D(frm), "to_date": D(to) if to is not None else None,
			"eot_status": eot, "eot_ref": f"{ref} dated {frappe.format(D(frm + 35), {'fieldtype': 'Date'})}" if ref else None}).insert(ignore_permissions=True)
	if frappe.db.exists("Daily Progress Report", {"project": "P-2401"}):
		return
	for p in PROJECTS:
		pid, name, cat, tpl, client, br, loc, pm, se, qs, f, step, govt, eic, adv = p
		if step >= 22:
			continue
		b = CN.boq(pid)
		lines = {r.item_no: r for r in b.items}
		W = WORK[tpl]
		scale = f[0] / 20
		hin = frappe.db.get_value("Hindrance", {"project": pid, "to_date": ["is", "not set"]})
		for d in range(-7, 0):
			dt = D(d)
			if getdate(dt).weekday() == 6:
				continue
			k = (d + 9) % len(W)
			act, item_no, unit = W[k]
			l = lines.get(item_no)
			plan = max(1, round(flt(l.qty) * .006 * (1 + (k % 3) * .3) * 10) / 10) if l else 10
			rain = br == "HO" and d in (-5, -2)
			achieved = flt(plan * (.55 if rain else .82 if f[4] > f[5] else 1.04), 2)
			own, sub = round(28 * scale + 14 + (d % 3)), round(46 * scale + 20 + ((d * 7) % 5))
			frappe.get_doc({"doctype": "Daily Progress Report", "project": pid, "report_date": dt, "weather": "Heavy rain" if rain else "Fair", "hours_lost": 3 if rain else 0,
				"own_labour": own, "sub_labour": sub, "skilled": round((own + sub) * .42), "boq_item": item_no, "activity": act, "unit": unit, "planned_qty": plan,
				"actual_qty": achieved, "hindrance": hin,
				"materials": {"road": "GSB 180 Cum · bitumen VG-30 12 MT", "bld": "Cement 420 bags · TMT 8.4 MT · M-sand 36 Cum"}.get(tpl, "Gypsum boards 260 · adhesive 40 bags"),
				"equipment": {"road": "Paver 7 h · roller 9 h · grader 6 h", "bld": "Tower crane 9 h · batching plant 7 h"}.get(tpl, "Scissor lift 6 h"),
				"reported_by": se, "status": "Submitted" if d >= -2 else "Approved", "approved_by": pm if d < -2 else None}).insert(ignore_permissions=True)


# ---------------------------------------------------------------- 6. cost brought forward per cost head
def cn_costs(c):
	from hipersign_trading.api import construction as CN
	from hipersign_trading.api import projects as P

	if frappe.db.exists("Journal Entry", {"company": CO, "user_remark": ["like", "Hipersign demo — HCI cost brought forward%"]}):
		return
	acc = CN.accounts(CO)
	bank = CN.bank_account(CO)
	cur_liab = P._group(CO, "Liability", ("Current Liabilities",))
	accrued = P._account(CO, "Accrued Site Costs", "Liability", cur_liab)
	for p in PROJECTS:
		pid, name, cat, tpl, client, br, loc, pm, se, qs, f, step, govt, eic, adv = p
		factor = f[3] / f[2]
		b = CN.boq(pid)
		target = {k: 0.0 for k in HEAD}
		for r in b.items:
			pct = 1 if step >= 22 else flt(r.measured_pct) / 100
			for k, fld in SHARE.items():
				target[k] += flt(r.amount) * flt(r.get(fld)) / 100 * pct * factor
		target["plant"] += f[0] * CR * P.PLANT_PCT / 100 * (f[5] / 100)
		P.clear_cache()
		have = P._gl_by_head(pid, CO)  # materials issued, wages, subcontract bills booked by the documents above
		for k, h in HEAD.items():
			target[k] = max(0, target[k] - flt(have.get(h)))
		start = getdate(R(f[6]))
		end = min(getdate(today()), getdate(R(f[7])))
		months = max(1, date_diff(end, start) // 30)
		# booked month by month so the bank and the margin move as the work does
		for mth in range(months):
			w = ((mth + 1) / months) ** 1.1 - (mth / months) ** 1.1
			rows = []
			for k, h in HEAD.items():
				amt = flt(target[k] * w, 2)
				if amt > 1:
					rows.append({"account": acc.heads[h], "debit_in_account_currency": amt, "project": pid, "cost_center": _cc(), "user_remark": h})
			if not rows:
				continue
			total = flt(sum(r["debit_in_account_currency"] for r in rows), 2)
			rows.append({"account": bank, "credit_in_account_currency": flt(total * .85, 2), "cost_center": _cc()})
			rows.append({"account": accrued, "credit_in_account_currency": flt(total - flt(total * .85, 2), 2), "cost_center": _cc()})
			je = frappe.get_doc({"doctype": "Journal Entry", "company": CO, "posting_date": add_days(start, 30 * mth + 28), "voucher_type": "Journal Entry", "accounts": rows,
				"user_remark": f"Hipersign demo — HCI cost brought forward {pid}: materials, labour, subcontract, plant hire and site overheads (85% paid, 15% accrued)"})
			je.flags.hs_system_entry = True
			je.insert(ignore_permissions=True)
			je.submit()
	for p in PROJECTS:
		CN.clear_cache()
		frappe.db.set_value("Project", p[0], "percent_complete", round(CN.fig(p[0]).pct), update_modified=False)


# ---------------------------------------------------------------- 7. business: enquiries, visits, quotations, contracts, claims, collections (A2)
PROSPECTS = [  # name, state, city, line 1, pincode, PAN
	("Cochin Waterfront Developers Pvt. Ltd.", "Kerala", "Kochi", "Marine Drive", "682031", "AAKCC2210B"),
	("Periyar Residency Builders LLP", "Kerala", "Aluva", "Bank Junction", "683101", "AAPFP7781R"),
	("Malnad Agro Processing Ltd. (fictional)", "Karnataka", "Shivamogga", "KIADB Industrial Area", "577202", "AAHCM9012E"),
	("Chettinad Heritage Resorts Pvt. Ltd. (fictional)", "Tamil Nadu", "Karaikudi", "Devakottai Road", "630001", "AAJCC5523D"),
]
OPPS = [  # title, party, category, location, value Cr, stage / status, probability, next (days), competition, source, visits
	("Marine Drive Mixed-use Tower — civil & structure", "Cochin Waterfront Developers Pvt. Ltd.", "Commercial buildings", "Marine Drive, Kochi", 64.0, "Negotiation", 75, 2,
		"Shapoorji Pallonji, Sobha", "Referral"),
	("Aluva Riverside Villas — 18 units", "Periyar Residency Builders LLP", "Villas & individual houses", "Aluva", 22.4, "Proposal sent", 60, -3, "Local contractors (2)", "Existing client"),
	("Shivamogga Food Processing Plant — PEB & civil", "Malnad Agro Processing Ltd. (fictional)", "Industrial buildings", "Shivamogga", 18.9, "Estimating", 45, 5,
		"Pennar, Kirby (PEB only)", "Website"),
	("Karaikudi Heritage Resort — 40 keys", "Chettinad Heritage Resorts Pvt. Ltd. (fictional)", "Interior fit-out", "Karaikudi", 11.5, "Site visit", 35, 0, "", "Architect"),
	("Skyline Residency Phase 2 — Block C", "Malabar Habitat Developers Pvt. Ltd.", "Apartment complexes", "Kakkanad, Kochi", 21.0, "Qualified", 25, 9, "", "Existing client"),
	("Technopark Phase IV — Food Court & Amenities", "Ananthapuri Tech Parks Ltd.", "Commercial buildings", "Kazhakoottam, Thiruvananthapuram", 6.2, "Lead", 10, 12, "", "Existing client"),
	("OMR Business Hotel — Interior Fit-out", "Coromandel Hospitality Pvt. Ltd.", "Interior fit-out", "Thoraipakkam, Chennai", 9.75, "Converted", 100, None, "Two Chennai fit-out firms", "Architect"),
	("Bommasandra Cold Store", "Deccan Warehousing LLP", "Industrial buildings", "Bommasandra, Bengaluru", 8.4, "Lost", 0, None, "Kirby Building Systems", "Existing client"),
	("Kakkanad Co-working Hub — Interiors", "Malabar Habitat Developers Pvt. Ltd.", "Interior fit-out", "Kakkanad, Kochi", 3.6, "Lost", 0, None, "Design-build studio", "Existing client"),
]


def cn_business(c):
	from hipersign_trading.api import construction as CN
	from hipersign_trading.api import construction_biz as B

	if not frappe.db.exists("DocType", "Construction Contract"):
		return
	for p in PROJECTS:
		frappe.db.set_value("Project", p[0], "hs_cn_planned_pct", p[10][4], update_modified=False)
	for st in B.STAGES:
		B._sales_stage(st)
	grp = "Commercial" if frappe.db.exists("Customer Group", "Commercial") else frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	terr = "India" if frappe.db.exists("Territory", "India") else frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
	for name, state, city, line1, pin, pan in PROSPECTS:
		if not frappe.db.exists("Customer", name):
			cu = frappe.get_doc({"doctype": "Customer", "customer_name": name, "customer_type": "Company", "customer_group": grp, "territory": terr})
			if cu.meta.has_field("gstin"):
				cu.gstin, cu.gst_category = gstin(STATE_CODE[state], pan), "Registered Regular"
			cu.insert(ignore_permissions=True)
		_address(name, "Customer", name, state, city, line1, pin, gstin(STATE_CODE[state], pan))
	if frappe.db.exists("Opportunity", {"company": CO, "hs_cn": 1}):
		return
	for src in {o[9] for o in OPPS}:
		if frappe.db.exists("DocType", "UTM Source") and not frappe.db.exists("UTM Source", src):
			frappe.get_doc({"doctype": "UTM Source", "name": src, "__newname": src}).insert(ignore_permissions=True, set_name=src)
	opp = {}
	for i, (title, party, cat, loc, val, stage, prob, nxt, comp, src) in enumerate(OPPS):
		o = frappe.get_doc({"doctype": "Opportunity", "opportunity_from": "Customer", "party_name": party, "title": title, "company": CO, "opportunity_type": "Sales",
			"transaction_date": D(-200 + i * 18), "opportunity_amount": val * CR, "currency": "INR", "probability": prob, "expected_closing": D(30 + i * 10),
			"sales_stage": stage if stage in B.STAGES else "Negotiation", "hs_cn": 1, "hs_cn_category": cat, "hs_cn_location": loc,
			"hs_cn_next_date": D(nxt) if nxt is not None else None, "hs_cn_competition": comp})
		if o.meta.has_field("utm_source") and frappe.db.exists("UTM Source", src):
			o.utm_source = src
		o.insert(ignore_permissions=True)
		opp[title] = o.name
	# visits & meetings
	V = [(0, -40, "Site visit", "Arjun Menon, Rahul Nair", "Mr. Thomas Kurian (MD)", "Walked the plot; soil report shared; client wants podium + 22 floors", "Send budget estimate", 2),
		(0, -12, "Office meeting", "Arjun Menon, Deepa Krishnan", "Client's PMC", "Negotiated rates for RCC and shuttering; asked for M30 in the podium", "Revised offer", -2),
		(1, -26, "Site visit", "Arjun Menon", "Mr. Joy Varghese (partner)", "18 villa plots marked; access road pending from the panchayat", "Proposal", -10),
		(1, -5, "Call", "Arjun Menon", "Mr. Joy Varghese", "Client comparing with two local contractors; wants 4% off", "Discuss with MD", -3),
		(2, -9, "Presentation", "Arjun Menon, Karthik Rao", "Plant head and consultant", "Presented PEB + civil single-point responsibility", "Estimate by Friday", 5),
		(3, -2, "Site visit", "Senthil Kumar", "Ar. Meenakshi (architect)", "Heritage façade to be kept; interiors and MEP in scope", "Visit report and BOQ", 6),
		(4, -15, "Office meeting", "Arjun Menon", "Malabar Habitat — projects head", "Phase 2 planned after Block A handover", "Call in December", 9)]
	for k, d, kind, us, them, notes, step, nd in V:
		t = OPPS[k]
		frappe.get_doc({"doctype": "Client Visit", "opportunity": opp[t[0]], "customer": t[1], "party_name": t[1], "company": CO, "visit_date": D(d), "kind": kind,
			"visited_by": us, "met": them, "notes": notes, "next_step": step, "next_date": D(nd)}).insert(ignore_permissions=True)
	# quotations: revised and approved (Marine Drive), waiting for the MD (Aluva), draft (Shivamogga), won (OMR hotel), lost (cold store)
	def quote(t, value, cost, lst, docstatus, days, approval=None, outcome="Open", rev=0, rev_of=None, reason=None, project=None):
		o = OPPS[[x[0] for x in OPPS].index(t)]
		q = frappe.get_doc({"doctype": "Quotation", "quotation_to": "Customer", "party_name": o[1], "company": CO, "opportunity": opp[t], "transaction_date": D(days),
			"valid_till": D(days + 45), "order_type": "Sales", "hs_subject": t, "hs_cn": 1, "hs_cn_cost": cost * CR, "hs_cn_list_value": lst * CR,
			"hs_cn_revision": rev, "hs_cn_revision_of": rev_of, "hs_cn_revision_reason": reason,
			"items": [{"item_code": CN.works_item(o[2]), "qty": 1, "rate": value * CR, "description": f"{t} — construction works as per the scope, drawings and specifications"}],
			"tc_name": None, "terms": "Monthly RA bills on joint measurement, 30 days · 10% mobilisation advance against BG · 5% retention · GST extra as applicable · validity 45 days"})
		st = next((x[1] for x in CUSTOMERS + PROSPECTS if x[0] == o[1]), "Kerala")
		br = next((k for k, v in BRANCHES.items() if v[1] == st), "HO")
		q.company_address = frappe.db.get_value("Address", {"address_title": f"{CO} — {BRANCHES[br][0]}"})
		q.taxes_and_charges = CN._tax_template(CO, q.company_address, o[1])
		q.run_method("set_missing_values")
		if q.taxes_and_charges:
			q.set("taxes", [])
			for r in frappe.get_doc("Sales Taxes and Charges Template", q.taxes_and_charges).taxes:
				q.append("taxes", {"charge_type": r.charge_type, "account_head": r.account_head, "rate": r.rate, "description": r.description})
		q.insert(ignore_permissions=True)
		if approval == "Approved":
			q.db_set({"hs_cn_approval": "Approved", "hs_cn_approved_by": "Arjun Menon", "hs_cn_approved_value": q.base_net_total})
			q.reload()
		if docstatus:
			q.submit()
		if outcome != "Open":
			frappe.db.set_value("Quotation", q.name, {"hs_cn_outcome": outcome, "hs_cn_project": project})
		return q
	q0 = quote(OPPS[0][0], 66.5, 57.2, 66.5, 1, -30)
	q0.cancel()
	frappe.db.set_value("Quotation", q0.name, "hs_cn_outcome", "Revised")
	q1 = quote(OPPS[0][0], 62.6, 56.1, 66.5, 1, -8, approval="Approved", rev=1, rev_of=q0.name, reason="Client asked for M30 in the podium; rates negotiated on 12 Nov — 5.9% off")
	quote(OPPS[1][0], 21.5, 19.7, 22.4, 0, -4)  # margin 8.4% → waiting for the MD
	quote(OPPS[2][0], 18.9, 16.4, 18.9, 0, -1)
	qw = quote(OPPS[6][0], 9.75, 8.3, 9.75, 1, -280, outcome="Accepted", project="P-2406")
	frappe.db.set_value("Opportunity", opp[OPPS[6][0]], {"status": "Converted", "hs_cn_project": "P-2406"})
	ql = quote(OPPS[7][0], 8.4, 7.5, 8.4, 1, -120)
	r = B._lost_reason("Lost to competitor")
	ql.reload()
	ql.declare_enquiry_lost([{"lost_reason": r}], [], "Kirby quoted a PEB-only price 9% lower")
	frappe.db.set_value("Quotation", ql.name, "hs_cn_outcome", "Lost")
	for k, reason in ((7, "Lost to competitor"), (8, "Client chose design-build")):
		o = frappe.get_doc("Opportunity", opp[OPPS[k][0]])
		if o.status != "Lost":
			o.declare_enquiry_lost([{"lost_reason": B._lost_reason(reason)}], [], None)
	frappe.db.set_value("Opportunity", opp[OPPS[0][0]], "status", "Quotation")
	# contracts (LOA) for every project, then claims and the collections log
	for p in PROJECTS:
		pid, name, cat, tpl, client, br, loc, pm, se, qs, f, step, govt, eic, adv = p
		if frappe.db.exists("Construction Contract", {"project": pid}):
			continue
		tnd = frappe.db.get_value("Tender", {"project": pid})
		frappe.get_doc({"doctype": "Construction Contract", "project": pid, "status": "In DLP" if step >= 22 else "Active", "tender": tnd,
			"quotation": qw.name if pid == "P-2406" else None, "loa_no": f"{'WO' if govt else 'LOA'}/{pid[2:]}/{getdate(R(f[6])).year}", "loa_date": add_days(R(f[6]), -60),
			"agreement_no": f"AGR/{pid[2:]}", "agreement_date": add_days(R(f[6]), -45), "original_value": f[0] * CR, "retention_pct": 5, "advance_pct": adv,
			"price_escalation": "Price variation clause (indices)" if govt else "Steel & cement only" if tpl == "bld" else "None — firm price",
			"start_date": R(f[6]), "completion_date": R(f[7]), "ld_rate_pct": .5, "ld_cap_pct": 10, "dlp_months": 12,
			"payment_terms": frappe.db.get_value("Project", pid, "hs_payment_terms")}).insert(ignore_permissions=True)
	hin = {h.cause[:20]: h.name for h in frappe.get_all("Hindrance", fields=["name", "cause"])}
	CL = [("P-2403", "EOT — monsoon suspension of bituminous work", "Extension of time", "Monsoon — continuous", 29, 0, "Awarded", 21, 0, -60),
		("P-2403", "Prolongation cost — monsoon and utility shifting", "Prolongation cost", None, 0, 3800000, "Submitted", 0, 0, -20),
		("P-2401", "EOT — Block B transfer-beam drawings late", "Extension of time", "Revised structural d", 21, 0, "Under negotiation", 0, 0, -14),
		("P-2401", "Additional excavation in soft strata — rate for excess", "Cost claim", None, 0, 412000, "Draft", 0, 0, -10),
		("P-2406", "Steel & cement escalation — Q2 to Q3", "Price escalation", None, 0, 1260000, "Submitted", 0, 0, -9)]
	for pid, title, kind, hkey, days, amt, status, adays, aamt, d in CL:
		k = frappe.get_doc({"doctype": "Contract Claim", "project": pid, "title": title, "kind": kind, "hindrance": hin.get(hkey) if hkey else None,
			"claimed_days": days, "claimed_amount": amt, "basis": "As per the hindrance register, site instructions and correspondence on file"})
		k.insert(ignore_permissions=True)
		if status != "Draft":
			k.db_set({"status": status, "submitted_on": D(d)})
		if status == "Awarded":
			k.db_set({"awarded_days": adays, "awarded_amount": aamt, "decided_on": D(d + 30)})
			if k.hindrance:
				frappe.db.set_value("Hindrance", k.hindrance, {"eot_status": "Granted", "eot_days": adays})
	for p in PROJECTS:
		B.sync_contract(p[0])
	late = frappe.get_all("RA Bill", filters={"project": "P-2403", "status": "Invoiced"}, pluck="name", order_by="bill_no desc", limit=1)
	if late:
		for lvl, d, note, pd in (("L1 — e-mail reminder", -16, "Reminder e-mailed to the Executive Engineer with the invoice and certificate copy", None),
				("L2 — PM call", -6, "Rahul Nair called the EE's office — bill with the treasury, payment expected next week", 5)):
			frappe.get_doc({"doctype": "Collection Follow-up", "ra_bill": late[0], "level": lvl, "followed_on": D(d), "by": "Rahul Nair" if "PM" in lvl else "Accounts",
				"note": note, "promised_date": D(pd) if pd else None}).insert(ignore_permissions=True)


# ---------------------------------------------------------------- 8. site resources: materials, vendors, stores, subcontractors, workers, equipment (A3)
MATERIALS = [  # code, name, uom, HSN, GST %, rate, group
	("CEM-OPC53", "Cement OPC 53 grade (50 kg bag)", "Bag", "2523", 18, 395, "Raw Material"),
	("TMT-FE500D", "TMT bars Fe500D", "Tonne", "7214", 18, 58500, "Raw Material"),
	("MSAND", "M-sand (manufactured sand)", "Cubic Meter", "2505", 5, 2350, "Raw Material"),
	("AGG-20", "Coarse aggregate 20 mm", "Cubic Meter", "2517", 5, 1650, "Raw Material"),
	("AAC-BLOCK", "AAC blocks 600 × 200 × 200", "Cubic Meter", "6810", 18, 4150, "Raw Material"),
	("BIT-VG30", "Bitumen VG-30", "Tonne", "2713", 18, 48500, "Raw Material"),
	("GYP-BOARD", "Gypsum board 12.5 mm (2.97 m²)", "Nos", "6809", 18, 395, "Raw Material"),
	("PLY-SHUT", "Shuttering plywood 12 mm", "Nos", "4412", 18, 1650, "Consumable"),
]
NORMS = [  # material, BOQ text, BOQ unit, per unit, wastage %
	("CEM-OPC53", "RCC M25", "Cum", 8.06, 2), ("CEM-OPC53", "PCC M10", "Cum", 4.4, 2), ("CEM-OPC53", "plaster", "Sqm", .1, 3),
	("CEM-OPC53", "PCC M15 & RCC M25", "Cum", 7.5, 2), ("CEM-OPC53", "RCC M30", "Cum", 8.6, 2),
	("TMT-FE500D", "Reinforcement", "MT", 1.0, 2.5), ("MSAND", "RCC M25", "Cum", .45, 3), ("AGG-20", "RCC M25", "Cum", .86, 3),
	("AAC-BLOCK", "AAC block", "Cum", 1.0, 3), ("BIT-VG30", "Dense bituminous", "Cum", .105, 2), ("BIT-VG30", "Bituminous concrete", "Cum", .13, 2),
	("GYP-BOARD", "Gypsum false ceiling", "Sqm", .36, 5), ("GYP-BOARD", "Gypsum & glass partitions", "Sqm", .7, 5),
]
VENDORS = [  # name, state, city, line 1, pin, PAN, group, MSME, KYC, type
	("Malabar Cements Distributors (fictional)", "Kerala", "Kochi", "Edappally Bypass", "682024", "AAFFM3311K", "Raw Material", "Small", "Verified", "Company"),
	("Kerala Steel Traders Pvt. Ltd. (fictional)", "Kerala", "Kochi", "Kalamassery Industrial Estate", "683104", "AAKCK8820L", "Raw Material", "Medium", "Verified", "Company"),
	("Periyar Aggregates & Sand LLP", "Kerala", "Aluva", "Desom Road", "683101", "AAPFP4410M", "Raw Material", "Micro", "Verified", "Company"),
	("Bengaluru TMT Mart (fictional)", "Karnataka", "Bengaluru", "Peenya Industrial Area", "560058", "AAJCB2290N", "Raw Material", "Not MSME", "Verified", "Company"),
	("Coastal Bitumen Supplies (fictional)", "Kerala", "Kozhikode", "West Hill", "673005", "AAKFC6612P", "Raw Material", "Small", "Verified", "Company"),
	("Chennai Interiors Supply Co. (fictional)", "Tamil Nadu", "Chennai", "Guindy Industrial Estate", "600032", "AAKFC7713Q", "Raw Material", "Micro", "Pending", "Company"),
	("Siporex AAC Blocks (fictional)", "Kerala", "Palakkad", "Kanjikode Industrial Area", "678621", "AAKCS5541R", "Raw Material", "Small", "Verified", "Company"),
	("Thrissur Labour Contractors", "Kerala", "Thrissur", "Round North", "680001", "ABCPT4521K", "Services", "Micro", "Verified", "Individual"),
	("Karnataka Labour Services", "Karnataka", "Bengaluru", "Hosur Road", "560068", "AAKFK3381S", "Services", "Micro", "Verified", "Company"),
	("Precision MEP Services Pvt. Ltd.", "Kerala", "Kochi", "Vyttila", "682019", "AAKCP9921T", "Services", "Small", "Verified", "Company"),
	("Southern Earthmovers (fictional)", "Kerala", "Kochi", "Aroor Bypass", "682304", "AAKFS1182U", "Services", "Micro", "Verified", "Company"),
]
STORY = {"P-2401": {"CEM-OPC53": 1.066, "TMT-FE500D": 1.018}, "P-2403": {"BIT-VG30": 1.051}, "P-2406": {"GYP-BOARD": 1.118}}
WORKERS = {  # project: [(name, trade, skill, home state, own?)]
	"P-2401": [("Biju K", "Mason", "Skilled", "", 1), ("Saji Thomas", "Carpenter", "Skilled", "", 1), ("Rajan P", "Bar bender", "Semi-skilled", "", 1), ("Anil Kumar", "Helper", "Unskilled", "", 1),
		("Subhash Mondal", "Helper", "Unskilled", "West Bengal", 1), ("Rakesh Oraon", "Helper", "Unskilled", "Jharkhand", 1), ("Shibu Varghese", "Electrician", "Skilled", "", 1),
		("Manoj M", "Mason", "Skilled", "", 0), ("Gopal Das", "Helper", "Unskilled", "Odisha", 0), ("Ratan Sardar", "Bar bender", "Semi-skilled", "West Bengal", 0),
		("Pradeep Sahu", "Helper", "Unskilled", "Odisha", 0), ("Ajith V", "Carpenter", "Skilled", "", 0)],
	"P-2402": [("Sreejith R", "Mason", "Skilled", "", 1), ("Vineeth S", "Welder", "Skilled", "", 1), ("Bablu Sheikh", "Helper", "Unskilled", "Assam", 1), ("Ramesh N", "Fitter", "Semi-skilled", "", 1),
		("Dilip Munda", "Helper", "Unskilled", "Jharkhand", 1), ("Joby Joseph", "Operator", "Highly skilled", "", 1)],
	"P-2403": [("Sunil Kumar", "Operator", "Highly skilled", "", 1), ("Abdul Rasheed", "Helper", "Unskilled", "", 1), ("Shaji C", "Mason", "Skilled", "", 1), ("Bikash Pradhan", "Helper", "Unskilled", "Odisha", 1),
		("Nandakumar", "Rigger", "Semi-skilled", "", 1)],
	"P-2405": [("Manjunath G", "Fitter", "Skilled", "", 0), ("Ravi Gowda", "Helper", "Unskilled", "", 0), ("Shivappa", "Welder", "Skilled", "", 0), ("Imran Pasha", "Helper", "Unskilled", "", 0),
		("Lokesh R", "Rigger", "Semi-skilled", "", 0)],
	"P-2406": [("Murugan S", "Carpenter", "Skilled", "", 1), ("Karthik V", "Painter", "Semi-skilled", "", 1), ("Selvam P", "Tiler", "Skilled", "", 1), ("Arun Raj", "Helper", "Unskilled", "", 1)],
}
MIN_WAGE = {"Kerala": (780, 850, 950, 1050), "Karnataka": (650, 720, 800, 880), "Tamil Nadu": (620, 690, 760, 830), "Maharashtra": (600, 670, 740, 810)}
SKILL_I = {"Unskilled": 0, "Semi-skilled": 1, "Skilled": 2, "Highly skilled": 3}
EQUIP = [  # name, kind, project, own/hired, supplier, rate, basis, reg, norm L/h, plan h, start HMR, status, insurance (days), fitness (days)
	("Tower crane TC-01 (Potain MC 85)", "Tower crane", "P-2401", "Own", None, 0, "Hour", "TC-HCI-01", 0, 220, 6210, "Working", 210, 300),
	("Concrete pump CP-03", "Concrete pump", "P-2401", "Hired", "Southern Earthmovers (fictional)", 1850, "Hour", "KL-07-BX-4410", 9, 120, 3320, "Breakdown", 120, 160),
	("Batching plant BP-02 (30 m³/h)", "Batching plant", "P-2402", "Own", None, 0, "Hour", "BP-HCI-02", 6, 200, 8840, "Working", 260, 400),
	("Transit mixer TM-05", "Transit mixer", "P-2402", "Own", None, 0, "Hour", "KL-01-CK-2207", 4.5, 180, 12450, "Working", 95, 12),
	("Excavator JCB 3DX", "Excavator", "P-2403", "Hired", "Southern Earthmovers (fictional)", 1450, "Hour", "KL-60-H-8830", 6.5, 200, 4410, "Working", 140, 200),
	("Sensor paver SP-01", "Paver", "P-2403", "Hired", "Southern Earthmovers (fictional)", 3200, "Hour", "KL-60-J-1101", 12, 150, 2290, "Working", 180, 220),
	("Vibratory roller VR-02", "Roller", "P-2403", "Own", None, 0, "Hour", "KL-07-CR-5512", 7, 180, 5630, "Working", 22, 250),
	("Motor grader MG-01", "Grader", "P-2403", "Own", None, 0, "Hour", "KL-07-CM-9081", 10, 150, 7105, "Working", 300, 9),
	("DG set 125 kVA", "DG set", "P-2405", "Own", None, 0, "Hour", "DG-HCI-07", 18, 160, 10220, "Working", 200, 400),
	("Scissor lift SL-04", "Scissor lift", "P-2406", "Hired", "Chennai Interiors Supply Co. (fictional)", 2800, "Day", "SL-CIS-04", 0, 180, 1880, "Working", 160, 300),
]


def _uom(u):
	if not frappe.db.exists("UOM", u):
		frappe.get_doc({"doctype": "UOM", "uom_name": u, "must_be_whole_number": 1 if u in ("Bag", "Nos") else 0}).insert(ignore_permissions=True)
	return u


def _vendor_addr(name):
	return frappe.db.get_value("Dynamic Link", {"link_doctype": "Supplier", "link_name": name, "parenttype": "Address"}, "parent")


def _post(doc, date):
	if doc.meta.has_field("set_posting_time"):
		doc.set_posting_time = 1
	doc.posting_date = date
	return doc


def _purchase(project, supplier, lines, date, warehouse, bill=True, pay=True, rejected=None):
	"""A receipt at the store (accepted / rejected), the supplier's bill and its payment — what the site actually bought."""
	from hipersign_trading.api import construction as CN
	from hipersign_trading.api import construction_site as S

	addr = frappe.db.get_value("Project", project, "hs_cn_address") if project else CN.branch_address(CO)
	pr = frappe.get_doc({"doctype": "Purchase Receipt", "company": CO, "supplier": supplier, "project": project, "set_warehouse": warehouse, "supplier_delivery_note": f"DC/{date[2:].replace('-', '')}",
		"lr_no": "KL-07-" + str(1000 + len(supplier) * 37 % 8999), "billing_address": addr, "shipping_address": addr,
		"items": [{"item_code": c, "qty": q, "received_qty": q + ((rejected or {}).get(c) or 0), "rejected_qty": (rejected or {}).get(c) or 0, "rate": r, "warehouse": warehouse,
			"rejected_warehouse": S.rejected_store(CO) if (rejected or {}).get(c) else None, "project": project} for c, q, r in lines]})
	_post(pr, date)
	S._apply_taxes(pr, S.input_tax_template(CO, addr, supplier))
	pr.insert(ignore_permissions=True)
	pr.submit()
	if not bill:
		return pr.name
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice

	pi = make_purchase_invoice(pr.name)
	pi.bill_no, pi.bill_date = f"INV/{pr.name[-5:]}", date
	_post(pi, add_days(date, 1))
	pi.due_date = add_days(date, 45)
	pi.insert(ignore_permissions=True)
	pi.submit()
	if pay and getdate(add_days(date, 30)) < getdate(today()):
		pe = frappe.get_doc({"doctype": "Payment Entry", "payment_type": "Pay", "company": CO, "posting_date": add_days(date, 30), "party_type": "Supplier", "party": supplier,
			"paid_from": CN.bank_account(CO), "paid_to": pi.credit_to, "paid_amount": pi.outstanding_amount, "received_amount": pi.outstanding_amount, "reference_no": f"NEFT/{pi.name}",
			"reference_date": add_days(date, 30), "references": [{"reference_doctype": "Purchase Invoice", "reference_name": pi.name, "allocated_amount": pi.outstanding_amount}]})
		pe.setup_party_account_field()
		pe.set_missing_values()
		pe.insert(ignore_permissions=True)
		pe.submit()
	return pr.name


def _issue(project, lines, date, warehouse, to):
	from hipersign_trading.api import projects as P

	acc = P.accounts(CO)
	se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Issue", "purpose": "Material Issue", "company": CO, "project": project, "remarks": to,
		"items": [{"item_code": c, "qty": q, "s_warehouse": warehouse, "expense_account": acc.heads["Materials"], "project": project, "cost_center": _cc()} for c, q in lines if q > 0]})
	_post(se, date)
	se.insert(ignore_permissions=True)
	se.submit()


def cn_resources(c):
	from hipersign_trading.api import construction as CN
	from hipersign_trading.api import construction_site as S
	from hipersign_trading.api import projects as P

	if not frappe.db.exists("DocType", "Material Norm") or frappe.db.exists("Material Norm", {"item": "CEM-OPC53"}):
		return
	_uom("Bag")
	t18 = frappe.db.get_value("Item Tax Template", {"gst_rate": 18, "company": CO}) if frappe.db.exists("DocType", "Item Tax Template") else None
	t5 = frappe.db.get_value("Item Tax Template", {"gst_rate": 5, "company": CO}) if frappe.db.exists("DocType", "Item Tax Template") else None
	for code, name, uom, hsn, gst, rate, grp in MATERIALS:
		if frappe.db.exists("Item", code):
			continue
		it = frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": name, "item_group": grp, "stock_uom": uom, "is_stock_item": 1, "is_purchase_item": 1, "is_sales_item": 0,
			"valuation_rate": rate, "include_item_in_manufacturing": 0})
		if it.meta.has_field("gst_hsn_code") and frappe.db.exists("GST HSN Code", hsn):
			it.gst_hsn_code = hsn
		tt = t5 if gst == 5 else t18
		if tt:
			it.append("taxes", {"item_tax_template": tt})
		it.insert(ignore_permissions=True)
	for item, match, unit, per, w in NORMS:
		frappe.get_doc({"doctype": "Material Norm", "item": item, "boq_match": match, "boq_unit": unit, "qty_per_unit": per, "wastage_pct": w, "recovery_factor": 1.5}).insert(ignore_permissions=True)
	for name, state, city, line1, pin, pan, grp, msme, kyc, stype in VENDORS:
		if not frappe.db.exists("Supplier", name):
			sg = "Services" if grp == "Services" and frappe.db.exists("Supplier Group", "Services") else frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
			su = frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_group": sg, "supplier_type": stype, "country": "India", "hs_kyc_status": kyc,
				"hs_msme_category": msme, "hs_msme_no": f"UDYAM-{STATE_CODE[state][:2]}-0{len(name) % 9}-00{pin[-5:]}" if msme != "Not MSME" else None})
			if su.meta.has_field("gstin"):
				su.gstin, su.gst_category = gstin(STATE_CODE[state], pan), "Registered Regular"
			if su.meta.has_field("pan"):
				su.pan = pan
			su.insert(ignore_permissions=True)
		_address(name, "Supplier", name, state, city, line1, pin, gstin(STATE_CODE[state], pan))
	live = [p for p in PROJECTS if p[11] < 22]
	cs = S.central_store(CO)
	# central store: opening stock (and plywood idle since summer — dead stock)
	_purchase(None, "Malabar Cements Distributors (fictional)", [("CEM-OPC53", 6000, 390)], D(-75), cs)
	_purchase(None, "Kerala Steel Traders Pvt. Ltd. (fictional)", [("TMT-FE500D", 120, 57800)], D(-70), cs)
	_purchase(None, "Chennai Interiors Supply Co. (fictional)" if False else "Kerala Steel Traders Pvt. Ltd. (fictional)", [("PLY-SHUT", 400, 1650)], D(-130), cs)
	# what each site bought and used: the work measured × the norm, with the story's over-use
	vend = {"CEM-OPC53": "Malabar Cements Distributors (fictional)", "TMT-FE500D": "Kerala Steel Traders Pvt. Ltd. (fictional)", "MSAND": "Periyar Aggregates & Sand LLP",
		"AGG-20": "Periyar Aggregates & Sand LLP", "AAC-BLOCK": "Siporex AAC Blocks (fictional)", "BIT-VG30": "Coastal Bitumen Supplies (fictional)", "GYP-BOARD": "Chennai Interiors Supply Co. (fictional)"}
	price = {m[0]: m[5] for m in MATERIALS}
	for p in live:
		pid = p[0]
		w = P.site_warehouse(pid)
		st = S.material_status(pid)
		start = R(p[10][6])
		for x in st:
			if x.theory <= 0:
				continue
			f = STORY.get(pid, {}).get(x.item, 1 + (x.wastage - .8) / 100)
			used = round(x.theory * f, 1 if frappe.get_cached_value("Item", x.item, "stock_uom") not in ("Bag", "Nos") else 0)
			stock = round(used * .06, 1 if frappe.get_cached_value("Item", x.item, "stock_uom") not in ("Bag", "Nos") else 0)
			v = vend[x.item]
			if pid == "P-2405" and x.item == "TMT-FE500D":
				v = "Bengaluru TMT Mart (fictional)"
			buy = used + stock
			chunks = [.55, .45]
			span = max(60, date_diff(today(), start) - 20)
			for k, share in enumerate(chunks):
				d = add_days(start, int(span * (.35 + .5 * k)))
				_purchase(pid, v, [(x.item, round(buy * share, 1) if frappe.get_cached_value("Item", x.item, "stock_uom") not in ("Bag", "Nos") else round(buy * share),
					price[x.item] * (1 + .01 * k))], d, w)
				_issue(pid, [(x.item, round(used * share, 1) if frappe.get_cached_value("Item", x.item, "stock_uom") not in ("Bag", "Nos") else round(used * share))],
					add_days(d, 8), w, "To the work fronts — BOQ " + ", ".join(x.lines[:3]))
		CN.clear_cache()
	# a receipt with rejected bags, not billed yet
	_purchase("P-2405", "Malabar Cements Distributors (fictional)" if False else "Bengaluru TMT Mart (fictional)", [("CEM-OPC53", 480, 405)], D(-3), P.site_warehouse("P-2405"), bill=False,
		rejected={"CEM-OPC53": 20})
	# indents: above the BOQ need (waits for the PM), within it, approved with three quotations (lowest basic is not L1 on landed cost)
	def indent(pid, item, qty, days, submit=False):
		m = frappe.get_doc({"doctype": "Material Request", "material_request_type": "Purchase", "company": CO, "hs_project": pid, "transaction_date": D(days), "schedule_date": D(days + 10),
			"set_warehouse": P.site_warehouse(pid), "items": [{"item_code": item, "qty": qty, "schedule_date": D(days + 10), "warehouse": P.site_warehouse(pid), "project": pid}]})
		m.insert(ignore_permissions=True)
		if submit:
			m.submit()
		return m
	indent("P-2401", "CEM-OPC53", 15500, -2)
	indent("P-2402", "TMT-FE500D", 45, -1)
	m = indent("P-2402", "CEM-OPC53", 2400, -9, submit=True)
	for sup, rate, freight, unl, tech in (("Malabar Cements Distributors (fictional)", 392, 9600, 4800, 1), ("Periyar Aggregates & Sand LLP", 386, 31200, 7200, 1),
			("Coastal Bitumen Supplies (fictional)", 381, 12000, 4800, 0)):
		from erpnext.stock.doctype.material_request.material_request import make_supplier_quotation

		sq = make_supplier_quotation(m.name)
		sq.supplier, sq.transaction_date, sq.valid_till = sup, D(-6), D(24)
		for i in sq.items:
			i.rate = rate
		sq.hs_project, sq.hs_freight, sq.hs_unloading, sq.hs_tech_ok = "P-2402", freight, unl, tech
		addr = frappe.db.get_value("Project", "P-2402", "hs_cn_address")
		sq.billing_address = addr
		S._apply_taxes(sq, S.input_tax_template(CO, addr, sup))
		sq.insert(ignore_permissions=True)
		sq.submit()
	# an open PO waiting for delivery (TMT for P-2402), and its rate contract
	addr = frappe.db.get_value("Project", "P-2402", "hs_cn_address")
	po = frappe.get_doc({"doctype": "Purchase Order", "company": CO, "supplier": "Kerala Steel Traders Pvt. Ltd. (fictional)", "transaction_date": D(-5), "schedule_date": D(4),
		"hs_project": "P-2402", "hs_cost_head": "Materials", "billing_address": addr, "shipping_address": addr, "set_warehouse": P.site_warehouse("P-2402"),
		"items": [{"item_code": "TMT-FE500D", "qty": 38, "rate": 58200, "schedule_date": D(4), "warehouse": P.site_warehouse("P-2402"), "project": "P-2402"}]})
	S._apply_taxes(po, S.input_tax_template(CO, addr, po.supplier))
	po.insert(ignore_permissions=True)
	po.submit()
	for sup, item, qty, rate, frm, to, drawn in (("Malabar Cements Distributors (fictional)", "CEM-OPC53", 60000, 388, -150, 120, 41200),
			("Kerala Steel Traders Pvt. Ltd. (fictional)", "TMT-FE500D", 400, 57900, -200, 20, 372), ("Siporex AAC Blocks (fictional)", "AAC-BLOCK", 3000, 4100, -90, 200, 1100)):
		bo = frappe.get_doc({"doctype": "Blanket Order", "blanket_order_type": "Purchasing", "supplier": sup, "company": CO, "from_date": D(frm), "to_date": D(to),
			"items": [{"item_code": item, "qty": qty, "rate": rate}]})
		bo.insert(ignore_permissions=True)
		bo.submit()
		frappe.db.set_value("Blanket Order Item", {"parent": bo.name}, "ordered_qty", drawn)
	# transfers from the central store: delivered, in transit for two days, requested
	tr = S.transit_store(CO)
	for pid, item, qty, days, status, veh, drv in (("P-2401", "CEM-OPC53", 1200, -20, "Delivered", "KL-07-CB-3321", "Sathyan K"), ("P-2401", "TMT-FE500D", 18, -12, "Delivered", "KL-07-CD-8810", "Rafeeq M"),
			("P-2402", "CEM-OPC53", 1500, -2, "In transit", "KL-07-CB-3321", "Sathyan K"), ("P-2406", "PLY-SHUT", 0, -1, "Requested", "", "")):
		if status == "Requested":
			item, qty = "TMT-FE500D", 6
		se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Transfer", "purpose": "Material Transfer", "company": CO, "project": pid,
			"hs_destination": P.site_warehouse(pid), "hs_vehicle": veh, "hs_driver": drv, "hs_driver_mobile": "98470 12345" if drv else None,
			"hs_eway_bill": f"3410 {abs(days) * 7919 % 9999:04d} {len(pid) * 1234:04d}" if drv else None, "hs_transfer_status": "Requested",
			"items": [{"item_code": item, "qty": qty, "s_warehouse": cs, "t_warehouse": tr if status != "Requested" else P.site_warehouse(pid)}]})
		_post(se, D(days))
		if status != "Requested":
			se.add_to_transit = 1
			se.hs_transfer_status = "In transit"
		se.insert(ignore_permissions=True)
		if status == "Requested":
			continue
		se.submit()
		if status == "Delivered":
			from erpnext.stock.doctype.stock_entry.stock_entry import make_stock_in_entry

			n = make_stock_in_entry(se.name)
			for d in n.items:
				d.t_warehouse = P.site_warehouse(pid)
			_post(n, D(days + 1))
			n.project, n.hs_transfer_status = pid, "Delivered"
			n.insert(ignore_permissions=True)
			n.submit()
			frappe.db.set_value("Stock Entry", se.name, "hs_transfer_status", "Delivered")
	# subcontractors: work orders, running bills (paid, approved, certified on hold), labour-law documents
	from frappe.utils import get_first_day, add_months

	for sup, months, missing in (("Thrissur Labour Contractors", 3, False), ("Karnataka Labour Services", 3, True)):
		for k in range(1, months + 1):
			mth = get_first_day(add_months(today(), -k))
			ok = not (missing and k == 1)
			frappe.get_doc({"doctype": "Labour Compliance", "supplier": sup, "company": CO, "month": mth, "workers": 14 if sup.startswith("Thrissur") else 9,
				"clra_licence": "CLRA/KL/2025/0412" if sup.startswith("Thrissur") else "CLRA/KA/2024/1180", "licence_valid_to": D(300) if sup.startswith("Thrissur") else D(30),
				"wage_register": 1, "pf_ecr": 1 if ok else 0, "esi_challan": 1 if ok else 0}).insert(ignore_permissions=True)
	WO = [("P-2401", "Labour — RCC frame & masonry", "Thrissur Labour Contractors", "Labour only (materials issued free)", [("2.2", 1450), ("3.1", 900)], 4, 1),
		("P-2401", "Internal plumbing & sanitary", "Precision MEP Services Pvt. Ltd.", "Item rate (with materials)", [("6.1", None)], 3, 2),
		("P-2405", "Labour — PEB erection support & flooring", "Karnataka Labour Services", "Labour only (materials issued free)", [("3.2", 160), ("4.1", 140)], 3, 1),
		("P-2403", "Road marking & signage", "Precision MEP Services Pvt. Ltd.", "Item rate (with materials)", [("5.1", None)], 0, 0)]
	for pid, scope, sup, kind, its, nbills, tdsp in WO:
		b = CN.boq(pid)
		lines = {r.item_no: r for r in b.items}
		items = []
		for no, rate in its:
			r = lines[no]
			items.append({"item_no": no, "description": r.description, "unit": r.unit, "qty": r.qty, "rate": rate if rate else round(flt(r.rate) * .82, 2)})
		w = frappe.get_doc({"doctype": "Subcontractor Work Order", "project": pid, "supplier": sup, "scope": scope, "kind": kind, "wo_date": add_days(R(next(p for p in PROJECTS if p[0] == pid)[10][6]), 30),
			"tds_pct": tdsp, "retention_pct": 5, "gst_rate": 18, "items": items, "status": "Draft"})
		w.insert(ignore_permissions=True)
		if not nbills:
			continue
		w.db_set("status", "Active")
		for k in range(1, nbills + 1):
			last = k == nbills
			bi = []
			for r in items:
				done = flt(lines[r["item_no"]].measured_pct) / 100 * flt(r["qty"]) * (k / (nbills + .6))
				prev = flt(lines[r["item_no"]].measured_pct) / 100 * flt(r["qty"]) * ((k - 1) / (nbills + .6))
				bi.append({"item_no": r["item_no"], "this_qty": round(done - prev, 3)})
			d = D(-120 + k * 28)
			sb = frappe.get_doc({"doctype": "Subcontractor Bill", "work_order": w.name, "bill_no": k, "bill_date": d, "period_to": add_days(d, -3), "supplier_invoice_no": f"RB{k:02d}/{w.name[-3:]}",
				"items": bi, "material_recovery": 393000 if (pid == "P-2401" and kind.startswith("Labour") and last) else 0})
			sb.insert(ignore_permissions=True)
			sb.db_set({"status": "Certified", "certified_by": next(p for p in PROJECTS if p[0] == pid)[9]})
			if last and pid == "P-2405":
				continue  # certified, on hold — last month's PF / ESI missing
			if last and pid == "P-2401" and kind.startswith("Item"):
				continue  # certified, waiting for the PM
			sb.db_set("approved_by", next(p for p in PROJECTS if p[0] == pid)[7])
			S.make_sub_invoice(sb.name, add_days(d, 2))
			if not last:
				S.pay_sub(sb.name, add_days(d, 16))
	# own workers, minimum wages, advances and the weekly musters (two weeks paid, this week to approve)
	for st, rates in MIN_WAGE.items():
		for sk, i in SKILL_I.items():
			frappe.get_doc({"doctype": "Minimum Wage", "state": st, "skill": sk, "daily_rate": rates[i], "effective_from": "2026-10-01"}).insert(ignore_permissions=True)
	con = {"P-2401": "Thrissur Labour Contractors", "P-2405": "Karnataka Labour Services"}
	k = 0
	for pid, ws in WORKERS.items():
		st = BRANCHES[next(p for p in PROJECTS if p[0] == pid)[5]][1]
		for name, trade, skill, home, own in ws:
			k += 1
			rate = MIN_WAGE[st][SKILL_I[skill]] + (60 if skill in ("Skilled", "Highly skilled") else 30) + (k % 3) * 20
			frappe.get_doc({"doctype": "Site Worker", "worker_name": name, "project": pid, "contractor": None if own else con.get(pid), "trade": trade, "skill": skill, "state": st,
				"daily_rate": rate, "status": "Active", "joined_on": D(-200 + k * 3), "upi_id": f"{name.split()[0].lower()}{k}@okaxis" if own else None, "mobile": f"9{(846000000 + k * 7919) % 1000000000:09d}",
				"aadhaar_last4": f"{(k * 3571) % 10000:04d}", "home_state": home, "pf_uan": f"10{k * 917331 % 10**10:010d}" if own else None,
				"bocw_reg_no": None if k % 7 == 0 else f"BOCW/{st[:2].upper()}/{24000 + k}", "id_expiry": D(20) if k % 11 == 0 else D(400),
				"induction_done": 0 if k % 9 == 0 else 1, "ppe_issued": 0 if k % 8 == 0 else 1, "police_verified": 0 if (home and k % 2) else 1, "medical_fit": 1}).insert(ignore_permissions=True)
	for wname, amt, days, status in (("Subhash Mondal", 9000, -24, "Paid"), ("Bablu Sheikh", 3000, -18, "Paid"), ("Rakesh Oraon", 6000, -1, "Requested"),
			("Abdul Rasheed", 2500, -2, "Requested"), ("Arun Raj", 3500, -3, "Approved")):
		wk = frappe.db.get_value("Site Worker", {"worker_name": wname})
		a = frappe.get_doc({"doctype": "Worker Advance", "worker": wk, "amount": amt, "requested_on": D(days), "reason": "Family needs — sending money home" if days < -10 else "Medical expense"})
		a.insert(ignore_permissions=True)
		if status in ("Approved", "Paid"):
			a.db_set("status", "Approved")
		if status == "Paid":
			S.pay_advance(a.name, D(days + 1))
	for pid in ("P-2401", "P-2402", "P-2403", "P-2406"):
		ws = frappe.get_all("Site Worker", filters={"project": pid, "contractor": ["is", "not set"]}, fields=["name", "daily_rate"])
		for wk in (2, 1, 0):
			start = S.week_start(D(-7 * wk - 7))
			m = frappe.get_doc({"doctype": "Weekly Muster", "project": pid, "week_start": start,
				"rows": [{"worker": w.name, "rate": w.daily_rate, "days": 6 - ((i + wk) % 4 == 0), "ot_hours": (i * 3 + wk) % 5} for i, w in enumerate(ws)]})
			m.insert(ignore_permissions=True)
			if wk:
				m.db_set({"status": "Approved", "approved_by": next(p for p in PROJECTS if p[0] == pid)[7]})
				S.pay_muster(m.name, add_days(start, 7))
	# plant & equipment: register, ten days of log sheets, maintenance
	for name, kind, pid, own, sup, rate, basis, reg, norm, plan, hmr, status, ins, fit in EQUIP:
		e = frappe.get_doc({"doctype": "Construction Equipment", "equipment_name": name, "kind": kind, "company": CO, "project": pid, "ownership": own, "supplier": sup, "hire_rate": rate,
			"hire_basis": basis, "reg_no": reg, "diesel_norm_lph": norm, "planned_hours_month": plan, "status": status, "service_interval": 250,
			"next_service_hmr": hmr + 95 if kind != "Grader" else hmr + 60, "insurance_expiry": D(ins), "fitness_expiry": D(fit)})
		e.insert(ignore_permissions=True)
		cur = hmr
		for d in range(-10, 0):
			if getdate(D(d)).weekday() == 6 or (status == "Breakdown" and d > -4):
				continue
			hrs = round(plan / 26 * (.75 + ((d * 7) % 5) / 10), 1)
			idle = round(hrs * .08, 1)
			diesel = round(hrs * norm * (1.18 if kind == "Excavator" else 1.0), 0) if norm else 0
			frappe.get_doc({"doctype": "Equipment Log", "equipment": e.name, "project": pid, "log_date": D(d), "operator": "Sunil Kumar" if pid == "P-2403" else "Joby Joseph",
				"start_hmr": cur, "end_hmr": round(cur + hrs + idle, 1), "idle_hours": idle, "diesel_litres": diesel,
				"work_done": {"Tower crane": "Lifting steel & shuttering — Block B", "Batching plant": "Concrete for podium slab", "Excavator": "Drain excavation Ch. 3+100",
					"Paver": "DBM laying Ch. 2+650", "Roller": "Compaction behind the paver", "Grader": "GSB grading Ch. 4+000"}.get(kind, "Site work")}).insert(ignore_permissions=True)
			cur = round(cur + hrs + idle, 1)
	for name, d, job, down, cost, by, desc in (("Concrete pump CP-03", -3, "Hydraulics", 26, 48000, "Southern Earthmovers", "Boom cylinder seal failed — pump off site for repair"),
			("Tower crane TC-01 (Potain MC 85)", -16, "Scheduled service", 6, 18500, "Potain service engineer", "500-hour service, wire rope inspection"),
			("Excavator JCB 3DX", -9, "Tyres & tracks", 4, 22000, "Southern Earthmovers", "Rear tyre replaced"),
			("Transit mixer TM-05", -22, "Scheduled service", 5, 14200, "Own workshop", "Drum rollers greased, oil change"),
			("Vibratory roller VR-02", -30, "Breakdown", 18, 36500, "Own workshop", "Vibration motor rewound"),
			("Batching plant BP-02 (30 m³/h)", -12, "Electrical", 3, 9800, "Own electrician", "Load cell recalibrated")):
		e = frappe.db.get_value("Construction Equipment", {"equipment_name": name})
		frappe.get_doc({"doctype": "Equipment Maintenance", "equipment": e, "project": frappe.db.get_value("Construction Equipment", e, "project"), "job_date": D(d), "job_type": job,
			"downtime_hours": down, "cost": cost, "done_by": by, "description": desc}).insert(ignore_permissions=True)


# ---------------------------------------------------------------- 9. quality, safety, drawings, handover (A4)
ITP = {  # template: (activity, test, standard, point, frequency, BOQ item, one test per)
	"bld": [("Excavation & foundation bed", "Bearing strata and levels", "IS 1200 / soil report", "Hold", "Each footing", "1.1", 2500),
		("Reinforcement", "Pre-pour check — bars, cover, laps", "IS 456 cl. 26", "Hold", "Each pour", "2.3", 20),
		("RCC M25 concrete", "Slump and cubes", "IS 1199, IS 516", "Witness", "Each pour (cubes per 50 m³)", "2.2", 150),
		("Centering & shuttering", "Line, level, props", "IS 14687", "Hold", "Each pour", "2.4", 1500),
		("AAC block masonry", "Line, plumb, joints", "IS 2185-3", "Review", "Each floor", "3.1", 120),
		("Internal plaster", "Thickness, plumb, finish", "IS 1661", "Review", "Per 1,000 m²", "4.1", 2500),
		("Vitrified tiling", "Level, hollowness, joints", "IS 15622", "Witness", "Per 500 m²", "4.2", 1200)],
	"road": [("Embankment", "Compaction — field density", "MoRTH 305, IS 2720-28", "Hold", "Per 1,000 m² per layer", "1.2", 5000),
		("Granular sub-base", "Gradation, density", "MoRTH 401", "Hold", "Per 1,500 m³", "2.1", 1500),
		("Wet mix macadam", "Gradation, density, thickness", "MoRTH 406", "Hold", "Per 1,500 m³", "2.2", 1500),
		("Dense bituminous macadam", "Binder content, density, thickness", "MoRTH 505", "Witness", "Per 400 t mix", "2.3", 350),
		("Bituminous concrete", "Binder content, density, surface", "MoRTH 507", "Witness", "Per 400 t mix", "2.4", 300),
		("Box culverts", "Pre-pour and cubes", "IRC 112", "Hold", "Each pour", "3.1", 150)],
	"peb": [("Anchor bolts", "Alignment and level", "IS 800", "Hold", "Each bay", "2.3", 60), ("PEB erection", "Plumb, bolt torque", "IS 800 / MBMA", "Witness", "Per 100 t", "3.1", 120),
		("FM2 floor", "Flatness FF/FL, thickness", "ACI 117", "Witness", "Per 2,000 m²", "4.1", 2500)],
	"fit": [("Gypsum ceiling", "Grid level, board fixing", "IS 2095", "Review", "Per floor", "1.1", 900), ("Partitions", "Line, plumb, acoustic seal", "Specification", "Review", "Per floor", "1.2", 900),
		("Joinery", "Shop drawing, finish, fittings", "Approved samples", "Witness", "Per 20 sets", "3.1", 20)],
}
DRAWINGS = {  # project: (no, title, discipline, revisions (last is current), current status)
	"P-2401": [("STR-B-101", "Block B — transfer beams level 2", "Structural", ["R0", "R1"], "GFC"), ("STR-B-102", "Block B — slab at level 3", "Structural", ["R0"], "For approval"),
		("ARC-A-201", "Block A — typical floor plan", "Architectural", ["R0", "R1", "R2"], "GFC"), ("MEP-P-301", "Plumbing risers — Block A", "MEP", ["R0"], "GFC")],
	"P-2402": [("STR-201", "Basement raft & retaining walls", "Structural", ["R0", "R1"], "GFC"), ("ARC-110", "Ground floor & entrance lobby", "Architectural", ["R0"], "GFC"),
		("STR-215", "Podium slab — level 1", "Structural", ["R0"], "For approval")],
	"P-2403": [("RD-PP-03", "Plan & profile Ch. 2+000 to 4+000", "Civil / roads", ["R0", "R1"], "GFC"), ("CUL-C9", "Box culvert C-9 at Ch. 3+950", "Civil / roads", ["R0"], "For approval"),
		("CUL-C7", "Box culvert C-7 at Ch. 3+820", "Civil / roads", ["R0"], "GFC")],
	"P-2405": [("PEB-GA-01", "PEB general arrangement", "Structural", ["R0", "R1"], "GFC"), ("FLR-01", "FM2 floor joint layout", "Civil / roads", ["R0"], "GFC")],
	"P-2406": [("INT-GR-05", "Guest room — typical joinery", "Interior", ["R0", "R1", "R2"], "GFC"), ("INT-LB-01", "Lobby ceiling & lighting", "Interior", ["R0"], "For approval")],
}


def cn_quality(c):
	from hipersign_trading.api import construction as CN
	from hipersign_trading.api import construction_qhse as Q

	if not frappe.db.exists("DocType", "ITP Item") or frappe.db.exists("ITP Item", {"project": "P-2401"}):
		return
	live = [p for p in PROJECTS if p[11] < 22]
	who = {p[0]: p for p in PROJECTS}
	# inspection & test plan, with the inspections behind it (two lines behind on purpose)
	behind = {("P-2401", "2.3"): 2, ("P-2403", "2.3"): 1, ("P-2406", "1.2"): 1}
	for p in live:
		pid, tpl, eic = p[0], p[3], p[13]
		for act, test, std, point, freq, boq_item, per in ITP[tpl]:
			i = frappe.get_doc({"doctype": "ITP Item", "project": pid, "activity": act, "test": test, "standard": std, "point": point, "frequency": freq, "boq_item": boq_item,
				"per_qty": per, "acceptance": "As per the standard and the approved specification"})
			i.insert(ignore_permissions=True)
			due = Q.itp_due(i)
			for k in range(max(0, due - behind.get((pid, boq_item), 0))):
				frappe.get_doc({"doctype": "Inspection Request", "project": pid, "itp_item": i.name, "activity": act, "location": LOC[tpl][k % len(LOC[tpl])], "boq_item": boq_item,
					"requested_on": D(-6 - k * 9), "wanted_on": D(-5 - k * 9), "inspected_on": D(-5 - k * 9), "inspector": eic, "requested_by": p[8], "status": "Approved",
					"result_note": "Accepted — proceed"}).insert(ignore_permissions=True)
			i.save(ignore_permissions=True)
	waiting = [("P-2401", "Reinforcement", "Block B — 4th floor slab", 0), ("P-2401", "Centering & shuttering", "Block B — 4th floor slab", -1),
		("P-2402", "RCC M25 concrete", "Podium — grid C/4–C/9", 1), ("P-2403", "Dense bituminous macadam", "Ch. 2+650 to 2+900 RHS", -2), ("P-2406", "Partitions", "Guest floor 7", 1)]
	for pid, act, loc, d in waiting:
		it = frappe.db.get_value("ITP Item", {"project": pid, "activity": act})
		frappe.get_doc({"doctype": "Inspection Request", "project": pid, "itp_item": it, "activity": act, "location": loc, "requested_on": D(d - 1), "wanted_on": D(d),
			"inspector": who[pid][13], "requested_by": who[pid][8]}).insert(ignore_permissions=True)
	r = frappe.get_doc({"doctype": "Inspection Request", "project": "P-2402", "itp_item": frappe.db.get_value("ITP Item", {"project": "P-2402", "activity": "Reinforcement"}),
		"activity": "Reinforcement", "location": "Block A — 5th floor columns", "requested_on": D(-4), "wanted_on": D(-3), "inspector": who["P-2402"][13], "requested_by": who["P-2402"][8]})
	r.insert(ignore_permissions=True)
	Q._a_ir_reject(r.name, frappe._dict(note="Cover blocks missing at column C-6; lap length short on two bars"))
	# cube tests: passes, one failure at 28 days, results awaited
	cubes = [("P-2401", "Block A — 4th floor slab", "M25", -40, (21.4, 22.0, 20.9), (33.8, 34.6, 32.9)), ("P-2401", "Block B — 3rd floor slab", "M25", -32, (20.6, 21.8, 22.2), (32.4, 33.1, 34.0)),
		("P-2401", "Block B — staircase core", "M25", -12, (19.8, 20.4, 21.1), None), ("P-2401", "Block B — 4th floor columns", "M25", -4, None, None),
		("P-2402", "Basement raft — pour 3", "M30", -55, (24.8, 25.6, 24.1), (39.2, 38.4, 40.1)), ("P-2402", "Podium slab — pour 2", "M25", -36, (15.2, 14.6, 15.9), (26.4, 22.6, 25.1)),
		("P-2402", "Retaining wall RW-2", "M30", -10, (25.1, 24.4, 26.0), None),
		("P-2403", "Culvert C-7 raft", "M30", -45, (24.2, 25.0, 23.8), (37.6, 38.8, 36.9)), ("P-2403", "Culvert C-7 walls", "M30", -9, (23.9, 24.6, 24.1), None),
		("P-2405", "Pedestals bay 5–8", "M25", -60, (20.9, 21.5, 22.0), (33.0, 32.2, 34.4))]
	for pid, pour, grade, d, s7, s28 in cubes:
		frappe.get_doc(dict({"doctype": "Cube Test", "project": pid, "pour": pour, "grade": grade, "cast_on": D(d), "lab": "Site laboratory" if pid != "P-2403" else "NABL lab, Kannur"},
			**({"s7_1": s7[0], "s7_2": s7[1], "s7_3": s7[2]} if s7 else {}), **({"s28_1": s28[0], "s28_2": s28[1], "s28_3": s28[2]} if s28 else {}))).insert(ignore_permissions=True)
	ncrs = [("P-2402", "Podium slab pour 2 — 28-day cubes below M25", "Major", "Own team", None, -8, 6, "Cube results 22.6–26.4 N/mm² against 28 required", None, None, 0),
		("P-2402", "Honeycombing at retaining wall RW-1", "Major", "Subcontractor", None, -15, -2, "Honeycombing over 1.2 m² at the wall base", None, None, 0),
		("P-2401", "Cover blocks missing in slab reinforcement", "Minor", "Subcontractor", "Thrissur Labour Contractors", -30, -20, "Bottom cover not maintained at grid B/3",
			"Cover blocks not stocked at the work front", "Cover blocks issued with steel; checked in the pre-pour list", 18500),
		("P-2403", "DBM thickness short Ch. 2+650 to 2+780", "Major", "Own team", None, -11, -1, "Cores show 48–52 mm against 60 mm", None, None, 0),
		("P-2405", "Anchor bolts out of position — bay 7", "Major", "Subcontractor", "Karnataka Labour Services", -70, -50, "Four bolts 25 mm off grid",
			"Template not fixed before the pour", "Chemical anchors after the structural engineer's approval; templates checked by QA", 64000),
		("P-2406", "Partition alignment — guest floor 6", "Minor", "Own team", None, -6, 8, "Partition 12 mm out of plumb at rooms 612–614", None, None, 0)]
	for pid, title, sev, resp, sup, raised, close_by, desc, rc, ca, cost in ncrs:
		n = frappe.get_doc({"doctype": "NCR", "project": pid, "title": title, "severity": sev, "responsible": resp, "supplier": sup, "raised_on": D(raised), "close_by": D(close_by),
			"description": desc, "root_cause": rc, "corrective_action": ca, "rework_cost": cost})
		n.insert(ignore_permissions=True)
		if rc:
			n.db_set({"status": "Closed", "closed_on": D(close_by - 3)})
	# safety
	incs = [("P-2402", -38, "Lost time injury (LTI)", "Basement — grid D/2", "Dilip Munda", 21, "Fell from a scaffold platform without a toe board; fractured wrist",
			"Toe board missing after the scaffold was shifted", "Scaffold tags and daily inspection by the supervisor; refresher on scaffolds", 1),
		("P-2401", -9, "First aid", "Block B — 4th floor", "Subhash Mondal", 0, "Cut on the hand while handling binding wire", "Gloves not worn", "Gloves enforced at the bar-bending yard", 1),
		("P-2401", -3, "Near miss", "Block A — hoist", "", 0, "Bucket of debris slipped from the material hoist", None, None, 0),
		("P-2403", -5, "Property damage", "Ch. 3+100", "", 0, "Tipper reversed into the KSEB pole guard", None, None, 0),
		("P-2406", -2, "Near miss", "Guest floor 7", "", 0, "Unsecured ladder slipped on a polished floor", None, None, 0),
		("P-2405", -16, "Near miss", "Bay 6", "", 0, "Wind lifted a roof sheet during fixing", "Sheets not tied down at end of shift", "Wind speed check before sheeting; tie-down at every break", 1)]
	for pid, d, kind, loc, person, lost, desc, rc, act, closed in incs:
		i = frappe.get_doc({"doctype": "Safety Incident", "project": pid, "incident_date": D(d), "kind": kind, "location": loc, "person": person, "days_lost": lost, "description": desc,
			"root_cause": rc, "action": act, "reported_by": "Sajith Kumar"})
		i.insert(ignore_permissions=True)
		if closed:
			i.db_set("status", "Closed")
	for pid, kind, loc, work, frm, to, status in (("P-2401", "Work at height", "Block B — 5th floor edge", "Edge shuttering and safety net fixing", 0, 3, "Requested"),
			("P-2402", "Hot work", "Basement — pump room", "Welding of pipe supports", 0, 1, "Requested"), ("P-2401", "Lifting operation", "Tower crane TC-01", "Lifting the lift-machine room steel", -1, 2, "Issued"),
			("P-2403", "Excavation", "Ch. 3+950 culvert C-9", "Excavation 2.4 m deep with shoring", -2, 4, "Issued"), ("P-2406", "Electrical isolation", "Guest floor 6 DB", "Shifting the sub-main", -6, -5, "Closed")):
		w = frappe.get_doc({"doctype": "Work Permit", "project": pid, "kind": kind, "location": loc, "work": work, "valid_from": D(frm), "valid_to": D(to), "requested_by": who[pid][8],
			"precautions": "Barricading, trained crew, supervisor present, PPE checked"})
		w.insert(ignore_permissions=True)
		if status != "Requested":
			w.db_set({"status": status, "issued_by": "Sajith Kumar"})
	topics = ["Working at height — harness and anchor points", "Scaffold inspection tags", "Housekeeping and stacking", "Handling of cement and PPE", "Monsoon — slips and electrical safety",
		"Traffic management on live roads", "Hot work and fire watch"]
	lang = {"P-2401": "Malayalam", "P-2402": "Malayalam", "P-2403": "Malayalam", "P-2405": "Kannada", "P-2406": "Tamil"}
	for p in live:
		for k in range(3):
			frappe.get_doc({"doctype": "Toolbox Talk", "project": p[0], "talk_date": D(-2 - k * 5), "topic": topics[(k + len(p[0]) + int(p[0][-1])) % len(topics)], "conducted_by": p[8],
				"attendees": 18 + (k * 7 + int(p[0][-1])) % 20, "language": lang[p[0]]}).insert(ignore_permissions=True)
		scores = {"P-2406": (86, 81, 74), "P-2403": (84, 88, 82)}.get(p[0], (88, 90, 92))
		for k, sc in enumerate(scores):
			frappe.get_doc({"doctype": "Safety Audit", "project": p[0], "audit_date": D(-15 + k * 7), "auditor": "Sajith Kumar", "score": sc, "observations": max(1, (100 - sc) // 3),
				"findings": "Ladders without stoppers, guard rails missing at slab edges, extension boards on wet floors" if sc < 80 else "Minor housekeeping points"}).insert(ignore_permissions=True)
	# drawings, RFIs, transmittals
	dw = {}
	for pid, rows in DRAWINGS.items():
		for no, title, disc, revs, status in rows:
			for k, rev in enumerate(revs):
				last = k == len(revs) - 1
				d = frappe.get_doc({"doctype": "Construction Drawing", "project": pid, "drawing_no": no, "revision": rev, "title": title, "discipline": disc, "issued_on": D(-150 + k * 40)})
				d.insert(ignore_permissions=True)
				if last:
					if status == "GFC":
						Q._a_drg_gfc(d.name, frappe._dict())
						frappe.db.set_value("Construction Drawing", d.name, "gfc_on", D(-145 + k * 40))
					dw[(pid, no)] = d.name
				else:
					d.db_set({"status": "GFC", "gfc_on": D(-145 + k * 40)})
	rfis = [("P-2401", "Transfer beam TB-3 — rebar congestion at column C-4", "STR-B-101", "Holds work", -14, -6, None),
		("P-2401", "Waterproofing detail at the terrace upstand", "ARC-A-201", "Cost", -10, 4, None),
		("P-2403", "Culvert C-9 — invert level clash with the existing drain", "CUL-C9", "Holds work", -9, -3, None),
		("P-2402", "Raft construction joint location", "STR-201", "None", -40, -33, "Joint at 1/3 span as per sketch SK-14 — answered by CBRE structures"),
		("P-2406", "Wallcovering substitute for guest corridors", "INT-GR-05", "Cost and time", -55, -48, "Approved the imported alternative — see EI")]
	for pid, subj, dno, impact, raised, due, ans in rfis:
		r = frappe.get_doc({"doctype": "RFI", "project": pid, "subject": subj, "drawing": dw.get((pid, dno)), "impact": impact, "raised_on": D(raised), "reply_due": D(due),
			"raised_by": who[pid][8], "question": subj + " — please confirm the detail to follow."})
		r.insert(ignore_permissions=True)
		if ans:
			r.db_set({"answer": ans, "status": "Closed", "answered_on": D(due - 2)})
	for pid, to, purpose, d, ack, nos in (("P-2401", "Thrissur Labour Contractors (site)", "For construction", -20, -18, ["STR-B-101", "ARC-A-201"]),
			("P-2402", "CBRE Project Management", "For approval", -10, None, ["STR-215"]), ("P-2403", "Executive Engineer, Roads Division", "For approval", -6, None, ["CUL-C9"])):
		t = frappe.get_doc({"doctype": "Transmittal", "project": pid, "sent_to": to, "purpose": purpose, "sent_on": D(d), "items": [{"drawing": dw[(pid, n)], "copies": 2} for n in nos]})
		t.insert(ignore_permissions=True)
		if ack:
			t.db_set({"status": "Acknowledged", "acknowledged_on": D(ack)})
	# handover: P-2405 snags and documents; P-2408 in DLP (completion, documents, defects, warranties)
	sn = [("Bay 2 — dock leveller 3", "External works", "Leveller lip does not seat fully", "Open", 3), ("Office block — toilets", "Plumbing", "Wash basin waste leaking", "Fixed", -2),
		("Bay 5 — roof", "Civil", "Two roof sheets with dents near the ridge", "Open", -1), ("Office block — mezzanine", "Painting", "Paint touch-up on the stair railing", "Verified", -6),
		("Dock area — north", "External works", "Kerb paint missing", "Open", 5), ("Bay 1–4", "Electrical", "Three high-bay lights not working", "Fixed", -3),
		("Office block — reception", "Doors & windows", "Glass door closer noisy", "Open", 2), ("Bay 8", "Fire", "Hydrant valve hand wheel missing", "Open", -2),
		("FM2 floor — bay 3", "Civil", "Joint sealant missing in two panels", "Open", 4), ("Office block — AC", "HVAC", "Condensate drain slope wrong", "Verified", -8)]
	for loc, trade, desc, st, tgt in sn:
		x = frappe.get_doc({"doctype": "Snag", "project": "P-2405", "location": loc, "trade": trade, "description": desc, "raised_on": D(-12), "target": D(tgt),
			"supplier": "Karnataka Labour Services" if trade in ("Civil", "External works") else None})
		x.insert(ignore_permissions=True)
		if st != "Open":
			x.db_set({"status": st, "fixed_on": D(-4), "verified_on": D(-2) if st == "Verified" else None})
	for pid, docs in (("P-2405", [("Fire NOC", "Karnataka Fire & Emergency Services", "Applied", -20), ("Occupancy certificate", "BBMP / KIADB", "Not started", None),
			("Electrical inspectorate (CEIG) approval", "Electrical Inspectorate, Karnataka", "Applied", -9), ("As-built drawings", "Client", "Not started", None),
			("O&M manuals", "Client", "Received", -5), ("Test certificates — FM2 floor, bolts", "Client", "Received", -7)]),
			("P-2408", [("Completion certificate", "Executive Engineer, PWD", "Received", -18), ("Fire NOC", "Kerala Fire & Rescue Services", "Received", -40),
			("As-built drawings", "PWD Buildings", "Received", -15), ("O&M manuals", "PWD Buildings", "Received", -15)])):
		for doc, auth, st, d in docs:
			h = frappe.get_doc({"doctype": "Handover Document", "project": pid, "document": doc, "authority": auth})
			h.insert(ignore_permissions=True)
			if st != "Not started":
				h.db_set({"status": st, "applied_on": D(d - 10) if d else None, "received_on": D(d) if st == "Received" else None,
					"reference": f"{auth.split(',')[0][:12].upper().replace(' ', '')}/{abs(d or 0) * 37}" if st == "Received" else None})
	frappe.db.set_value("Project", "P-2408", "hs_cn_completed_on", R(who["P-2408"][10][7]))
	for loc, desc, d, st in (("Hostel block — 2nd floor toilets", "Seepage below the shower area", -40, "Rectified"), ("Terrace", "Ponding near the water tank", -28, "Rectified"),
			("Room 214", "Window handle broken", -12, "Responded"), ("Mess hall", "Ceiling fan wobbling", -10, "Reported"), ("Corridor 1st floor", "Floor tile hollow sound", -3, "Reported")):
		x = frappe.get_doc({"doctype": "DLP Defect", "project": "P-2408", "location": loc, "description": desc, "reported_on": D(d), "reported_by": "Assistant Engineer, PWD"})
		x.insert(ignore_permissions=True)
		if st != "Reported":
			x.db_set({"status": st, "responded_on": D(d + 2), "rectified_on": D(d + 9) if st == "Rectified" else None, "cost": 14500 if st == "Rectified" else 0})
	for pid, item, sup, months, frm, ho in (("P-2408", "Terrace waterproofing (APP membrane)", None, 120, R(who["P-2408"][10][7]), 1),
			("P-2408", "uPVC windows", None, 60, R(who["P-2408"][10][7]), 1), ("P-2408", "Water pumps & pressure system", "Precision MEP Services Pvt. Ltd.", 24, R(who["P-2408"][10][7]), 1),
			("P-2405", "PEB roof & wall sheeting", None, 120, D(-10), 0), ("P-2405", "Dock levellers (4 nos)", None, 24, D(-10), 0)):
		frappe.get_doc({"doctype": "Construction Warranty", "project": pid, "item": item, "supplier": sup, "months": months, "valid_from": frm, "handed_over": ho}).insert(ignore_permissions=True)


STAFF = [  # name, gender, designation, project (None = head office), state, basic, hra, special, joined
	("Shihab Musthafa", "Male", "Managing Director", None, "Kerala", 180000, 72000, 48000, "2009-04-01"),
	("Rahul Nair", "Male", "Project Manager", "P-2401", "Kerala", 72000, 28800, 19200, "2014-06-16"),
	("Meera Pillai", "Female", "Project Manager", "P-2402", "Kerala", 70000, 28000, 18000, "2016-01-04"),
	("Karthik Rao", "Male", "Project Manager", "P-2405", "Karnataka", 66000, 26400, 15600, "2019-08-01"),
	("Senthil Kumar", "Male", "Project Manager", "P-2406", "Tamil Nadu", 62000, 24800, 13200, "2020-02-10"),
	("Vishnu Prasad", "Male", "Site Engineer", "P-2401", "Kerala", 32000, 12800, 6200, "2021-07-01"),
	("Aswin Raj", "Male", "Site Engineer", "P-2402", "Kerala", 30000, 12000, 5000, "2022-06-13"),
	("Nikhil Varghese", "Male", "Site Engineer", "P-2403", "Kerala", 34000, 13600, 6400, "2020-11-02"),
	("Manjunath S", "Male", "Site Engineer", "P-2405", "Karnataka", 31000, 12400, 5600, "2022-01-17"),
	("Divya R", "Female", "Site Engineer", "P-2406", "Tamil Nadu", 29000, 11600, 4400, "2023-03-06"),
	("Deepa Krishnan", "Female", "Quantity Surveyor", None, "Kerala", 48000, 19200, 10800, "2017-09-11"),
	("Joseph Mathew", "Male", "Quantity Surveyor", "P-2403", "Kerala", 46000, 18400, 9600, "2018-04-02"),
	("Sajith Kumar", "Male", "Safety Officer", "P-2401", "Kerala", 28000, 11200, 3800, "2021-10-04"),
	("Anju Thomas", "Female", "Accounts Manager", None, "Kerala", 52000, 20800, 11200, "2015-05-18"),
	("Ramesh Babu", "Male", "Storekeeper", "P-2402", "Kerala", 11500, 4600, 1400, "2023-08-21"),
	("Lakshmi Menon", "Female", "HR & Admin", None, "Kerala", 9800, 3900, 1300, "2024-01-15"),
]


def cn_finance(c):
	"""Staff on the payroll (two months paid, this month in draft), the statutory payments of the last two months — one
	ESI payment left overdue and last month's GST to pay — and BOCW cess part-paid on the private sites."""
	from hipersign_trading.api import construction_fin as FN

	if not frappe.db.exists("DocType", "Staff Payroll") or frappe.db.exists("Staff Payroll", {"company": CO}):
		return
	from frappe.utils import add_months, get_first_day, get_last_day

	for name, gender, desig, pid, state, basic, hra, special, joined in STAFF:
		first, last = (name.split(" ", 1) + [""])[:2]
		if frappe.db.exists("Employee", {"employee_name": name, "company": CO}):
			continue
		if desig and not frappe.db.exists("Designation", desig):
			frappe.get_doc({"doctype": "Designation", "designation_name": desig}).insert(ignore_permissions=True)
		e = frappe.get_doc({"doctype": "Employee", "first_name": first, "last_name": last, "gender": gender if frappe.db.exists("Gender", gender) else None,
			"date_of_birth": f"{1968 + (len(name) * 7) % 30}-0{1 + len(name) % 9}-1{len(first) % 9}", "date_of_joining": joined, "company": CO, "status": "Active", "designation": desig,
			"hs_cn_project": pid, "hs_cn_state": state, "hs_cn_basic": basic, "hs_cn_hra": hra, "hs_cn_special": special, "hs_cn_uan": f"10{abs(hash(name)) % 10 ** 10:010d}",
			"ctc": (basic + hra + special) * 12 * 1.1})
		if e.meta.has_field("pan_number"):
			e.pan_number = f"{''.join(ch for ch in name.upper() if ch.isalpha())[:3]}P{name[0].upper()}{1000 + len(name) * 37}{chr(65 + len(name) % 26)}"
		e.flags.ignore_mandatory = True
		e.insert(ignore_permissions=True)
	emps = frappe.get_all("Employee", filters={"company": CO, "status": "Active"}, pluck="name")
	t = getdate(today())
	for k in (2, 1, 0):
		m = get_first_day(add_months(t, -k))
		s = frappe.get_doc({"doctype": "Staff Payroll", "company": CO, "month": m, "rows": [{"employee": e} for e in emps]})
		s.insert(ignore_permissions=True)
		if k:
			s.db_set({"status": "Approved", "approved_by": "Shihab Musthafa"})
			FN.pay_payroll(s.name, get_last_day(m))
	# statutory payments: two months ago all paid on time; last month TDS and PF paid, ESI left (overdue), GST and PT to pay
	for k in (2, 1):
		m = get_first_day(add_months(t, -k))
		kinds = ["GST", "TDS 194C (contractors)", "TDS 192 (salaries)", "PF", "ESI", "Professional tax"] if k == 2 else ["TDS 194C (contractors)", "TDS 192 (salaries)", "PF"]
		for kind in kinds:
			if kind == "GST":
				for g, x in FN.gst_month(CO, m).items():
					if x.out or x.inp:
						d = frappe.get_doc({"doctype": "Statutory Deposit", "company": CO, "kind": "GST", "month": m, "gstin": g, "amount": max(.01, x.cash), "challan_no": f"CPIN{g[:2]}{m.month:02d}{abs(hash(g)) % 10 ** 8}"})
						d.insert(ignore_permissions=True)
						FN.pay_deposit(d.name, add_days(FN.due_date("GST", m), -2))
				continue
			amt = FN.liability_for(CO, m, kind)
			if not amt:
				continue
			d = frappe.get_doc({"doctype": "Statutory Deposit", "company": CO, "kind": kind, "month": m, "amount": flt(amt, 0), "challan_no": f"{kind[:3].upper()}{m.month:02d}{int(amt) % 99991:05d}"})
			d.insert(ignore_permissions=True)
			FN.pay_deposit(d.name, min(t, getdate(add_days(FN.due_date(kind, m), -1))))
	# GSTR-1 filed on the portal for both months (India Compliance keeps the filing in its GST Return Log)
	if frappe.db.exists("DocType", "GST Return Log"):
		for k in (2, 1):
			m = get_first_day(add_months(t, -k))
			for g in FN.gst_month(CO, m):
				if g != "—" and not FN._filed(CO, g, m):
					try:
						frappe.get_doc({"doctype": "GST Return Log", "return_type": "GSTR1", "return_period": m.strftime("%m%Y"), "gstin": g, "company": CO, "filing_status": "Filed",
							"filing_date": add_days(add_months(m, 1), 9), "acknowledgement_number": f"AA{g[:2]}{m.strftime('%m%y')}{abs(hash(g)) % 10 ** 9:09d}"}).insert(ignore_permissions=True)
					except Exception:
						frappe.log_error(title="Demo: GSTR-1 log")
	# BOCW cess on private work: paid up to last quarter on two sites
	for pid, share in (("P-2401", .7), ("P-2402", .6), ("P-2406", 0)):
		cd = FN.cess_due(pid)
		if share and cd.due > 1000:
			d = frappe.get_doc({"doctype": "Statutory Deposit", "company": CO, "kind": "BOCW labour cess", "month": get_first_day(add_months(t, -2)), "project": pid,
				"amount": round(cd.due * share, -2), "challan_no": f"KBOCWWB/{pid}/{t.year}"})
			d.insert(ignore_permissions=True)
			FN.pay_deposit(d.name, D(-40))
	# a manual journal waiting for the Accounts Manager — provision for the audit fee
	exp = frappe.db.get_value("Account", {"company": CO, "account_name": ["like", "%Audit%"], "is_group": 0}) or frappe.db.get_value("Account", {"company": CO, "root_type": "Expense", "is_group": 0, "account_type": ""})
	prov = frappe.db.get_value("Account", {"company": CO, "account_name": ["like", "%Creditors%"], "is_group": 0, "account_type": ["!=", "Payable"]}) \
		or frappe.db.get_value("Account", {"company": CO, "root_type": "Liability", "is_group": 0, "account_type": ""})
	if exp and prov:
		frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Journal Entry", "company": CO, "posting_date": D(-1), "user_remark": "Provision for statutory audit fee FY 2026-27 (H1)",
			"accounts": [{"account": exp, "debit_in_account_currency": 175000, "cost_center": frappe.get_cached_value("Company", CO, "cost_center")},
				{"account": prov, "credit_in_account_currency": 175000, "cost_center": frappe.get_cached_value("Company", CO, "cost_center")}]}).insert(ignore_permissions=True)


def _demo_photo(text, sub, hue):
	"""A drawn stand-in for a site photo (sky, structure, ground and a caption band) — the demo has no real photographs."""
	import io

	from PIL import Image, ImageDraw

	W, H = 960, 640
	im = Image.new("RGB", (W, H))
	d = ImageDraw.Draw(im)
	for y in range(H):
		k = y / H
		d.line([(0, y), (W, y)], fill=(int(150 + 70 * k), int(185 + 40 * k), int(225 - 20 * k)) if y < H * .55 else (int(150 - 40 * k), int(130 - 30 * k), int(100 - 20 * k)))
	base = (hue * 37) % 80
	for i in range(5):  # a frame of columns and slabs
		x = 120 + i * 170
		d.rectangle([x, 150, x + 22, H * .62], fill=(150 + base // 2, 150 + base // 2, 155))
	for j in range(4):
		y = 150 + j * 70
		d.rectangle([110, y, 830, y + 14], fill=(170, 170, 172))
	d.rectangle([0, H - 90, W, H], fill=(19, 35, 91))
	d.text((24, H - 76), text, fill=(255, 255, 255))
	d.text((24, H - 46), sub, fill=(200, 210, 240))
	b = io.BytesIO()
	im.save(b, "JPEG", quality=78)
	return b.getvalue()


def cn_portal(c):
	"""Project controls (constraints, milestones, last week's review) and the portals and apps: geo-tagged site photos and
	the publishing queue, client and partner logins with what they did, today's check-ins, site cash, worker app PINs, a
	danger reported by a worker and a driver for the transfer on the road."""
	from hipersign_trading.api import construction_portal as PT

	if not frappe.db.exists("DocType", "Project Constraint") or frappe.db.exists("Project Constraint", {"project": "P-2401"}):
		return
	t = getdate(today())
	cons = [("P-2401", "Transfer beam TB-3 reinforcement detail (RFI) — holds the 5th floor slab", "Design / drawings", "Block B 5th floor slab", "Arch. Suresh Menon (PMC)", -3),
		("P-2401", "Lift machine-room steel delivery", "Material", "Lift MR roof", "Purchase — Ramesh", 6),
		("P-2402", "Tower crane TC-02 load test certificate", "Authority / permit", "Podium level 2 lifting", "Plant Manager", 2),
		("P-2403", "Shifting of KSEB pole at Ch. 3+100", "Authority / permit", "Service road widening Ch. 3+050–3+200", "KSEB Kanhangad (via EE)", -9),
		("P-2405", "Fire NOC inspection date", "Authority / permit", "Handover", "Karthik Rao", 10),
		("P-2406", "Client decision on lobby ceiling finish", "Client decision", "Lobby ceiling", "Coromandel Hospitality", 4)]
	for pid, desc, cat, actv, owner, d in cons:
		frappe.get_doc({"doctype": "Project Constraint", "project": pid, "description": desc, "category": cat, "activity": actv, "owner_name": owner, "need_by": add_days(t, d),
			"raised_by": "Rahul Nair"}).insert(ignore_permissions=True)
	x = frappe.get_doc({"doctype": "Project Constraint", "project": "P-2402", "description": "Basement dewatering pump spares", "category": "Equipment", "owner_name": "Plant Manager",
		"need_by": add_days(t, -12)})
	x.insert(ignore_permissions=True)
	x.db_set({"status": "Removed", "removed_on": add_days(t, -14), "notes": "Spares air-freighted from Coimbatore"})
	ms = {"P-2401": [("Block A structure complete", "Contract milestone", -60, -52, -50), ("Block B 5th floor slab", "Contract milestone", 8, 24, None),
			("Lift installation start", "Deliverable", 40, 46, None), ("Handover of Block A flats", "Handover", 120, 120, None)],
		"P-2402": [("Raft complete", "Contract milestone", -150, -150, -146), ("Podium slab complete", "Contract milestone", 20, 34, None), ("Structure top-out", "Contract milestone", 260, 275, None)],
		"P-2403": [("Culvert C-7 complete", "Contract milestone", -30, -30, -26), ("DBM Ch. 2+000–3+000", "Payment milestone", -5, 18, None), ("Culvert C-9 complete", "Contract milestone", 45, 60, None)],
		"P-2405": [("Roof sheeting complete", "Contract milestone", -40, -40, -38), ("FM2 floor complete", "Contract milestone", -10, -10, -9), ("Handover to the client", "Handover", 30, 36, None)],
		"P-2406": [("Guest floors 5–6 complete", "Contract milestone", -20, -8, -6), ("Mock-up room approved", "Deliverable", -60, -60, -62), ("Guest floors 7–8 complete", "Contract milestone", 35, 48, None)]}
	for pid, rows in ms.items():
		for title, kind, pl, fc, ac in rows:
			frappe.get_doc({"doctype": "Construction Milestone", "project": pid, "title": title, "kind": kind, "planned": add_days(t, pl), "forecast": add_days(t, fc),
				"actual": add_days(t, ac) if ac is not None else None, "client_visible": 1}).insert(ignore_permissions=True)
	# last week's review (what moved since: cost and schedule were better on P-2401 and P-2403)
	import json

	lastmon = add_days(PT.week_monday(), -7)
	for pid, better, note in (("P-2401", ("cost", "schedule"), "TB-3 RFI escalated to the PMC; steel reconciliation to be closed by Friday"),
			("P-2402", ("quality",), "Podium cube failure — core tests ordered; NCR open"), ("P-2403", ("schedule",), "KSEB pole shifting chased through the EE; night work on DBM")):
		R = PT.rag(pid)
		snap = {d.key: [("Green" if d.key in better and d.state != "Green" else d.state), d.why[:2]] for d in R}
		o = PT.overall([frappe._dict(state=v[0]) for v in snap.values()])
		frappe.get_doc({"doctype": "Project Review", "project": pid, "week_start": lastmon, "rag_json": json.dumps(snap), "overall": o[0], "reds": o[1], "ambers": o[2],
			"notes": note, "decisions": "Owners named in the constraints log", "reviewed_by": "Shihab Musthafa"}).insert(ignore_permissions=True)
	# site photos (drawn stand-ins), geo-tagged
	geo = {"P-2401": (10.0159, 76.3419), "P-2402": (8.5587, 76.8814), "P-2403": (12.3069, 75.0898), "P-2405": (12.8167, 77.6944), "P-2406": (12.9327, 80.2317)}
	shots = [("P-2401", "Block B — 4th floor slab reinforcement", "Grid B/1–B/6", -2), ("P-2401", "Block A — blockwork 5th floor", "Block A east", -1),
		("P-2401", "Material yard — steel stacked on sleepers", "Yard", -4), ("P-2402", "Podium slab pour 3 — curing", "Grid C/4–C/9", -3),
		("P-2402", "Retaining wall RW-2 shuttering", "North boundary", -1), ("P-2403", "Culvert C-9 excavation with shoring", "Ch. 3+950", -2),
		("P-2403", "DBM laying Ch. 2+650", "RHS", -6), ("P-2405", "FM2 floor — bay 6 finished", "Bay 6", -5), ("P-2405", "Dock levellers installed", "Dock area", -3),
		("P-2406", "Guest room mock-up — joinery fixed", "Floor 7, room 712", -1), ("P-2406", "Corridor ceiling grid", "Floor 6", -2), ("P-2401", "Scaffold at Block B east face", "Block B east", 0)]
	from frappe.utils import add_to_date, now_datetime

	for i, (pid, cap, loc, d) in enumerate(shots):
		la, lo = geo[pid]
		ph = frappe.get_doc({"doctype": "Site Photo", "project": pid, "image": "/files/placeholder.png", "caption": cap, "location": loc, "source": "Site app",
			"taken_on": add_to_date(now_datetime(), days=d, hours=-(i % 5)), "latitude": la + i * .0001, "longitude": lo + i * .0001,
			"taken_by": {"P-2401": "Vishnu Prasad", "P-2402": "Aswin Raj", "P-2403": "Nikhil Varghese", "P-2405": "Manjunath S", "P-2406": "Divya R"}[pid]})
		ph.insert(ignore_permissions=True)
		f = frappe.get_doc({"doctype": "File", "file_name": f"{ph.name}.jpg", "attached_to_doctype": "Site Photo", "attached_to_name": ph.name, "attached_to_field": "image", "is_private": 1,
			"content": _demo_photo(cap, f"{pid} · {loc} · demo image", i)})
		f.flags.ignore_permissions = True
		f.insert()
		ph.db_set("image", f.file_url)
	PT.sync_publications(["P-2401", "P-2402", "P-2403", "P-2405", "P-2406"])
	# the PM published most of it; the newest photos and a drawing still wait
	waiting = set(frappe.get_all("Client Publication", filters={"kind": "Photo"}, fields=["name", "creation"], order_by="creation desc", limit=3, pluck="name"))
	waiting |= set(frappe.get_all("Client Publication", filters={"kind": "Drawing", "project": "P-2401"}, pluck="name", limit=1))
	for p in frappe.get_all("Client Publication", filters={"status": "Waiting"}, fields=["name", "project", "kind"]):
		if p.name in waiting:
			continue
		if p.kind == "Drawing" and p.project == "P-2402":
			frappe.db.set_value("Client Publication", p.name, {"status": "Kept internal", "published_by": "Meera Pillai"})
			continue
		frappe.db.set_value("Client Publication", p.name, {"status": "Published", "published_on": add_to_date(now_datetime(), days=-1), "published_by": "Rahul Nair"})
	# portal logins: two clients and a labour contractor — and what they did
	inv = [("Customer", "Malabar Habitat Developers Pvt. Ltd.", "anil.varghese@malabarhabitat.example", "Anil Varghese"),
		("Customer", "Deccan Warehousing LLP", "priya.shetty@deccanwarehousing.example", "Priya Shetty"),
		("Customer", "Coromandel Hospitality Pvt. Ltd.", "ravi.chandran@coromandel.example", "Ravi Chandran"),
		("Supplier", "Thrissur Labour Contractors", "office@thrissurlabour.example", "Joy Thomas")]
	frappe.flags.hs_demo_loading = True
	for kind, party, email, name in inv:
		PT._a_invite(f"{kind}::{party}", frappe._dict(email=email, first_name=name))
	frappe.db.set_value("Customer", "Coromandel Hospitality Pvt. Ltd.", {"hs_cnp_certify": 0, "hs_cnp_whatsapp": 1})
	me = frappe.session.user
	try:
		frappe.set_user("anil.varghese@malabarhabitat.example")
		frappe.form_dict.party = None
		PT.cp_snag("P-2401", "Show flat 3B — kitchen", "Granite counter edge chipped near the sink", "Finishes")
		frappe.set_user("office@thrissurlabour.example")
		w = frappe.get_doc("Subcontractor Work Order", "SWO-26-001")
		q = {w.items[0].item_no: round(flt(w.items[0].qty) * .08, 1)}
		if len(w.items) > 1:
			q[w.items[1].item_no] = round(flt(w.items[1].qty) * .06, 1)
		PT.sp_bill("SWO-26-001", q, "TLC/RB/26-118", today())
		m = add_days(get_first_day_(t), -1)
		import base64
		import io

		from pypdf import PdfWriter

		pw, buf = PdfWriter(), io.BytesIO()
		pw.add_blank_page(width=595, height=842)
		pw.add_metadata({"/Title": "Demo labour document"})
		pw.write(buf)
		pdf = "data:application/pdf;base64," + base64.b64encode(buf.getvalue()).decode()
		PT.sp_compliance("P-2401", str(m), 34, pdf, pdf, None)
		img = "data:image/jpeg;base64," + base64.b64encode(_demo_photo("Plastering — Block A 3rd floor", "Thrissur Labour Contractors · demo image", 7)).decode()
		PT.sp_photo("P-2401", img, "Plastering — Block A 3rd floor", "Block A")
	finally:
		frappe.set_user(me)
		frappe.form_dict.party = None
	# today's check-ins at P-2401 (all but one own worker), a site engineer's check-in record and site cash
	own = frappe.get_all("Site Worker", filters={"project": "P-2401", "status": "Active", "contractor": ["is", "not set"]}, pluck="name", order_by="worker_name")
	for wk in own[:-1]:
		frappe.get_doc({"doctype": "Site Attendance", "project": "P-2401", "worker": wk, "attendance_date": t, "method": "Gang check-in", "time_in": "07:52:00",
			"latitude": geo["P-2401"][0], "longitude": geo["P-2401"][1], "marked_by": "Vishnu Prasad"}).insert(ignore_permissions=True)
	imp = PT.imprest_account(CO)
	from hipersign_trading.api import construction as CN

	je = frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Bank Entry", "company": CO, "posting_date": D(-20), "cheque_no": "IMP/26-11", "cheque_date": D(-20),
		"user_remark": "Site imprest top-up for the site engineers", "accounts": [{"account": imp, "debit_in_account_currency": 150000},
			{"account": CN.bank_account(CO), "credit_in_account_currency": 150000}]})
	je.flags.ignore_permissions = True
	je.flags.hs_system_entry = True
	je.insert()
	je.submit()
	for pid, d, head, desc, to, amt in (("P-2401", -6, "Site overheads", "Drinking water cans — 40 nos", "Aqua Fresh, Kakkanad", 1600), ("P-2401", -3, "Materials", "Binding wire 25 kg (urgent)", "Local hardware", 2350),
			("P-2402", -4, "Plant & equipment", "Vibrator needle repair", "Sree Motors", 3800), ("P-2403", -2, "Site overheads", "Night-work lighting — diesel 40 L", "HP pump, Kanhangad", 4120),
			("P-2406", -1, "Site overheads", "Housekeeping consumables", "Saravana Stores", 2780)):
		x = frappe.get_doc({"doctype": "Site Expense", "project": pid, "expense_date": D(d), "head": head, "description": desc, "paid_to": to, "amount": amt,
			"requested_by": {"P-2401": "Vishnu Prasad", "P-2402": "Aswin Raj", "P-2403": "Nikhil Varghese", "P-2406": "Divya R"}[pid]})
		x.insert(ignore_permissions=True)
		PT.book_expense(x.name)
	frappe.get_doc({"doctype": "Site Expense", "project": "P-2405", "expense_date": D(-1), "head": "Plant & equipment", "description": "Crane hire — 4 hours for dock leveller fixing",
		"paid_to": "Hosur Crane Services", "amount": 14500, "requested_by": "Manjunath S"}).insert(ignore_permissions=True)
	# worker app: three workers with PINs (demo PIN 1234) and their languages; one asked for an advance, one reported a danger
	langs = ["മലയാളം", "हिन्दी", "தமிழ்"]
	for i, wk in enumerate(own[:3]):
		w = frappe.get_doc("Site Worker", wk)
		w.app_pin, w.app_language = "1234", langs[i]
		w.flags.ignore_permissions = True
		w.save()
	if own:
		w = frappe.get_doc("Site Worker", own[1])
		frappe.get_doc({"doctype": "Safety Incident", "project": "P-2401", "incident_date": t, "kind": "Near miss", "location": "Block B — 4th floor east edge",
			"description": "Danger reported on the worker app: guard rail missing at the slab edge near the hoist", "reported_by": w.worker_name}).insert(ignore_permissions=True)
		PT.log("Site Worker", w.name, "Reported a danger", "P-2401")
	# the driver of the transfer on the road
	if not frappe.db.exists("Driver", {"full_name": "Sathyan K"}):
		frappe.get_doc({"doctype": "Driver", "full_name": "Sathyan K", "cell_number": "98470 12345", "status": "Active"}).insert(ignore_permissions=True)


def get_first_day_(d):
	return getdate(d).replace(day=1)


# rate analyses: title, code, category, unit, BOQ text it prices, SOR code, SOR rate (sample), resources [type, item, description, unit, per unit, rate]
RATE_ANALYSES = [
	("RCC M25 in footings, columns, beams & slabs", "DSR 5.33", "Concrete", "Cum", ("RCC M25", "RCC M2", "RCC M3"), "KL-SOR 4.14", 8900, [
		("Material", "CEM-OPC53", "Cement OPC 53 (bags)", "Bag", 8.06, 410), ("Material", "MSAND", "M-sand", "Cum", .45, 2350), ("Material", "AGG-20", "20 mm aggregate", "Cum", .86, 1650),
		("Material", None, "Admixture", "Litre", 2.4, 95), ("Labour", None, "Mason", "Day", .17, 950), ("Labour", None, "Beldar / helper", "Day", 1.9, 720),
		("Plant", None, "Concrete mixer & vibrator", "Hour", 1.2, 320), ("Material", None, "Water & curing", "LS", 1, 85)]),
	("PCC M10 (1:3:6) in foundation bed", "DSR 4.1.8", "Concrete", "Cum", ("PCC M1",), "KL-SOR 4.02", 6050, [
		("Material", "CEM-OPC53", "Cement OPC 53 (bags)", "Bag", 4.4, 410), ("Material", "MSAND", "M-sand", "Cum", .47, 2350), ("Material", None, "40 mm aggregate", "Cum", .94, 1500),
		("Labour", None, "Mason", "Day", .1, 950), ("Labour", None, "Beldar / helper", "Day", 1.65, 720), ("Plant", None, "Concrete mixer", "Hour", .9, 260)]),
	("Reinforcement Fe500D — cutting, bending & placing", "DSR 5.22.6", "Reinforcement", "MT", ("Reinforcement",), "KL-SOR 5.06", 76200, [
		("Material", "TMT-FE500D", "TMT Fe500D bars", "MT", 1.03, 58500), ("Material", None, "Binding wire", "Kg", 10, 92), ("Labour", None, "Bar bender", "Day", 4.2, 1050),
		("Labour", None, "Helper", "Day", 4.2, 720), ("Plant", None, "Bar cutting & bending machine", "Hour", 3, 180)]),
	("AAC block masonry 200 mm in CM 1:6", "DSR 6.13", "Masonry", "Cum", ("AAC block",), "KL-SOR 6.21", 7150, [
		("Material", "AAC-BLOCK", "AAC blocks 600 × 200 × 200", "Cum", 1.0, 4150), ("Material", None, "Block jointing mortar", "Bag", 1.6, 420), ("Labour", None, "Mason", "Day", .6, 950),
		("Labour", None, "Helper", "Day", .9, 720)]),
	("Cement plaster 12 mm in CM 1:4", "DSR 13.4.1", "Finishes", "Sqm", ("plaster",), "KL-SOR 13.03", 372, [
		("Material", "CEM-OPC53", "Cement OPC 53 (bags)", "Bag", .1, 410), ("Material", None, "Plastering sand", "Cum", .015, 2600), ("Labour", None, "Mason", "Day", .075, 950),
		("Labour", None, "Helper", "Day", .09, 720), ("Plant", None, "Scaffolding hire", "Sqm", 1, 18)]),
	("Vitrified tile flooring 800 × 800 incl. bedding", "DSR 11.41", "Finishes", "Sqm", ("Vitrified tile",), "KL-SOR 11.18", 1395, [
		("Material", None, "Vitrified tiles 800 × 800 (incl. 5% wastage)", "Sqm", 1.05, 720), ("Material", "CEM-OPC53", "Cement for bedding & joints", "Bag", .2, 410),
		("Material", "MSAND", "Sand for bedding", "Cum", .025, 2350), ("Labour", None, "Tile mason", "Day", .12, 1100), ("Labour", None, "Helper", "Day", .12, 720)]),
	("Dense bituminous macadam (DBM) 60 mm", "MoRTH 507", "Roads", "Cum", ("Dense bituminous",), "KL-SOR R-5.07", 9200, [
		("Material", "BIT-VG30", "Bitumen VG-30", "MT", .105, 48500), ("Material", "AGG-20", "Graded aggregate", "Cum", 1.25, 1650), ("Material", None, "Filler (lime / cement)", "MT", .02, 6500),
		("Plant", None, "Hot mix plant, paver & rollers", "Cum", 1, 1180), ("Labour", None, "Road gang", "Day", .08, 760)]),
	("Wet mix macadam (WMM)", "MoRTH 406", "Roads", "Cum", ("Wet mix macadam",), "KL-SOR R-4.06", 2590, [
		("Material", None, "Graded crushed aggregate", "Cum", 1.32, 1250), ("Plant", None, "WMM plant, paver & rollers", "Cum", 1, 410), ("Labour", None, "Road gang", "Day", .05, 760)]),
]


def cn_estimating(c):
	"""Rate analyses linked to the BOQ lines they price, BOQ templates from the standard BOQs, the tender BOQ of the Kochi
	Water Metro bid being priced, BOQ versions (tender → contract → revised) on the awarded projects, the submission
	checklists of the open tenders and the bids opened on the decided ones."""
	from hipersign_trading.api import construction_est as EST

	if not frappe.db.exists("DocType", "Rate Analysis") or frappe.db.exists("Rate Analysis", {"company": CO}):
		return
	ras = {}
	for title, code, cat, unit, texts, sor_code, sor_rate, res in RATE_ANALYSES:
		a = frappe.get_doc({"doctype": "Rate Analysis", "company": CO, "title": title, "code": code, "category": cat, "unit": unit, "based_on": "CPWD DSR 2023" if not code.startswith("MoRTH")
			else "Company norms", "sor_name": "Kerala PWD SOR 2025 (sample)", "sor_code": sor_code, "sor_rate": sor_rate,
			"resources": [{"resource_type": t, "item": i if i and frappe.db.exists("Item", i) else None, "description": d, "unit": u, "coefficient": q, "rate": r} for t, i, d, u, q, r in res]})
		EST.refresh_rates(a)
		a.insert(ignore_permissions=True)
		if cat != "Roads":
			a.db_set({"status": "Approved", "approved_by": "Deepa Krishnan"})
		ras[a.name] = texts
	def match(desc):
		return next((n for n, texts in ras.items() if any(t.lower() in (desc or "").lower() for t in texts)), None)
	# link the existing BOQ lines (the awarded budgets stay as they are)
	for r in frappe.get_all("Project BOQ Item", filters={"parenttype": "Project BOQ"}, fields=["name", "description"]):
		n = match(r.description)
		if n:
			frappe.db.set_value("Project BOQ Item", r.name, {"rate_analysis": n, "analysed_rate": frappe.db.get_value("Rate Analysis", n, "analysed_rate")}, update_modified=False)
	# BOQ templates
	labels = {"bld": "Buildings — RCC frame G+5", "road": "Roads — service road with culverts", "peb": "Industrial — PEB warehouse", "fit": "Interior fit-out — hotel"}
	for k, lines in TPL.items():
		items = []
		for code, ch, d, unit, rate, w, s_, sh in lines:
			items.append({"section_name": ch, "item_no": code, "description": d, "unit": unit, "rate": rate, "weight_pct": round(w * 100, 2), "rate_analysis": match(d),
				**{SHARE[x]: v * 100 for x, v in sh.items()}})
		items.insert(0, {"section_name": "Preliminaries", "item_no": "0.1", "description": "Preliminaries, site establishment, insurance & statutory registrations", "unit": "LS",
			"rate": 0, "weight_pct": round(100 - sum(x["weight_pct"] for x in items), 2), "ovh_share": 85})
		frappe.get_doc({"doctype": "BOQ Template", "title": labels[k], "category": CATEGORY[k], "description": f"Standard BOQ for {CATEGORY[k].lower()} — the shares are of the contract value",
			"items": items}).insert(ignore_permissions=True)
	# versions on the awarded projects: the tender BOQ (V0) behind P-2401 and P-2403; P-2401 revised with its approved variations
	for pid, tid, up in (("P-2401", "TND-2507-019", 1.021), ("P-2403", "TND-2505-011", 1.034)):
		cur = frappe.get_doc("Project BOQ", frappe.db.get_value("Project BOQ", {"project": pid, "status": ["!=", "Superseded"]}))
		v0 = frappe.copy_doc(cur)
		v0.update({"version_type": "Tender BOQ", "revision": 0, "status": "Submitted", "tender": tid, "project": None})
		for r in v0.items:
			r.rate, r.measured_pct, r.certified_pct = round(flt(r.rate) * up, 2), 0, 0
		v0.insert(ignore_permissions=True)
		v0.db_set({"status": "Superseded", "project": pid})
		frappe.db.set_value("Project BOQ", cur.name, {"version_type": "Contract BOQ", "version_of": v0.name, "tender": tid}, update_modified=False)
		frappe.db.set_value("Tender", tid, "boq", v0.name)
	frappe.clear_cache(doctype="Project BOQ")
	EST.new_version(frappe.db.get_value("Project BOQ", {"project": "P-2401", "status": ["!=", "Superseded"]}), "Revised")
	# the tender being priced: Kochi Water Metro Terminal from the buildings template, at 11.8% margin
	b = EST.from_template("Buildings — RCC frame G+5", 21.5 * CR * .955, tender="TND-2611-021", company=CO)
	b.reload()
	b.target_margin = 11.8
	b.save(ignore_permissions=True)
	t = frappe.get_doc("Tender", "TND-2611-021")
	t.our_bid, t.our_margin_pct = b.bid_price, 11.8
	t.save(ignore_permissions=True)
	# submission checklists
	ready = {"TND-2611-021": 7, "TND-2611-024": 2}
	for tid in frappe.get_all("Tender", filters={"company": CO}, pluck="name"):
		t = frappe.get_doc("Tender", tid)
		if not t.checklist:
			for x in EST.CHECKLIST:
				t.append("checklist", {"item": x})
		n = ready.get(tid, len(t.checklist) if t.status not in ("Bid / no-bid", "Being priced") else 0)
		for r in t.checklist:
			r.done = 1 if r.idx <= n else 0
			if r.done:
				r.done_by, r.done_on = "Arjun Menon", add_days(t.due_date or today(), -3) if t.due_date else today()
		t.flags.ignore_permissions = True
		t.save()
		for r in t.checklist:
			if r.done:
				frappe.db.set_value("Tender Checklist Item", r.name, {"done_by": "Arjun Menon", "done_on": add_days(t.due_date, -3 - (len(t.checklist) - r.idx) // 3) if t.due_date else today()})
	# bids opened
	bidders = {"TND-2610-014": [("Hindustan Infra Projects", 1.034), ("Malabar Builders & Engineers", 1.057), ("Sree Ganesh Constructions", 1.112)],
		"TND-2609-009": [("Kerala Infra Builders", .967), ("Ernad Constructions", 1.021), ("Southern Structurals", 1.048)],
		"TND-2608-006": [("Interio Spaces LLP", .955), ("Design Build Co.", .981), ("Studio Fitouts", 1.06)],
		"TND-2505-011": [("Coastal Roadways Ltd.", 1.022), ("NH Infra & Paving", 1.046)], "TND-2507-019": [("Kochi Habitat Builders", 1.031)]}
	for tid, others in bidders.items():
		t = frappe.get_doc("Tender", tid)
		us = flt(t.our_bid) or flt(t.estimated_value)
		t.set("bidders", [{"bidder": "Hipersign Constructions India (us)", "is_us": 1, "bid_amount": us}] +
			[{"bidder": n, "bid_amount": round(us * f, -3)} for n, f in others])
		t.flags.ignore_permissions = True
		t.save()


# ---------------------------------------------------------------- v1.9.1 B2: risks & issues, minutes of meeting, tasks
RISKS = [  # project, kind, title, category, probability, impact, owner, review (days), mitigation, cost (₹ L), delay days
	("P-2401", "Risk", "Monsoon delays the terrace and podium waterproofing", "Weather", "High", "Medium", "Rahul Nair", 10,
		"Finish the APP membrane on Block A before the rains; tarpaulin cover and a dewatering pump on standby", 6, 21),
	("P-2401", "Risk", "Steel price rise — firm-price contract, 420 MT still to buy", "Materials & supply", "Medium", "High", "Deepa Krishnan", 20,
		"Book the balance TMT with SAIL dealer at today's rate; stagger deliveries", 38, 0),
	("P-2402", "Issue", "Revised MEP drawings for floors 6–8 not issued — sleeves on hold", "Design", "High", "High", "Meera Pillai", -4,
		"RFI raised; CBRE to release the drawings; slab cycle shifted to the core walls meanwhile", 12, 14),
	("P-2403", "Risk", "Land not handed over at Ch. 3+100 — utility shifting by KSEB", "Client", "High", "High", "Rahul Nair", 7,
		"Hindrance logged; EOT application with the KSEB letter; crews moved to culvert C-7", 0, 45),
	("P-2406", "Risk", "Imported sanitaryware for guest floors stuck at customs", "Materials & supply", "Medium", "Medium", "Senthil Kumar", 12,
		"Clearing agent following up; local alternate approved by the designer for floor 5", 3, 10),
	("P-2405", "Risk", "PEB roof sheeting subcontractor short of crew for the last two bays", "Subcontractor", "Low", "Medium", "Karthik Rao", 15,
		"Second crew from the Hosur sheeting contractor on standby at the same rate", 2, 7),
]
MEETINGS = [  # project, title, kind, days ago, chair, attendees, points, [(action, by, due in days)], raise tasks
	("P-2401", "Weekly site progress review — week 46", "Site progress review", 3, "Rahul Nair", "Rahul Nair, Vishnu Prasad, Deepa Krishnan, Marble & tiling subcontractor",
		"<p>Block A 5th-floor columns 80% cast; slab shuttering from Monday. Waterproofing to finish before the rains. RA bill 9 with the PMC since last week.</p>",
		[("Follow up RA bill 9 certification with the PMC", "Deepa Krishnan", 2), ("Book balance TMT steel at today's rate", "Rahul Nair", -2), ("Mock-up of the lobby tiling for approval", "Vishnu Prasad", 6)], 1),
	("P-2402", "Client / PMC coordination meeting", "Client / PMC meeting", 6, "Meera Pillai", "Meera Pillai, CBRE PM, MEP consultant, Aswin Raj",
		"<p>MEP drawings for floors 6–8 still pending; sleeves on hold. Cube results for the 5th-floor slab passed. Next RA bill on 30th.</p>",
		[("Issue revised MEP drawings for floors 6–8", "CBRE PM", 4), ("Submit the EOT notice for the drawing delay", "Meera Pillai", 9)], 1),
	("P-2403", "Monthly review with the MD", "Monthly review (MD)", 1, "Managing Director", "Managing Director, Rahul Nair, Joseph Mathew, Finance Manager",
		"<p>RA bill 11 overdue with the client; GST-TDS credit to accept. Utility shifting at Ch. 3+100 holding the work front.</p>",
		[("Meet the Executive Engineer about the overdue RA bill", "Managing Director", 5), ("Apply EOT for the KSEB hindrance", "Rahul Nair", 7)], 0),
]


def cn_controls2(c):
	"""Risks and issues per project, minutes of meeting with action points (two already turned into tasks) and a few tasks
	on the live projects, one of them overdue."""
	if not frappe.db.exists("DocType", "Project Risk") or frappe.db.exists("Project Risk", {"company": CO}):
		return
	for pid, kind, title, cat, pr, im, owner, rv, mit, cost, dl in RISKS:
		frappe.get_doc({"doctype": "Project Risk", "project": pid, "kind": kind, "title": title, "category": cat, "probability": pr, "impact": im, "owner_name": owner,
			"review_by": D(rv), "mitigation": mit, "cost_impact": cost * 1e5, "days_impact": dl}).insert(ignore_permissions=True)
	r = frappe.get_doc({"doctype": "Project Risk", "project": "P-2405", "kind": "Risk", "title": "Fire NOC inspection before handover", "category": "Statutory & permits",
		"probability": "Medium", "impact": "High", "owner_name": "Karthik Rao", "review_by": D(-20), "mitigation": "Sprinkler test witnessed by the fire officer"})
	r.insert(ignore_permissions=True)
	frappe.db.set_value("Project Risk", r.name, {"status": "Closed", "closed_on": D(-12), "outcome": "Fire NOC inspection passed on the first visit"}, update_modified=False)
	from hipersign_trading.api import construction_ctl as CTL

	for pid, title, kind, ago, chair, att, pts, acts, raise_tasks in MEETINGS:
		m = frappe.get_doc({"doctype": "Project Meeting", "project": pid, "title": title, "meeting_type": kind, "meeting_date": D(-ago), "chaired_by": chair, "attendees": att,
			"minutes": pts, "next_meeting": D(7 - ago), "actions": [{"action": a, "owner_name": by, "due": D(due - ago if due >= 0 else due)} for a, by, due in acts]})
		m.insert(ignore_permissions=True)
		if raise_tasks:
			frappe.flags.hs_cn_skip_role = True
			try:
				CTL._a_mtg_tasks(m.name, frappe._dict())
			finally:
				frappe.flags.hs_cn_skip_role = False
	for pid, subj, by, due, pri in (("P-2406", "Designer sign-off on the guest-room mock-up", "Senthil Kumar", 4, "High"),
			("P-2405", "Witness the dock-leveller load test with the client", "Karthik Rao", 9, "Medium"),
			("P-2403", "Renew the CAR policy before expiry", "Joseph Mathew", -3, "High")):
		frappe.get_doc({"doctype": "Task", "subject": subj, "project": pid, "company": CO, "exp_end_date": D(due), "status": "Open", "priority": pri,
			"hs_task_owner": by}).insert(ignore_permissions=True)


# ---------------------------------------------------------------- v1.9.1 B3: diary, productivity, plant hire, returnables, scrap, subcontractor advances
PROD_NORMS = [  # trade, activity, DPR text, unit, output per man-day
	("Mason", "RCC slab casting (placing & vibrating)", "slab casting", "Cum", 1.6), ("Bar bender", "Reinforcement cut, bend & tie", "Reinforcement", "MT", .25),
	("Mason", "AAC block masonry", "block masonry", "Cum", 1.25), ("Mason", "Internal plaster 12 mm", "plaster", "Sqm", 10),
	("Paving gang", "GSB laying & compaction", "GSB", "Cum", 12), ("Paving gang", "WMM laying", "WMM", "Cum", 10), ("Paving gang", "DBM paving", "DBM", "Cum", 8),
	("Mason", "Culvert concreting", "Culvert", "Cum", 1.4), ("Fitter", "Roof sheeting", "Roof sheeting", "Sqm", 18), ("Mason", "Industrial floor pour", "floor pour", "Sqm", 22),
	("Gypsum fixer", "Gypsum false ceiling", "Gypsum ceiling", "Sqm", 12), ("Gypsum fixer", "Gypsum partitions", "Partitions", "Sqm", 10), ("Tiler", "Vitrified tile flooring", "Flooring", "Sqm", 8)]
DIARY_INSTR = {"bld": [("Change the lobby floor tile layout to the 600 × 1200 pattern", "Arch. Suresh Menon (PMC)"), ("Expedite podium waterproofing before the rains", "Client PM"),
		("Hold work at grid C/4 till the revised drawing comes", "Structural consultant"), ("Add a 150 mm upstand around the terrace plant room", "Client engineer")],
	"road": [("Provide additional speed breakers near the school at Ch. 3+400", "Executive Engineer"), ("Raise the culvert C-7 headwall by 300 mm", "Assistant Engineer")],
	"peb": [("Add two more dock levellers on the north side", "Client PM")], "fit": [("Change the guest-room ceiling to a coffered design on floor 7", "Interior designer")]}
SCRAP_BUYERS = [("Kochi Metal Traders (fictional)", "Kochi", "Edappally Industrial Estate", "682024", "AAKFK7712A", 0),
	("Sree Scrap Merchants (fictional)", "Aluva", "Kalamassery Road", "683104", "AAKFS7713B", 0), ("Malabar Recyclers — PCB authorised (fictional)", "Kozhikode", "Nallalam", "673027",
	"AAKCM7714C", 1)]


def cn_ops(c):
	"""B3: productivity norms and man-days on the DPRs, a week of site diary with instructions, last month's logbook and
	hire bills of the hired machines, returnable props and scaffolding at two sites, scrap lots with bids and one sale,
	a subcontractor advance with its recovery on the next bill, and AAC blocks issued free to the masonry contractor."""
	from hipersign_trading.api import construction as CN
	from hipersign_trading.api import construction_ops as OPS
	from hipersign_trading.api import construction_site as S
	from hipersign_trading.api import projects as P

	if not frappe.db.exists("DocType", "Site Diary") or frappe.db.exists("Productivity Norm", {"match": "plaster"}):
		return
	frappe.flags.hs_cn_skip_role = True
	try:
		# productivity: the norms, and the man-days on each DPR (each site a little above or below the standard)
		N = []
		for tr, act, m, u, out in PROD_NORMS:
			N.append(frappe.get_doc({"doctype": "Productivity Norm", "trade": tr, "activity": act, "match": m, "unit": u, "output_per_manday": out}).insert(ignore_permissions=True))
		eff = {"P-2401": .93, "P-2402": .81, "P-2403": 1.06, "P-2405": .97, "P-2406": .88}
		for d in frappe.get_all("Daily Progress Report", fields=["name", "project", "activity", "actual_qty"]):
			n = next((x for x in N if x.match.lower() in (d.activity or "").lower()), None)
			if n and flt(d.actual_qty):
				f = eff.get(d.project, .95) * (1 + (sum(map(ord, d.name)) % 7 - 3) / 100)
				frappe.db.set_value("Daily Progress Report", d.name, {"trade": n.trade, "mandays": max(1, round(flt(d.actual_qty) / (n.output_per_manday * f), 1))}, update_modified=False)
		# site diary: the last six working days on each live site
		k = 0
		for p in PROJECTS:
			if p[11] >= 22:
				continue
			for dd in range(-12, 0):
				if getdate(D(dd)).weekday() == 6 or (dd < -6 and p[0] != "P-2401"):
					continue
				k += 1
				L = DIARY_INSTR[p[3]]
				ins = L[k % len(L)] if k % 4 == 0 or (p[0] == "P-2401" and dd == -10) else None
				frappe.get_doc({"doctype": "Site Diary", "project": p[0], "diary_date": D(dd), "recorded_by": p[8], "weather": ["Clear", "Cloudy", "Clear", "Light rain", "Heavy rain"][k % 5],
					"visitors": ["Client engineer — slab inspection", "", "Labour officer — routine inspection", "Consultant — MEP coordination", ""][k % 5],
					"instructions": ins[0] if ins else None, "instruction_from": ins[1] if ins else None,
					"events": ["Concrete pour 42 cum completed by 6 pm", "Power cut 2 hours — DG used", "18 MT TMT received", "Scaffold inspection, 2 tags renewed", "Cube samples sent to the lab"][k % 5],
					"safety": ["Toolbox talk — work at height", "No incident", "Near miss reported — loose plank", "No incident"][k % 4]}).insert(ignore_permissions=True)
		# plant hire: the minimum in the hire terms, last month's logbook and one hire bill booked
		last = get_first_day(add_months(today(), -1))
		for e in frappe.get_all("Construction Equipment", filters={"ownership": "Hired"}, fields=["name", "equipment_name", "hire_basis", "planned_hours_month", "diesel_norm_lph", "project", "kind"]):
			if e.hire_basis == "Hour":
				frappe.db.set_value("Construction Equipment", e.name, "min_hours_month", 200 if e.kind != "Paver" else 120)
			first = flt(frappe.db.get_value("Equipment Log", {"equipment": e.name}, "start_hmr", order_by="log_date asc"))
			days = [x for x in range(get_last_day(last).day) if add_days(last, x).weekday() != 6]
			hrs = [round(flt(e.planned_hours_month) / 26 * (.7 + (i * 7 % 5) / 10), 1) for i in range(len(days))]
			cur = first - sum(hrs) - len(days) * .4
			for x, h in zip(days, hrs):
				frappe.get_doc({"doctype": "Equipment Log", "equipment": e.name, "project": e.project, "log_date": add_days(last, x), "operator": "Hirer's operator",
					"start_hmr": round(cur, 1), "end_hmr": round(cur + h + .4, 1), "idle_hours": .4, "diesel_litres": round(h * flt(e.diesel_norm_lph) * (1.14 if e.kind == "Excavator" else 1), 0),
					"work_done": "Site work"}).insert(ignore_permissions=True)
				cur = round(cur + h + .4, 1)
		pv = frappe.db.get_value("Construction Equipment", {"kind": "Paver"})
		if pv:
			OPS._a_eq_hire_book(pv, frappe._dict(month=str(last), date=add_days(get_last_day(last), 5)))
		# returnables: steel props and cuplock scaffolding bought for the central store, out at two sites
		cs = S.central_store(CO)
		for code, name, rate in (("PROP-3M", "Adjustable steel prop 3 m", 1150), ("CUPLOCK-V3", "Cuplock vertical 3 m", 980)):
			if not frappe.db.exists("Item", code):
				frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": name, "item_group": frappe.db.get_value("Item", "PLY-SHUT", "item_group"), "stock_uom": _uom("Nos"),
					"is_stock_item": 1, "is_purchase_item": 1, "hs_returnable": 1, "gst_hsn_code": "73084000" if frappe.db.exists("GST HSN Code", "73084000") else None,
					"valuation_rate": rate}).insert(ignore_permissions=True)
		frappe.db.set_value("Item", "PLY-SHUT", "hs_returnable", 1)
		_purchase(None, "Kerala Steel Traders Pvt. Ltd. (fictional)", [("PROP-3M", 900, 1150), ("CUPLOCK-V3", 600, 980)], D(-95), cs)
		for pid, lines, dd in (("P-2401", [("PROP-3M", 520), ("CUPLOCK-V3", 360)], -88), ("P-2402", [("PROP-3M", 260), ("CUPLOCK-V3", 140)], -50)):
			se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Transfer", "purpose": "Material Transfer", "company": CO, "project": pid,
				"hs_transfer_status": "Delivered", "hs_destination": P.site_warehouse(pid), "hs_vehicle": "KL-07-CD-8814", "hs_driver": "Ramesh P.",
				"items": [{"item_code": i, "qty": q, "s_warehouse": cs, "t_warehouse": P.site_warehouse(pid), "project": pid} for i, q in lines]})
			_post(se, D(dd))
			se.insert(ignore_permissions=True)
			se.submit()
		# scrap: three dealers, four lots — one sold last month, one with bids, two identified
		grp = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		terr = "India" if frappe.db.exists("Territory", "India") else frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
		for name, city, line1, pin, pan, pcb in SCRAP_BUYERS:
			if not frappe.db.exists("Customer", name):
				cu = frappe.get_doc({"doctype": "Customer", "customer_name": name, "customer_type": "Company", "customer_group": grp, "territory": terr})
				if cu.meta.has_field("gstin"):
					cu.gstin, cu.gst_category = gstin("32", pan), "Registered Regular"
				if cu.meta.has_field("pan"):
					cu.pan = pan
				cu.insert(ignore_permissions=True)
			_address(name, "Customer", name, "Kerala", city, line1, pin, gstin("32", pan))
		B = [b[0] for b in SCRAP_BUYERS]
		lots = [("P-2408", "Damaged shuttering plywood", 160, "Nos", 12800, 0, -28, [(B[0], 13600), (B[1], 12900), (B[2], 12100)], "sell"),
			("P-2401", "Steel scrap — cut bits of TMT", 3.8, "MT", 38000, 0, -6, [(B[0], 39200), (B[1], 38600), (B[2], 37900)], "bids"),
			("P-2401", "Empty cement bags (HDPE)", 14200, "Nos", 28400, 0, -3, [], None), ("P-2403", "Used engine oil", 640, "L", 9600, 1, -2, [], None)]
		for pid, desc, q, u, est, haz, dd, bids, step in lots:
			x = frappe.get_doc({"doctype": "Scrap Lot", "company": CO, "project": pid, "lot_date": D(dd), "description": desc, "qty": q, "uom": u, "estimate": est, "hazardous": haz,
				"bids": [{"bidder": b, "amount": a, "pcb_authorised": 1 if "PCB" in b else 0} for b, a in bids]})
			x.insert(ignore_permissions=True)
			if step:
				OPS._a_scrap_invite(x.name, frappe._dict())
			if step == "sell":
				OPS._a_scrap_sell(x.name, frappe._dict(date=D(dd + 4)))
		# subcontractor advance: a façade glazing work order on P-2402 with 10% advance, paid, and its first bill in draft
		b = CN.boq("P-2402")
		r = b.items[-1]
		w = frappe.get_doc({"doctype": "Subcontractor Work Order", "project": "P-2402", "supplier": "Precision MEP Services Pvt. Ltd.", "scope": "Façade glazing & cladding",
			"kind": "Item rate (with materials)", "wo_date": D(-45), "tds_pct": 2, "retention_pct": 5, "gst_rate": 18,
			"items": [{"item_no": r.item_no, "description": r.description, "unit": r.unit, "qty": r.qty, "rate": round(flt(r.rate) * .84, 2)}], "status": "Draft"})
		w.insert(ignore_permissions=True)
		w.db_set({"status": "Active", "advance": round(flt(w.value) * .1, -3), "advance_recovery_pct": 10})
		OPS._a_swo_adv_pay(w.name, frappe._dict(date=D(-40), ref="UTR 6118842017"))
		frappe.get_doc({"doctype": "Subcontractor Bill", "work_order": w.name, "bill_no": 1, "bill_date": D(-2), "period_to": D(-4), "supplier_invoice_no": f"RB01/{w.name[-3:]}",
			"items": [{"item_no": r.item_no, "this_qty": round(flt(r.qty) * .22, 2)}]}).insert(ignore_permissions=True)
		# free issue: the AAC blocks for BOQ 3.1 went to the masonry contractor (labour only)
		wo = frappe.db.get_value("Subcontractor Work Order", {"project": "P-2401", "kind": ["like", "Labour%"]})
		for se in frappe.db.sql("""select distinct e.name from `tabStock Entry` e join `tabStock Entry Detail` d on d.parent = e.name where e.docstatus = 1
				and e.purpose = 'Material Issue' and e.project = 'P-2401' and d.item_code = 'AAC-BLOCK'""", pluck=True):
			frappe.db.set_value("Stock Entry", se, "hs_sub_wo", wo, update_modified=False)
	finally:
		frappe.flags.hs_cn_skip_role = False


def cn_finish(c):
	"""The Capstone edition (every Construction module) and the menu."""
	from hipersign_trading import features, navigation

	s = frappe.get_doc("Hipersign Settings")
	if not s.get("setup_done"):
		s.setup_done = 1
		s.company_mode = s.company_mode or "Single company"
	features.set_switches(s, "Capstone")
	s.flags.ignore_mandatory = True
	s.save(ignore_permissions=True)
	navigation.apply()


STEPS = [cn_company, cn_customers, cn_projects, cn_tenders, cn_bonds, cn_billing, cn_measurements, cn_site, cn_resources, cn_costs, cn_business, cn_quality, cn_finance, cn_portal, cn_estimating, cn_controls2, cn_ops, cn_finish]
