import pathlib as _pl
import sys as _sys

BASE = _pl.Path(__file__).resolve().parents[1]
_sys.path.insert(0, str(BASE / 'models'))

import kprl_math as m

FAILS = []


def check(label, got, want, tol=1e-9):
    ok = abs(got - want) <= tol
    print(('PASS' if ok else 'FAIL') + ' ' + label + ' got=' + str(got) + ' want=' + str(want))
    if not ok:
        FAILS.append(label)


# Workbook piecewise curve (band-wise linear, REFERENCE TABLES/BONUS ENGINE B38)
check('company s=0.50', m.score_to_multiplier(0.50), 0.7)
check('company s=0.599', m.score_to_multiplier(0.599), 0.7)
check('company s=0.60', m.score_to_multiplier(0.60), 0.7)
check('company s=0.65', m.score_to_multiplier(0.65), 0.75)
check('company s=0.70', m.score_to_multiplier(0.70), 0.8)
check('company s=0.80', m.score_to_multiplier(0.80), 0.9)
check('company s=0.87 (Production)', m.score_to_multiplier(0.87), 0.97)
check('company s=0.92 (QA/QC)', m.score_to_multiplier(0.92), 1.04)
check('company s=0.90', m.score_to_multiplier(0.90), 1.0)
check('company s=1.00', m.score_to_multiplier(1.00), 1.2)
check('company s=1.50 capped', m.score_to_multiplier(1.50), 1.2)
check('company pct 90 in', m.score_to_multiplier(90), 1.0)
# Excel anchors: scorecard total 0.909775 -> 1.01955 (B38); AIP 0.83975 -> 0.93975
check('anchor scorecard 0.909775', m.score_to_multiplier(0.909775), 1.01955, tol=1e-4)
check('anchor aip 0.83975', m.score_to_multiplier(0.83975), 0.93975, tol=1e-4)
# Appraisal: <0.65->0; 0.65-0.75 0.6->0.75; 0.75-0.9 slope 1.0; >=0.9 MIN(1.1, 0.9+(a-0.9)*2)
check('appraisal 0.64', m.appraisal_to_multiplier(0.64), 0.0)
check('appraisal 0.65', m.appraisal_to_multiplier(0.65), 0.6)
check('appraisal 0.75', m.appraisal_to_multiplier(0.75), 0.75)
check('appraisal 0.90', m.appraisal_to_multiplier(0.90), 0.9)
check('appraisal 1.00', m.appraisal_to_multiplier(1.00), 1.1)
check('appraisal 1.20 capped', m.appraisal_to_multiplier(1.20), 1.1)
# Behaviour: 0.9 + (n/25)*0.2
check('behav 0/25', m.behaviour_to_multiplier(0), 0.9)
check('behav 23/25', m.behaviour_to_multiplier(23), 0.9 + (23 / 25.0) * 0.2)
check('behav 25/25', m.behaviour_to_multiplier(25), 1.1)
# Tenure: 1 + MIN(0.12, INT(y/3)*0.03)
check('tenure 0y', m.tenure_to_multiplier(0), 1.0)
check('tenure 3y', m.tenure_to_multiplier(3), 1.03)
check('tenure 15y capped', m.tenure_to_multiplier(15), 1.12)
# GMP severity Clean/Minor/Major/Critical -> 1/0.95/0.80/0.60, halved if self-reported
check('gmp clean', m.dept_gmp_factor('clean', False), 1.0)
check('gmp minor', m.dept_gmp_factor('minor', False), 0.95)
check('gmp major', m.dept_gmp_factor('major', False), 0.80)
check('gmp critical', m.dept_gmp_factor('critical', False), 0.60)
check('gmp major self', m.dept_gmp_factor('major', True, 0.5), 0.90)
check('gmp critical self', m.dept_gmp_factor('critical', True, 0.5), 0.80)
# Sales KPI: weights 40/10/30/20, 0.80 + weighted*0.40 clamp 0.80-1.20
def sales_kpi(pk, call, cov, new):
    w = pk * 0.40 + call * 0.10 + cov * 0.30 + new * 0.20
    return max(0.80, min(1.20, 0.80 + w * 0.40))

check('sales kpi zeros', sales_kpi(0, 0, 0, 0), 0.80)
check('sales kpi ones', sales_kpi(1, 1, 1, 1), 1.20)
check('sales kpi mid', sales_kpi(0.8, 0.9, 0.7, 0.6), max(0.80, min(1.20, 0.80 + (0.8 * 0.40 + 0.9 * 0.10 + 0.7 * 0.30 + 0.6 * 0.20) * 0.40)))
# EBITDA auto-score MIN(1, EBITDA/22)
check('ebitda auto 29pct', m.ebitda_autoscore(29.0), 1.0)
check('ebitda auto 11pct', m.ebitda_autoscore(11.0), 11.0 / 22.0)
# Normalize helper
check('norm pct', m.normalize_score(90), 0.9)
check('norm frac', m.normalize_score(0.9), 0.9)
print('----')
if FAILS:
    print('HARNESS FAIL: ' + str(len(FAILS)) + ' checks failed')
    raise SystemExit(1)
print('HARNESS OK: all helper checks passed')
