"""Shared bonus calculation helpers.

Every curve here replicates the KPRL Bonus Calculator v30 workbook formulas
exactly so company, department and appraisal multipliers stay consistent
across the module.
"""


def score_to_multiplier(score):
    """Workbook piecewise KPI-score -> multiplier curve (band-wise linear):
    0.6->0.7, 0.7->0.8, 0.8->0.9, 0.9->1.0, then +0.2 per 0.1 capped at 1.2.
    Used for company, department and AIP multipliers."""
    s = normalize_score(score or 0.0)
    if s < 0.6:
        return 0.7
    if s < 0.7:
        return 0.7 + (s - 0.6) / 0.1 * 0.1
    if s < 0.8:
        return 0.8 + (s - 0.7) / 0.1 * 0.1
    if s < 0.9:
        return 0.9 + (s - 0.8) / 0.1 * 0.1
    return min(1.2, 1.0 + (s - 0.9) / 0.1 * 0.2)


def appraisal_to_multiplier(score):
    """STAFF PAYOUT column M appraisal multiplier (score on 0-1 scale).

        a < 0.65          -> 0
        0.65 <= a < 0.75  -> 0.6 + (a - 0.65) / 0.1 * 0.15   (0.60 -> 0.75)
        0.75 <= a < 0.9   -> 0.75 + (a - 0.75) / 0.15 * 0.15 (slope 1.0)
        a >= 0.9          -> min(1.1, 0.9 + (a - 0.9) / 0.1 * 0.2)
    """
    a = score or 0.0
    if a < 0.65:
        return 0.0
    if a < 0.75:
        return 0.6 + (a - 0.65) / 0.1 * 0.15
    if a < 0.90:
        return 0.75 + (a - 0.75) / 0.15 * 0.15
    return min(1.1, 0.9 + (a - 0.9) / 0.1 * 0.2)


def behaviour_to_multiplier(behaviour, maximum=25.0):
    """STAFF PAYOUT column O: 0.9 + (n / 25) * 0.2  (range 0.90 - 1.10)."""
    n = behaviour or 0.0
    maximum = maximum or 25.0
    return 0.9 + (n / maximum) * 0.2


def tenure_to_multiplier(years):
    """TenureTbl implementing formula: 1 + MIN(0.12, INT(Yrs/3) * 0.03)."""
    y = years or 0.0
    return 1.0 + min(0.12, int(y / 3) * 0.03)


def ebitda_autoscore(ebitda_margin, gate_pct=30.0):
    """Scorecard EBITDA auto-score: MIN(1, EBITDA / Gate_Full). Accepts the
    margin as a percent (e.g. 30 or '30%') or a fraction (0.30)."""
    e = normalize_score(ebitda_margin or 0.0) * 100.0
    gate = 30.0 if gate_pct is None else gate_pct
    if gate <= 1.0:
        gate *= 100.0
    if not gate:
        return 0.0
    return min(1.0, e / gate)


def normalize_score(score):
    """Accept a KPI score as 0-1 fraction or 0-100 percent; return 0-1."""
    s = score or 0.0
    return s / 100.0 if s > 2.0 else s


STAFF_ID_PATTERN = r"(KPRL/[0-9A-Z]+|[0-9]+)"


def normalize_staff_id(value):
    """Canonical staff-ID form: trimmed, uppercased, dash -> slash.

    KPRL-0057 -> KPRL/0057. Bare digits (181818) pass through. None/False
    pass through for callers to handle. Never raises."""
    if value is None or value is False:
        return value
    return str(value).strip().upper().replace("-", "/")


def check_staff_id(value):
    """Validate canonical staff-ID format. Returns normalized value.

    Raises ValueError for anything that is neither KPRL/xxxx nor bare
    digits, so bad IDs fail loudly instead of drifting."""
    import re
    norm = normalize_staff_id(value)
    if not norm or not re.fullmatch(STAFF_ID_PATTERN, norm):
        raise ValueError(f"Invalid staff ID: {value!r}. Use KPRL/xxxx.")
    return norm


def staff_id_variants(number):
    """Search spellings covering the dash/slash drift (KPRL-043/KPRL/043)."""
    if number is None or number is False:
        return []
    raw = str(number).strip()
    if not raw:
        return []
    out = []
    for cand in (raw, normalize_staff_id(raw), raw.replace("/", "-")):
        if cand and cand not in out:
            out.append(cand)
    return out


def parse_pms_employment_date(value):
    """Parse PMS employment_date (contract: ISO YYYY-MM-DD string or null).

    Returns a datetime.date or None. Missing/blank -> None (caller keeps
    the existing value); unparseable -> None (caller warns and keeps the
    existing value, so one bad record never wipes tenure)."""
    import re
    from datetime import date as _date
    from datetime import datetime as _dt
    if value is None or value is False:
        return None
    if isinstance(value, _dt):
        return value.date()
    if isinstance(value, _date):
        return value
    txt = str(value).strip()
    if not txt:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", txt):
        return None
    try:
        return _date.fromisoformat(txt)
    except ValueError:
        return None


