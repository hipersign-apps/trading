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
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

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


STEPS = [cn_company, cn_customers, cn_projects, cn_tenders, cn_bonds, cn_billing, cn_measurements, cn_site, cn_costs, cn_business, cn_finish]
