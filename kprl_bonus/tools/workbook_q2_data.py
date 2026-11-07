"""Pure parser for the v31 workbook (no Odoo dependency).

Exposes load_workbook_data(path) returning plain dicts for the 2026-Q2
demo import: employees, Q2 performance rows, SKUs, CONTROL parameters,
department scores, quarter rows. Formula anchors are recalculated from
their source inputs instead of trusting possibly stale XLSX formula caches.
Unit conversion to Odoo field units happens in import_workbook_q2.py.

Run standalone: python3 tools/workbook_q2_data.py
"""
try:
    import openpyxl as _oxl
    _HAS_OPENPYXL = hasattr(_oxl, "load_workbook")
except ImportError:
    _oxl = None
    _HAS_OPENPYXL = False
import xlsx_min as _mini
from pathlib import Path
import sys

MODEL_DIR = str(Path(__file__).resolve().parents[1] / "models")
if MODEL_DIR not in sys.path:
    sys.path.insert(0, MODEL_DIR)
from compensation import multipliers as _M

WORKBOOK_DEFAULT = str(
    Path(__file__).resolve().parents[2]
    / "KPRL_Bonus_Calculator_v31_working1.xlsx")

GRADE_MAP = {
    "Senior Management": "SENMGT",
    "Senior Managers - Tier 1": "TIER1",
    "Senior Managers - Tier 2": "TIER2",
    "Senior Managers - Tier 3": "TIER3",
    "Team Leads - Tier 1": "LEAD1",
    "Ast. Team Leads": "ALEAD",
    "Asst. Manager": "ASMGR",
    "Manager": "MGR",
    "1st Level Supervisor": "SUP1",
    "2nd Level Supervisor": "SUP2",
    "Junior Staff": "JUNIOR",
    "Hygiene Staff": "HYGIENE",
    "ASM": "SALES",
    "RSM+ASM": "SALES",
}

DEPT_MAP = {
    "Admin": "Administration",
    "HR": "Human Resources",
    "Inventory": "Inventory Dept",
    "Marketing": "Marketing Dept",
    "Production": "Production",
    "Logistics": "Logistics",
    "Diagnostics": "Diagnostics",
    "Finance": "Finance",
    "Management": "Management",
    "Hygiene": "Hygiene",
    "Sales": "Sales",
    "QA/QC": "QA/QC",
}

POOL_MAP = {"SUP-POOL": "SUP", "OPM": "OPM", "SALES": "SALES"}
TRACK_MAP = {"Ops": "ops", "Sales": "sales", "Ops+Sales": "both"}
SALES_ROLE_MAP = {"GM": "gm", "NSM": "nsm", "HeadTech": "headtech",
                  "ASM": "asm", "RSM": "rsm", "RSM+ASM": "rsm_asm",
                  "None": "none", None: "none"}
