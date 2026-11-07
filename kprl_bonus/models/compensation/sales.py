"""Sales commission engine (pure Python, no Odoo imports, no ORM).

Implements spec steps 19-25 (sales leg), faithful to the workbook pattern
confirmed in sales_engine_main_line.py:
  role shares -> attainment/retrieval by role -> ramp gates (sales gate
  is master) -> commissionable bases -> 0.30%/0.70% legs -> eligible ->
  sales KPI -> accelerator -> tenure -> leadership floor (RSM/RSM+ASM) ->
  2M/5M caps -> final payout.

Every intermediate is returned, not just the final amount.
"""
try:
    from . import multipliers as M
except ImportError:
    import multipliers as M

TOP_ROLES = ("gm", "nsm", "headtech", "head_tech")
RSM_ROLES = ("rsm",)
DUAL_ROLES = ("rsm_asm", "rsm+asm", "dual")
ASM_ROLES = ("asm",)


def normalize_role(role):
    """Canonical role key. None/empty -> None (missing, not zero)."""
    if role is None:
        return None
    r = str(role).strip().lower().replace("+", "_").replace(" ", "_")
    return r or None


def role_share(role, policy):
    """Commissionable share fraction for a role (dual = (rsm+asm)*factor)."""
    p = policy if isinstance(policy, dict) else policy.__dict__
    r = normalize_role(role)
    if r in TOP_ROLES:
        key = {"gm": "gm_share", "nsm": "nsm_share"}.get(r, "headtech_share")
        return float(p.get(key, 0.0) or 0.0)
    if r in RSM_ROLES:
        return float(p.get("rsm_share", 0.22) or 0.0)
    if r in ASM_ROLES:
        return float(p.get("asm_share", 0.55) or 0.0)
    if r in DUAL_ROLES:
        rsm = float(p.get("rsm_share", 0.22) or 0.0)
        asm = float(p.get("asm_share", 0.55) or 0.0)
        return (rsm + asm) * float(p.get("dual_factor", 0.55) or 0.0)
    return 0.0


def attainment_for_role(role, s):
    """Sales attainment by role. None when the divisor is missing/zero."""
    r = normalize_role(role)
    if r in TOP_ROLES:
        t = s.get("national_target")
        return (s.get("national_sales") / t) if t else None
    if r in RSM_ROLES or r in DUAL_ROLES:
        t = s.get("territory_target")
        return (s.get("territory_sales") / t) if t else None
    t = s.get("own_target")
    return (s.get("own_sales") / t) if t else None


def retrieval_rate_for_role(role, s):
    """Retrieval rate by role. None when the divisor is missing/zero."""
    r = normalize_role(role)
    if r in TOP_ROLES:
        base = s.get("national_sales")
        return (s.get("national_retrieval") / base) if base else None
    if r in RSM_ROLES or r in DUAL_ROLES:
        base = s.get("territory_sales")
        return (s.get("territory_retrieval") / base) if base else None
    base = s.get("own_sales")
    return (s.get("own_retrieval") / base) if base else None


def gate_pair_for_role(role, policy):
    """((sales_floor, sales_min), (retr_floor, retr_min)) for a role."""
    p = policy if isinstance(policy, dict) else policy.__dict__
    r = normalize_role(role)
    if r in TOP_ROLES:
        return (p.get("top_sales_gate", (0.50, 0.65)),
                p.get("top_retrieval_gate", (0.65, 0.75)))
    if r in RSM_ROLES:
        return (p.get("rsm_sales_gate", (0.65, 0.75)),
                p.get("rsm_retrieval_gate", (0.70, 0.75)))
    if r in DUAL_ROLES:
        return (p.get("dual_sales_gate", (0.65, 0.75)),
                p.get("dual_retrieval_gate", (0.70, 0.75)))
    return (p.get("asm_sales_gate", (0.65, 0.70)),
            p.get("asm_retrieval_gate", (0.70, 0.70)))


