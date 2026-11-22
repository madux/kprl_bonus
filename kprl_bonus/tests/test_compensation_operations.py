"""Operations engine tests (pure Python, no Odoo required)."""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
import operations as O
from policy import PolicySnapshot
FAILS = []
def check(label, got, want, tol=1e-6):
    ok = abs(float(got) - want) <= tol if isinstance(want, float) else got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
pol = PolicySnapshot()
ebitda_pol = PolicySnapshot(**{**pol.__dict__, "funding_method": "ebitda"})
# pool: EBITDA-scaled path
pool = O.compute_pool(ebitda_pol, {"revenue": 223800000.0, "ebitda_margin": 0.45,
    "gmp_status": "clean",
    "company_scores": {"revenue": 1.0, "gmp": 1.0, "people": 1.0},
    "dept_kpi": {"PROD": 0.97}, "dept_points": {"PROD": 30.0}})
check("auto rate maxed", pool["auto_pool_rate"], 0.018)
check("base pool", pool["base_pool"], 223800000.0 * 0.018)
check("profit full", pool["profitability_factor"], 1.0)
check("funded", pool["funded_pool"], pool["base_pool"])
check("effective capped", pool["effective_pool"] <= pool["ebitda_cap"], True)
check("senior split", round(pool["senior_mgmt_pool"], 2), round(pool["effective_pool"] * 0.50 * 0.70, 2))
# pool: SKU path + partial gate ramp
pool2 = O.compute_pool(pol, {"revenue": 100.0, "ebitda_margin": 0.20,
    "products": [{"units": 10.0, "unit_price": 1000.0, "pool_rate": 0.01}],
    "gmp_status": "minor", "company_scores": {}, "dept_kpi": {}, "dept_points": {}})
check("sku base", pool2["base_pool"], 100.0)
check("gate starts at zero", pool2["profitability_factor"], 0.0)
check("minor gmp", pool2["gmp_factor"], 0.90)
# Workbook BONUS ENGINE B55:B57: IF(total points=0, 0, pool/total points)
check("vpp zero points", O.value_per_point(1000.0, 0.0), 0.0)
check("vpp zero pool", O.value_per_point(0.0, 4.0), 0.0)
check("vpp normal", O.value_per_point(1000.0, 4.0), 250.0)
check("workbook OPM vpp", O.value_per_point(1891418.9246727275, 59.0),
      32057.947875808939)
check("workbook senior vpp", O.value_per_point(1323993.2472709091, 86.0),
      15395.270317103596)
check("workbook ops support vpp", O.value_per_point(567425.6774018183, 20.0),
      28371.283870090916)
# A zero Value Point is a valid workbook result, not a missing pool.
r_zero_vpp = O.calculate_operations_payout(
    {"base_points": 1.0, "skill_premium": 0.0, "skill_max": 0.0,
     "years_of_service": 0, "malus_percent": 0.0, "deferral_rate": 0.0},
    {"appraisal": 0.80, "behaviour": 20.0, "dept_kpi_score": 0.80},
    pol, {"value_per_point": 0.0, "floor_eligible": False})
check("zero vpp is valid", r_zero_vpp["value_per_point"], 0.0)
check("zero vpp base eligible", r_zero_vpp["base_eligible"], 0.0)
check("zero vpp not blocked", r_zero_vpp.get("blocked_reason"), None)
# employee: KPRL-035-style junior
emp = {"base_points": 1.0, "skill_premium": 0.0, "skill_max": 0.0,
       "years_of_service": 4, "malus_percent": 0.0, "deferral_rate": 0.0}
perf = {"appraisal": 0.791, "behaviour": 23.0, "dept_kpi_score": 0.97}
r = O.calculate_operations_payout(emp, perf, pol, {"value_per_point": 39924.42, "floor_eligible": True})
check("gross positive", r["gross_bonus"] > 0, True)
check("exception none", r["exception_premium"], 0.0)
check("tenure 1.03", r["tenure_multiplier"], 1.03)
check("floor 30k", r["floor"], 30000.0)
check("no deferral", r["deferred_amount"], 0.0)
check("net==immediate", r["net_payable"], r["immediate_payment"])
# appraisal <65 -> zero appraisal multiplier propagates
r0 = O.calculate_operations_payout(emp, {"appraisal": 0.60, "behaviour": 23.0, "dept_kpi_score": 0.97},
                                   pol, {"value_per_point": 39924.42, "floor_eligible": True})
check("sub65 gross zero", r0["gross_bonus"], 0.0)
check("sub65 floor off", r0["floor"], 0.0)
# appraisal >=90 -> exception + stretch behaviour
r90 = O.calculate_operations_payout(emp, {"appraisal": 0.95, "behaviour": 25.0, "dept_kpi_score": 0.97},
                                    pol, {"value_per_point": 39924.42, "floor_eligible": True})
check("exception 10pct", round(r90["exception_premium"], 2), round(r90["adjusted_bonus"] * 0.10, 2))
# hygiene floor tier
rh = O.calculate_operations_payout({"base_points": 0.5, "skill_premium": 0.0, "skill_max": 0.0,
    "years_of_service": 1, "malus_percent": 0.0, "deferral_rate": 0.0},
    {"appraisal": 0.70, "behaviour": 10.0, "dept_kpi_score": 0.70},
    pol, {"value_per_point": 1.0, "floor_eligible": True})
check("hygiene floor 20k", rh["floor"], 20000.0)
check("hygiene final floored", rh["final_before_deferral"] >= 20000.0, True)
# manager grade: no floor
rm = O.calculate_operations_payout({"base_points": 3.0, "skill_premium": 0.0, "skill_max": 0.0,
    "years_of_service": 6, "malus_percent": 0.0, "deferral_rate": 0.0},
    {"appraisal": 0.88, "behaviour": 22.0, "dept_kpi_score": 1.04},
    pol, {"value_per_point": 31450.0, "floor_eligible": True})
check("manager no floor", rm["floor"], 0.0)
check("manager tenure 1.06", rm["tenure_multiplier"], 1.06)
# senior deferral 20%
rs = O.calculate_operations_payout({"base_points": 10.0, "skill_premium": 2.0, "skill_max": 2.0,
    "years_of_service": 12, "malus_percent": 0.0, "deferral_rate": 0.20},
    {"appraisal": 0.92, "behaviour": 25.0, "dept_kpi_score": 1.0},
    pol, {"value_per_point": 50000.0, "floor_eligible": True})
check("senior deferred 20pct", round(rs["deferred_amount"], 2), round(rs["final_before_deferral"] * 0.20, 2))
check("senior tenure cap", rs["tenure_multiplier"], 1.12)
# malus + gmp
rg = O.calculate_operations_payout(dict(emp, malus_percent=10.0),
    {"appraisal": 0.80, "behaviour": 20.0, "dept_kpi_score": 0.90,
     "dept_gmp_status": "major", "dept_gmp_self_reported": True},
    pol, {"value_per_point": 10000.0, "floor_eligible": True})
check("major self gmp", rg["gmp_factor"], 0.90)
check("malus applied", round(rg["net_payable"], 2), round(rg["immediate_payment"] * 0.90 * 0.90, 2))
# proration helper
check("proration over", O.pool_proration_factor(100.0, 60.0), 0.6)
check("proration under", O.pool_proration_factor(60.0, 100.0), 1.0)
check("proration zero", O.pool_proration_factor(0.0, 100.0), 1.0)
print("----")
if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
print("ALL OPERATIONS CHECKS PASSED")
