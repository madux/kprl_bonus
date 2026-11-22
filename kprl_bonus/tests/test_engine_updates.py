"""AJ6 cap + PK normalization tests (pure Python, no Odoo required)."""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
import operations as O
import sales as S
from policy import PolicySnapshot
FAILS = []
def check(label, got, want, tol=1e-6):
    ok = abs(float(got) - want) <= tol if isinstance(want, float) else got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
pol = PolicySnapshot()
# AJ6: normal cap binds below 90% appraisal
big = {"base_points": 10.0, "skill_premium": 2.0, "skill_max": 2.0,
       "years_of_service": 12, "malus_percent": 0.0, "deferral_rate": 0.0}
r = O.calculate_operations_payout(big,
    {"appraisal": 0.85, "behaviour": 25.0, "dept_kpi_score": 1.0},
    pol, {"value_per_point": 500000.0, "floor_eligible": True})
check("normal cap value", r["cap"], 2000000.0)
check("normal cap binds", r["net_payable"] <= 2000000.0, True)
check("cap adjustment", round(r["cap_adjustment"], 2) >= 0.0, True)
# AJ6: stretch cap at >=90%
r2 = O.calculate_operations_payout(big,
    {"appraisal": 0.95, "behaviour": 25.0, "dept_kpi_score": 1.0},
    pol, {"value_per_point": 500000.0, "floor_eligible": True})
check("stretch cap value", r2["cap"], 5000000.0)
check("stretch flag", r2["stretch_cap_applied"], True)
check("normal flag", r["stretch_cap_applied"], False)
# small payout unaffected
r3 = O.calculate_operations_payout(
    {"base_points": 1.0, "skill_premium": 0.0, "skill_max": 0.0,
     "years_of_service": 4, "malus_percent": 0.0, "deferral_rate": 0.0},
    {"appraisal": 0.791, "behaviour": 23.0, "dept_kpi_score": 0.97},
    pol, {"value_per_point": 39924.42, "floor_eligible": True})
check("small net untouched", round(r3["net_payable"], 2), round(r3["immediate_payment"], 2))
# PK normalization: team 0.2..0.8 -> effective 0..1
entries = [
    {"employee_id": 1, "role": "asm", "own_target": 100.0, "own_sales": 80.0, "own_retrieval": 70.0,
     "product_knowledge": 0.2, "call_report": 0.5, "customer_coverage": 0.5, "new_customer": 0.5,
     "years_of_service": 3, "territory_key": "T1"},
    {"employee_id": 2, "role": "asm", "own_target": 100.0, "own_sales": 80.0, "own_retrieval": 70.0,
     "product_knowledge": 0.8, "call_report": 0.5, "customer_coverage": 0.5, "new_customer": 0.5,
     "years_of_service": 3, "territory_key": "T1"},
]
pmap = S.normalize_pk_team(entries, pol)
check("pk min->0", pmap[1], 0.0)
check("pk max->1", pmap[2], 1.0)
# degenerate: all equal -> raw fallback
same = [dict(e, product_knowledge=0.5) for e in entries]
pmap2 = S.normalize_pk_team(same, pol)
check("pk degenerate raw", pmap2[1], 0.5)
# batch with flag on uses effective pk
pol_norm = PolicySnapshot(**{**pol.__dict__, "pk_normalization_enabled": True})
b = S.calculate_sales_batch([dict(e) for e in entries], pol_norm)
e1 = [x for x in b if x["employee_id"] == 1][0]
check("batch effective pk", e1["effective_pk"], 0.0)
check("batch kpi uses eff pk", round(e1["kpi_multiplier"], 6),
      round(0.80 + (0.0 * 0.40 + 0.5 * 0.10 + 0.5 * 0.30 + 0.5 * 0.20) * 0.40, 6))
# flag off -> no effective pk
b2 = S.calculate_sales_batch([dict(e) for e in entries], pol)
check("flag off equals raw", [x for x in b2 if x["employee_id"] == 1][0].get("effective_pk"), 0.2)
print("----")
if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
print("ALL UPDATE CHECKS PASSED")
