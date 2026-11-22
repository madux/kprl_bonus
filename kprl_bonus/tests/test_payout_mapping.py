"""Old-form mapping test: payout_vals_from_payload == engine outputs.

Extracts the pure mapper from models/bonus_payout.py (no Odoo import)
and asserts every old-form field equals its engine counterpart on a
KPRL-035-style fixture, plus blocked-state zeros.
"""
import re
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
import operations as O
from policy import PolicySnapshot
SRC = (BASE / "models" / "bonus_payout.py").read_text()
m = re.search(r"(def payout_vals_from_payload\(.*?\n(?:    .*\n|\n)*?)(?=\n    def |\nclass |\Z)",
              SRC)
assert m, "mapper not found in bonus_payout.py"
NS = {}
exec(m.group(1), NS)
mapper = NS["payout_vals_from_payload"]
FAILS = []
def check(label, got, want, tol=1e-6):
    ok = abs(float(got) - want) <= tol if isinstance(want, float) else got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
pol = PolicySnapshot()
eng = O.calculate_operations_payout(
    {"base_points": 1.0, "skill_premium": 0.0, "skill_max": 0.0,
     "years_of_service": 4, "malus_percent": 0.0, "deferral_rate": 0.0},
    {"appraisal": 0.791, "behaviour": 23.0, "dept_kpi_score": 0.97},
    pol, {"value_per_point": 39924.42, "floor_eligible": True})
payload = {
    "status": "calculated", "blocking_errors": [], "warnings": [],
    "classification": {"engines": ["operations"], "total_points": 1.0, "deferral_rate": 0.0},
    "operations_breakdown": eng, "sales_breakdown": None,
    "totals": {"gross": eng["gross_bonus"]},
}
v = mapper(payload, dept_gmp=1.0, malus_pct=0.0, fixed_deduction=0.0)
for f, k in [("total_points", "total_points"), ("value_point", "value_per_point"),
             ("base_eligible", "base_eligible"), ("adjusted_amount", "adjusted_bonus"),
             ("exception_premium", "exception_premium"), ("gross_payable", "gross_bonus"),
             ("tenure_mult", "tenure_multiplier"), ("tenure_enhance", "tenure_enhanced"),
             ("final_floor", "final_before_deferral"), ("deferred_amount", "deferred_amount"),
             ("net_immediate", "immediate_payment")]:
    check("map %s" % f, v[f], eng[k])
check("net == engine net (no gov)", v["net_payable"], eng["net_payable"])
check("deferral pct scale", v["deferral_rate"], 0.0)
check("engine status", v["engine_status"], "calculated")
# governance overlay
v2 = mapper(payload, dept_gmp=0.9, malus_pct=10.0, fixed_deduction=1000.0)
check("gov overlay", round(v2["net_payable"], 2),
      round(max(eng["immediate_payment"] * 0.9 * 0.9, 0.0), 2))
check("gmp stored", v2["gmp_factor"], 0.9)
# AJ6 QA/QC company-gate relief: net x 1/company GMP gate factor.
vq = mapper(payload, dept_gmp=1.0, malus_pct=0.0, fixed_deduction=0.0,
            qa_relief=1.0 / 0.9)
check("qa relief net", round(vq["net_payable"], 2),
      round(min(eng["immediate_payment"] / 0.9, 2000000.0), 2))
combined_payload = dict(payload)
combined_payload.update({
    "classification": {"engines": ["operations", "sales"], "total_points": 1.0,
                       "deferral_rate": 0.0},
    "sales_breakdown": {
        "sales_commission": 100.0,
        "retrieval_commission": 200.0,
        "final_payout": 250.0,
    },
})
combined = mapper(combined_payload, dept_gmp=1.0, malus_pct=0.0)
# Workbook parity: STAFF PAYOUT is ops-only; sales commission is paid
# once, from the SALES ENGINE, and combined only in the PAYOUT REPORT.
check("staff payout excludes sales payout",
      combined["net_payable"], eng["net_payable"])
check("staff payout carries no sales commission", combined["sales_payout"], 0.0)
check("sales leg still flagged", combined["has_sales_leg"], True)
# Sales-only blocking reasons must not block the ops leg.
sales_blocked = dict(combined_payload)
sales_blocked.update({"status": "blocked",
                      "blocking_errors": ["own_target is missing for this period - enter it in Performance Inputs, then press Calculate",
                                          "Sales KPI inputs are incomplete - enter all four sales KPIs in Performance Inputs, then press Calculate"]})
sb = mapper(sales_blocked, dept_gmp=1.0, malus_pct=0.0)
check("sales-only block keeps ops net", sb["net_payable"], eng["net_payable"])
check("sales-only block status", sb["engine_status"], "calculated")
# Sales-pool staff with zero points: ops gross 0, hygiene floor (STAFF PAYOUT X6/Z6).
sales_ops = O.calculate_operations_payout(
    {"base_points": 0.0, "skill_premium": 0.0, "skill_max": 0.0,
     "years_of_service": 5, "malus_percent": 0.0, "deferral_rate": 0.0},
    {"appraisal": 0.72, "behaviour": 22.0, "dept_kpi_score": 0.89},
    pol, {"value_per_point": 28371.28, "floor_eligible": True})
sp = mapper({"status": "calculated", "blocking_errors": [], "warnings": [],
             "classification": {"engines": ["operations", "sales"], "total_points": 0.0, "deferral_rate": 0.0},
             "operations_breakdown": sales_ops,
             "sales_breakdown": {"final_payout": 41050.42}, "totals": {}}, 1.0, 0.0, 0.0)
check("sales pool staff payout = workbook floor", sp["net_payable"], 20000.0)
# blocked -> zeros + reasons, engine status preserved
vb = mapper({"status": "blocked", "blocking_errors": ["behaviour missing"],
             "classification": {}, "operations_breakdown": None,
             "sales_breakdown": None, "totals": {}}, 1.0, 0.0, 0.0)
check("blocked gross zero", vb["gross_payable"], 0.0)
check("blocked net zero", vb["net_payable"], 0.0)
check("blocked reason kept", vb["blocking_errors_text"], "behaviour missing")
check("blocked status", vb["engine_status"], "blocked")
print("----")
if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
# AJ6 cap flows through the mapper untouched (engine already capped)
big_eng = O.calculate_operations_payout(
    {"base_points": 10.0, "skill_premium": 2.0, "skill_max": 2.0,
     "years_of_service": 12, "malus_percent": 0.0, "deferral_rate": 0.0},
    {"appraisal": 0.85, "behaviour": 25.0, "dept_kpi_score": 1.0},
    pol, {"value_per_point": 500000.0, "floor_eligible": True})
big_payload = {"status": "calculated", "blocking_errors": [], "warnings": [],
    "classification": {"engines": ["operations"], "total_points": 12.0, "deferral_rate": 0.0},
    "operations_breakdown": big_eng, "sales_breakdown": None, "totals": {}}
vb2 = mapper(big_payload, 1.0, 0.0, 0.0)
check("mapper respects engine cap", vb2["net_payable"] <= 2000000.0, True)
check("mapper cap value", vb2["net_payable"], big_eng["net_payable"])
print("ALL MAPPING CHECKS PASSED")
