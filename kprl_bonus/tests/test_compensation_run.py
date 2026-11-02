"""Run-level shared-cap tests (pure Python, no Odoo required)."""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
import run as runmod
FAILS = []
def check(label, got, want, tol=1e-6):
    ok = abs(float(got) - want) <= tol if isinstance(want, float) else got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
legs = [{"employee_id": 1, "status": "calculated", "ops_gross": 90000.0, "sales_gross": 120000.0},
        {"employee_id": 2, "status": "calculated", "ops_gross": 30000.0, "sales_gross": 0.0},
        {"employee_id": 3, "status": "blocked", "ops_gross": None, "sales_gross": None}]
r = runmod.apply_run_rules(legs, {"ebitda_cap_amount": None})
check("no-cap proration", r["totals"]["proration"], 1.0)
check("no-cap net", r["totals"]["total_net_payable"], 240000.0)
check("blocked passthrough", r["lines"][2]["net_payable"], None)
check("blocked count", r["totals"]["blocked_count"], 1)
r2 = runmod.apply_run_rules(legs, {"ebitda_cap_amount": 120000.0})
check("cap pressure", r2["totals"]["cap_pressure"], True)
check("cap proration", r2["totals"]["proration"], 0.5)
check("cap net", r2["totals"]["total_net_payable"], 120000.0)
check("line cap adj", r2["lines"][0]["cap_adjustment"], 105000.0)
r3 = runmod.apply_run_rules(legs, {"ebitda_cap_amount": 240000.0})
check("cap equal no pressure", r3["totals"]["cap_pressure"], False)
check("cap equal proration", r3["totals"]["proration"], 1.0)
print("----")
if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
print("ALL RUN CHECKS PASSED")
