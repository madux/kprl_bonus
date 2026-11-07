"""Blocked-propagation tests: no more calculated-with-zero states."""
import re
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
from preview import preview_payout
from policy import PolicySnapshot
from multipliers import missing_reason
SRC = (BASE / "models" / "bonus_payout.py").read_text()
m = re.search(r"(def payout_vals_from_payload\(.*?\n(?:    .*\n|\n)*?)(?=\n    def |\nclass |\Z)", SRC)
assert m, "mapper not found"
NS = {}
exec(m.group(1), NS)
mapper = NS["payout_vals_from_payload"]
FAILS = []
def check(label, got, want):
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
# 1. full performance but NO pool -> BLOCKED with pool reason (was: calculated zeros)
r = preview_payout(emp(), perf(), pol, {})
check("no-pool status blocked", r["status"], "blocked")
check("no-pool reason mentions pool", any("pool" in e.lower() for e in r["blocking_errors"]), True)
check("no-pool stub flagged", r["operations_breakdown"]["stub"], True)
check("no-pool gross none", r["operations_breakdown"]["gross"], None)
# 2. with pool -> calculated with real gross
r2 = preview_payout(emp(), perf(), pol, {"value_per_point": 39924.42, "floor_eligible": True})
check("pool status calculated", r2["status"], "calculated")
check("pool gross set", r2["operations_breakdown"]["gross"] is not None, True)
check("pool gross equals engine", r2["operations_breakdown"]["gross"], r2["operations_breakdown"]["gross_bonus"])
check("totals carry gross", r2["totals"]["gross"], r2["operations_breakdown"]["gross_bonus"])
# 3. mapper guard: calculated status but no gross -> downgraded to blocked
v = mapper({"status": "calculated", "blocking_errors": [], "warnings": [],
            "classification": {}, "operations_breakdown": {"gross_bonus": None},
            "sales_breakdown": None, "totals": {}}, 1.0, 0.0, 0.0)
check("mapper downgrades", v["engine_status"], "blocked")
check("mapper zeros", v["net_payable"], 0.0)
check("mapper reason added", len(v["blocking_errors_text"]) > 0, True)
# 4. mapper honest path unchanged: blocked in -> blocked out
v2 = mapper({"status": "blocked", "blocking_errors": ["behaviour missing"],
             "classification": {}, "operations_breakdown": None,
             "sales_breakdown": None, "totals": {}}, 1.0, 0.0, 0.0)
check("blocked stays blocked", v2["engine_status"], "blocked")
print("----")
if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
# 5. no vague echoes: single specific reason, no duplicates
rd = preview_payout(emp(), perf(behaviour=None), pol, {"value_per_point": 39924.42, "floor_eligible": True})
check("one reason only", rd["blocking_errors"], [missing_reason("behaviour")])
rm = preview_payout(emp(), perf(appraisal=None, behaviour=None), pol, {"value_per_point": 1.0, "floor_eligible": True})
check("two distinct reasons", sorted(rm["blocking_errors"]),
      sorted([missing_reason("appraisal"), missing_reason("behaviour")]))
print("ALL BLOCKED-PROPAGATION CHECKS PASSED")
