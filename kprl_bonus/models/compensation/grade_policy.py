"""Grade contract over the authoritative kprl.grade records (pure Python).

The database is the source of truth for grade rows. This module defines:
- the calculation contract (what an engine needs from a grade),
- validation of live records against workbook defaults (repair lives in
  grade.action_reset_to_workbook, not here),
- skill-premium normalization, deferral mapping, and sub-pool classification.

It never hard-codes a competing grade table for runtime use.
"""
from dataclasses import dataclass

# Workbook reference defaults, used ONLY for validation/repair comparison
# and as explicit fallbacks when a grade record is missing. Live values
# always come from the kprl.grade row.
REFERENCE_DEFAULTS = {
    "SENMGT": {"base_points": 10.0, "skill_max": 2.0, "aip": True, "senior": True, "deferral": 0.20},
    "TIER1": {"base_points": 8.0, "skill_max": 1.0, "aip": True, "senior": True, "deferral": 0.20},
    "TIER2": {"base_points": 7.0, "skill_max": 1.0, "aip": True, "senior": True, "deferral": 0.20},
    "TIER3": {"base_points": 6.0, "skill_max": 0.0, "aip": False, "senior": False},
    "LEAD1": {"base_points": 5.0, "skill_max": 0.0, "aip": False, "senior": False},
    "ALEAD": {"base_points": 4.0, "skill_max": 0.0, "aip": False, "senior": False},
    "MGR": {"base_points": 3.0, "skill_max": 0.0, "aip": False, "senior": False},
    "ASMGR": {"base_points": 2.0, "skill_max": 0.0, "aip": False, "senior": False},
    "SUP1": {"base_points": 2.0, "skill_max": 0.0, "aip": False, "senior": False},
    "SUP2": {"base_points": 1.5, "skill_max": 0.0, "aip": False, "senior": False},
    "JUNIOR": {"base_points": 1.0, "skill_max": 0.0, "aip": False, "senior": False},
    "HYGIENE": {"base_points": 0.5, "skill_max": 0.0, "aip": False, "senior": False},
}

SENIOR_DEFERRAL_RATE = 0.20
DEFAULT_DEFERRAL_RATE = 0.0


@dataclass(frozen=True)
class GradeContract:
    code: str
    name: str
    base_points: float
    skill_max: float
    aip_eligible: bool
    is_senior_tier: bool
    deferral_rate: float


def from_grade_record(grade, warnings=None):
    """Build the contract from a live kprl.grade record (or None).

    Returns (contract_or_None, warnings_list). Missing grade -> (None, [...]);
    callers treat that as a blocking error, never as zero points.
    """
    warns = list(warnings or [])
    if grade is None or (hasattr(grade, "exists") and not grade.exists()):
        return None, warns + ["grade record is missing"]
    code = (getattr(grade, "code", "") or "").strip().upper()
    ref = REFERENCE_DEFAULTS.get(code, {})
    base = getattr(grade, "yp_points", None)
    if base is None:
        base = ref.get("base_points", 0.0)
        warns.append("grade %s: base points missing, reference default used" % code)
    skill_max = getattr(grade, "skill_max", None)
    if skill_max is None:
        skill_max = ref.get("skill_max", 0.0)
    senior = bool(getattr(grade, "is_senior_mgmt_tier", False) or ref.get("senior", False))
    if code and ref and bool(getattr(grade, "is_senior_mgmt_tier", False)) != ref.get("senior", False):
        warns.append("grade %s: senior-tier flag differs from workbook reference" % code)
    raw_deferral = getattr(grade, "deferral_rate", None)
    if raw_deferral not in (None, False):
        try:
            raw_f = float(raw_deferral)
        except (TypeError, ValueError):
            raw_f = 0.0
        deferral = raw_f / 100.0 if raw_f > 1.0 else raw_f
        expected = SENIOR_DEFERRAL_RATE if senior else DEFAULT_DEFERRAL_RATE
        if abs(deferral - expected) > 1e-9:
            warns.append("grade %s: deferral %.2f differs from workbook reference %.2f" % (code, deferral, expected))
    else:
        deferral = SENIOR_DEFERRAL_RATE if senior else DEFAULT_DEFERRAL_RATE
    return GradeContract(
        code=code,
        name=getattr(grade, "name", "") or code,
        base_points=float(base or 0.0),
        skill_max=float(skill_max or 0.0),
        aip_eligible=bool(getattr(grade, "aip_eligible", False)),
        is_senior_tier=senior,
        deferral_rate=deferral,
    ), warns


def clamp_skill_premium(skill_premium, skill_max):
    """Workbook STAFF PAYOUT uses the entered skill premium without a cap."""
    try:
        return float(skill_premium or 0.0)
    except (TypeError, ValueError):
        return 0.0


def classify_subpool(pool_type, grade_contract):
    """OPM -> OPM; SALES -> SALES; SUP -> SEN-MGT for senior tiers else OPS-SUP."""
    pool = (pool_type or "OPM").strip().upper()
    if pool == "SALES":
        return "SALES"
    if pool == "SUP":
        if grade_contract is not None and grade_contract.is_senior_tier:
            return "SEN-MGT"
        return "OPS-SUP"
    return "OPM"


def required_engines(pool_type, track, sales_role):
    """Employees assigned the sales engine also receive the staff payout."""
    engines = set()
    pool = (pool_type or "OPM").strip().upper()
    tr = (track or "ops").strip().lower()
    role = (sales_role or "none").strip().lower()
    has_sales_role = role not in ("", "none", "false")
    if pool == "SALES" or has_sales_role or tr in ("sales", "both"):
        engines.add("sales")
    if pool in ("OPM", "SUP") or tr in ("ops", "both") or "sales" in engines or not engines:
        engines.add("operations")
    if tr == "both":
        engines.update(("operations", "sales"))
    if pool == "SALES" and tr == "ops" and not has_sales_role:
        engines = {"operations"}
    return sorted(engines)
