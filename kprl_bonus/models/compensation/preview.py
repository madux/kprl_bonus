"""Frozen PayoutPreview contract + preview_payout service (pure Python).

FROZEN CONTRACT (Slice 1): the simulator UI renders exactly these keys.
Later slices (operations.py / sales.py / run.py) fill the breakdown values
but MUST NOT change this response shape.

Flow (classify first, engines independent):
    load employee -> classify -> required engines -> shared read-only
    company/pool context -> independent OPS leg + SALES leg -> combined
    totals (shared cap applied at run level, only flagged here).

Missing data rule: a missing performance record or missing required field
is reported as None + a blocking_errors entry with status BLOCKED. It is
never coerced to zero. A present zero is a legitimate result.
"""
try:
    from . import grade_policy
    from . import multipliers as M
except ImportError:
    import grade_policy
    import multipliers as M
try:
    from . import operations as OPS
except ImportError:
    import operations as OPS
try:
    from . import sales as SALES
except ImportError:
    import sales as SALES

STATUS_CALCULATED = "calculated"
STATUS_WAITING = "waiting"
STATUS_BLOCKED = "blocked"


def _add_blocking(blocking, reason):
    """Append a blocking reason, skipping exact (or semicolon-joined)
    duplicates so the UI shows each missing piece once."""
    for part in [r.strip() for r in str(reason or "").split(";")]:
        if part and part not in blocking:
            blocking.append(part)

# Preview keys (frozen)
KEYS = ("employee", "classification", "source_inputs", "policy_values",
        "operations_breakdown", "sales_breakdown", "totals", "warnings",
        "blocking_errors", "status")


def _is_missing(value):
    return value is None


