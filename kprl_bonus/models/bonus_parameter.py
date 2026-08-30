from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError


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
                                 default=0.61)
    min_pool_rate_min = fields.Float(string='Pool Rate Min (floor) — Lower Bound', digits=(5, 4), default=0.3)
    min_pool_rate_max = fields.Float(string='Pool Rate Min (floor) — Upper Bound', digits=(5, 4), default=0.8)
    min_pool_rate_approver = fields.Char(string='Approver', default='Board')

    max_pool_rate = fields.Float(string='Pool Rate Max (ceiling)', digits=(5, 4),
                                 default=1.70
                                 )

    max_pool_rate_min = fields.Float(string='Pool Rate Max (ceiling) — Lower Bound', default=1.50)
    max_pool_rate_max = fields.Float(string='Pool Rate Max (ceiling) — Upper Bound', default=2.0)
    max_pool_rate_approver = fields.Char(default='Board')

    ebitda_scaling_start = fields.Float(string='EBITDA threshold Scaling Start',
                                        digits=(5, 4), default=12.0)
    ebitda_scaling_start_min = fields.Float(string='EBITDA threshold Scaling Start — Lower Bound', default=10)
    ebitda_scaling_start_max = fields.Float(string='EBITDA threshold Scaling Start — Upper Bound', default=15)
    ebitda_scaling_start_approver = fields.Char(default='Board')

    ebitda_max_rate_threshold = fields.Float(string='EBITDA Threshold — Max Rate Reached',
                                             digits=(5, 4), default=30)
    ebitda_max_rate_threshold_min = fields.Float(default=25.00)
    ebitda_max_rate_threshold_max = fields.Float(default=70.00)
    ebitda_max_rate_threshold_approver = fields.Char(default='Board')

    partial_gate_floor = fields.Float(string='Profitability Gate (Partial unlock)',
                                      digits=(5, 4), default=18.0)
    partial_gate_floor_min = fields.Float(string='Profitability Gate (Partial unlock) — Lower Bound', default=15.0)
    partial_gate_floor_max = fields.Float(string='Profitability Gate (Partial unlock) — Upper Bound', default=22.0)
    partial_gate_floor_approver = fields.Char(default='Board')

    full_gate_floor = fields.Float(string='Profitability Gate (full unlock)', digits=(5, 4), default=22.0)
    full_gate_floor_min = fields.Float(string='Profitability Gate (full unlock) — Lower Bound', default=20)
    full_gate_floor_max = fields.Float(string='Profitability Gate (full unlock) — Upper Bound', default=30)
    full_gate_floor_approver = fields.Char(default='Board')
        # ── Grand Pool → OPM (input) / SUP (auto-remainder) ──
    l4_opm_share_pct = fields.Float(
        string='Opm Share Pct (%)', digits=(5, 2), default=60,
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

    aip_annual_rate = fields.Float(string='AIP Annual Rate', digits=(5, 4),
                                   help='% of annual revenue for year-end management bonus')
    aip_annual_rate_min = fields.Float(default=5.0)
    aip_annual_rate_max = fields.Float(default=6.0)
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
                                          digits=(5, 4))
    product_pool_share_pct_min = fields.Float(default=0.20)
    product_pool_share_pct_max = fields.Float(default=1.00)
    product_pool_share_pct_approver = fields.Char(default='Finance Director')

    commission_share_pct = fields.Float(string='Commission Share (%)', digits=(5, 4))
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
                                             digits=(5, 4))
    tier1_deferred_rate = fields.Float(string='Tier 1 Deferred Rate (%)',
                                       digits=(5, 4))
    tier2_deferred_rate = fields.Float(string='Tier 2 Deferred Rate (%)',
                                       digits=(5, 4))
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
                                 digits=(5, 2), default="20")
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
    g_bonus_pool_cap_pct = fields.Float(string='Bonus Pool Cap (% of EBITDA)', digits=(5, 2), default=12.0, help='Hard ceiling: effective pool cannot exceed this share of EBITDA')
    g_individual_quarterly_cap = fields.Float(string='Individual Quarterly Cap (N)', digits='Product Price', default=2000000, help='Max any one person can receive per quarter')
    g_leadership_premium = fields.Float(string='Leadership Premium (manager vs top subordinate)', digits=(5, 2), default=1.10, help='RSM / RSM+ASM commission floored at this multiple of the top subordinate in territory')
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
    l2_manual_pool_rate_override = fields.Float(string='Manual Pool Rate Override (%)', digits=(5, 4), help='L2: blank = auto (uses Auto Pool Rate)')
    l3_gmp_compliance_status = fields.Selection([('clean','Clean'),('minor','Minor'),('major','Major'),('critical','Critical')], string='GMP Compliance Status', default='clean', help='L3')
    l_score_rev_weight = fields.Float(string='Revenue Achievement Weight (%)', digits=(5, 2), default=33.0)
    l_score_ebitda_weight = fields.Float(string='EBITDA Margin Achievement Weight (%)', digits=(5, 2), default=30.0)
    l_score_gmp_weight = fields.Float(string='GMP & Quality Compliance Weight (%)', digits=(5, 2), default=25.0)
    l_score_people_weight = fields.Float(string='People Weight (%)', digits=(5, 2), default=12.0)
    # TODO TEST THE FUNCTIONS
    funded_pool_after_both_gate = fields.Float(default=0, compute="_compute_funded_pool")
    profitability_gate_factor = fields.Float(default=1,string="Profitability Gate Factor (continuous ramp)")
    base_bonus_pool = fields.Float(default=0, string="Base Bonus Pool")
    gmp_gate_factor = fields.Float(default=1, string="GMP Gate Factor")

    @api.depends('profitability_gate_factor', 'base_bonus_pool', 'gmp_gate_factor')
    def _compute_funded_pool(self):
        for rec in self:
            rec.funded_pool_after_both_gate = rec.profitability_gate_factor * rec.base_bonus_pool * rec.gmp_gate_factor

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
                    'max_pool_rate', 'opm_subpool_share', 'sen_mgt_share',
                    'ops_sup_share', 'aip_annual_rate', 'aip_deferral_rate',
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
                        'Profitability Gate (full unlock) (%s%%) — prevents dead zone.'
                    ) % (
                        rec.ebitda_scaling_start / 100,
                        rec.full_gate_floor / 100,
                    ))
            if rec.ebitda_max_rate_threshold and rec.full_gate_floor:
                if rec.ebitda_max_rate_threshold <= rec.full_gate_floor:
                    raise ValidationError(_(
                        'EBITDA Max Rate Threshold (%s%%) must exceed '
                        'Profitability Gate (full unlock) (%s%%) — ensures scaling in full zone.'
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
                        'Profitability Gate (Partial unlock) (%s%%) must be below '
                        'Profitability Gate (full unlock) (%s%%).'
                    ) % (
                        rec.partial_gate_floor / 100,
                        rec.full_gate_floor / 100,
                    ))

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
        return super().write(vals)

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