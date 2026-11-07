"""Pure multiplier curves (no Odoo imports, no database, no side effects).

Consolidates models/kprl_math.py formulas plus the sales/pool helpers so
there is exactly one implementation of each curve. kprl_math.py is kept
untouched for backward compatibility; new code imports from here.
"""


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def normalize_fraction(score):
    """Accept 0-100 percent or 0-1 fraction -> 0-1 fraction. None -> None."""
    if score is None:
        return None
    s = float(score)
    return s / 100.0 if s > 2.0 else s


def score_to_multiplier(score):
    """Company/department KPI curve: <60%->0.70 ... 90%->1.00, 100%->1.20."""
    s = normalize_fraction(score if score is not None else 0.0)
    if s < 0.6:
        return 0.70
    if s < 0.7:
        return 0.70 + (s - 0.6) / 0.1 * 0.1
    if s < 0.8:
        return 0.80 + (s - 0.7) / 0.1 * 0.1
    if s < 0.9:
        return 0.90 + (s - 0.8) / 0.1 * 0.1
    return min(1.20, 1.00 + (s - 0.9) / 0.1 * 0.2)


def appraisal_to_multiplier(appraisal):
    """65%->0.60, 75%->0.75, 90%->0.90, 100%->1.10; below 65% -> 0."""
    if appraisal is None:
        return None
    a = normalize_fraction(appraisal)
    if a < 0.65:
        return 0.0
    if a < 0.75:
        return 0.60 + (a - 0.65) / 0.10 * 0.15
    if a < 0.90:
        return 0.75 + (a - 0.75) / 0.15 * 0.15
    return min(1.10, 0.90 + (a - 0.90) / 0.10 * 0.20)


def behaviour_to_multiplier(behaviour, maximum=25.0):
    """Workbook STAFF PAYOUT formula: 0.90 + (n/maximum)*0.20."""
    if behaviour is None:
        return None
    mx = float(maximum or 25.0)
    return 0.90 + (float(behaviour) / mx) * 0.20


def tenure_to_multiplier(years, step=0.03, step_years=3, cap=0.12):
    """1 + min(cap, floor(years/step_years)*step). None -> None."""
    if years is None:
        return None
    import math
    return 1.0 + min(float(cap), math.floor(float(years) / int(step_years)) * float(step))


def ramp_gate(attainment, floor, minimum):
    """Configurable floor-to-minimum ramp. None input -> None.

    If floor >= minimum the gate is a hard cliff at minimum, else linear
    0->1 between floor and minimum, clamped.
    """
    if attainment is None:
        return None
    a = normalize_fraction(attainment)
    f = normalize_fraction(floor)
    m = normalize_fraction(minimum)
    if m <= f:
        return 1.0 if a >= m else 0.0
    denom = m - f
    if not denom:
        return 0.0
    return _clamp((a - f) / denom, 0.0, 1.0)


def sales_kpi_multiplier(pk, call, coverage, new, w_pk=0.40, w_call=0.10,
                         w_cov=0.30, w_new=0.20, floor=0.80, span=0.40):
    """0.80 + weighted*0.40. Any None input -> None (missing, not zero)."""
    if pk is None or call is None or coverage is None or new is None:
        return None
    w = (float(pk) * w_pk + float(call) * w_call
         + float(coverage) * w_cov + float(new) * w_new)
    return float(floor) + _clamp(w, 0.0, 1.0) * float(span)


def accelerator_factor(attainment, kick_in=1.00, ceiling=1.50, boost=0.50):
    """1 + boost*clamp((attainment-kick)/(ceiling-kick)). None -> None."""
    if attainment is None:
        return None
    a = normalize_fraction(attainment)
    k = normalize_fraction(kick_in)
    c = normalize_fraction(ceiling)
    if not (c - k):
        return 1.0
    return 1.0 + float(boost) * _clamp((a - k) / (c - k), 0.0, 1.0)


