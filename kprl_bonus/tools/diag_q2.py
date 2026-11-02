"""Diagnose Q2 parity gaps: roster, points, sales engine state. Read-only.

Run: Get-Content -Raw tools/diag_q2.py | python odoo-bin shell -d DB
Env: KPRL_PERIOD (default 2026-Q2).
"""
import os

Name = os.environ.get("KPRL_PERIOD", "2026-Q2")
period = env["kprl.bonus.period"].search([("name", "=", Name)], limit=1)
if not period:
    print("no period %s" % Name)
    raise SystemExit(3)
print("PERIOD ID=%s EBITDA=%s KPI=%s" % (period.id, period.ebitda_margin, period.company_kpi))
payouts = env["kprl.bonus.payout"].search([("period_id", "=", period.id)])
print("payout lines: %d" % len(payouts))
subs = {}
for p in payouts:
    code = (p.subpool_id.code or "?") if p.subpool_id else "?"
    subs[code] = subs.get(code, 0.0) + (p.total_points or 0.0)
print("points by subpool: %s (excel OPM=57 SEN=93 OPSSUP=17)" % subs)
for p in payouts.sorted(key=lambda r: (r.employee_id.staff_id or "")):
    emp = p.employee_id
    print("ROW %s grade=%s pts=%s appr=%s gross=%s net=%s" % (
        emp.staff_id, (emp.grade_id.code or "?") if emp.grade_id else "?",
        p.total_points, p.appraisal_score,
        round(p.gross_payable or 0.0, 2), round(p.net_payable or 0.0, 2)))
eng = env["kprl.territory.engine"].search([("period_id", "=", period.id)])
print("sales engines: %d" % len(eng))
for e in eng:
    lines = e.kprl_employee_engine_line_ids
    print("engine ID=%s lines=%d total_payout=%s" % (e.id, len(lines), e.total_sales_payout))
beng = env["kprl.bonus.engine"].search([("period_id", "=", period.id)], order="create_date desc")
for b in beng:
    print("bonus engine ID=%s state=%s eff=%s sen_vpp=%s opm_vpp=%s sup_vpp=%s" % (
        b.id, b.state, round(b.effective_pool or 0.0, 2),
        round(b.senior_mgt_value_point or 0.0, 2),
        round(b.opm_value_point or 0.0, 2),
        round(b.ops_sup_value_point or 0.0, 2)))