def preview_payout(employee, performance, policy, pool_ctx=None):
    """Pure preview builder.

    employee: dict(id, name, staff_id, grade->{code,name,yp_points,skill_max,
        aip_eligible,is_senior_mgmt_tier}, department->{name}, pool_type,
        track, sales_role, territory->{name}, years_of_service,
        skill_premium, active, status)
    performance: dict|None with keys appraisal, behaviour, own_target,
        own_sales, own_retrieval, territory_sales, territory_retrieval,
        territory_target, product_knowledge, call_report,
        customer_coverage, new_customer, dept_kpi_score (all 0-1 or money;
        None = not supplied). None = no record for (period, employee).
    policy: PolicySnapshot (or dict with same attribute names).
    pool_ctx: dict|None with company/pool context (ebitda_margin, revenue,
        company_kpi_score, ...). Read-only shared context for both legs.
    """
    warnings = list(getattr(policy, "warnings", []) or [])
    blocking = []
    pool_ctx = dict(pool_ctx or {})

    emp = employee or {}
    grade = (emp.get("grade") or {})
    status_flag = (emp.get("status") or "active").lower()
    if not emp.get("id"):
        _add_blocking(blocking, M.missing_reason("no_employee"))
    if status_flag != "active":
        _add_blocking(blocking, "Employee %s is not active - " % (emp.get("name", "?")) + M.missing_reason("inactive").split(" - ", 1)[-1])

    # --- classification (grade record is authoritative) ---
    from types import SimpleNamespace
    g = SimpleNamespace(
        code=grade.get("code", ""), name=grade.get("name", ""),
        yp_points=grade.get("yp_points"), skill_max=grade.get("skill_max"),
        aip_eligible=grade.get("aip_eligible", False),
        is_senior_mgmt_tier=grade.get("is_senior_mgmt_tier", False),
        exists=lambda: True,
    )
    has_grade = grade.get("code") or grade.get("name")
    if not has_grade:
        _add_blocking(blocking, M.missing_reason("no_grade"))
        contract, gw = None, ["grade record is missing"]
    else:
        contract, gw = grade_policy.from_grade_record(g)
    warnings.extend(gw)
    skill_raw = emp.get("skill_premium", 0.0) or 0.0
    skill_max = contract.skill_max if contract else 0.0
    skill = grade_policy.clamp_skill_premium(skill_raw, skill_max)
    if contract and float(skill_raw or 0.0) != float(skill):
        warnings.append("skill premium clamped from %s to grade max %s" % (skill_raw, skill_max))
    base_points = contract.base_points if contract else 0.0
    sub_pool = grade_policy.classify_subpool(emp.get("pool_type"), contract) if contract else None
    engines = grade_policy.required_engines(emp.get("pool_type"), emp.get("track"), emp.get("sales_role"))
    deferral = contract.deferral_rate if contract else 0.0

    classification = {
        "engines": engines,
        "engine": "+".join(engines) if engines else None,
        "sub_pool": sub_pool,
        "base_points": base_points,
        "skill_premium": skill,
        "skill_max": skill_max,
        "total_points": base_points + skill,
        "deferral_rate": deferral,
        "aip_eligible": contract.aip_eligible if contract else False,
    }

    # --- source inputs: missing stays None ---
    perf = dict(performance or {})
    has_record = performance is not None
    if not has_record:
        _add_blocking(blocking, M.missing_reason("no_record"))
    source_inputs = {
        "appraisal": perf.get("appraisal"),
        "behaviour": perf.get("behaviour"),
        "own_target": perf.get("own_target"),
        "own_sales": perf.get("own_sales"),
        "own_retrieval": perf.get("own_retrieval"),
        "territory_sales": perf.get("territory_sales"),
        "territory_retrieval": perf.get("territory_retrieval"),
        "territory_target": perf.get("territory_target"),
        "product_knowledge": perf.get("product_knowledge"),
        "call_report": perf.get("call_report"),
        "customer_coverage": perf.get("customer_coverage"),
        "new_customer": perf.get("new_customer"),
        "years_of_service": emp.get("years_of_service"),
    }

    # Required-field gating per engine (missing -> blocked, not zero)
    if "operations" in engines:
        if source_inputs["appraisal"] is None:
            _add_blocking(blocking, M.missing_reason("appraisal"))
        if source_inputs["behaviour"] is None:
            _add_blocking(blocking, M.missing_reason("behaviour"))
    if "sales" in engines:
        role_key = str(emp.get("sales_role") or "none").strip().lower().replace(" ", "")
        national_role = role_key in ("gm", "nsm", "headtech")
        for k in ("own_target", "own_sales", "own_retrieval"):
            if source_inputs[k] is None and not national_role:
                _add_blocking(blocking, M.missing_reason("sales_field", field=k))

    # --- policy values surfaced to the UI ---
    def _p(name, default=None):
        v = getattr(policy, name, default) if not isinstance(policy, dict) else policy.get(name, default)
        return v
    dept_kpi = perf.get("dept_kpi_score")
    if dept_kpi is None:
        dept_kpi = pool_ctx.get("dept_kpi_score")
    policy_values = {
        "policy_source_id": _p("source_id", 0),
        "policy_version": _p("version", 1),
        "department_kpi": dept_kpi,
        "department_kpi_multiplier": M.score_to_multiplier(dept_kpi) if dept_kpi is not None else None,
        "sales_commission_rate": _p("sales_commission_rate"),
        "retrieval_commission_rate": _p("retrieval_commission_rate"),
        "normal_cap": _p("normal_cap"),
        "stretch_cap": _p("stretch_cap"),
        "hygiene_floor": _p("hygiene_floor"),
        "junior_floor": _p("junior_floor"),
        "ebitda_margin": pool_ctx.get("ebitda_margin"),
        "funding_method": _p("funding_method", "sku"),
    }

    # --- engine legs: independent stub breakdowns (full engines later) ---
    operations_breakdown = None
    sales_breakdown = None
    if "operations" in engines:
        operations_breakdown = _operations_stub(
            source_inputs, classification, policy, policy_values, pool_ctx, blocking)
    if "sales" in engines:
        sales_breakdown = _sales_stub(
            source_inputs, emp, policy, pool_ctx, blocking)

    gross = 0.0
    for leg in (operations_breakdown, sales_breakdown):
        if leg and leg.get("gross") is not None:
            gross += leg["gross"]
    cap_pressure = False
    ebitda_cap = pool_ctx.get("ebitda_cap_amount")
    if ebitda_cap is not None and gross is not None:
        cap_pressure = gross > ebitda_cap
        if cap_pressure:
            warnings.append("combined gross exceeds run-level EBITDA cap; proration applies at payout-run time")
    totals = {"gross": gross, "deferred": 0.0, "net_payable": None,
              "cap_pressure": cap_pressure, "note": "stub legs: full engines in operations.py/sales.py"}

    if blocking:
        status = STATUS_BLOCKED
    elif warnings and operations_breakdown is None and sales_breakdown is None:
        status = STATUS_WAITING
    else:
        status = STATUS_CALCULATED if not any(
            v is None for v in (operations_breakdown, sales_breakdown) if v is not None or True) else STATUS_CALCULATED

    employee_out = {
        "id": emp.get("id"), "name": emp.get("name"),
        "staff_id": emp.get("staff_id"),
        "grade": grade.get("name"), "grade_code": grade.get("code"),
        "department": (emp.get("department") or {}).get("name") if isinstance(emp.get("department"), dict) else emp.get("department"),
        "pool_type": emp.get("pool_type"), "track": emp.get("track"),
        "sales_role": emp.get("sales_role"),
        "territory": (emp.get("territory") or {}).get("name") if isinstance(emp.get("territory"), dict) else emp.get("territory"),
        "status": emp.get("status"),
    }
    return {
        "employee": employee_out,
        "classification": classification,
        "source_inputs": source_inputs,
        "policy_values": policy_values,
        "operations_breakdown": operations_breakdown,
        "sales_breakdown": sales_breakdown,
        "totals": totals,
        "warnings": warnings,
        "blocking_errors": blocking,
        "status": status,
    }


