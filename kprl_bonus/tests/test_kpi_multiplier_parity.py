"""v31 KPI multiplier Excel-parity tests (pure Python, no Odoo required).

Pins models/dept_kpi_multiplier._compute_multiplier mapping against the
v31 REFERENCE TABLES col C values, including the zero/blank edge
(Excel -> 0.7). Row order/scores from KPRL_Bonus_Calculator_v31_working1.
"""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
sys.path.insert(0, str(BASE / "models"))
import multipliers as M
import kprl_math as KM
FAILS = []
def dept_mult(score, mx=100.0):
    # Mirror of dept_kpi_multiplier._compute_multiplier mapping
    s = score or 0.0
    frac = s if s <= 1.0 else s / (mx if mx > 1.0 else 100.0)
    return M.score_to_multiplier(frac)
def check(label, got, want, tol=1e-9):
    ok = abs(float(got) - want) <= tol
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
EXCEL_ROWS = [
    ("Production", 0.87, 0.97), ("QA/QC", 0.92, 1.04),
    ("Logistics", 0.00, 0.70), ("Inventory", 0.83, 0.93),
    ("Diagnostics", 0.88, 0.98), ("Finance", 0.90, 1.00),
    ("HR", 0.85, 0.95), ("Admin", 0.77, 0.87),
    ("Marketing", 0.80, 0.90), ("Management", 0.86, 0.96),
    ("Hygiene", 0.82, 0.92), ("Sales", 0.89, 0.99),
]
for name, score, want in EXCEL_ROWS:
    check("excel parity %s" % name, dept_mult(score), want)
    check("kprl_math agrees %s" % name, KM.score_to_multiplier(score), want)
# Zero/blank edge: Excel -> 0.7
check("zero score", dept_mult(0.0), 0.7)
check("blank score", dept_mult(None), 0.7)
check("zero kprl_math", KM.score_to_multiplier(0.0), 0.7)
# Entry-scale handling unchanged: percent 87 == fraction 0.87 at max 100
check("percent entry", dept_mult(87.0), dept_mult(0.87))
if FAILS:
    print("FAILURES: %s" % FAILS)
    raise SystemExit(1)
print("ALL KPI PARITY TESTS PASSED")
