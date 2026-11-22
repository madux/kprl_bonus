"""Operations bonus engine (pure Python, no Odoo imports, no ORM).

Implements spec steps 1-20 (operations leg):
  total points -> pool rate -> base pool -> profitability/GMP gates ->
  company KPI -> department multiplier -> effective pool -> allocation ->
  value/point -> base eligible -> appraisal/behaviour -> gross (+10%
  exception at >=90%) -> pool proration -> tenure -> floor -> deferral ->
  GMP x malus -> net payable.

Every intermediate is returned, not just the final amount.
"""
try:
    from . import multipliers as M
    from . import grade_policy as G
except ImportError:
    import multipliers as M
    import grade_policy as G


def compute_pool(policy, inputs):
    """Pool-level computation shared by all operations employees.

    policy: PolicySnapshot (or dict). inputs (dict, fractions/money):
      revenue, ebitda_margin, products=[{units, unit_price, pool_rate}],
      gmp_status, gmp_self_reported, company_scores={revenue, gmp, people},
      dept_kpi={dept_key: score}, dept_points={dept_key: points}
    Returns dict with every pool intermediate.
    """
    p = policy if isinstance(policy, dict) else policy.__dict__
    inp = dict(inputs or {})

    def gv(name, default=None):
        v = p.get(name, default)
        return v

    revenue = float(inp.get("revenue") or 0.0)
    ebitda_m = inp.get("ebitda_margin")
    auto_rate = M.auto_pool_rate(ebitda_m, gv("pool_rate_min", 0.00606),
                                 gv("pool_rate_max", 0.017),
                                 gv("ebitda_scale_start", 0.12),
                                 gv("ebitda_scale_max", 0.30))
    manual = gv("manual_pool_rate", None)
    manual_enabled = bool(gv("manual_pool_rate_enabled", False)
                          or manual not in (None, False, ""))
    selected_rate = float(manual or 0.0) if manual_enabled else auto_rate
    funding = gv("funding_method", "sku")
    if funding == "ebitda":
        base_pool = revenue * (selected_rate or 0.0)
    else:
        base_pool = 0.0
        for prod in inp.get("products") or []:
            base_pool += (float(prod.get("units") or 0.0)
                          * float(prod.get("unit_price") or 0.0)
                          * float(prod.get("pool_rate") or 0.0))
    profit_f = M.profitability_factor(ebitda_m, gv("partial_gate", 0.20),
                                      gv("full_gate", 0.30))
    gmp_f = M.company_gmp_factor(inp.get("gmp_status", "clean"),
                                   inp.get("gmp_self_reported", False),
                                   gv("gmp_self_relief", 0.50))
    funded = base_pool * (profit_f or 0.0) * (gmp_f if gmp_f is not None else 1.0)

    scores = inp.get("company_scores") or {}
    company_weights = {
        "revenue": gv("company_w_revenue", 0.33),
        "ebitda": gv("company_w_ebitda", 0.30),
        "gmp": gv("company_w_gmp", 0.25),
        "people": gv("company_w_people", 0.12),
        "park1": gv("company_w_park1", 0.0),
        "park2": gv("company_w_park2", 0.0),
        "park3": gv("company_w_park3", 0.0),
        "park4": gv("company_w_park4", 0.0),
        "park5": gv("company_w_park5", 0.0),
    }
    e_margin = M.normalize_fraction(ebitda_m) if ebitda_m is not None else 0.0
    full_gate = M.normalize_fraction(gv("full_gate", 0.30))
    ebitda_score = min(1.0, e_margin / full_gate) if full_gate else 0.0

    def sc(key):
        v = ebitda_score if key == "ebitda" else scores.get(key)
        return float(v) if v is not None else 0.0

    company_score = sum(
        weight * sc(key) for key, weight in company_weights.items())
    company_mult = M.score_to_multiplier(company_score)

    dept_kpi = inp.get("dept_kpi") or {}
    dept_pts = inp.get("dept_points") or {}
    dept_mults = {
        k: M.score_to_multiplier(v) if v is not None else 1.0
        for k, v in dept_kpi.items()
    }
    tw, tp = 0.0, 0.0
    for k, pts in dept_pts.items():
        pts = float(pts or 0.0)
        tw += dept_mults.get(k, 1.0) * pts
        tp += pts
    dept_weighted = (tw / tp) if tp else 1.0
    blended = (gv("company_blend", 0.60) * company_mult
               + gv("dept_blend", 0.40) * dept_weighted)
    ebitda_amt = revenue * (M.normalize_fraction(ebitda_m) or 0.0)
    cap = ebitda_amt * gv("bonus_pool_cap_pct", 0.10)
    effective = funded * blended
    effective = min(effective, cap)

    opm_share = gv("opm_share", 0.60)
    sen_share = gv("senior_mgmt_share_of_sup", 0.70)
    opm_pool = effective * opm_share
    sup_pool = effective * (1.0 - opm_share)
    sen_pool = sup_pool * sen_share
    opssup_pool = sup_pool * (1.0 - sen_share)
    return {
        "auto_pool_rate": auto_rate, "selected_pool_rate": selected_rate,
        "funding_method": funding, "base_pool": base_pool,
        "profitability_factor": profit_f, "gmp_factor": gmp_f,
        "funded_pool": funded, "ebitda_score": ebitda_score,
        "company_kpi_score": company_score, "company_multiplier": company_mult,
        "dept_multipliers": dept_mults,
        "points_weighted_dept_multiplier": dept_weighted,
        "blended_multiplier": blended, "ebitda_amount": ebitda_amt,
        "ebitda_cap": cap, "effective_pool": effective,
        "opm_pool": opm_pool, "sup_pool": sup_pool,
        "senior_mgmt_pool": sen_pool, "ops_support_pool": opssup_pool,
    }


