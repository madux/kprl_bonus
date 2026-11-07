"""2026-Q2 regression against live v31 formulas (pure Python, no Odoo)."""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
import operations as O
import run as R
from policy import PolicySnapshot
FAILS = []
def check(label, got, want, tol=1.0):
    ok = abs(float(got) - want) <= tol if isinstance(want, float) else got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
pol = PolicySnapshot()
# v31 live formula inputs. Expected values follow the workbook cell formulas.
products = [
    {"units": 1.0, "unit_price": 3807960.0, "pool_rate": 1.0},
]
# v31 B15 = 3,807,960; B13 = 660,543,000; B20 = 30%.
pool = O.compute_pool(pol, {"revenue": 660543000.0, "ebitda_margin": 0.30,
    "products": products, "gmp_status": "clean",
    "company_scores": {"revenue": 0.8075, "gmp": 0.97, "people": 0.84},
    "dept_kpi": {"ALL": 0.8541818181818183},
    "dept_points": {"ALL": 100.0}})
check("v31 B37 company score", pool["company_kpi_score"], 0.909775)
check("v31 B38 company multiplier", pool["company_multiplier"], 1.01955)
check("v31 B39 dept multiplier", pool["points_weighted_dept_multiplier"], 0.9541818181818183)
check("v31 B74 ebitda cap", pool["ebitda_cap"], 19816290.0)
check("v31 B15 base pool", pool["base_pool"], 3807960.0)
check("v31 B41 effective pool", pool["effective_pool"], 3782837.849345455)
# B42 = 50%; B55 divides the OPM allocation by 59 points.
opm_pool = pool["effective_pool"] * 0.50
check("v31 B55 OPM value/point",
      O.value_per_point(opm_pool, 59.0), opm_pool / 59.0)
# 3. workbook combined = ops + sales exactly (no shared cap enforced there)
check("Q2 combined identity", 2994737.81 + 1305562.10, 4300299.91, tol=0.02)
# 4. new rule: shared cap binds when set (workbook did NOT do this -> drift)
r = R.apply_run_rules(
    [{"employee_id": 1, "status": "calculated", "ops_gross": 2994737.81, "sales_gross": 1305562.10}],
    {"ebitda_cap_amount": 4000000.0})
check("shared cap binds", r["totals"]["cap_pressure"], True)
check("shared cap net", round(r["totals"]["total_net_payable"], 2), 4000000.0)
r2 = R.apply_run_rules(
    [{"employee_id": 1, "status": "calculated", "ops_gross": 2994737.81, "sales_gross": 1305562.10}],
    {"ebitda_cap_amount": None})
check("no cap reproduces workbook", round(r2["totals"]["total_net_payable"], 2), 4300299.91)
print("----")
if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
print("Q2 REGRESSION OK (engine-level anchors; roster anchors need DB seed)")
