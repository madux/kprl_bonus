"""Per-staff Q2 parity: app payouts vs workbook STAFF PAYOUT. Read-only.

Run: Get-Content -Raw tools/check_q2_parity.py | python odoo-bin shell -d DB
Env: KPRL_PERIOD (default 2026-Q2), KPRL_WORKBOOK (default v31 workbook).
Prints per-staff diffs plus engine totals vs BONUS ENGINE anchors.
"""
import os
import sys

try:
    TOOLS = os.path.dirname(os.path.abspath(__file__))
except NameError:
    TOOLS = "C:/Program Files/Odoo 17.0.20260507/server/custom/kprl/kprl_bonus/tools"
sys.path.insert(0, TOOLS)
import xlsx_min
import workbook_q2_data

Name = os.environ.get("KPRL_PERIOD", "2026-Q2")
WB = os.environ.get("KPRL_WORKBOOK", os.path.normpath(os.path.join(
    os.path.dirname(TOOLS), "..", "KPRL_Bonus_Calculator_v31_working1.xlsx")))
if not os.path.exists(WB):
    raise FileNotFoundError("v31 parity workbook not found: %s" % WB)

wb = xlsx_min.load_workbook(WB)
workbook_data = workbook_q2_data.load_workbook_data(WB, Name)
if not workbook_data["anchors"]["cached_formulas_are_current"]:
    anchors = workbook_data["anchors"]
    raise ValueError(
        "Workbook formula caches are stale: %s. Open and save the workbook "
        "in Excel before comparing cached STAFF PAYOUT results."
        % anchors["stale_formula_anchors"])
sp = wb["STAFF PAYOUT"]
xl = {}
r = 6
while True:
    ag = sp.cell(row=r, column=33).value
    if ag is None and r > 520:
        break
    if ag:
        xl[str(ag)] = {"h": sp.cell(row=r, column=8).value or 0.0,
                       "sub": sp.cell(row=r, column=23).value,
                       "gross": sp.cell(row=r, column=18).value or 0.0,
                       "net": sp.cell(row=r, column=36).value or 0.0,
                       "appr": sp.cell(row=r, column=12).value}
    r += 1
    if r > 600:
        break
print("excel rows: %d" % len(xl))
period = env["kprl.bonus.period"].search([("name", "=", Name)], limit=1)
lines = env["kprl.bonus.payout"].search([("period_id", "=", period.id)])
seen = set()
for p in lines.sorted(key=lambda x: (x.employee_id.staff_id or "~")):
    sid = (p.employee_id.staff_id or "?") if p.employee_id else "?"
    seen.add(sid)
    x = xl.get(sid)
    scode = ((p.subpool_id.code or "?") if p.subpool_id else "?").replace("-", "")
    if not x:
        print("EXTRA %s sub=%s pts=%s gross=%s net=%s" % (
            sid, scode, p.total_points,
            round(p.gross_payable or 0.0, 2), round(p.net_payable or 0.0, 2)))
        continue
    flags = []
    if abs((p.total_points or 0.0) - (x["h"] or 0.0)) > 0.005:
        flags.append("pts app=%s xl=%s" % (p.total_points, x["h"]))
    if (scode or "").replace("-", "") != (x["sub"] or "").replace("-", ""):
        flags.append("sub app=%s xl=%s" % (scode, x["sub"]))
    if abs((p.gross_payable or 0.0) - (x["gross"] or 0.0)) > 0.02:
        flags.append("gross app=%s xl=%s" % (round(p.gross_payable or 0.0, 2), x["gross"]))
    if abs((p.net_payable or 0.0) - (x["net"] or 0.0)) > 0.02:
        flags.append("net app=%s xl=%s" % (round(p.net_payable or 0.0, 2), x["net"]))
    if flags:
        blk = (p.blocking_errors_text or "").replace(chr(10), "; ")[:160]
        st = p.employee_id.status if p.employee_id else "?"
        appr = p.appraisal_score
        print("DIFF %s [status=%s appr=%s blocked=%s] :: %s" % (sid, st, appr, blk, " | ".join(flags)))
for sid, x in sorted(xl.items()):
    if sid not in seen:
        print("MISSING payout line for %s (xl pts=%s)" % (sid, x["h"]))
be = env["kprl.bonus.engine"].search([("period_id", "=", period.id)], order="create_date desc", limit=1)
if be:
    print("engine eff=%s sen_vpp=%s opm_vpp=%s sup_vpp=%s blended=%.6f" % (round(be.effective_pool or 0.0, 2), round(be.senior_mgt_value_point or 0.0, 2), round(be.opm_value_point or 0.0, 2), round(be.ops_sup_value_point or 0.0, 2), (be.effective_pool or 0.0) / (be.pool_contribution or 1.0) if be.pool_contribution else 0.0))
    print("company_mult=%s dept_weighted=%s" % (be.company_performance_multiplier, be.points_weighted_dept_multiplier))
for dm in env["kprl.dept.kpi.multiplier"].search([("period_id", "=", period.id)]):
    pts = sum(env["kprl.bonus.payout"].search([("period_id", "=", period.id), ("department_id", "=", dm.department_id.id)]).mapped("total_points"))
    print("DEPT %s score=%s mult=%s pts=%s" % (dm.department_id.name, dm.kpi_score, dm.multiplier, pts))
opm_rows = []
for p in lines:
    code = (p.subpool_id.code or "?") if p.subpool_id else "?"
    if code == "OPM":
        sid = (p.employee_id.staff_id or "?") if p.employee_id else "?"
        opm_rows.append((sid, p.total_points or 0.0))
print("OPM members %d sum=%.1f" % (len(opm_rows), sum(v for _, v in opm_rows)))
for sid, v in sorted(opm_rows):
    print("  OPM %s pts=%s" % (sid, v))
print("parity check done")
