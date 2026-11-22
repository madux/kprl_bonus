"""List bonus periods (default: 2026-Q2 lookalikes) with child counts.

Run: Get-Content -Raw tools/list_periods.py | python odoo-bin shell -d DB
Env: KPRL_PERIOD_SUBSTR (default "2026-Q2").
Read-only: changes nothing.
"""
import os

Sub = os.environ.get("KPRL_PERIOD_SUBSTR", "2026-Q2")
Period = env["kprl.bonus.period"]
found = Period.search([("name", "like", Sub)])
print("periods matching %r: %d" % (Sub, len(found)))
for p in found:
    counts = {}
    for model, field in [("kprl.performance.input", "period_id"),
                         ("kprl.bonus.parameter", "period_id"),
                         ("kprl.product.pool", "period_id"),
                         ("kprl.bonus.payout", "period_id"),
                         ("kprl.bonus.engine", "period_id"),
                         ("kprl.territory.engine", "period_id"),
                         ("kprl.dept.kpi.multiplier", "period_id")]:
        counts[model.split(".")[-1]] = env[model].search_count([(field, "=", p.id)])
    print("ID=%s NAME=%s EBITDA=%s KPI=%s REV_TARGET=%s STATE=%s" % (
        p.id, p.name, p.ebitda_margin, p.company_kpi, p.revenue_target, p.state))
    print("   children: %s" % counts)