def profitability_factor(ebitda_margin, partial_gate, full_gate):
    """0 below partial, 1 at/above full, linear ramp between. None -> None."""
    if ebitda_margin is None:
        return None
    e = normalize_fraction(ebitda_margin)
    p = normalize_fraction(partial_gate)
    f = normalize_fraction(full_gate)
    if e < p:
        return 0.0
    if e >= f:
        return 1.0
    return (e - p) / (f - p) if (f - p) else 0.0


def auto_pool_rate(ebitda_margin, rate_min, rate_max, scale_start, scale_max):
    """Interpolated pool rate, clamped to [min, max]. None margin -> None."""
    if ebitda_margin is None:
        return None
    e = normalize_fraction(ebitda_margin)
    s = normalize_fraction(scale_start)
    t = normalize_fraction(scale_max)
    lo = float(rate_min)
    hi = float(rate_max)
    if not (t - s):
        return lo
    if e <= s:
        return lo
    if e >= t:
        return hi
    return lo + ((e - s) / (t - s)) * (hi - lo)


# Canonical blocking reasons. Each names the missing value AND where to
# enter it, so the UI never shows a bare "missing" message.
BLOCKING_REASONS = {
    "no_employee": "No employee selected - select an employee on the payout form",
    "inactive": "Employee is not active - reactivate the employee record to calculate",
    "no_grade": "Employee has no grade - assign a grade on the employee record",
    "no_record": "No performance record for this period and employee - add a Performance Inputs row, then press Calculate",
    "appraisal": "Appraisal is missing for this period - enter it in Performance Inputs (Appraisal % column), then press Calculate",
    "behaviour": "Behaviour is missing for this period - enter it in Performance Inputs (Behaviour /25 column), then press Calculate",
    "dept_kpi": "Department KPI is unavailable - set the score in Dept KPI Multipliers for the department, then press Calculate",
    "pool": "Pool value/point is unavailable for this period - open Bonus Engine for the period and Run Computation, then press Calculate",
    "sales_role": "Sales role is missing - set it on the employee record (sales track)",
    "sales_kpi": "Sales KPI inputs are incomplete - enter all four sales KPIs in Performance Inputs, then press Calculate",
    "attainment": "Sales attainment cannot be determined - check Own Target and Own Sales in Performance Inputs",
}


def missing_reason(key, field=None):
    """Blocking reason with entry location. Field-specific sales inputs
    name the Performance Inputs column."""
    if key == "sales_field":
        return "%s is missing for this period - enter it in Performance Inputs, then press Calculate" % (field or "value")
    return BLOCKING_REASONS.get(key, "Required input is missing - check Performance Inputs, then press Calculate")


COMPANY_GMP_FACTORS = {'clean': 1.00, 'minor': 0.90, 'major': 0.70, 'critical': 0.50}
DEPT_GMP_FACTORS = {'clean': 1.00, 'minor': 0.95, 'major': 0.80, 'critical': 0.60}

# Deprecated uniform alias (company table). Kept for backward compatibility.
GMP_FACTORS = dict(COMPANY_GMP_FACTORS)


GMP_PENALTY = {"clean": 0.00, "minor": 0.05, "major": 0.20, "critical": 0.40}

def _gmp_apply(table, status, self_reported=False, relief=0.50):
    if status is None or status is False:
        st = 'clean'
    else:
        st = str(status).strip().lower()
    if st not in table:
        raise ValueError(f"Invalid GMP status: {status!r}")
    base = table[st]
    if base >= 1.0:
        return 1.0
    if self_reported:
        # relief = share of the penalty RETAINED (0.5 halves the cut per status).
        penalty = (1.0 - base) * float(relief if relief else 0.50)
        return 1.0 - penalty
    return base


def company_gmp_factor(status, self_reported=False, relief=0.50):
    return _gmp_apply(COMPANY_GMP_FACTORS, status, self_reported, relief)


def dept_gmp_factor(status, self_reported=False, relief=0.50):
    return _gmp_apply(DEPT_GMP_FACTORS, status, self_reported, relief)


def gmp_factor(status, self_reported=False, relief=0.50):
    return company_gmp_factor(status, self_reported, relief)
