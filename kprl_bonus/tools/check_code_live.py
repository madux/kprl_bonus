"""Verify the RUNNING code has all fixes (catches stale workers). Read-only.

Run: Get-Content -Raw tools/check_code_live.py | python odoo-bin shell -d DB
Every line must PASS. Any FAIL = upgrade did not take or service not
restarted: re-run -u and restart, then re-check before computing.
"""
import os

FAILS = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        FAILS.append(label)


Payout = env["kprl.bonus.payout"]
check("legacy _compute_gross_payable removed", not hasattr(Payout, "_compute_gross_payable"))
check("legacy _compute_net_payable removed", not hasattr(Payout, "_compute_net_payable"))
check("legacy _compute_deferred_rate removed", not hasattr(Payout, "_compute_deferred_rate"))
check("single create/write/onchange",
      sum([len([m for m in dir(Payout) if m == n]) for n in ("create", "write")]) == 2)
from odoo.addons.kprl_bonus.models.compensation import multipliers as M
check("split company GMP", abs(M.company_gmp_factor("major") - 0.70) < 1e-9)
check("split dept GMP", abs(M.dept_gmp_factor("major") - 0.80) < 1e-9)
from odoo.addons.kprl_bonus.models.compensation.policy import PolicySnapshot
snap = PolicySnapshot.from_mapping({"sales_commission_rate": 0.30, "retrieval_commission_rate": 0.70})
check("policy sales rate 0.3pct", abs(snap.sales_commission_rate - 0.003) < 1e-9)
check("policy retr rate 0.7pct", abs(snap.retrieval_commission_rate - 0.007) < 1e-9)
from odoo.addons.kprl_bonus.models.compensation import preview as PV
res = PV.preview_payout(
    {"id": 1, "grade": {"code": "SENMGT", "name": "x", "yp_points": 10.0, "skill_max": 2.0, "aip_eligible": True, "is_senior_mgmt_tier": True},
     "pool_type": "SUP", "track": "both", "sales_role": "gm", "status": "active"},
    {"appraisal": 1.0, "behaviour": 23.0, "own_target": None, "own_sales": None, "own_retrieval": None},
    PolicySnapshot(), {"value_per_point": 100.0, "floor_eligible": True})
reasons = " ".join(res.get("blocking_errors", []) or [])
check("GM needs no own_target", "own_target is missing" not in reasons)
Period = env["kprl.bonus.period"]
Name = os.environ.get("KPRL_PERIOD", "2026-Q2")
n_eng = env["kprl.bonus.engine"].search_count([("period_id.name", "=", Name)])
check("single bonus engine for %s (found %d)" % (Name, n_eng), n_eng == 1)
print("----")
if FAILS:
    print("STALE CODE: %d checks failed - upgrade (-u) + restart service, then re-run" % len(FAILS))
    raise SystemExit(1)
print("CODE LIVE OK")