# (cell, parameter field, conversion). Conversions: pct = fraction*100
# (Odoo stores percent-numbers), frac = as-is fraction, money = as-is,
# yn = Yes/No to bool, onoff = On/Off to bool, select = mapped value.
CONTROL_MAP = [
    ("B8", "min_pool_rate", "pct"),
    ("B9", "max_pool_rate", "pct"),
    ("B10", "ebitda_scaling_start", "pct"),
    ("B11", "ebitda_max_rate_threshold", "pct"),
    ("B12", "full_gate_floor", "pct"),
    ("B13", "partial_gate_floor", "pct"),
    ("B24", "sales_commission_rate", "pct"),
    ("B25", "retrieval_commission_rate", "pct"),
    ("B26", "gm_poolshare_rate", "pct"),
    ("B27", "national_sm_pool", "pct"),
    ("B28", "head_technical_poolshare", "pct"),
    ("B29", "rsm_pool_share", "pct"),
    ("B31", "rsm_asm_dual_factor", "frac"),
    ("B34", "b34_top_mgmt_min_sales_attainment", "pct"),
    ("B35", "b35_top_mgmt_min_retrieval_rate", "pct"),
    ("B36", "b36_rsm_min_territory_sales_attainment", "pct"),
    ("B37", "b37_rsm_min_territory_retrieval_rate", "pct"),
    ("B38", "b38_asm_min_personal_sales_attainment", "pct"),
    ("B39", "b39_asm_min_personal_retrieval_rate", "pct"),
    ("B42", "aip_annual_rate", "pct"),
    ("B43", "aip_deferral_rate", "frac"),
    ("B43", "aip_deferred_rate_param", "pct"),
    ("B44", "senior_mgmt_deferred_rate", "pct"),
    ("B45", "tier1_deferred_rate", "pct"),
    ("B46", "tier2_deferred_rate", "pct"),
    ("B47", "minimum_floor", "money"),
    ("B48", "maximum_cap", "money"),
    ("B51", "sales_pk_weight", "pct"),
    ("B52", "sales_call_weight", "pct"),
    ("B53", "sales_coverage_weight", "pct"),
    ("B54", "sales_new_cust_weight", "pct"),
    ("B60", "annual_revenue_target", "money"),
    ("B76", "g_bonus_pool_cap_pct", "pct"),
    ("B77", "g_individual_quarterly_cap", "money"),
    ("B78", "g_leadership_premium", "frac"),
    ("B79", "g_gmp_self_report_relief", "frac"),
    ("B80", "g_company_gmp_self_reported", "yn"),
    ("B84", "h1_top_mgmt_sales_floor", "pct"),
    ("B85", "h2_rsm_sales_floor", "pct"),
    ("B86", "h3_asm_sales_floor", "pct"),
    ("B87", "h4_top_mgmt_retrieval_floor", "pct"),
    ("B88", "h5_rsm_retrieval_floor", "pct"),
    ("B89", "h6_asm_retrieval_floor", "pct"),
    ("B94", "i1_accelerator_kick_in", "pct"),
    ("B95", "i2_accelerator_ceiling", "pct"),
    ("B96", "i3_accelerator_boost", "pct"),
    ("B97", "i4_stretch_individual_cap", "money"),
    ("B101", "kpi_multiplier_floor", "frac"),
    ("B102", "kpi_multiplier_range", "frac"),
    ("B103", "pk_normalization_enabled", "onoff"),
    ("B109", "k1_dual_min_sales", "pct"),
    ("B110", "k2_dual_min_retrieval", "pct"),
    ("B111", "k3_dual_sales_floor", "pct"),
    ("B112", "k4_dual_retrieval_floor", "pct"),
    ("B120", "l1_pool_funding_method", "select"),
    ("B121", "l2_manual_pool_rate_override", "pctblank"),
    ("B122", "l3_gmp_compliance_status", "lower"),
    ("B126", "l_score_rev_weight", "pct"),
    ("B127", "l_score_ebitda_weight", "pct"),
    ("B128", "l_score_gmp_weight", "pct"),
    ("B129", "l_park1_weight", "pct"),
    ("B130", "l_park2_weight", "pct"),
    ("B131", "l_park3_weight", "pct"),
    ("B132", "l_score_people_weight", "pct"),
    ("B133", "l_park4_weight", "pct"),
    ("B134", "l_park5_weight", "pct"),
    ("B137", "l4_opm_share_pct", "pct"),
    ("B138", "senior_mgmt_share_pct", "pct"),
]

SCORE_MAP = [
    ("C126", "l_score_rev_score"),
    ("C128", "l_score_gmp_score"),
    ("C129", "l_park1_score"),
    ("C130", "l_park2_score"),
    ("C131", "l_park3_score"),
    ("C132", "l_score_people_score"),
    ("C133", "l_park4_score"),
    ("C134", "l_park5_score"),
]

ROLE_SHARES = {"gm": 0.10, "nsm": 0.08, "headtech": 0.05, "rsm": 0.22,
               "asm": 0.55}

FUNDING_MAP = {"SKU Contributions": "sku", "EBITDA-Scaled Rate": "ebitda",
               "EBITDA-scaled Rate": "ebitda"}
