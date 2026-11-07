"""GMP factor tests (pure Python, no Odoo required).

Dept/individual schedule (Excel): Clean 1.00 / Minor 0.95 / Major 0.80 /
Critical 0.60, self-report retains the penalty share (default 0.5 halves
the cut per status). Company-wide Quarterly Incentive Pool band on the
mean of all dept factors: Clean avg 1.0-0.9 -> 1.0; Minor avg 0.89-0.70
-> 0.8; Major avg 0.69-0.5 -> 0.4; Critical avg below 0.5 -> 0.0.
Unknown statuses must raise, never silently pass or penalise.
"""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
sys.path.insert(0, str(BASE / "models"))
import multipliers as M
import kprl_math as KM
FAILS = []
def check(label, got, want, tol=1e-6):
    ok = abs(float(got) - want) <= tol if isinstance(want, float) else got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
def check_raises(label, fn):
    try:
        fn()
    except ValueError:
        print("PASS " + label + " raised ValueError")
        return
    print("FAIL " + label + " did not raise")
    FAILS.append(label)
# Dept schedule, not self-reported
check("clean", M.dept_gmp_factor("clean", False), 1.00)
check("minor", M.dept_gmp_factor("minor", False), 0.95)
check("major", M.dept_gmp_factor("major", False), 0.80)
check("critical", M.dept_gmp_factor("critical", False), 0.60)
# Self-reported halves the cut per status (retained share 0.5)
check("minor self", M.dept_gmp_factor("minor", True, 0.5), 0.975)
check("major self", M.dept_gmp_factor("major", True, 0.5), 0.90)
check("critical self", M.dept_gmp_factor("critical", True, 0.5), 0.80)
check("clean self unaffected", M.dept_gmp_factor("clean", True, 0.5), 1.00)
# Case/whitespace tolerant
check("Minor padded", M.dept_gmp_factor("  Minor ", False), 0.95)
# Unknown must raise, never silent
for bad in ["N/A", "", "mimor", "unknown"]:
    check_raises("dept rejects %r" % (bad,), lambda b=bad: M.dept_gmp_factor(b, False))
check_raises("company rejects N/A", lambda: M.company_gmp_factor("N/A", False))
# Wrappers agree with canonical
check("kprl_math minor", KM.dept_gmp_factor("minor", False), 0.95)
check("kprl_math critical self", KM.dept_gmp_factor("critical", True, 0.5), 0.80)
# Company band on dept-factor mean
check("band 1.0", KM.company_gmp_band(1.0), 1.0)
check("band 0.90", KM.company_gmp_band(0.90), 1.0)
check("band 0.89", KM.company_gmp_band(0.89), 0.8)
check("band 0.70", KM.company_gmp_band(0.70), 0.8)
check("band 0.69", KM.company_gmp_band(0.69), 0.4)
check("band 0.50", KM.company_gmp_band(0.50), 0.4)
check("band below 0.5", KM.company_gmp_band(0.49), 0.0)
# Workbook parity: Production critical-no -> 0.60; minor-no -> 0.95
check("production parity", M.dept_gmp_factor("critical", False), 0.60)
check("minor dept parity", M.dept_gmp_factor("minor", False), 0.95)
if FAILS:
    print("FAILURES: %s" % FAILS)
    raise SystemExit(1)
print("ALL GMP TESTS PASSED")
