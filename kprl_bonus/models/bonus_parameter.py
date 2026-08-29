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

    # -- Section C: Sales Eligibility Thresholds --
    top_mgmt_min_sales = fields.Float(string='Top Mgmt Min Sales',
                                      digits='Product Price', default=75)
    top_mgmt_min_sales_min = fields.Float(default=65)
    top_mgmt_min_sales_max = fields.Float(default=100)

    sen_mgmt_min_sales = fields.Float(string='Senior Mgmt Min Sales',
                                      digits='Product Price')
    sen_mgmt_min_sales_min = fields.Float(default=0.20)
    sen_mgmt_min_sales_max = fields.Float(default=1.00)

    mid_mgmt_min_sales = fields.Float(string='Mid Mgmt Min Sales',
                                      digits='Product Price')
    mid_mgmt_min_sales_min = fields.Float(default=0.20)
    mid_mgmt_min_sales_max = fields.Float(default=1.00)

    first_entrant_sales_threshold = fields.Float(string='First Entrant Threshold',
                                                 digits='Product Price')
    first_entrant_sales_threshold_min = fields.Float(default=0.20)
    first_entrant_sales_threshold_max = fields.Float(default=1.00)

    entry_level_sales_retrieval = fields.Float(string='Entry Level Sales Retrieval',
                                               digits=(5, 4))
    entry_level_sales_retrieval_min = fields.Float(default=0.20)
    entry_level_sales_retrieval_max = fields.Float(default=1.00)

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

    # -- Section F: National Targets --
    quarterly_revenue_target = fields.Float(string='Quarterly Revenue Target',
                                            digits='Product Price')
    annual_revenue_target = fields.Float(string='Annual Revenue Target',
                                         digits='Product Price')

    # -- Tenure Multiplier Defaults --
    tenure_default_mult = fields.Float(string='Default Tenure Multiplier',
                                       digits=(5, 4), default=1.0)

    # -- Sales Entry Gate Ramp --
    ramp_new_hire_months = fields.Integer(string='New Hire Ramp Period (months)',
                                          default=3)
    ramp_entry_mult = fields.Float(string='Entry Gate Multiplier', digits=(5, 4),
                                   default=0.5)

    # -- Sales Accelerators --
    accelerator_threshold_1 = fields.Float(string='Accelerator Threshold 1 (%)',
                                           digits=(5, 2))
    accelerator_mult_1 = fields.Float(string='Accelerator Multiplier 1', digits=(5, 4))
    accelerator_threshold_2 = fields.Float(string='Accelerator Threshold 2 (%)',
                                           digits=(5, 2))
    accelerator_mult_2 = fields.Float(string='Accelerator Multiplier 2', digits=(5, 4))
    individual_cap = fields.Float(string='Individual Cap (%)', digits=(5, 2))
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
