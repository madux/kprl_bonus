# 2026-Q2 regression notes (engine-level)

Anchors: base 3,808,260 | effective 3,792,819.67 | OPM/pt 39,924.42 |
ops 2,994,737.81 | sales 1,305,562.10 | combined 4,300,299.91 |
KPRL-001 net 146,318.84 | deferred 212,450.41.

test_regression_q2.py is pinned to the REAL workbook inputs (BONUS ENGINE
dump): revenue 651,273,000, EBITDA 0.30, SKU funding, company scores
0.8075/1.0/0.97/0.84 -> 0.909775 -> mult 1.01955, dept mult 0.9605389,
cap 23,445,828 (12% of EBITDA), sub-pool points 57/93/17.

The kprl.bonus.engine effective pool follows the same workbook v30 chain
(BONUS ENGINE B28 -> B38/B39 -> B41): funded = base x gate x company GMP
gate factor (graduated, B26); effective = MIN(funded x (0.6 x company
performance multiplier + 0.4 x points-weighted dept multiplier),
12% x EBITDA).

Known deviations from the workbook (intentional, per approved decisions):
1. Shared cap: workbook paid ops+sales uncapped; new runs prorate both
   legs when the EBITDA cap binds.
2. QA/QC GMP: workbook insulated QA/QC (STAFF PAYOUT AH6); that removal
   was later reversed - the engine restores AH6/AJ6 (dept GMP forced to 1
   for QA/QC and net x 1/company-GMP-gate via the qa_relief overlay).
3. Floor tiers: old code applied the junior floor to hygiene staff too;
   new engine tiers correctly (20k / 30k).
4. Ops individual cap: AJ6 MIN(2M, 5M stretch at appraisal >= 90%) now
   enforced on the ops leg (previously only the sales leg was capped).
5. PK normalization: workbook supports team min-max effective PK
   (AD18, PK_Norm flag); engine implements it when the policy flag is on.

Pending (need 57-row roster seed in DB): ops aggregate, KPRL-001 net,
deferred total. DB-level asserts live in tools/validate_v30_odoo.py.