def convert(raw, conv):
    if conv == "pctblank" and raw in (None, ""):
        return 0.0
    if raw is None:
        return None
    if conv == "pct":
        return float(raw) * 100.0
    if conv == "frac":
        return float(raw)
    if conv == "money":
        return float(raw)
    if conv == "yn":
        return str(raw).strip().lower() in ("yes", "y", "true", "1")
    if conv == "onoff":
        return str(raw).strip().lower() == "on"
    if conv == "lower":
        return str(raw).strip().lower()
    if conv == "select":
        return FUNDING_MAP.get(str(raw).strip(), "sku")
    if conv == "pctblank":
        return float(raw) * 100.0 if raw not in (None, "") else 0.0
    return raw


def quarter_dates(name):
    year, qtr = name.split("-")
    starts = {"Q1": "-01-01", "Q2": "-04-01", "Q3": "-07-01", "Q4": "-10-01"}
    ends = {"Q1": "-03-31", "Q2": "-06-30", "Q3": "-09-30", "Q4": "-12-31"}
    return year + starts[qtr], year + ends[qtr]


def territory_of(note):
    if note and "Territory:" in str(note):
        return str(note).split("Territory:")[-1].strip()
    return None
def load_workbook_data(path, period="2026-Q2"):
    wb = _oxl.load_workbook(path, data_only=True) if _HAS_OPENPYXL else _mini.load_workbook(path)
    data = {"period": period}
    em = wb["EMPLOYEE MASTER"]
    employees = []
    for r in range(5, 600):
        sid = em.cell(row=r, column=1).value
        if not sid:
            continue
        grade_name = em.cell(row=r, column=3).value
        employees.append({
            "staff_id": str(sid).strip(),
            "name": em.cell(row=r, column=2).value,
            "grade_name": grade_name,
            "grade_code": GRADE_MAP.get(grade_name),
            "dept": DEPT_MAP.get(em.cell(row=r, column=4).value,
                                 em.cell(row=r, column=4).value),
            "pool": POOL_MAP.get(em.cell(row=r, column=5).value),
            "track": TRACK_MAP.get(em.cell(row=r, column=6).value),
            "base_pts": em.cell(row=r, column=7).value or 0.0,
            "skill": em.cell(row=r, column=8).value or 0.0,
            "years": em.cell(row=r, column=11).value or 0,
            "active": str(em.cell(row=r, column=13).value).strip().lower() in ("yes", "y", "true", "1"),
            "sales_role": SALES_ROLE_MAP.get(em.cell(row=r, column=15).value, "none"),
            "territory": territory_of(em.cell(row=r, column=14).value),
        })
    data["employees"] = employees
    pi = wb["PERFORMANCE INPUT"]
    data["active_period"] = pi["B4"].value
    perf = []
    for r in range(35, 400):
        if pi.cell(row=r, column=1).value != period:
            if pi.cell(row=r, column=1).value is None and pi.cell(row=r, column=2).value is None:
                continue
            else:
                continue
        perf.append({
            "staff_id": str(pi.cell(row=r, column=2).value).strip(),
            "appraisal": pi.cell(row=r, column=5).value,
            "behaviour": pi.cell(row=r, column=6).value,
            "own_target": pi.cell(row=r, column=7).value,
            "own_sales": pi.cell(row=r, column=8).value,
            "own_retr": pi.cell(row=r, column=9).value,
            "pk": pi.cell(row=r, column=10).value,
            "call": pi.cell(row=r, column=11).value,
            "coverage": pi.cell(row=r, column=12).value,
            "new": pi.cell(row=r, column=13).value,
        })
    data["perf"] = perf
    qdp = []
    for r in range(8, 33):
        name = pi.cell(row=r, column=1).value
        if not name:
            continue
        qdp.append({
            "name": name,
            "nat_target": pi.cell(row=r, column=2).value,
            "nat_retr_target": pi.cell(row=r, column=3).value,
            "ebitda": pi.cell(row=r, column=4).value,
            "kpi": pi.cell(row=r, column=5).value,
        })
    data["quarters"] = qdp
    pp = wb["PRODUCT POOL"]
    skus = []
    for r in range(7, 60):
        name = pp.cell(row=r, column=1).value
        if not name:
            continue
        skus.append({
            "name": name,
            "category": pp.cell(row=r, column=2).value,
            "units": pp.cell(row=r, column=3).value or 0.0,
            "price": pp.cell(row=r, column=4).value or 0.0,
            "rate_pct": float(pp.cell(row=r, column=5).value or 0.0) * 100.0,
            "margin_pct": float(pp.cell(row=r, column=8).value or 0.0) * 100.0,
        })
    data["skus"] = skus
    cp = wb["CONTROL PANEL"]
    params = {}
    for cell, field, conv in CONTROL_MAP:
        params[field] = convert(cp[cell].value, conv)
    params["l2_manual_pool_rate_enabled"] = cp["B121"].value not in (None, "")
    for cell, field in SCORE_MAP:
        params[field] = cp[cell].value
    data["params"] = params
    be = wb["BONUS ENGINE"]
    active_quarter = next(
        (q for q in qdp if q["name"] == data["active_period"]), None)
    margin = float(active_quarter["ebitda"] or 0.0) if active_quarter else 0.0
    quarterly_revenue = sum(
        float(sku["units"] or 0.0) * float(sku["price"] or 0.0)
        for sku in skus)
    sku_pool = sum(
        float(sku["units"] or 0.0) * float(sku["price"] or 0.0)
        * (float(sku["rate_pct"] or 0.0) / 100.0)
        for sku in skus)
    min_rate = float(params["min_pool_rate"] or 0.0) / 100.0
    max_rate = float(params["max_pool_rate"] or 0.0) / 100.0
    scale_start = float(params["ebitda_scaling_start"] or 0.0) / 100.0
    scale_max = float(params["ebitda_max_rate_threshold"] or 0.0) / 100.0
    manual_cell = cp["B121"].value
    if params["l1_pool_funding_method"] == "ebitda":
        rate = (float(manual_cell) if manual_cell not in (None, "")
                else _M.auto_pool_rate(
                    margin, min_rate, max_rate, scale_start, scale_max))
        base_pool = quarterly_revenue * rate
    else:
        base_pool = sku_pool

    gate_full = float(cp["B12"].value or 0.0)
    gate_partial = float(cp["B13"].value or 0.0)
    if margin < gate_partial:
        gate_factor = 0.0
    elif margin >= gate_full:
        gate_factor = 1.0
    else:
        gate_factor = (margin - gate_partial) / (gate_full - gate_partial)
    company_gmp = _M.company_gmp_factor(
        params["l3_gmp_compliance_status"],
        params["g_company_gmp_self_reported"],
        params["g_gmp_self_report_relief"])
    ebitda_score = min(1.0, margin / gate_full) if gate_full else 0.0
    company_score = sum(
        float(cp.cell(row=r, column=2).value or 0.0)
        * (ebitda_score if r == 127 else
           float(cp.cell(row=r, column=3).value or 0.0))
        for r in range(126, 135))
    company_multiplier = _M.score_to_multiplier(company_score)
    ref = wb["REFERENCE TABLES"]
    department_multipliers = {
        DEPT_MAP.get(ref.cell(row=r, column=1).value,
                     ref.cell(row=r, column=1).value):
        _M.score_to_multiplier(ref.cell(row=r, column=2).value or 0.0)
        for r in range(30, 42)
        if ref.cell(row=r, column=1).value
    }
    total_staff_points = 0.0
    weighted_department_points = 0.0
    for employee in employees:
        points = float(employee["base_pts"] or 0.0) + float(employee["skill"] or 0.0)
        total_staff_points += points
        weighted_department_points += (
            points * department_multipliers.get(employee["dept"], 1.0))
    department_multiplier = (
        weighted_department_points / total_staff_points
        if total_staff_points else 1.0)
    funded_pool = base_pool * gate_factor * company_gmp
    ebitda_amount = quarterly_revenue * margin
    cap = ebitda_amount * (float(cp["B76"].value or 0.0))
    effective_pool = min(
        funded_pool * (0.60 * company_multiplier
                       + 0.40 * department_multiplier),
        cap)
    opm_share = float(cp["B137"].value or 0.0)
    senior_share = float(cp["B138"].value or 0.0)
    senior_pool = effective_pool * (1.0 - opm_share) * senior_share
    senior_grade_names = {
        "Senior Management", "Senior Managers - Tier 1",
        "Senior Managers - Tier 2",
    }
    senior_points = sum(
        float(employee["base_pts"] or 0.0) + float(employee["skill"] or 0.0)
        for employee in employees
        if employee["pool"] == "SUP"
        and employee["grade_name"] in senior_grade_names)
    senior_vpp = senior_pool / senior_points if senior_points else 0.0
    formula_anchors = {
        "company_score": company_score,
        "company_multiplier": company_multiplier,
        "department_multiplier": department_multiplier,
        "effective_pool": effective_pool,
    }
    cached_anchors = {
        "company_score": be["B37"].value,
        "company_multiplier": be["B38"].value,
        "department_multiplier": be["B39"].value,
        "effective_pool": be["B41"].value,
    }
    stale_formula_anchors = {
        name: {"cached": cached, "formula": formula_anchors[name]}
        for name, cached in cached_anchors.items()
        if cached is None
        or abs(float(cached) - formula_anchors[name]) >=
        (0.02 if name == "effective_pool" else 1e-8)
    }
    data["anchors"] = {
        "base_pool": base_pool,
        "effective_pool": effective_pool,
        "sen_pool": senior_pool,
        "sen_points": senior_points,
        "sen_vpp": senior_vpp,
        "company_score": company_score,
        "company_multiplier": company_multiplier,
        "department_multiplier": department_multiplier,
        "cached_anchors": cached_anchors,
        "stale_formula_anchors": stale_formula_anchors,
        "cached_formulas_are_current": not stale_formula_anchors,
    }
    dash = wb["DASHBOARD"]
    terr_targets = {}
    for r in range(19, 23):
        terr = dash.cell(row=r, column=8).value
        if not terr:
            continue
        terr_targets[str(terr).strip()] = {
            "rsm": dash.cell(row=r, column=10).value or 0.0,
            "team": dash.cell(row=r, column=11).value or 0.0,
            "source": str(dash.cell(row=r, column=12).value or "").strip().lower(),
        }
    data["terr_targets"] = terr_targets
    dept_scores = []
    for r in range(30, 42):
        name = ref.cell(row=r, column=1).value
        if not name:
            continue
        dept_scores.append({
            "dept": DEPT_MAP.get(name, name),
            "score": ref.cell(row=r, column=2).value,
            "gmp": str(ref.cell(row=r, column=7).value or "Clean").strip().lower(),
            "selfrep": str(ref.cell(row=r, column=8).value or "No").strip().lower() in ("yes", "y"),
        })
    data["dept_scores"] = dept_scores
    return data


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else WORKBOOK_DEFAULT
    d = load_workbook_data(path)
    print("employees: %d" % len(d["employees"]))
    print("perf Q2 rows: %d" % len(d["perf"]))
    print("skus: %d" % len(d["skus"]))
    print("quarters: %s" % [q["name"] for q in d["quarters"] if q["ebitda"] is not None])
    print("anchors: %s" % d["anchors"])
    k1 = [e for e in d["employees"] if e["staff_id"] == "KPRL-001"][0]
    print("KPRL-001: %s" % k1)
    p1 = [p for p in d["perf"] if p["staff_id"] == "KPRL-001"][0]
    print("KPRL-001 perf: %s" % p1)
    print("min_pool_rate: %s max: %s funding: %s" % (d["params"]["min_pool_rate"], d["params"]["max_pool_rate"], d["params"]["l1_pool_funding_method"]))
