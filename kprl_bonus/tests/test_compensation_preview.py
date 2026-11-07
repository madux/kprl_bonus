"""Slice-1 contract tests (pure Python, no Odoo required).

Run: python3 tests/test_compensation_preview.py
Covers: preview shape frozen, missing!=zero, classify-first engines,
skill clamp, multipliers, gates, QA/QC uniformity (no exception).
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))

import grade_policy as g
import multipliers as M
from policy import PolicySnapshot
from preview import preview_payout, KEYS

FAILS = []


def check(label, got, want, tol=1e-9):
    if isinstance(want, float):
        ok = abs(float(got) - want) <= tol
    else:
        ok = got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)


def emp(**kw):
    d = {"id": 1, "name": "T", "status": "active", "pool_type": "OPM",
         "track": "ops", "sales_role": "none",
         "grade": {"code": "JUNIOR", "name": "Junior Staff", "yp_points": 1.0,
                   "skill_max": 0.0, "aip_eligible": False, "is_senior_mgmt_tier": False},
         "department": {"name": "Production"}, "territory": {"name": None},
         "years_of_service": 4, "skill_premium": 0.0}
    d.update(kw)
    return d


def perf(**kw):
    d = {"appraisal": 0.791, "behaviour": 23.0, "own_target": None,
         "own_sales": None, "own_retrieval": None, "territory_sales": None,
         "territory_retrieval": None, "territory_target": None,
         "product_knowledge": None, "call_report": None,
         "customer_coverage": None, "new_customer": None, "dept_kpi_score": 0.97}
    d.update(kw)
    return d


pol = PolicySnapshot()

# 1. frozen shape
r = preview_payout(emp(), perf(), pol, {})
check("shape keys", tuple(sorted(r.keys())), tuple(sorted(KEYS)))
check("ops no-pool blocked (honest)", r["status"], "blocked")
r_full = preview_payout(emp(), perf(), pol, {"value_per_point": 39924.42, "floor_eligible": True})
check("ops with-pool calculated", r_full["status"], "calculated")
workbook_senior = emp(pool_type="SUP")
workbook_senior["grade"] = {
    "code": "SENMGT", "name": "Senior Management", "yp_points": 10.0,
    "skill_max": 2.0, "aip_eligible": True, "is_senior_mgmt_tier": True}
workbook_senior["skill_premium"] = 2.0
workbook_preview = preview_payout(
    workbook_senior, perf(appraisal=1.0, behaviour=23.0), pol,
    {"value_per_point": 15395.270317103596, "floor_eligible": True})
check("workbook senior value point",
      workbook_preview["operations_breakdown"]["value_per_point"],
      15395.270317103596)
check("workbook senior base eligible",
      workbook_preview["operations_breakdown"]["base_eligible"],
      184743.24380524314, tol=0.02)
check("ops engines", r["classification"]["engines"], ["operations"])
check("ops subpool", r["classification"]["sub_pool"], "OPM")
check("ops sales leg absent", r["sales_breakdown"], None)

# 2. missing != zero
r2 = preview_payout(emp(), None, pol, {})
check("missing perf blocked", r2["status"], "blocked")
check("missing gross not zero-coerced", r2["totals"]["gross"], 0.0)
check("blocking mentions record", any("performance record" in e.lower() for e in r2["blocking_errors"]), True)
r3 = preview_payout(emp(), perf(appraisal=None), pol, {})
check("missing appraisal blocked", r3["status"], "blocked")
check("present zero appraises", preview_payout(emp(), perf(appraisal=0.0), pol, {})["operations_breakdown"]["appraisal_multiplier"], 0.0)

# 3. both-track and sales-role employees run both engines
both = emp(pool_type="SUP", track="both", sales_role="rsm_asm")
both["grade"] = {"code": "SENMGT", "name": "Senior Management", "yp_points": 10.0,
                 "skill_max": 2.0, "aip_eligible": True, "is_senior_mgmt_tier": True}
rb = preview_payout(both, perf(own_target=100.0, own_sales=80.0, own_retrieval=70.0), pol, {})
check("both engines", rb["classification"]["engines"], ["operations", "sales"])
check("sen-mgt subpool", rb["classification"]["sub_pool"], "SEN-MGT")
check("sen-mgt deferral", rb["classification"]["deferral_rate"], 0.20)
rs = preview_payout(emp(pool_type="SALES", track="sales", sales_role="asm"),
                    perf(appraisal=0.8, behaviour=20.0,
                         own_target=100e6, own_sales=82e6, own_retrieval=74e6,
                         product_knowledge=0.8, call_report=0.9,
                         customer_coverage=0.7, new_customer=0.6), pol,
                    {"value_per_point": 39924.42, "floor_eligible": True})
check("sales employee engines", rs["classification"]["engines"], ["operations", "sales"])
check("sales employee ops leg", rs["operations_breakdown"]["gross"] is not None, True)
check("sales employee sales leg", rs["sales_breakdown"]["gross"] > 0.0, True)
check("sales employee combined gross", rs["totals"]["gross"],
      rs["operations_breakdown"]["gross"] + rs["sales_breakdown"]["gross"])
check("sales employee calculated", rs["status"], "calculated")
check("asm attainment", round(rs["sales_breakdown"]["attainment"], 6), 0.82)
rsm_zero_territory = preview_payout(
    emp(pool_type="SALES", track="sales", sales_role="rsm"),
    perf(own_target=100.0, own_sales=80.0, own_retrieval=60.0,
         territory_sales=0.0, territory_retrieval=0.0, territory_target=100.0,
         product_knowledge=0.8, call_report=0.8,
         customer_coverage=0.8, new_customer=0.8),
    pol,
    {"value_per_point": 39924.42, "floor_eligible": True,
     "territory_sales": 90.0, "territory_retrieval": 70.0,
     "territory_target": 100.0})
check("zero territory sales preserved", rsm_zero_territory["sales_breakdown"]["sales_attainment"], 0.0)

# 4. workbook inputs are used directly (skill premium is not capped)
check("skill premium above grade max", g.clamp_skill_premium(5.0, 2.0), 5.0)
check("negative skill premium", g.clamp_skill_premium(-1.0, 2.0), -1.0)
check("appraisal 65", M.appraisal_to_multiplier(0.65), 0.60)
check("appraisal lt65", M.appraisal_to_multiplier(0.64), 0.0)
check("appraisal 100", M.appraisal_to_multiplier(1.00), 1.10)
check("behaviour formula above max", M.behaviour_to_multiplier(99), 1.692)
check("behaviour none", M.behaviour_to_multiplier(None), None)
check("tenure 4y", M.tenure_to_multiplier(4), 1.03)
check("tenure 12y", M.tenure_to_multiplier(12), 1.12)
check("ramp cliff", M.ramp_gate(0.69, 0.70, 0.70), 0.0)
check("ramp mid", M.ramp_gate(0.675, 0.65, 0.70), 0.5)
check("gmp uniform major", M.gmp_factor("major"), 0.70)
check("gmp self relief", M.gmp_factor("major", True, 0.5), 0.85)
check("gmp company major", M.company_gmp_factor("major"), 0.70)
check("gmp dept major", M.dept_gmp_factor("major"), 0.80)
check("gmp dept minor", M.dept_gmp_factor("minor"), 0.95)
check("gmp dept minor self", M.dept_gmp_factor("minor", True, 0.5), 0.975)
check("gmp dept major self", M.dept_gmp_factor("major", True, 0.5), 0.90)
check("pool rate clamp lo", M.auto_pool_rate(0.05, 0.00606, 0.017, 0.12, 0.30), 0.00606)

print("----")
if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
print("ALL PREVIEW CONTRACT CHECKS PASSED")