def _operations_stub(source_inputs, classification, policy, policy_values, pool_ctx, blocking):
    """Ops leg: full engine when pool value/point is present, else stub multipliers.

    Deliberately returns value_per_point/base_eligible as None (pool
    allocation arrives with operations.py) so the UI shows WAITING for those
    rows instead of a second calculation system.
    """
    if pool_ctx.get("value_per_point") is not None:
        full = OPS.calculate_operations_payout(
            {"base_points": classification.get("base_points"),
             "skill_premium": classification.get("skill_premium"),
             "skill_max": classification.get("skill_max"),
             "years_of_service": source_inputs.get("years_of_service"),
             "malus_percent": pool_ctx.get("malus_percent", 0.0),
             "deferral_rate": classification.get("deferral_rate")},
            {"appraisal": source_inputs.get("appraisal"),
             "behaviour": source_inputs.get("behaviour"),
             "dept_kpi_score": policy_values.get("department_kpi"),
             "dept_gmp_status": pool_ctx.get("dept_gmp_status", "clean"),
             "dept_gmp_self_reported": pool_ctx.get("dept_gmp_self_reported", False)},
            policy, pool_ctx,
            proration_factor=pool_ctx.get("pool_proration_factor", 1.0))
        full.update({"engine": "operations", "sub_pool": classification.get("sub_pool"),
                     "total_points": classification.get("total_points"),
                     "deferral_rate": classification.get("deferral_rate"),
                     "stub": False})
        if full.get("blocked_reason"):
            _add_blocking(blocking, full["blocked_reason"])
        else:
            full["gross"] = full.get("gross_bonus")
        return full
    _add_blocking(blocking, M.missing_reason("pool"))
    appraisal_m = M.appraisal_to_multiplier(source_inputs["appraisal"])
    behaviour_m = M.behaviour_to_multiplier(source_inputs["behaviour"])
    tenure_m = M.tenure_to_multiplier(source_inputs["years_of_service"])
    return {
        "engine": "operations",
        "sub_pool": classification.get("sub_pool"),
        "total_points": classification.get("total_points"),
        "value_per_point": pool_ctx.get("value_per_point"),
        "base_eligible": None,
        "department_kpi_multiplier": policy_values.get("department_kpi_multiplier"),
        "appraisal_multiplier": appraisal_m,
        "behaviour_multiplier": behaviour_m,
        "tenure_multiplier": tenure_m,
        "deferral_rate": classification.get("deferral_rate"),
        "gross": None,
        "net_payable": None,
        "blocked_reason": M.missing_reason("pool"),
        "stub": True,
    }