def commissionable_bases(role, s, policy):
    """(sales_base, retrieval_base) before commission rates."""
    p = policy if isinstance(policy, dict) else policy.__dict__
    r = normalize_role(role)
    gm = float(p.get("gm_share", 0.10) or 0.0)
    nsm = float(p.get("nsm_share", 0.08) or 0.0)
    ht = float(p.get("headtech_share", 0.05) or 0.0)
    rsm = float(p.get("rsm_share", 0.22) or 0.0)
    asm = float(p.get("asm_share", 0.55) or 0.0)
    dual = float(p.get("dual_factor", 0.55) or 0.0)
    nz = lambda v: float(v or 0.0)
    if r == "gm":
        return nz(s.get("national_sales")) * gm, nz(s.get("national_retrieval")) * gm
    if r == "nsm":
        return nz(s.get("national_sales")) * nsm, nz(s.get("national_retrieval")) * nsm
    if r in ("headtech", "head_tech"):
        return nz(s.get("national_sales")) * ht, nz(s.get("national_retrieval")) * ht
    if r in RSM_ROLES:
        return nz(s.get("territory_sales")) * rsm, nz(s.get("territory_retrieval")) * rsm
    if r in ASM_ROLES:
        return nz(s.get("own_sales")) * asm, nz(s.get("own_retrieval")) * asm
    if r in DUAL_ROLES:
        sb = (nz(s.get("territory_sales")) * rsm + nz(s.get("own_sales")) * asm) * dual
        rb = (nz(s.get("territory_retrieval")) * rsm + nz(s.get("own_retrieval")) * asm) * dual
        return sb, rb
    return 0.0, 0.0


def calculate_sales_payout(sales, policy, highest_asm_sub_base=0.0):
    """Single-employee sales payout. Missing inputs -> None legs + reason.

    sales: {role, own_target, own_sales, own_retrieval, territory_sales,
            territory_retrieval, territory_target, national_sales,
            national_target, national_retrieval, product_knowledge,
            call_report, customer_coverage, new_customer, years_of_service}
    """
    p = policy if isinstance(policy, dict) else policy.__dict__
    s = dict(sales or {})
    out = {"sales_role": normalize_role(s.get("role"))}
    if out["sales_role"] is None:
        out.update({"final_payout": None, "blocked_reason": M.missing_reason("sales_role")})
        return out
    attain = attainment_for_role(out["sales_role"], s)
    retr_rate = retrieval_rate_for_role(out["sales_role"], s)
    (sf, sm), (rf, rm) = gate_pair_for_role(out["sales_role"], policy)
    sales_gate = M.ramp_gate(attain, sf, sm) if attain is not None else None
    retr_gate = M.ramp_gate(retr_rate, rf, rm) if retr_rate is not None else None
    out.update({"sales_attainment": attain, "retrieval_rate": retr_rate,
                "sales_gate": sales_gate, "retrieval_gate": retr_gate,
                "sales_gate_floor": sf, "sales_gate_minimum": sm,
                "retrieval_gate_floor": rf, "retrieval_gate_minimum": rm})
    if attain is None or sales_gate is None:
        out.update({"final_payout": None,
                    "blocked_reason": M.missing_reason("attainment")})
        return out
    s_base, r_base = commissionable_bases(out["sales_role"], s, policy)
    s_rate = float(p.get("sales_commission_rate", 0.003) or 0.0)
    r_rate = float(p.get("retrieval_commission_rate", 0.007) or 0.0)
    s_comm = s_base * s_rate
    r_comm = r_base * r_rate
    out.update({"role_share": role_share(out["sales_role"], policy),
                "commissionable_sales_base": s_base,
                "commissionable_retrieval_base": r_base,
                "sales_commission": s_comm, "retrieval_commission": r_comm})
    eligible = sales_gate * (s_comm + (retr_gate or 0.0) * r_comm)
    out["eligible_commission"] = eligible
    pk_eff = s.get("effective_pk", s.get("product_knowledge"))
    out["effective_pk"] = pk_eff
    kpi = M.sales_kpi_multiplier(
        pk_eff, s.get("call_report"),
        s.get("customer_coverage"), s.get("new_customer"),
        w_pk=float(p.get("kpi_pk", 0.40) or 0.40),
        w_call=float(p.get("kpi_call", 0.10) or 0.10),
        w_cov=float(p.get("kpi_coverage", 0.30) or 0.30),
        w_new=float(p.get("kpi_new", 0.20) or 0.20),
        floor=float(p.get("sales_kpi_floor", 0.80) or 0.80),
        span=float(p.get("sales_kpi_range", 0.40) or 0.40))
    out["kpi_multiplier"] = kpi
    if kpi is None:
        out.update({"final_payout": None,
                    "blocked_reason": M.missing_reason("sales_kpi")})
        return out
    accel = M.accelerator_factor(
        attain, p.get("accel_kick_in", 1.00), p.get("accel_ceiling", 1.50),
        p.get("accel_boost", 0.50))
    tenure_m = M.tenure_to_multiplier(s.get("years_of_service"))
    calculated = eligible * kpi * (accel or 1.0) * (tenure_m or 1.0)
    out.update({"accelerator": accel, "years_of_service": s.get("years_of_service"),
                "tenure_multiplier": tenure_m, "calculated_payout": calculated})
    leadership_floor = 0.0
    if out["sales_role"] in RSM_ROLES + DUAL_ROLES:
        leadership_floor = (sales_gate or 0.0) * float(p.get("leadership_premium", 1.10) or 0.0) * float(highest_asm_sub_base or 0.0)
    out["leadership_floor"] = leadership_floor
    kick = M.normalize_fraction(p.get("accel_kick_in", 1.00))
    a = M.normalize_fraction(attain)
    stretch = a is not None and kick is not None and a > kick
    cap = float(p.get("stretch_cap", 5000000.0)) if stretch else float(p.get("normal_cap", 2000000.0))
    out.update({"cap": cap, "stretch_cap_applied": bool(stretch)})
    out["final_payout"] = max(min(max(calculated, leadership_floor), cap), 0.0)
    return out