def weighted_department_multiplier(staff_points, department_multipliers):
    """Workbook BONUS ENGINE B39: SUM(points × dept multiplier) / SUM(points).

    Missing department lookups use the workbook STAFF PAYOUT default of 1;
    no points use the workbook IFERROR fallback of 1.
    """
    weighted = 0.0
    total_points = 0.0
    for department_id, points in staff_points:
        points = float(points or 0.0)
        weighted += points * float(department_multipliers.get(department_id, 1.0))
        total_points += points
    return weighted / total_points if total_points else 1.0


def workbook_effective_pool(base_pool, gate_factor, company_gmp_factor,
                            company_multiplier, department_multiplier,
                            ebitda_amount, cap_pct):
    """Workbook BONUS ENGINE B28/B41 calculation with a hard cap."""
    funded_pool = (float(base_pool or 0.0) * float(gate_factor or 0.0)
                   * float(company_gmp_factor or 0.0))
    blended_multiplier = (0.60 * float(company_multiplier or 0.0)
                          + 0.40 * float(department_multiplier or 0.0))
    uncapped_pool = funded_pool * blended_multiplier
    cap = float(ebitda_amount or 0.0) * float(cap_pct or 0.0)
    return {
        "funded_pool": funded_pool,
        "blended_multiplier": blended_multiplier,
        "ebitda_cap": cap,
        "effective_pool": min(uncapped_pool, cap),
    }


def value_per_point(pool_amount, total_points):
    """Workbook formula: zero when the sub-pool has no points."""
    if not total_points:
        return 0.0
    return float(pool_amount or 0.0) / float(total_points)


