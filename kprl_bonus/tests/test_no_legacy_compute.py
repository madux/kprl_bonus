"""Single-writer guard: kprl.bonus.payout derived fields come only from the engine.

Run: python3 tests/test_no_legacy_compute.py
Fails if legacy per-field computes are reintroduced (they used to fight
_recalculate_from_engine and zeroed engine values, e.g. exception premium)
or if duplicate create/write/onchange overrides reappear.
"""
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SRC = (BASE / "models" / "bonus_payout.py").read_text(encoding="utf-8")
ENG = (BASE / "models" / "bonus_engine.py").read_text(encoding="utf-8")
FAILS = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        FAILS.append(label)


dead = ["compute_appraisal_mult", "compute_base_eligible", "_compute_total_point",
        "_compute_tenure_enhance", "_compute_payable", "_compute_gross_payable",
        "_compute_net_payable", "_compute_deferred", "_compute_deferred_rate",
        "_compute_adjusted", "_governance_adjustments", "_compute_behavioural_mult"]
for name in dead:
    check("legacy %s gone" % name, ("def %s" % name) not in SRC)

for name in ["def create(", "def write(", "def _onchange_fetch_appraisal("]:
    check("single %s" % name.strip(), SRC.count(name) == 1)

check("engine writer present", "def _recalculate_from_engine(" in SRC)
check("mapper present", "def payout_vals_from_payload(" in SRC)
m = re.search(r"@api\.depends\(([^)]*)\)\s*\n\s*def _compute_value_point", ENG)
check("value_point depends on pools",
      bool(m) and all(f in m.group(1) for f in
                      ("opm_pool", "senior_management_pool", "ops_sub_pool")))

print("----")
if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
print("ALL SINGLE-WRITER CHECKS PASSED")

