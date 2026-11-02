"""Reset Q2 derived lines so engines regenerate them cleanly. DESTRUCTIVE.

Deletes bonus payout lines + sales engine lines for the period (masters,
inputs, params, pool, engines themselves are kept). Nothing else is
touched. Run Bonus Engine + sales recompute afterwards.

Run: KPRL_CONFIRM=yes Get-Content -Raw tools/reset_q2_lines.py | python odoo-bin shell -d DB
Env: KPRL_PERIOD (default 2026-Q2). Without KPRL_CONFIRM=yes it only counts.
"""
import os

Name = os.environ.get("KPRL_PERIOD", "2026-Q2")
go = os.environ.get("KPRL_CONFIRM", "no").strip().lower() == "yes"
period = env["kprl.bonus.period"].search([("name", "=", Name)], limit=1)
if not period:
    print("no period %s" % Name)
    raise SystemExit(3)
payouts = env["kprl.bonus.payout"].search([("period_id", "=", period.id)])
teng = env["kprl.territory.engine"].search([("period_id", "=", period.id)])
slines = env["kprl.territory.engine.lines"].search([("territory_engine_id", "in", teng.ids)]) if teng else []
print("period %s: payouts=%d sales_lines=%d" % (Name, len(payouts), len(slines)))
if not go:
    print("dry run - nothing deleted. Set KPRL_CONFIRM=yes to reset.")
else:
    n_p, n_s = len(payouts), len(slines)
    payouts.unlink()
    slines.unlink()
    env.cr.commit()
    print("deleted %d payout lines + %d sales lines, committed" % (n_p, n_s))
    print("next: Bonus Engine action_compute for %s (regenerates payouts), then sales recompute" % Name)
