from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from .kprl_math import profitability_gate, company_gmp_factor


class BonusParameter(models.Model):
    _name = 'kprl.bonus.parameter'
    _description = 'Bonus Parameter Configuration'
    _rec_name = 'period_id'

    def open_record(self):
        view_id = self.env.ref('kprl_bonus.view_kprl_bonus_parameter_form')
        val = {
            'name':'Control panel',
            'view_mode': 'form',
            'view_id': view_id.id,
            'view_type': 'form',
            'res_model': 'kprl.bonus.parameter',
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'current'
            }
        return val
    
    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True)
    is_locked = fields.Boolean(string='Locked', default=False,
                               help='Prevents edits after approval')
    version = fields.Integer(string='Version', default=1)

    approver_id = fields.Many2one('res.users', string='Approved By')
    approval_date = fields.Datetime(string='Approval Date')
    submitted_by = fields.Many2one('res.users', string='Submitted By', readonly=True)
    notes = fields.Text(string='Change Notes')

    # -- Section A: Main Bonus Pool Parameters (Board approval required) --
    min_pool_rate = fields.Float(string='Pool Rate Min (floor)', digits=(5, 4),
                                 default=0.8)
    min_pool_rate_min = fields.Float(string='Pool Rate Min (floor) — Lower Bound', digits=(5, 4), default=0.3)
    min_pool_rate_max = fields.Float(string='Pool Rate Min (floor) — Upper Bound', digits=(5, 4), default=0.8)
    min_pool_rate_approver = fields.Char(string='Approver', default='Board')

    max_pool_rate = fields.Float(string='Pool Rate Max (ceiling)', digits=(5, 4),
                                 default=1.80
                                 )

    max_pool_rate_min = fields.Float(string='Pool Rate Max (ceiling) — Lower Bound', default=1.50)
    max_pool_rate_max = fields.Float(string='Pool Rate Max (ceiling) — Upper Bound', default=2.0)
    max_pool_rate_approver = fields.Char(default='Board')

    ebitda_scaling_start = fields.Float(string='EBITDA threshold Scaling Start',
                                        digits=(5, 4), default=15.0)
    ebitda_scaling_start_min = fields.Float(string='EBITDA threshold Scaling Start — Lower Bound', default=10)
    ebitda_scaling_start_max = fields.Float(string='EBITDA threshold Scaling Start — Upper Bound', default=15)
    ebitda_scaling_start_approver = fields.Char(default='Board')

    ebitda_max_rate_threshold = fields.Float(string='EBITDA Threshold — Max Rate Reached',
                                             digits=(5, 4), default=40.0)
    ebitda_max_rate_threshold_min = fields.Float(default=25.00)
    ebitda_max_rate_threshold_max = fields.Float(default=70.00)
    ebitda_max_rate_threshold_approver = fields.Char(default='Board')

    partial_gate_floor = fields.Float(string='Ramp Start Margin (zero-payout)',
                                      digits=(5, 4), default=20.0)
    partial_gate_floor_min = fields.Float(string='Ramp Start Margin (zero-payout) — Lower Bound', default=15.0)
    partial_gate_floor_max = fields.Float(string='Ramp Start Margin (zero-payout) — Upper Bound', default=22.0)
    partial_gate_floor_approver = fields.Char(default='Board')

    full_gate_floor = fields.Float(string='Full Unlock Threshold', digits=(5, 4), default=30.0)
    full_gate_floor_min = fields.Float(string='Full Unlock Threshold — Lower Bound', default=20)
    full_gate_floor_max = fields.Float(string='Full Unlock Threshold — Upper Bound', default=30)
    full_gate_floor_approver = fields.Char(default='Board')
        # ── Grand Pool → OPM (input) / SUP (auto-remainder) ──
    l4_opm_share_pct = fields.Float(
        string='Opm Share Pct (%)', digits=(5, 2), default=50,
        help="OPM's share of the Grand Pool. "
             "SUP pool auto-computes as 100% minus this value.")
    l4_sup_share_pct = fields.Float(
        string='SUP Share (%)', digits=(5, 2),
        compute='_compute_l4_sup_share', store=True,
        help="Auto-computed: 100 − OPM share")
    l4_opm_share_pct_min = fields.Float(string='Opm Share Pct — Lower Bound', default=20)
    l4_opm_share_pct_max = fields.Float(string='Opm Share Pct — Upper Bound', default=80)
    l4_opm_share_pct_approver = fields.Char(string='Opm Share Pct Approver', default='Finance Director')

    # ── L5: SUP Pool → Senior-Mgmt (input) / Ops-Support (auto-remainder) ──
    senior_mgmt_share_pct = fields.Float(
        string='Senior-Mgmt Share (%)', digits=(5, 2), default=70,
        help="Senior-Mgmt's share of the SUP Pool. "
             "Ops-Support auto-computes as 100% minus this value.")
    l5_ops_support_share_pct = fields.Float(
        string='Ops-Support Share (%)', digits=(5, 2),
        compute='_compute_l5_ops_share', store=True,
        help="Auto-computed: 100 − Senior-Mgmt share")
    senior_mgmt_share_pct_min = fields.Float(default=50)
    senior_mgmt_share_pct_max = fields.Float(default=80)
    senior_mgmt_share_pct_approver = fields.Char(default='Finance Director')

    aip_annual_rate = fields.Float(string='AIP Pool Rate', digits=(5, 4), default=0.2,
                                   help='% of annual revenue for the year-end management incentive (workbook: 0.2%)')
    aip_annual_rate_min = fields.Float(default=0.0)
    aip_annual_rate_max = fields.Float(default=12.0)
    aip_annual_rate_approver = fields.Char(default='Board')

    aip_deferral_rate = fields.Float(string='AIP Deferral Rate', digits=(5, 4))
    aip_deferral_rate_min = fields.Float(default=0.20)
    aip_deferral_rate_max = fields.Float(default=0.40)
    aip_deferral_rate_approver = fields.Char(default='Finance Director')

    # -- Section B: Sales Commission Rates (Finance Director) --
    sales_commission_rate = fields.Float(string='Sales Commission Rate (%)',
                                         digits=(5, 4), default=0.30)
    sales_commission_rate_min = fields.Float(default=0.20)
    sales_commission_rate_max = fields.Float(default=1.00)
    sales_commission_rate_approver = fields.Char(default='Finance Director')

    retrieval_commission_rate = fields.Float(string='Retrieval Commission Rate (%)',
                                             digits=(5, 4), default=0.70)
    retrieval_commission_min = fields.Float(default=0.20)
    retrieval_commission_max = fields.Float(default=1.00)
    retrieval_commission_rate_approver = fields.Char(default='Finance Director')

    rsm_pool_share = fields.Float(default=22)
    rsm_pool_min = fields.Float(default=15)
    rsm_pool_rate_max = fields.Float(default=30)
    rsm_pool_rate_approver = fields.Char(default='Finance Director')


    rsm_asm_commission_rate = fields.Float(string='RSM+ASM Commission Rate (%)',
                                           digits=(5, 4), default=55.0)
    rsm_asm_commission_rate_min = fields.Float(default=55)
    rsm_asm_commission_rate_max = fields.Float(default=85)
    rsm_asm_commission_rate_approver = fields.Char(default='Finance Director')

    asm_commission_rate_min = fields.Float(default=0.20)
    asm_commission_rate_max = fields.Float(default=1.00)
    asm_commission_rate_approver = fields.Char(default='Finance Director')


    national_sm_pool = fields.Float(default=8.0)
    national_sm_poolshare_min = fields.Float(default=4.0)
    national_sm_poolshare_max = fields.Float(default=10)

    head_technical_poolshare = fields.Float(default=5.0)
    head_technical_poolshare_min = fields.Float(default=3.0)
    head_technical_poolshare_max = fields.Float(default=8.0)

    gm_poolshare_rate = fields.Float(default=10)
    gm_poolshare_rate_min = fields.Float(default=5)
    gm_poolshare_rate_max = fields.Float(default=12)
    gm_poolshare_rate_approver = fields.Char(default='Finance Director')

    product_pool_share_pct = fields.Float(string='Product Pool Share (%)',
                                          digits=(5, 4), default=0.20)
    product_pool_share_pct_min = fields.Float(default=0.20)
    product_pool_share_pct_max = fields.Float(default=1.00)
    product_pool_share_pct_approver = fields.Char(default='Finance Director')

    commission_share_pct = fields.Float(string='Commission Share (%)', digits=(5, 4), default=0.20)
    commission_share_pct_min = fields.Float(default=0.20)
    commission_share_pct_max = fields.Float(default=1.00)
    commission_share_pct_approver = fields.Char(default='Finance Director')

    rsm_asm_dual_factor = fields.Float(string='RSM+ASM Dual Role Factor',
                                       digits=(5, 4))
    rsm_asm_dual_factor_min = fields.Float(default=0.20)
    rsm_asm_dual_factor_max = fields.Float(default=1.00)
    rsm_asm_dual_factor_approver = fields.Char(default='Finance Director')

    # -- Section C: Sales Eligibility Thresholds (Finance + HR Director) --
    b34_top_mgmt_min_sales_attainment = fields.Float(string='Top Management — Min Sales Attainment (%)', digits=(5, 2), default=65.0, help='Min attainment to unlock commission at full strength; distinct from entry floor Sec H')
    b35_top_mgmt_min_retrieval_rate = fields.Float(string='Top Management — Min Retrieval Rate (%)', digits=(5, 2), default=75.0)
    b36_rsm_min_territory_sales_attainment = fields.Float(string='RSM — Min Territory Sales Attainment (%)', digits=(5, 2), default=75.0)
    b37_rsm_min_territory_retrieval_rate = fields.Float(string='RSM — Min Territory Retrieval Rate (%)', digits=(5, 2), default=75.0)
    b38_asm_min_personal_sales_attainment = fields.Float(string='ASM — Min Personal Sales Attainment (%)', digits=(5, 2), default=70.0)
    b39_asm_min_personal_retrieval_rate = fields.Float(string='ASM — Min Personal Retrieval Rate (%)', digits=(5, 2), default=70.0)

    # -- Section D: AIP & Deferred Parameters --
    aip_eligibility_threshold = fields.Float(string='AIP Eligibility Threshold (%)',
                                             digits=(5, 2))
    senior_mgmt_deferred_rate = fields.Float(string='Senior Mgmt Deferred Rate (%)',
                                             digits=(5, 4), default=20.0)
    tier1_deferred_rate = fields.Float(string='Tier 1 Deferred Rate (%)',
                                       digits=(5, 4), default=20.0)
    tier2_deferred_rate = fields.Float(string='Tier 2 Deferred Rate (%)',
                                       digits=(5, 4), default=20.0)
    aip_deferred_rate_param = fields.Float(string='AIP Deferred Rate (%)',
                                           digits=(5, 4))
    minimum_floor = fields.Float(string='MIN floor - Hygiene/Security(₦)', digits='Product Price')
    maximum_cap = fields.Float(string='MIN floor — Junior Staff (₦)', digits='Product Price')

    # -- Section E: KPI Weights (must sum to 100%) --
    revenue_weight = fields.Float(string='Revenue Achievement Weight (%)',
                                  digits=(5, 2), default=25)
    revenue_weight_min = fields.Float(default=0.0)
    revenue_weight_max = fields.Float(default=25.0)

    ebitda_weight = fields.Float(string='EBITDA Achievement Weight (%)',
                                 digits=(5, 2), default=25)
    ebitda_weight_min = fields.Float(default=0.0)
    ebitda_weight_max = fields.Float(default=25.0)

    gmp_weight = fields.Float(string='GMP / Quality Score Weight (%)',
                              digits=(5, 2), default=25)
    gmp_weight_min = fields.Float(default=0.0)
    gmp_weight_max = fields.Float(default=25.0)

    extended_kpi_weight = fields.Float(string='Extended KPI Weight (%)',
                                       digits=(5, 2), default=25)
    extended_kpi_weight_min = fields.Float(default=0.0)
    extended_kpi_weight_max = fields.Float(default=25.0)

    kpi_weight_total = fields.Float(string='KPI Weight Total', digits=(5, 2),
                                    compute='_compute_kpi_weight_total', store=True)
    kpi_weight_valid = fields.Boolean(string='KPI Weights Valid',
                                      compute='_compute_kpi_weight_total', store=True)

    # -- Section E2: Sales KPI Weights (must sum to 100%) --
    sales_pk_weight = fields.Float(string='Product Knowledge Weight (%)',
                                   digits=(5, 2), default=40,
                                   help='Sales KPI: Product Knowledge weight')
    sales_call_weight = fields.Float(string='Call Report Compliance Weight (%)',
                                     digits=(5, 2), default=10,
                                     help='Sales KPI: Call Report Compliance weight')
    sales_coverage_weight = fields.Float(string='Customer Coverage Weight (%)',
                                         digits=(5, 2), default=30,
                                         help='Sales KPI: Customer Coverage weight')
    sales_new_cust_weight = fields.Float(string='New Customer Acquisition Weight (%)',
                                        digits=(5, 2), default=20,
                                        help='Sales KPI: New Customer Acquisition weight')
    
    sales_kpi_weight_total = fields.Float(string='Sales KPI Weight Total', digits=(5, 2),
                                         compute='_compute_sales_kpi_weight_total', store=True)
    sales_kpi_weight_valid = fields.Boolean(string='Sales KPI Weights Valid',
                                           compute='_compute_sales_kpi_weight_total', store=True)
    
    # -- KPI Multiplier Band Parameters --
    kpi_multiplier_floor = fields.Float(string='KPI Multiplier Floor', digits=(5, 4),
                                       default=0.80, help='J1: Multiplier at zero KPI score')
    kpi_multiplier_range = fields.Float(string='KPI Multiplier Range', digits=(5, 4),
                                       default=0.40, help='J2: Span above floor (top multiplier = floor + range)')
        # -- Company Performance Multiplier (configurable, Sec 5D governance-tuned) --
    company_mult_baseline = fields.Float(string='CompanyMult Baseline', digits=(5, 4), default=0.90,
        help='KPI baseline where boost starts (spec approx 0.90, workbook 0.909775→1.01955)')
    company_mult_k_factor = fields.Float(string='CompanyMult K-Factor', digits=(5, 4), default=0.20,
        help='Boost slope: Mult = 1 + max(0, KPI-Baseline)*KFactor. Spec approx 0.2')
    
    pk_normalization_enabled = fields.Boolean(string='PK Score Normalization',
                                             default=False,
                                             help='If On, min-max rescales product knowledge across the team')

    # -- Section F: National Targets --
    quarterly_revenue_target = fields.Float(string='Quarterly Revenue Target',
                                            digits='Product Price')
    annual_revenue_target = fields.Float(string='Annual Revenue Target',
                                         digits='Product Price')

    # -- Tenure Multiplier Defaults --
    tenure_default_mult = fields.Float(string='Default Tenure Multiplier',
                                       digits=(5, 4), default=1.0)

    # -- Section G: Governance, Caps & Policy (Board-approved) --
    g_bonus_pool_cap_pct = fields.Float(string='Bonus Pool Cap (% of EBITDA)', digits=(5, 2), default=10.0, help='Hard ceiling: effective pool cannot exceed this share of EBITDA (workbook Cap_PoolPctEBITDA = 0.10)')
    g_individual_quarterly_cap = fields.Float(string='Individual Quarterly Cap (N)', digits='Product Price', default=2000000, help='Max any one person can receive per quarter')
    g_leadership_premium = fields.Float(string='Leadership Premium (manager vs top subordinate)', digits=(5, 2), default=1.20, help='RSM / RSM+ASM commission floored at this multiple of the top subordinate in territory')
    g_gmp_self_report_relief = fields.Float(string='GMP Self-Report Relief (penalty x)', digits=(5, 2), default=0.50, help='If GMP issue is self-reported, the penalty is multiplied by this (0.5 = halved)')
    g_company_gmp_self_reported = fields.Boolean(string='Company GMP Self-Reported?', default=False)

    # -- Section H: Sales Entry-Gate Ramp Floors (v9) --
    h1_top_mgmt_sales_floor = fields.Float(string='Top Mgmt — Sales Entry Floor (%)', digits=(5, 2), default=50.0, help='Ramp start for GM/NSM/HeadTech sales. Below this = 0')
    h2_rsm_sales_floor = fields.Float(string='RSM — Sales Entry Floor (%)', digits=(5, 2), default=65.0, help='Ramp start for RSM/RSM+ASM territory sales')
    h3_asm_sales_floor = fields.Float(string='ASM — Sales Entry Floor (%)', digits=(5, 2), default=65.0)
    h4_top_mgmt_retrieval_floor = fields.Float(string='Top Mgmt — Retrieval Entry Floor (%)', digits=(5, 2), default=65.0, help='Ramp start for the retrieval leg (secondary gate)')
    h5_rsm_retrieval_floor = fields.Float(string='RSM — Retrieval Entry Floor (%)', digits=(5, 2), default=70.0)
    h6_asm_retrieval_floor = fields.Float(string='ASM — Retrieval Entry Floor (%)', digits=(5, 2), default=70.0, help='If Floor = Min the gate becomes a HARD CLIFF at Min')

    # -- Section I: Sales Accelerators & Stretch Cap (v10) --
    i1_accelerator_kick_in = fields.Float(string='Accelerator Kick-in (%)', digits=(5, 2), default=100.0, help='Attainment where boost begins')
    i2_accelerator_ceiling = fields.Float(string='Accelerator Ceiling (%)', digits=(5, 2), default=150.0, help='Attainment at which the full boost applies')
    i3_accelerator_boost = fields.Float(string='Accelerator Boost (%)', digits=(5, 2), default=50.0, help='Max extra multiplier (up to +50% on eligible commission)')
    i4_stretch_individual_cap = fields.Float(string='Stretch Individual Cap (N)', digits='Product Price', default=5000000, help='Higher cap for genuine over-performers when attainment > kick-in')
    # Legacy accelerators (kept for migration, use i1-i4)
    accelerator_threshold_1 = fields.Float(string='Accelerator Threshold 1 (%)', digits=(5, 2))
    accelerator_mult_1 = fields.Float(string='Accelerator Multiplier 1', digits=(5, 4))
    accelerator_threshold_2 = fields.Float(string='Accelerator Threshold 2 (%)', digits=(5, 2))
    accelerator_mult_2 = fields.Float(string='Accelerator Multiplier 2', digits=(5, 4))
    individual_cap = fields.Float(string='Individual Cap (%)', digits=(5, 2))

    # -- Section K: RSM+ASM (Dual Role) Separate Thresholds (v15) --
    k1_dual_min_sales = fields.Float(string='RSM+ASM — Min Territory Sales Attainment (%)', digits=(5, 2), default=75.0, help='Full-credit point for dual-role territory sales')
    k2_dual_min_retrieval = fields.Float(string='RSM+ASM — Min Territory Retrieval Rate (%)', digits=(5, 2), default=75.0)
    k3_dual_sales_floor = fields.Float(string='RSM+ASM — Sales Entry Floor (%)', digits=(5, 2), default=65.0, help='Below this = 0; floor->min ramps 0->100%')
    k4_dual_retrieval_floor = fields.Float(string='RSM+ASM — Retrieval Entry Floor (%)', digits=(5, 2), default=70.0)

    # -- Section L: Company Scorecard & Engine Switches (v23) --
    l1_pool_funding_method = fields.Selection([('sku','SKU Contributions'),('ebitda','EBITDA-scaled Rate')], string='Pool Funding Method', default='sku', help='L1: SKU Contributions vs EBITDA-scaled Rate')
    l2_manual_pool_rate_enabled = fields.Boolean(
        string='Use Manual Pool Rate Override',
        help='Apply the manual rate even when it is 0%. Non-zero manual rates are also applied automatically.')
    l2_manual_pool_rate_override = fields.Float(string='Manual Pool Rate Override (%)', digits=(5, 4), help='L2: blank = auto (uses Auto Pool Rate)')
    l3_gmp_compliance_status = fields.Selection([('clean','Clean'),('minor','Minor'),('major','Major'),('critical','Critical')], string='GMP Compliance Status', default='clean', help='L3')
    l_score_rev_weight = fields.Float(string='Revenue Achievement Weight (%)', digits=(5, 2), default=33.0)
    l_score_ebitda_weight = fields.Float(string='EBITDA Margin Achievement Weight (%)', digits=(5, 2), default=30.0)
    l_score_gmp_weight = fields.Float(string='GMP & Quality Compliance Weight (%)', digits=(5, 2), default=25.0)
    l_score_people_weight = fields.Float(string='People Weight (%)', digits=(5, 2), default=12.0)
    l_park1_weight = fields.Float(string='Parked Metric 1 Weight (%)', digits=(5, 2), default=0.0)
    l_park2_weight = fields.Float(string='Parked Metric 2 Weight (%)', digits=(5, 2), default=0.0)
    l_park3_weight = fields.Float(string='Parked Metric 3 Weight (%)', digits=(5, 2), default=0.0)
    l_park4_weight = fields.Float(string='Parked Metric 4 Weight (%)', digits=(5, 2), default=0.0)
    l_park5_weight = fields.Float(string='Parked Metric 5 Weight (%)', digits=(5, 2), default=0.0)
    l_park1_score = fields.Float(string='Parked Metric 1 Score', digits=(5, 4), default=0.0)
    l_park2_score = fields.Float(string='Parked Metric 2 Score', digits=(5, 4), default=0.0)
    l_park3_score = fields.Float(string='Parked Metric 3 Score', digits=(5, 4), default=0.0)
    l_park4_score = fields.Float(string='Parked Metric 4 Score', digits=(5, 4), default=0.0)
    l_park5_score = fields.Float(string='Parked Metric 5 Score', digits=(5, 4), default=0.0)

    # Scorecard input scores (EBITDA auto-scores from the period: MIN(1, EBITDA/Gate_Full))
    l_score_rev_score = fields.Float(string='Revenue Achievement Score', digits=(5, 4), default=0.0)
    l_score_gmp_score = fields.Float(string='GMP & Quality Score', digits=(5, 4), default=0.0)
    l_score_people_score = fields.Float(string='People Score', digits=(5, 4), default=0.0)
    period_ebitda_margin = fields.Float(string='Period EBITDA Margin (%)',
                                        related='period_id.ebitda_margin', readonly=False)
    company_scorecard_total = fields.Float(
        string='Company Scorecard Total', digits=(16, 4),
        compute='_compute_company_scorecard', store=True,
        help='BONUS ENGINE B37: SUMPRODUCT of the scorecard weights and workbook input scores.')

    @api.depends('l_score_rev_score', 'l_score_gmp_score', 'l_score_people_score',
                 'period_ebitda_margin', 'full_gate_floor',
                 'l_score_rev_weight', 'l_score_ebitda_weight', 'l_score_gmp_weight',
                 'l_score_people_weight',
                 'l_park1_weight', 'l_park2_weight', 'l_park3_weight', 'l_park4_weight', 'l_park5_weight',
                 'l_park1_score', 'l_park2_score', 'l_park3_score', 'l_park4_score', 'l_park5_score')
    def _compute_company_scorecard(self):
        from .kprl_math import ebitda_autoscore
        for rec in self:
            ebitda_score = ebitda_autoscore(
                rec.period_ebitda_margin or 0.0,
                rec.full_gate_floor)
            pairs = [
                (rec.l_score_rev_weight or 0.0, rec.l_score_rev_score or 0.0),
                (rec.l_score_ebitda_weight or 0.0, ebitda_score),
                (rec.l_score_gmp_weight or 0.0, rec.l_score_gmp_score or 0.0),
                (rec.l_score_people_weight or 0.0, rec.l_score_people_score or 0.0),
                (rec.l_park1_weight or 0.0, rec.l_park1_score or 0.0),
                (rec.l_park2_weight or 0.0, rec.l_park2_score or 0.0),
                (rec.l_park3_weight or 0.0, rec.l_park3_score or 0.0),
                (rec.l_park4_weight or 0.0, rec.l_park4_score or 0.0),
                (rec.l_park5_weight or 0.0, rec.l_park5_score or 0.0),
            ]
            rec.company_scorecard_total = sum(w * s for w, s in pairs) / 100.0

    funded_pool_after_both_gate = fields.Float(
        string='Funded Pool After Both Gate', digits='Product Price',
        compute='_compute_funded_pool', store=True, readonly=True)
    profitability_gate_factor = fields.Float(
        string='Profitability Gate Factor (continuous ramp)', digits=(5, 4),
        compute='_compute_profitability_gate_factor', store=True, readonly=True)
    base_bonus_pool = fields.Float(
        string='Base Bonus Pool', digits='Product Price',
        compute='_compute_base_bonus_pool', store=True, readonly=True)
    gmp_gate_factor = fields.Float(
        string='GMP Gate Factor', digits=(5, 4),
        compute='_compute_gmp_gate_factor', store=True, readonly=True,
        help='Workbook BONUS ENGINE B26 company GMP status factor, including self-report relief.')

    @api.depends('period_id.revenue_amount', 'period_id.revenue_target',
                 'period_id.product_pool_ids.pool_contribution',
                 'period_id.product_pool_ids.quantity_revenue',
                 'l1_pool_funding_method', 'l2_manual_pool_rate_override',
                 'l2_manual_pool_rate_enabled',
                 'min_pool_rate', 'max_pool_rate',
                 'ebitda_scaling_start', 'ebitda_max_rate_threshold')
    def _compute_base_bonus_pool(self):
        for rec in self:
            period = rec.period_id
            if not period:
                rec.base_bonus_pool = 0.0
                continue
            if rec.l1_pool_funding_method != 'ebitda':
                rec.base_bonus_pool = sum(
                    period.product_pool_ids.mapped('pool_contribution'))
                continue
            min_rate = (rec.min_pool_rate or 0.0) / 100.0
            max_rate = (rec.max_pool_rate or 0.0) / 100.0
            scale_start = (rec.ebitda_scaling_start or 0.0) / 100.0
            scale_max = (rec.ebitda_max_rate_threshold or 0.0) / 100.0
            margin = (period.ebitda_margin or 0.0) / 100.0
            if (rec.l2_manual_pool_rate_enabled
                    or rec.l2_manual_pool_rate_override):
                rate = rec.l2_manual_pool_rate_override / 100.0
            elif margin >= scale_max:
                rate = max_rate
            elif margin <= scale_start:
                rate = min_rate
            elif scale_max > scale_start:
                rate = min_rate + ((margin - scale_start) / (scale_max - scale_start)) * (max_rate - min_rate)
            else:
                rate = min_rate
            revenue = (sum(period.product_pool_ids.mapped('quantity_revenue'))
                       or period.revenue_amount
                       or period.revenue_target
                       or 0.0)
            rec.base_bonus_pool = revenue * rate

    @api.depends('period_id.ebitda_margin', 'partial_gate_floor', 'full_gate_floor')
    def _compute_profitability_gate_factor(self):
        for rec in self:
            ramp = (rec.partial_gate_floor or 20.0) / 100.0
            full = (rec.full_gate_floor or 30.0) / 100.0
            margin = (rec.period_id.ebitda_margin or 0.0) / 100.0
            try:
                rec.profitability_gate_factor = profitability_gate(
                    margin, ramp_start=ramp, full_unlock=full)
            except ValueError:
                rec.profitability_gate_factor = 0.0

    @api.depends('l3_gmp_compliance_status', 'g_company_gmp_self_reported',
                 'g_gmp_self_report_relief')
    def _compute_gmp_gate_factor(self):
        for rec in self:
            status = rec.l3_gmp_compliance_status or 'clean'
            try:
                rec.gmp_gate_factor = company_gmp_factor(
                    status, rec.g_company_gmp_self_reported,
                    rec.g_gmp_self_report_relief or 0.5)
            except ValueError as exc:
                raise ValidationError(
                    _('Invalid company GMP status %r.') % status) from exc

    @api.depends('base_bonus_pool', 'profitability_gate_factor', 'gmp_gate_factor')
    def _compute_funded_pool(self):
        for rec in self:
            rec.funded_pool_after_both_gate = (
                (rec.base_bonus_pool or 0.0)
                * (rec.profitability_gate_factor or 0.0)
                * (rec.gmp_gate_factor or 0.0))

    @api.depends('l4_opm_share_pct')
    def _compute_l4_sup_share(self):
        for rec in self:
            rec.l4_sup_share_pct = 100.0 - (rec.l4_opm_share_pct or 0.0)

    @api.depends('senior_mgmt_share_pct')
    def _compute_l5_ops_share(self):
        for rec in self:
            rec.l5_ops_support_share_pct = 100.0 - (rec.senior_mgmt_share_pct or 0.0)

    _sql_constraints = [
        ('period_unique', 'UNIQUE(period_id)',
         'Only one parameter set allowed per period!'),
    ]

    @api.constrains('min_pool_rate', 'partial_gate_floor', 'full_gate_floor',
                    'max_pool_rate', 'aip_annual_rate', 'aip_deferral_rate',
                    'revenue_weight', 'ebitda_weight', 'gmp_weight',
                    'extended_kpi_weight', 'ebitda_scaling_start',
                    'ebitda_max_rate_threshold')
    def _check_bounds(self):
        field_pairs = [
            ('min_pool_rate', 'min_pool_rate_min', 'min_pool_rate_max'),
            ('ebitda_scaling_start', 'ebitda_scaling_start_min', 'ebitda_scaling_start_max'),
            ('ebitda_max_rate_threshold', 'ebitda_max_rate_threshold_min', 'ebitda_max_rate_threshold_max'),
            ('partial_gate_floor', 'partial_gate_floor_min', 'partial_gate_floor_max'),
            ('full_gate_floor', 'full_gate_floor_min', 'full_gate_floor_max'),
            ('max_pool_rate', 'max_pool_rate_min', 'max_pool_rate_max'),
            ('l4_opm_share_pct', 'l4_opm_share_pct_min', 'l4_opm_share_pct_max'),
            ('senior_mgmt_share_pct', 'senior_mgmt_share_pct_min', 'senior_mgmt_share_pct_max'),
            ('aip_annual_rate', 'aip_annual_rate_min', 'aip_annual_rate_max'),
            ('aip_deferral_rate', 'aip_deferral_rate_min', 'aip_deferral_rate_max'),
            ('revenue_weight', 'revenue_weight_min', 'revenue_weight_max'),
            ('ebitda_weight', 'ebitda_weight_min', 'ebitda_weight_max'),
            ('gmp_weight', 'gmp_weight_min', 'gmp_weight_max'),
            ('extended_kpi_weight', 'extended_kpi_weight_min', 'extended_kpi_weight_max'),
            ('sales_commission_rate', 'sales_commission_rate_min', 'sales_commission_rate_max'),
            ('retrieval_commission_rate', 'retrieval_commission_min', 'retrieval_commission_max'),
            ('rsm_pool_share', 'rsm_pool_min', 'rsm_pool_rate_max'),
            ('rsm_asm_commission_rate', 'rsm_asm_commission_rate_min', 'rsm_asm_commission_rate_max'),
            ('national_sm_pool', 'national_sm_poolshare_min', 'national_sm_poolshare_max'),
            ('head_technical_poolshare', 'head_technical_poolshare_min', 'head_technical_poolshare_max'),
            ('gm_poolshare_rate', 'gm_poolshare_rate_min', 'gm_poolshare_rate_max'),
            ('product_pool_share_pct', 'product_pool_share_pct_min', 'product_pool_share_pct_max'),
            ('commission_share_pct', 'commission_share_pct_min', 'commission_share_pct_max'),
            ('rsm_asm_dual_factor', 'rsm_asm_dual_factor_min', 'rsm_asm_dual_factor_max'),
        ]
        for rec in self:
            for val_field, min_field, max_field in field_pairs:
                val = getattr(rec, val_field)
                min_val = getattr(rec, min_field)
                max_val = getattr(rec, max_field)
                if val is not None and (val < min_val or val > max_val):
                    raise ValidationError(_(
                        '%s must be between %s and %s. Current value: %s'
                    ) % (
                        rec._fields[val_field].string,
                        min_val, max_val, val,
                    ))

    @api.constrains('min_pool_rate', 'max_pool_rate')
    def _check_pool_rate_order(self):
        for rec in self:
            if rec.min_pool_rate and rec.max_pool_rate:
                if rec.min_pool_rate >= rec.max_pool_rate:
                    raise ValidationError(_(
                        'Pool Rate Min (floor) (%s%%) must be below Pool Rate Max (ceiling) (%s%%).'
                    ) % (
                        rec.min_pool_rate / 100,
                        rec.max_pool_rate / 100,
                    ))

    @api.constrains('ebitda_scaling_start', 'ebitda_max_rate_threshold',
                    'full_gate_floor')
    def _check_ebitda_thresholds(self):
        for rec in self:
            if rec.ebitda_scaling_start and rec.full_gate_floor:
                if rec.ebitda_scaling_start > rec.full_gate_floor: # 11 > 22
                    raise ValidationError(_(
                        'EBITDA threshold Scaling Start (%s%%) must not exceed '
                        'Full Unlock Threshold (%s%%) — prevents dead zone.'
                    ) % (
                        rec.ebitda_scaling_start / 100,
                        rec.full_gate_floor / 100,
                    ))
            if rec.ebitda_max_rate_threshold and rec.full_gate_floor:
                if rec.ebitda_max_rate_threshold <= rec.full_gate_floor:
                    raise ValidationError(_(
                        'EBITDA Max Rate Threshold (%s%%) must exceed '
                        'Full Unlock Threshold (%s%%) — ensures scaling in full zone.'
                    ) % (
                        rec.ebitda_max_rate_threshold / 100,
                        rec.full_gate_floor / 100,
                    ))

    @api.constrains('partial_gate_floor', 'full_gate_floor')
    def _check_gate_order(self):
        for rec in self:
            if rec.partial_gate_floor and rec.full_gate_floor:
                if rec.partial_gate_floor >= rec.full_gate_floor:
                    raise ValidationError(_(
                        'Ramp Start Margin (zero-payout) (%s%%) must be below '
                        'Full Unlock Threshold (%s%%).'
                    ) % (
                        rec.partial_gate_floor / 100,
                        rec.full_gate_floor / 100,
                    ))

    @api.constrains('h1_top_mgmt_sales_floor', 'b34_top_mgmt_min_sales_attainment',
                     'h2_rsm_sales_floor', 'b36_rsm_min_territory_sales_attainment',
                     'h3_asm_sales_floor', 'b38_asm_min_personal_sales_attainment',
                     'h4_top_mgmt_retrieval_floor', 'b35_top_mgmt_min_retrieval_rate',
                     'h5_rsm_retrieval_floor', 'b37_rsm_min_territory_retrieval_rate',
                     'h6_asm_retrieval_floor', 'b39_asm_min_personal_retrieval_rate',
                     'k1_dual_min_sales', 'k2_dual_min_retrieval',
                     'k3_dual_sales_floor', 'k4_dual_retrieval_floor')
    def _check_floor_min_order(self):
        pairs = [
            ('h1_top_mgmt_sales_floor', 'b34_top_mgmt_min_sales_attainment'),
            ('h2_rsm_sales_floor', 'b36_rsm_min_territory_sales_attainment'),
            ('h3_asm_sales_floor', 'b38_asm_min_personal_sales_attainment'),
            ('h4_top_mgmt_retrieval_floor', 'b35_top_mgmt_min_retrieval_rate'),
            ('h5_rsm_retrieval_floor', 'b37_rsm_min_territory_retrieval_rate'),
            ('h6_asm_retrieval_floor', 'b39_asm_min_personal_retrieval_rate'),
            ('k3_dual_sales_floor', 'k1_dual_min_sales'),
            ('k4_dual_retrieval_floor', 'k2_dual_min_retrieval'),
        ]
        for rec in self:
            bad = []
            for floor_f, min_f in pairs:
                floor = getattr(rec, floor_f) or 0.0
                minimum = getattr(rec, min_f) or 0.0
                if floor > minimum:
                    bad.append('%s (%s) exceeds %s (%s)' % (rec._fields[floor_f].string, floor, rec._fields[min_f].string, minimum))
            if bad:
                raise ValidationError(_('Entry floors must not exceed their full-credit minima (workbook gates): ' + '; '.join(bad)))

    @api.constrains('i1_accelerator_kick_in', 'i2_accelerator_ceiling',
                     'i3_accelerator_boost', 'i4_stretch_individual_cap',
                     'g_individual_quarterly_cap')
    def _check_accel_order(self):
        for rec in self:
            if (rec.i1_accelerator_kick_in or 0.0) > (rec.i2_accelerator_ceiling or 0.0):
                raise ValidationError(_('Accelerator Kick-in must not exceed the Accelerator Ceiling.'))
            if (rec.i3_accelerator_boost or 0.0) < 0.0:
                raise ValidationError(_('Accelerator Boost must not be negative.'))
            if rec.i4_stretch_individual_cap and rec.g_individual_quarterly_cap:
                if rec.i4_stretch_individual_cap < rec.g_individual_quarterly_cap:
                    raise ValidationError(_('Stretch Individual Cap must not be below the Individual Quarterly Cap.'))

    @api.constrains('senior_mgmt_deferred_rate', 'tier1_deferred_rate',
                     'tier2_deferred_rate', 'aip_deferred_rate_param',
                     'minimum_floor', 'maximum_cap', 'g_bonus_pool_cap_pct',
                     'g_gmp_self_report_relief', 'l2_manual_pool_rate_override',
                     'g_individual_quarterly_cap', 'i4_stretch_individual_cap')
    def _check_percent_sanity(self):
        for rec in self:
            for fname in ('senior_mgmt_deferred_rate', 'tier1_deferred_rate', 'tier2_deferred_rate', 'aip_deferred_rate_param'):
                val = getattr(rec, fname) or 0.0
                if val < 0.0 or val > 100.0:
                    raise ValidationError(_('%s must be between 0 and 100. Current value: %s') % (rec._fields[fname].string, val))
            for fname in ('minimum_floor', 'maximum_cap', 'g_individual_quarterly_cap', 'i4_stretch_individual_cap', 'l2_manual_pool_rate_override'):
                if (getattr(rec, fname) or 0.0) < 0.0:
                    raise ValidationError(_('%s must not be negative.') % rec._fields[fname].string)
            pool_cap = rec.g_bonus_pool_cap_pct or 0.0
            if pool_cap < 0.0 or pool_cap > 100.0:
                raise ValidationError(_('Bonus Pool Cap must be between 0 and 100. Current value: %s') % pool_cap)
            relief = rec.g_gmp_self_report_relief or 0.0
            if relief < 0.0 or relief > 1.0:
                raise ValidationError(_('GMP Self-Report Relief must be between 0 and 1. Current value: %s') % relief)

    @api.constrains('l_score_rev_weight', 'l_score_ebitda_weight', 'l_score_gmp_weight',
                     'l_score_people_weight', 'l_park1_weight', 'l_park2_weight',
                     'l_park3_weight', 'l_park4_weight', 'l_park5_weight')
    def _check_scorecard_weights(self):
        for rec in self:
            total = ((rec.l_score_rev_weight or 0.0) + (rec.l_score_ebitda_weight or 0.0)
                     + (rec.l_score_gmp_weight or 0.0) + (rec.l_score_people_weight or 0.0)
                     + (rec.l_park1_weight or 0.0) + (rec.l_park2_weight or 0.0)
                     + (rec.l_park3_weight or 0.0) + (rec.l_park4_weight or 0.0)
                     + (rec.l_park5_weight or 0.0))
            if not (99.99 <= total <= 100.01):
                raise ValidationError(_('Company scorecard weights must sum to 100. Current total: %s') % total)

    @api.depends('revenue_weight', 'ebitda_weight', 'gmp_weight',
                 'extended_kpi_weight')
    def _compute_kpi_weight_total(self):
        for rec in self:
            total = (rec.revenue_weight + rec.ebitda_weight +
                     rec.gmp_weight + rec.extended_kpi_weight)
            rec.kpi_weight_total = total
            rec.kpi_weight_valid = abs(total - 100.0) < 0.01

    @api.depends('sales_pk_weight', 'sales_call_weight', 'sales_coverage_weight',
                 'sales_new_cust_weight')
    def _compute_sales_kpi_weight_total(self):
        for rec in self:
            total = (rec.sales_pk_weight + rec.sales_call_weight +
                     rec.sales_coverage_weight + rec.sales_new_cust_weight)
            rec.sales_kpi_weight_total = total
            rec.sales_kpi_weight_valid = abs(total - 100.0) < 0.01

    @api.constrains('revenue_weight', 'ebitda_weight', 'gmp_weight',
                    'extended_kpi_weight')
    def _check_kpi_weights(self):
        for rec in self:
            total = (rec.revenue_weight + rec.ebitda_weight +
                     rec.gmp_weight + rec.extended_kpi_weight)
            if not (99.99 <= total <= 100.01):
                raise ValidationError(
                    _('KPI weights must sum to 100%%. Current total: %s%%') % total
                )

    @api.constrains('sales_pk_weight', 'sales_call_weight', 'sales_coverage_weight',
                    'sales_new_cust_weight')
    def _check_sales_kpi_weights(self):
        for rec in self:
            total = (rec.sales_pk_weight + rec.sales_call_weight +
                     rec.sales_coverage_weight + rec.sales_new_cust_weight)
            if not (99.99 <= total <= 100.01):
                raise ValidationError(
                    _('Sales KPI weights must sum to 100%%. Current total: %s%%') % total
                )

    def action_submit(self):
        self.submitted_by = self.env.user.id
        self.state = 'pending_approval'

    GOVERNANCE_FIELDS = [
        'min_pool_rate_min', 'min_pool_rate_max', 'min_pool_rate_approver',
        'ebitda_scaling_start_min', 'ebitda_scaling_start_max',
        'ebitda_scaling_start_approver',
        'ebitda_max_rate_threshold_min', 'ebitda_max_rate_threshold_max',
        'ebitda_max_rate_threshold_approver',
        'partial_gate_floor_min', 'partial_gate_floor_max',
        'partial_gate_floor_approver',
        'full_gate_floor_min', 'full_gate_floor_max',
        'full_gate_floor_approver',
        'max_pool_rate_min', 'max_pool_rate_max', 'max_pool_rate_approver',
        'l4_opm_share_pct_min', 'l4_opm_share_pct_max',
        'l4_opm_share_pct_approver',
        'senior_mgmt_share_pct_min', 'senior_mgmt_share_pct_max',
        'senior_mgmt_share_pct_approver',
        'aip_annual_rate_min', 'aip_annual_rate_max',
        'aip_annual_rate_approver',
        'aip_deferral_rate_min', 'aip_deferral_rate_max',
        'aip_deferral_rate_approver',
        'revenue_weight_min', 'revenue_weight_max',
        'ebitda_weight_min', 'ebitda_weight_max',
        'gmp_weight_min', 'gmp_weight_max',
        'extended_kpi_weight_min', 'extended_kpi_weight_max',
    ]

    def write(self, vals):
        governance_keys = set(vals.keys()) & set(self.GOVERNANCE_FIELDS)
        if governance_keys and not self.env.user.has_group(
                'kprl_bonus.group_kprl_ceo'):
            raise AccessError(
                _('Only the CEO / Superadmin can modify governance bounds '
                  '(min/max limits and approver assignments). '
                  'Restricted fields: %s') % ', '.join(sorted(governance_keys))
            )
        res = super().write(vals)
        try:
            self._sync_role_table()
        except Exception:
            pass
        return res

    def _sync_role_table(self):
        for rec in self:
            rows = {
                'rsm_asm': (rec.k3_dual_sales_floor, rec.k1_dual_min_sales, rec.k4_dual_retrieval_floor, rec.k2_dual_min_retrieval, False),
                'rsm': (rec.h2_rsm_sales_floor, rec.b36_rsm_min_territory_sales_attainment, rec.h5_rsm_retrieval_floor, rec.b37_rsm_min_territory_retrieval_rate, rec.rsm_pool_share),
                'asm': (rec.h3_asm_sales_floor, rec.b38_asm_min_personal_sales_attainment, rec.h6_asm_retrieval_floor, rec.b39_asm_min_personal_retrieval_rate, False),
                'gm': (rec.h1_top_mgmt_sales_floor, rec.b34_top_mgmt_min_sales_attainment, rec.h4_top_mgmt_retrieval_floor, rec.b35_top_mgmt_min_retrieval_rate, rec.gm_poolshare_rate),
                'nsm': (rec.h1_top_mgmt_sales_floor, rec.b34_top_mgmt_min_sales_attainment, rec.h4_top_mgmt_retrieval_floor, rec.b35_top_mgmt_min_retrieval_rate, rec.national_sm_pool),
                'headtech': (rec.h1_top_mgmt_sales_floor, rec.b34_top_mgmt_min_sales_attainment, rec.h4_top_mgmt_retrieval_floor, rec.b35_top_mgmt_min_retrieval_rate, rec.head_technical_poolshare),
            }
            for role, packs in rows.items():
                sf, ms, rf, mr, ps = packs
                rp = self.env['kprl.role.parameter'].search([('role', '=', role)], limit=1)
                if not rp:
                    continue
                vals = {}
                if sf:
                    vals['sales_floor'] = sf / 100.0
                if ms:
                    vals['min_sales_attainment'] = ms / 100.0
                if rf:
                    vals['retr_floor'] = rf / 100.0
                if mr:
                    vals['min_retrieval_rate'] = mr / 100.0
                if ps:
                    vals['pool_share'] = ps / 100.0
                if vals:
                    rp.write(vals)

    def action_approve(self):
        for rec in self:
            if rec.submitted_by and rec.submitted_by.id == self.env.user.id:
                raise ValidationError(_(
                    'You cannot approve this configuration because you submitted it. '
                    'The person who submitted must not be the same person who approves. '
                    'Only the CEO / Superadmin may approve.'
                ))
        self.write({
            'state': 'approved',
            'is_locked': True,
            'approver_id': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })

    def action_reject(self):
        self.state = 'rejected'

    def action_reset(self):
        self.state = 'draft'
        self.is_locked = False