def _sales_stub(source_inputs, emp, policy, pool_ctx, blocking):
    role = SALES.normalize_role(emp.get("sales_role") or "asm")
    if role is None:
        _add_blocking(blocking, M.missing_reason("sales_role"))
        return {"engine": "sales", "sales_role": None, "final_payout": None,
                "blocked_reason": "sales role is missing", "stub": False}
    if source_inputs.get("own_target") is None and role in ("asm",):
        pass
    full_in = {
        "role": role,
        "own_target": source_inputs.get("own_target"),
        "own_sales": source_inputs.get("own_sales"),
        "own_retrieval": source_inputs.get("own_retrieval"),
        "territory_sales": (source_inputs.get("territory_sales")
                            if source_inputs.get("territory_sales") is not None
                            else pool_ctx.get("territory_sales")),
        "territory_retrieval": (source_inputs.get("territory_retrieval")
                                if source_inputs.get("territory_retrieval") is not None
                                else pool_ctx.get("territory_retrieval")),
        "territory_target": (source_inputs.get("territory_target")
                             if source_inputs.get("territory_target") is not None
                             else pool_ctx.get("territory_target")),
        "national_sales": pool_ctx.get("national_sales"),
        "national_target": pool_ctx.get("national_target"),
        "national_retrieval": pool_ctx.get("national_retrieval"),
        "product_knowledge": source_inputs.get("product_knowledge"),
        "call_report": source_inputs.get("call_report"),
        "customer_coverage": source_inputs.get("customer_coverage"),
        "new_customer": source_inputs.get("new_customer"),
        "years_of_service": source_inputs.get("years_of_service"),
    }
    full = SALES.calculate_sales_payout(
        full_in, policy,
        highest_asm_sub_base=pool_ctx.get("highest_asm_sub_base", 0.0))
    full.update({"engine": "sales", "stub": False})
    if full.get("blocked_reason"):
        _add_blocking(blocking, full["blocked_reason"])
    full["attainment"] = full.get("sales_attainment")
    if full.get("final_payout") is not None:
        full["gross"] = full["final_payout"]
    else:
        full["gross"] = None
    return full


def _sales_stub_legacy(source_inputs, emp, policy, pool_ctx, blocking):
    """Slice-1 stub: attainment + gates only (commission legs with sales.py)."""
    role = (emp.get("sales_role") or "asm").lower()
    own_sales, own_target = source_inputs["own_sales"], source_inputs["own_target"]
    attainment = (own_sales / own_target) if (own_sales is not None and own_target) else None
    gates = _gate_pair(policy, role)
    sales_gate = M.ramp_gate(attainment, gates[0][0], gates[0][1]) if attainment is not None else None
    retr_base = source_inputs["own_retrieval"]
    retr_rate = (retr_base / own_sales) if (retr_base is not None and own_sales) else None
    retrieval_gate = M.ramp_gate(retr_rate, gates[1][0], gates[1][1]) if retr_rate is not None else None
    return {
        "engine": "sales",
        "sales_role": role,
        "attainment": attainment,
        "retrieval_rate": retr_rate,
        "sales_gate": sales_gate,
        "retrieval_gate": retrieval_gate,
        "sales_commission": None,
        "retrieval_commission": None,
        "kpi_multiplier": None,
        "accelerator": None,
        "gross": None,
        "final_payout": None,
        "stub": True,
    }


def _gate_pair(policy, role):
    def _p(name, default):
        v = getattr(policy, name, default) if not isinstance(policy, dict) else policy.get(name, default)
        return v or default
    if role in ("gm", "nsm", "headtech", "head_tech"):
        return _p("top_sales_gate", (0.50, 0.65)), _p("top_retrieval_gate", (0.65, 0.75))
    if role in ("rsm",):
        return _p("rsm_sales_gate", (0.65, 0.75)), _p("rsm_retrieval_gate", (0.70, 0.75))
    if role in ("rsm_asm", "rsm+asm", "dual"):
        return _p("dual_sales_gate", (0.65, 0.75)), _p("dual_retrieval_gate", (0.70, 0.75))
    return _p("asm_sales_gate", (0.65, 0.70)), _p("asm_retrieval_gate", (0.70, 0.70))
