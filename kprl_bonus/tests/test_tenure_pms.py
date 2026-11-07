"""Tenure/PMS date tests (pure Python, no Odoo required).

Parity with STAFF PAYOUT col V: 1 + MIN(0.12, INT(yrs/3) * 0.03), and the
PMS employment_date contract (ISO YYYY-MM-DD string or null; anything else ->
None so the existing value is kept).
"""
import sys
from datetime import date
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models"))
import kprl_math as KM
FAILS = []
def check(label, got, want, tol=1e-9):
    ok = abs(float(got) - want) <= tol if isinstance(want, float) else got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
# Excel TenureTbl parity via tenure_to_multiplier
for yrs, want in [(0, 1.00), (1, 1.00), (3, 1.03), (6, 1.06), (8, 1.06),
                  (9, 1.09), (12, 1.12), (15, 1.12), (30, 1.12)]:
    check("tenure %syrs" % yrs, KM.tenure_to_multiplier(yrs), want)
# PMS date contract
check("valid date", KM.parse_pms_employment_date("2019-04-15"), date(2019, 4, 15))
check("null keeps old", KM.parse_pms_employment_date(None), None)
check("blank keeps old", KM.parse_pms_employment_date(""), None)
check("N/A rejected", KM.parse_pms_employment_date("N/A"), None)
check("zeros rejected", KM.parse_pms_employment_date("0000-00-00"), None)
check("bad month rejected", KM.parse_pms_employment_date("2024-13-01"), None)
check("datetime trimmed rejected", KM.parse_pms_employment_date("2019-04-15T00:00:00"), None)
check("date obj passthrough", KM.parse_pms_employment_date(date(2020, 1, 31)), date(2020, 1, 31))
if FAILS:
    print("FAILURES: %s" % FAILS)
    raise SystemExit(1)
print("ALL TENURE TESTS PASSED")
