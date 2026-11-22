"""Single compensation-policy reader (pure Python, no Odoo imports).

Every payout number that is a business parameter MUST come from a
PolicySnapshot built here. Engines and the preview service receive the
snapshot as input; they never read kprl.bonus.parameter records and never
carry their own fallback defaults.

Odoo mapping: build via PolicySnapshot.from_mapping(obj) where obj is any
object with attribute access (an Odoo record works through getattr with the
FIELD_DEFAULTS below). Percent-vs-fraction normalisation happens once, here.
"""
from dataclasses import dataclass, field


def _pct(value, default):
    """Accept 0-100 percent or 0-1 fraction (or None) -> 0-1 fraction."""
    if value is None or value is False:
        return default
    v = float(value)
    if v > 1.0:
        v = v / 100.0
    return v


def _money(value, default):
    if value is None or value is False:
        return default
    return float(value)


@dataclass(frozen=True)
class PolicySnapshot:
    """Authoritative per-period compensation policy, versioned by source id."""
    source_id: int = 0
    period_id: int = 0
    version: int = 1

    # Pool
    pool_rate_min: float = 0.008
    pool_rate_max: float = 0.018
    ebitda_scale_start: float = 0.15
    ebitda_scale_max: float = 0.40
    funding_method: str = "sku"  # sku | ebitda
    manual_pool_rate: float = 0.0  # 0/None = auto
    manual_pool_rate_enabled: bool = False
    partial_gate: float = 0.20
    full_gate: float = 0.30
    bonus_pool_cap_pct: float = 0.10  # of EBITDA

    # Pool splits
    opm_share: float = 0.50
    senior_mgmt_share_of_sup: float = 0.70

    # Sales commission
    sales_commission_rate: float = 0.003
    retrieval_commission_rate: float = 0.007
    gm_share: float = 0.10
    nsm_share: float = 0.08
    headtech_share: float = 0.05
    rsm_share: float = 0.22
    asm_share: float = 0.55
    dual_factor: float = 0.55

    # Sales gates: (entry_floor, minimum) fractions per class
    top_sales_gate: tuple = (0.50, 0.65)
    top_retrieval_gate: tuple = (0.65, 0.75)
    rsm_sales_gate: tuple = (0.65, 0.75)
    rsm_retrieval_gate: tuple = (0.70, 0.75)
    asm_sales_gate: tuple = (0.65, 0.70)
    asm_retrieval_gate: tuple = (0.70, 0.70)
    dual_sales_gate: tuple = (0.65, 0.75)
    dual_retrieval_gate: tuple = (0.70, 0.75)

    # Sales KPI weights (must sum to 1.0)
    kpi_pk: float = 0.40
    kpi_call: float = 0.10
    kpi_coverage: float = 0.30
    kpi_new: float = 0.20
    sales_kpi_floor: float = 0.80
    sales_kpi_range: float = 0.40

    pk_normalization_enabled: bool = False

    # Accelerator + caps + leadership
    accel_kick_in: float = 1.00
    accel_ceiling: float = 1.50
    accel_boost: float = 0.50
    normal_cap: float = 2000000.0
    stretch_cap: float = 5000000.0
    leadership_premium: float = 1.20

    # Floors + tenure
    hygiene_floor: float = 20000.0
    junior_floor: float = 30000.0
    tenure_step: float = 0.03
    tenure_step_years: int = 3
    tenure_max: float = 0.12

    # Governance
    gmp_self_relief: float = 0.50

    # Company KPI weights (must sum to 1.0)
    company_w_revenue: float = 0.33
    company_w_ebitda: float = 0.30
    company_w_gmp: float = 0.25
    company_w_people: float = 0.12
    company_w_park1: float = 0.0
    company_w_park2: float = 0.0
    company_w_park3: float = 0.0
    company_w_park4: float = 0.0
    company_w_park5: float = 0.0

    # Blend
    company_blend: float = 0.60
    dept_blend: float = 0.40

    warnings: tuple = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, obj, source_id=0, period_id=0, version=1):
        """Build from an Odoo kprl.bonus.parameter record (or any mapping).

        Unknown/missing attributes fall back to the workbook defaults above,
        and every fallback is recorded in warnings so silent defaults are
        visible in the preview response.
        """
        warns = []

        def get(*names, default=None):
            for n in names:
                try:
                    v = getattr(obj, n, None) if not isinstance(obj, dict) else obj.get(n)
                except Exception:
                    v = None
                if v is not None and v is not False and v != "":
                    return v
            return default

        def pct(*names, default):
            raw = get(*names, default=None)
            if raw is None:
                warns.append("policy default used: %s" % (names[0],))
                return default
            return _pct(raw, default)

        def money(*names, default):
            raw = get(*names, default=None)
            if raw is None:
                warns.append("policy default used: %s" % (names[0],))
                return default
            return _money(raw, default)

        def pct_rate(*names, default):
            raw = get(*names, default=None)
            if raw is None:
                warns.append("policy default used: %s" % (names[0],))
                return default
            return float(raw) / 100.0

        funding = get("l1_pool_funding_method", default=None) or "sku"
        funding = "ebitda" if str(funding).lower().startswith("ebit") else "sku"
        manual = get("l2_manual_pool_rate_override", default=None)
        manual_enabled = bool(get("l2_manual_pool_rate_enabled", default=False))
        manual_rate = _pct(manual, 0.0) if manual else 0.0
        manual_enabled = manual_enabled or bool(manual_rate)

        return cls(
            source_id=int(source_id or 0),
            period_id=int(period_id or 0),
            version=int(version or 1),
            pool_rate_min=pct("min_pool_rate", default=0.008),
            pool_rate_max=pct("max_pool_rate", default=0.018),
            ebitda_scale_start=pct("ebitda_scaling_start", default=0.15),
            ebitda_scale_max=pct("ebitda_max_rate_threshold", default=0.40),
            funding_method=funding,
            manual_pool_rate=manual_rate,
            manual_pool_rate_enabled=manual_enabled,
            partial_gate=pct("partial_gate_floor", default=0.20),
            full_gate=pct("full_gate_floor", default=0.30),
            bonus_pool_cap_pct=pct("g_bonus_pool_cap_pct", default=0.10),
            opm_share=pct("l4_opm_share_pct", default=0.50),
            senior_mgmt_share_of_sup=pct("senior_mgmt_share_pct", default=0.70),
            sales_commission_rate=pct_rate("sales_commission_rate", default=0.003),
            retrieval_commission_rate=pct_rate("retrieval_commission_rate", default=0.007),
            gm_share=pct("gm_poolshare_rate", default=0.10),
            nsm_share=pct("national_sm_pool", default=0.08),
            headtech_share=pct("head_technical_poolshare", default=0.05),
            rsm_share=pct("rsm_pool_share", default=0.22),
            asm_share=pct("asm_commission_rate", "rsm_asm_commission_rate", default=0.55),
            dual_factor=_pct(get("rsm_asm_dual_factor", default=None), 0.55) if get("rsm_asm_dual_factor", default=None) else 0.55,
            top_sales_gate=(pct("h1_top_mgmt_sales_floor", default=0.50),
                            pct("b34_top_mgmt_min_sales_attainment", default=0.65)),
            top_retrieval_gate=(pct("h4_top_mgmt_retrieval_floor", default=0.65),
                                pct("b35_top_mgmt_min_retrieval_rate", default=0.75)),
            rsm_sales_gate=(pct("h2_rsm_sales_floor", default=0.65),
                            pct("b36_rsm_min_territory_sales_attainment", default=0.75)),
            rsm_retrieval_gate=(pct("h5_rsm_retrieval_floor", default=0.70),
                                pct("b37_rsm_min_territory_retrieval_rate", default=0.75)),
            asm_sales_gate=(pct("h3_asm_sales_floor", default=0.65),
                            pct("b38_asm_min_personal_sales_attainment", default=0.70)),
            asm_retrieval_gate=(pct("h6_asm_retrieval_floor", default=0.70),
                                pct("b39_asm_min_personal_retrieval_rate", default=0.70)),
            dual_sales_gate=(pct("k3_dual_sales_floor", default=0.65),
                             pct("k1_dual_min_sales", default=0.75)),
            dual_retrieval_gate=(pct("k4_dual_retrieval_floor", default=0.70),
                                 pct("k2_dual_min_retrieval", default=0.75)),
            kpi_pk=pct("sales_pk_weight", default=0.40),
            kpi_call=pct("sales_call_weight", default=0.10),
            kpi_coverage=pct("sales_coverage_weight", default=0.30),
            kpi_new=pct("sales_new_cust_weight", default=0.20),
            sales_kpi_floor=float(get("kpi_multiplier_floor", default=0.80) or 0.80),
            sales_kpi_range=float(get("kpi_multiplier_range", default=0.40) or 0.40),
            accel_kick_in=pct("i1_accelerator_kick_in", default=1.00),
            pk_normalization_enabled=bool(get("pk_normalization_enabled", default=False) or False),
            accel_ceiling=pct("i2_accelerator_ceiling", default=1.50),
            accel_boost=pct("i3_accelerator_boost", default=0.50),
            normal_cap=money("g_individual_quarterly_cap", default=2000000.0),
            stretch_cap=money("i4_stretch_individual_cap", default=5000000.0),
            leadership_premium=float(get("g_leadership_premium", default=1.20) or 1.20),
            hygiene_floor=money("minimum_floor", default=20000.0),
            junior_floor=money("maximum_cap", default=30000.0),
            gmp_self_relief=float(get("g_gmp_self_report_relief", default=0.50) or 0.50),
            company_w_revenue=pct("l_score_rev_weight", default=0.33),
            company_w_ebitda=pct("l_score_ebitda_weight", default=0.30),
            company_w_gmp=pct("l_score_gmp_weight", default=0.25),
            company_w_people=pct("l_score_people_weight", default=0.12),
            company_w_park1=pct("l_park1_weight", default=0.0),
            company_w_park2=pct("l_park2_weight", default=0.0),
            company_w_park3=pct("l_park3_weight", default=0.0),
            company_w_park4=pct("l_park4_weight", default=0.0),
            company_w_park5=pct("l_park5_weight", default=0.0),
            warnings=tuple(warns),
        )