def calculate_operations_payout(emp, perf, policy, pool, proration_factor=1.0):
    """Single-employee operations payout. Missing inputs -> None legs.

    emp: {base_points, skill_premium, skill_max, sub_pool,
          years_of_service, malus_percent, deferral_rate}
    perf: {appraisal, behaviour, dept_kpi_score, dept_gmp_status,
           dept_gmp_self_reported}
    pool: dict with value_per_point for the employee sub-pool plus
          floor_eligible (bool, EBITDA >= partial gate).
    """
    p = policy if isinstance(policy, dict) else policy.__dict__
    out = {}
    skill = G.clamp_skill_premium(emp.get("skill_premium"), emp.get("skill_max"))
    total_pts = float(emp.get("base_points") or 0.0) + skill
    out.update({"base_points": float(emp.get("base_points") or 0.0),
                "skill_premium": skill, "total_points": total_pts})
    vpp = (pool or {}).get("value_per_point")
    out["value_per_point"] = vpp
    if vpp is None:
        out.update({"base_eligible": None, "gross_bonus": None,
                    "net_payable": None,
                    "blocked_reason": "pool value/point unavailable"})
        return out
    base_elig = total_pts * vpp
    dept_score = (perf or {}).get("dept_kpi_score")
    dept_override = (perf or {}).get("dept_kpi_mult_override")
    dept_m = None
    if dept_override not in (None, False):
        # What-if hook: caller supplies the multiplier itself (e.g. a UI
        # scenario on the existing multiplier). Normal runs always pass a
        # score and take the canonical score_to_multiplier curve.
        try:
            dept_m = float(dept_override)
        except (TypeError, ValueError):
            dept_m = None
    elif dept_score is not None:
        dept_m = M.score_to_multiplier(dept_score)
    appr_m = M.appraisal_to_multiplier((perf or {}).get("appraisal"))
    beh_m = M.behaviour_to_multiplier((perf or {}).get("behaviour"))
    out.update({"department_kpi_score": dept_score,
                "department_kpi_multiplier": dept_m,
                "appraisal": (perf or {}).get("appraisal"),
                "appraisal_multiplier": appr_m,
                "behaviour": (perf or {}).get("behaviour"),
                "behaviour_multiplier": beh_m})
    if dept_m is None or appr_m is None or beh_m is None:
        missing = []
        if appr_m is None:
            missing.append(M.missing_reason("appraisal"))
        if beh_m is None:
            missing.append(M.missing_reason("behaviour"))
        if dept_m is None:
            missing.append(M.missing_reason("dept_kpi"))
        out.update({"gross_bonus": None, "net_payable": None,
                    "blocked_reason": "; ".join(missing)})
        return out
    adjusted = base_elig * dept_m * appr_m * beh_m
    appr = M.normalize_fraction((perf or {}).get("appraisal"))
    exception = adjusted * 0.10 if (appr is not None and appr >= 0.90) else 0.0
    gross = adjusted + exception
    out.update({"base_eligible": base_elig, "adjusted_bonus": adjusted,
                "exception_premium": exception, "gross_bonus": gross})
    factor = proration_factor if proration_factor is not None else 1.0
    prorated = gross * min(1.0, factor)
    out.update({"proration_factor": min(1.0, factor), "prorated_bonus": prorated})
    tenure_m = M.tenure_to_multiplier(emp.get("years_of_service"))
    tenured = prorated * (tenure_m or 1.0)
    out.update({"years_of_service": emp.get("years_of_service"),
                "tenure_multiplier": tenure_m, "tenure_enhanced": tenured})
    floor_ok = bool((pool or {}).get("floor_eligible", False)) and (appr is not None and appr >= 0.65)
    floor = 0.0
    if floor_ok:
        bp = float(emp.get("base_points") or 0.0)
        if bp <= 0.5:
            floor = float(p.get("hygiene_floor", 20000.0) or 20000.0)
        elif bp <= 1.0:
            floor = float(p.get("junior_floor", 30000.0) or 30000.0)
    final = max(tenured, floor)
    out.update({"floor": floor, "floor_applied": final > tenured,
                "final_before_deferral": final})
    deferral = float(emp.get("deferral_rate") or 0.0)
    deferred = final * deferral
    immediate = final - deferred
    out.update({"deferral_rate": deferral, "deferred_amount": deferred,
                "immediate_payment": immediate})
    dept_gmp = M.dept_gmp_factor((perf or {}).get("dept_gmp_status", "clean"),
                                 (perf or {}).get("dept_gmp_self_reported", False),
                                 p.get("gmp_self_relief", 0.50))
    malus = max(0.0, min(100.0, float(emp.get("malus_percent") or 0.0)))
    net = immediate * dept_gmp * (1.0 - malus / 100.0)
    # AJ6 individual cap: stretch cap when appraisal >= 90%, else normal cap.
    stretch = appr is not None and appr >= 0.90
    cap = float(p.get("stretch_cap", 5000000.0) or 5000000.0) if stretch \
        else float(p.get("normal_cap", 2000000.0) or 2000000.0)
    capped = min(max(net, 0.0), cap)
    out.update({"gmp_factor": dept_gmp, "malus_percent": malus,
                "cap": cap, "stretch_cap_applied": bool(stretch),
                "cap_adjustment": max(net, 0.0) - capped,
                "net_payable": capped})
    return out


def pool_proration_factor(total_gross, effective_pool):
    """MIN(1, effective/total). Zero gross -> 1 (no proration)."""
    if not total_gross:
        return 1.0
    return min(1.0, float(effective_pool or 0.0) / float(total_gross))