# Department GMP severity factors (REFERENCE TABLES col I). Halved when the
# breach was self-reported (GMP_SelfRelief = 0.50).
GMP_SEVERITY_FACTORS = {
    'clean': 0.0,
    'minor': 0.05,
    'major': 0.20,
    'critical': 0.40,
}

# Company-level GMP gate penalties (BONUS ENGINE Gate 2) — harsher than the
# department table.
GMP_GATE_PENALTIES = {
    'clean': 0.0,
    'minor': 0.10,
    'major': 0.30,
    'critical': 0.50,
}


def _canonical_gmp(kind, status, self_reported, relief):
    try:
        from .compensation.multipliers import (  # Odoo package context
            dept_gmp_factor as _d, company_gmp_factor as _c)
    except ImportError:
        try:
            from compensation.multipliers import (  # pure-python test context
                dept_gmp_factor as _d, company_gmp_factor as _c)
        except ImportError:
            from multipliers import (  # flat sys.path context
                dept_gmp_factor as _d, company_gmp_factor as _c)
    fn = _d if kind == "dept" else _c
    return fn(status, self_reported, relief if relief else 0.5)


def dept_gmp_factor(status, self_reported=False, self_relief=0.5):
    return _canonical_gmp("dept", status, self_reported, self_relief)


def company_gmp_factor(status, self_reported=False, self_relief=0.5):
    return _canonical_gmp("company", status, self_reported, self_relief)


# --- Profitability gate (BONUS ENGINE B18-B22 continuous ramp) ---
# Workbook: B18 Gate_Full (full unlock), B19 Gate_Partial (ramp START, NOT
# partial payout), B20 actual EBITDA margin, B21 gate factor 0..1.
# margin < ramp_start        -> 0.0 (LOCKED, no pool)
# ramp_start <= margin < full -> (margin - ramp_start) / (full - ramp_start)
# margin >= full              -> 1.0 (FULLY OPEN)
# At exactly ramp_start the factor is 0. Each 1pp of margin between
# 20%-30% releases 10% of the pool. No cliff, smooth ramp 0 -> 1.

DEFAULT_RAMP_START = 0.20
DEFAULT_FULL_UNLOCK = 0.30


def profitability_gate(margin_frac, ramp_start=DEFAULT_RAMP_START, full_unlock=DEFAULT_FULL_UNLOCK):
    if margin_frac is None or margin_frac is False:
        raise ValueError('EBITDA margin missing for active period (never default to 0)')
    if full_unlock is None or ramp_start is None:
        raise ValueError('Gate thresholds missing')
    ramp = float(ramp_start)
    full = float(full_unlock)
    # Accept percent (e.g. 25) or fraction (0.25)
    m = float(margin_frac)
    if m > 2.0:
        m /= 100.0
    if ramp > 2.0:
        ramp /= 100.0
    if full > 2.0:
        full /= 100.0
    if full <= ramp:
        raise ValueError('Full unlock threshold must exceed ramp start')
    if m < ramp:
        return 0.0
    if m >= full:
        return 1.0
    return (m - ramp) / (full - ramp)


def profitability_gate_label(factor, margin_frac=None):
    try:
        f = float(factor or 0.0)
    except (TypeError, ValueError):
        f = 0.0
    if f <= 0.0:
        return 'LOCKED - no pool'
    if f >= 1.0:
        return 'FULLY OPEN - 100%'
    return 'PARTIAL - %.1f%% of pool released' % (f * 100.0)

# --- Company GMP band (Quarterly Incentive Pool gate) ---
# Company-wide GMP status = average of all dept GMP factors, then banded:
# Clean avg 1.0-0.9 -> 1.0 | Minor avg 0.89-0.70 -> 0.8 |
# Major avg 0.69-0.5 -> 0.4 | Critical avg below 0.5 -> 0.0.
# Input: simple mean of dept GMP factors (def_factor, 0-1).
# Self-report relief applies ONLY at dept level (already inside def_factor).
# avg >= 0.90 -> 1.0 | >= 0.70 -> 0.8 | >= 0.50 -> 0.4 | below 0.50 -> 0.0
COMPANY_GMP_BANDS = ((0.90, 1.0), (0.70, 0.8), (0.50, 0.4))


def company_gmp_band(avg_factor):
    if avg_factor is None or avg_factor is False:
        raise ValueError('Dept GMP average missing for active period (never default to 0)')
    a = float(avg_factor)
    if a > 2.0:
        a /= 100.0
    for threshold, factor in COMPANY_GMP_BANDS:
        if a >= threshold:
            return factor
    return 0.0
