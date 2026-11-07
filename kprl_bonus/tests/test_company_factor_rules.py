"""Company KPI and Quarterly Incentive Pool GMP rule tests.

Pure Python components used by the Odoo engine:
  - Company KPI multiplier = score_to_multiplier(mean of dept appraisal means)
  - Funded pool = base x profitability gate x banded company GMP factor
No Odoo required.
"""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models"))
import kprl_math as KM
FAILS = []


def check(label, got, want, tol=1e-6):
    ok = abs(float(got) - want) <= tol if isinstance(want, float) else got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)


# Company KPI comes from the mean of all dept appraisal means.
check("company KPI 0.7619", KM.score_to_multiplier(0.7619), 0.8619)
check("company KPI 0.90", KM.score_to_multiplier(0.90), 1.0)

# Funded pool uses the banded GMP factor, including a hard zero for critical.
check("band 0.75 minor", KM.company_gmp_band(0.75), 0.8)
check("funded 0.75", 4007960.0 * 1.0 * KM.company_gmp_band(0.75), 3206368.0)
check("band 0.40 critical", KM.company_gmp_band(0.40), 0.0)
check("funded 0.40", 4007960.0 * 1.0 * KM.company_gmp_band(0.40), 0.0)

if FAILS:
    print("FAILURES: %s" % FAILS)
    raise SystemExit(1)
print("ALL COMPANY FACTOR RULE TESTS PASSED")