def asm_sub_base(sales, policy):
    """ASM sub-base for the leadership floor: MIN(normal cap, eligible*KPI*tenure)."""
    r = calculate_sales_payout(sales, policy)
    if r.get("sales_role") not in ASM_ROLES or r.get("eligible_commission") is None:
        return 0.0
    p = policy if isinstance(policy, dict) else policy.__dict__
    return min(float(p.get("normal_cap", 2000000.0) or 0.0),
               r["eligible_commission"] * (r.get("kpi_multiplier") or 0.0) * (r.get("tenure_multiplier") or 1.0))


def aggregate_territory_performance(entries):
    """Sum staff actuals and targets for the workbook's territory roll-up."""
    totals = {"territory_sales": 0.0, "territory_retrieval": 0.0,
              "team_target": 0.0}
    for entry in entries or ():
        totals["territory_sales"] += float(entry.get("own_sales") or 0.0)
        totals["territory_retrieval"] += float(entry.get("own_retrieval") or 0.0)
        totals["team_target"] += float(entry.get("own_target") or 0.0)
    return totals


def normalize_pk_team(entries, policy):
    """Min-max PK normalization across the team (AD18). Returns pk map.

    effective = MEDIAN(0, (pk - min) / (max - min), 1). Degenerate
    (max == min) or missing pk falls back to the raw value.
    """
    pks = [e.get("product_knowledge") for e in (entries or [])]
    pks = [float(v) for v in pks if v is not None]
    if not pks:
        return {}
    lo, hi = min(pks), max(pks)
    span = hi - lo
    out = {}
    for e in (entries or []):
        key = e.get("employee_id", id(e))
        raw = e.get("product_knowledge")
        if raw is None or not span:
            out[key] = raw
        else:
            out[key] = max(0.0, min(1.0, (float(raw) - lo) / span))
    return out


def calculate_sales_batch(entries, policy):
    """Two-pass batch: ASM sub-bases per territory first, then finals
    (RSM/RSM+ASM leadership floor needs the highest ASM sub-base)."""
    entries = [dict(e) for e in (entries or [])]
    best = {}
    for e in entries:
        if normalize_role(e.get("role")) in ASM_ROLES and e.get("territory_key") is not None:
            v = asm_sub_base(e, policy)
            k = e.get("territory_key")
            best[k] = max(best.get(k, 0.0), v)
    p = policy if isinstance(policy, dict) else policy.__dict__
    pk_norm = bool(p.get("pk_normalization_enabled", False))
    pk_map = normalize_pk_team(entries, policy) if pk_norm else {}
    results = []
    for _e in entries:
        e = _e
        if pk_norm:
            key = _e.get("employee_id", id(_e))
            e = dict(_e)
            e["effective_pk"] = pk_map.get(key, _e.get("product_knowledge"))
        top = best.get(e.get("territory_key"), 0.0)
        r = calculate_sales_payout(e, policy, highest_asm_sub_base=top)
        r["employee_id"] = e.get("employee_id")
        r["territory_key"] = e.get("territory_key")
        results.append(r)
    return results
