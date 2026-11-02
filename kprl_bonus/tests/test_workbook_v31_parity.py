"""Focused parity checks against v31 workbook formulas (pure Python)."""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
sys.path.insert(0, str(BASE / "models"))
sys.path.insert(0, str(BASE / "tools"))
import grade_policy as G
import multipliers as M
import operations as O
import workbook_q2_data as W
from policy import PolicySnapshot
from kprl_math import ebitda_autoscore

FAILS = []


def check(label, got, want, tol=1e-9):
    ok = abs(float(got) - want) <= tol
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)


# BONUS ENGINE B37 is a SUMPRODUCT over the weights and actual input scores.
# The workbook auto-scores EBITDA as MIN(1, margin / full gate).
company_score = (
    0.33 * 0.8075 + 0.30 * 1.0 + 0.25 * 0.97 + 0.12 * 0.84)
company_mult = M.score_to_multiplier(company_score)
check("B37 scorecard total", company_score, 0.909775)
check("B38 scorecard multiplier", company_mult, 1.01955)
check("zero full gate follows Excel IFERROR fallback",
      ebitda_autoscore(0.30, 0.0), 0.0)
weight_edge = O.compute_pool({
    "company_w_revenue": 0.3299,
    "company_w_ebitda": 0.0,
    "company_w_gmp": 0.0,
    "company_w_people": 0.0,
}, {
    "revenue": 100.0,
    "ebitda_margin": 0.30,
    "company_scores": {"revenue": 1.0, "gmp": 0.0, "people": 0.0},
})
check("scorecard keeps workbook SUMPRODUCT weights unnormalized",
      weight_edge["company_kpi_score"], 0.3299)

# B28/B41: base pool × profitability gate × company GMP, blended multiplier,
# then MIN with the EBITDA cap. Workbook cached B37/B38 are stale, so derive
# these values from the formulas and current input cells.
result = O.workbook_effective_pool(
    3807960.0, 1.0, M.company_gmp_factor("clean"),
    company_mult, 0.95418181818181835,
    660543000.0 * 0.30, 0.10)
check("B28 funded pool", result["funded_pool"], 3807960.0)
check("B74 EBITDA cap", result["ebitda_cap"], 19816290.0)
check("B41 effective pool", result["effective_pool"],
      3782837.849345455)
check("zero cap is enforced", O.workbook_effective_pool(
    100.0, 1.0, 1.0, 1.0, 1.0, 1000.0, 0.0)["effective_pool"], 0.0)

# B39 treats departments with no lookup as multiplier 1 and defaults to 1
# when there are no weighted staff points.
check("missing department lookup defaults to 1",
      O.weighted_department_multiplier(
          [(1, 10.0), (2, 10.0)], {1: 0.90}), 0.95)
check("no points defaults to 1",
      O.weighted_department_multiplier([], {1: 0.90}), 1.0)

# Formula edge cases: Excel IFERROR falls back to the minimum rate when the
# scaling denominator is zero; staff formulas do not clamp entered values.
check("zero scaling range falls back to min",
      M.auto_pool_rate(0.25, 0.008, 0.018, 0.25, 0.25), 0.008)
manual_zero = O.compute_pool({
    "pool_rate_min": 0.008,
    "pool_rate_max": 0.018,
    "ebitda_scale_start": 0.15,
    "ebitda_scale_max": 0.40,
    "funding_method": "ebitda",
    "manual_pool_rate": 0.0,
    "manual_pool_rate_enabled": True,
    "partial_gate": 0.20,
    "full_gate": 0.30,
    "bonus_pool_cap_pct": 0.10,
}, {"revenue": 100.0, "ebitda_margin": 0.30})
check("explicit zero manual rate overrides auto rate",
      manual_zero["base_pool"], 0.0)
manual_policy = PolicySnapshot.from_mapping({
    "l2_manual_pool_rate_override": 0.0,
    "l2_manual_pool_rate_enabled": True,
})
check("zero manual rate enable survives policy mapping",
      manual_policy.manual_pool_rate_enabled, 1.0)
check("skill premium is not capped by grade",
      G.clamp_skill_premium(5.0, 2.0), 5.0)
check("behavior formula is not capped at 25",
      M.behaviour_to_multiplier(26.0), 1.108)

# Company GMP factor uses BONUS ENGINE B26, not the department-average bands.
check("major company GMP with self-report relief",
      M.company_gmp_factor("major", True, 0.5), 0.85)

# Parse the supplied workbook and ensure the formula-derived anchors agree
# with its saved formula caches before the staff-level parity tool runs.
workbook_path = BASE.parent / "KPRL_Bonus_Calculator_v31_working1.xlsx"
workbook_data = W.load_workbook_data(str(workbook_path))
anchors = workbook_data["anchors"]
check("workbook B37 score", anchors["company_score"], 0.909775)
check("workbook B38 multiplier", anchors["company_multiplier"], 1.01955)
check("workbook B41 effective pool", anchors["effective_pool"],
      3782837.849345455)
check("workbook formula caches are current",
      anchors["cached_formulas_are_current"], 1.0)

if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
print("ALL V31 FORMULA CHECKS PASSED")
