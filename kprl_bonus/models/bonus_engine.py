from odoo import models, fields, api
from datetime import date


class BonusEngine(models.Model):
    _name = 'kprl.bonus.engine'
    _description = 'Bonus Engine Run'
    _rec_name = 'period_id'
    _order = 'period_id desc, create_date desc'

    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('finalized', 'Finalized'),
    ], string='Status', default='draft', required=True)

    quarterly_revenue = fields.Float(string='Quarterly Revenue',
                                     digits='Product Price')
    net_revenue = fields.Float(string='Net Revenue', digits='Product Price')
    pool_contribution = fields.Float(string='Pool Contribution',
                                     digits='Product Price')

    gate_status = fields.Selection([
        ('closed', 'Closed (< 18%)'),
        ('partial', 'Partial (18%-22%)'),
        ('full', 'Full (>= 22%)'),
    ], string='Profitability Gate', compute='_compute_gate_status', store=True)
    ebitda_margin = fields.Float(string='EBITDA Margin (%)', digits=(5, 2))
    gate_factor = fields.Float(string='Gate Factor', digits=(5, 4),
                               compute='_compute_gate_factor', store=True)
    
    # New fields for proper pool rate calculation
    auto_pool_rate = fields.Float(string='Auto Pool Rate (%)', digits=(5, 4),
                                 compute='_compute_auto_pool_rate', store=True,
                                 help='Linearly interpolated pool rate based on EBITDA margin')
    company_performance_multiplier = fields.Float(string='Company Performance Multiplier', digits=(5, 4),
                                                compute='_compute_company_performance_multiplier', store=True,
                                                help='Multiplier based on Company KPI Score')
    points_weighted_dept_multiplier = fields.Float(string='Points-Weighted Dept Multiplier', digits=(5, 4),
                                                  compute='_compute_points_weighted_dept_multiplier', store=True,
                                                  help='Weighted average of department KPI multipliers by staff points')

    gmp_status = fields.Selection([
        ('clean', 'Clean'),
        ('non_compliant', 'Non-Compliant'),
    ], string='GMP Status', default='clean')
    gmp_factor = fields.Float(string='GMP Factor', digits=(5, 4), default=1.0)

    company_kpi_score = fields.Float(string='Company KPI Score', digits=(5, 4))
    effective_pool = fields.Float(string='EFFECTIVE POOL (₦)',
                                  digits='Product Price', help="GMP Factor * Gate Factor * Quaterly revenue - [Funded × (0.6·CompanyMult + 0.4·DeptMult), capped]")
    proration_factor = fields.Float(string='Proration Factor', digits=(5, 4),
                                    default=1.0)
    total_payout = fields.Float(string='Total Quarterly Payout',
                                digits='Product Price')
    ops_payout = fields.Float(string='Ops Payout', digits='Product Price')
    sales_commission = fields.Float(string='Sales Commission',
                                    digits='Product Price')
    payout_as_pct_revenue = fields.Float(string='Payout as % of Revenue',
                                         digits=(5, 4))
    pool_util_vs_ebitda_cap = fields.Float(string='Pool Util. vs EBITDA Cap',
                                           digits=(5, 4))
    headcount = fields.Integer(string='Headcount Eligible',
                               compute='_compute_headcount', store=True)
    aip_pool = fields.Float(string='AIP Pool (Annual)', digits='Product Price') 
    # company_kpi_score = fields.Float(string='Company KPI Score', digits=(5, 4)) duplicate field, already defined above
        # ── Grand Pool split ──
    opm_pool_split = fields.Float(
        string='Opm Share Pct (%)', digits=(5, 2), default=60,
        help="User input: OPM's share of the Grand Pool")
    sup_pool_split = fields.Float(
        string='SUP Share (%)', digits=(5, 2),
        compute='_compute_sup_pool_split', store=True,
        help="Auto-computed: 100 − OPM share")
    opm_pool = fields.Float(
        string='OPM Pool', digits='Product Price',
        compute='_compute_pool_total', store=True)
    sub_pool = fields.Float(
        string='SUP Pool Total', digits='Product Price',
        compute='_compute_suppool_total', store=True)

    # ── L5: SUP Pool split ──
    senior_management_sub_pool = fields.Float(
        string='Senior-Mgmt Share (%)', digits=(5, 2), default=70,
        help="User input: Senior-Mgmt's share of the SUP Pool")
    ops_sub_pool_percentage = fields.Float(
        string='Ops-Support Share (%)', digits=(5, 2),
        compute='_compute_ops_sub_pool_pct', store=True,
        help="Auto-computed: 100 − Senior-Mgmt share")
    senior_management_pool = fields.Float(
        string='Senior-Mgmt Pool', digits='Product Price',
        compute='_compute_senior_mgtpool_total', store=True)
    ops_sub_pool = fields.Float(
        string='Ops-Support Pool Total', digits='Product Price',
        compute='_compute_opssuppool_total', store=True)
    
    opm_total_point = fields.Float(string='OPM Total Point',
                                  digits='Product Price', default=0)
    senior_mgt_total_point = fields.Float(string='Senior Mgt Total Point',
                                  digits='Product Price', default=0)
    
    ops_sup_total_point = fields.Float(string='OPS SUP Total Point',
                                  digits='Product Price', default=0)
 
    opm_value_point = fields.Float(string='OPM Value Point (₦)',
                                   help="rec.opm_pool / rec.opm_total_point",
                                  digits='Product Price', readonly=True,compute="_compute_value_point")
    
    senior_mgt_value_point = fields.Float(string='Senior Mgt Value Point (₦)',
                                  digits='Product Price', help="rec.senior_management_pool / rec.senior_mgt_total_point", readonly=True,compute="_compute_value_point")
    ops_sup_value_point = fields.Float(string='OPS SUP Value Point (₦)',
                                  digits='Product Price', readonly=True, help="rec.ops_sub_pool / rec.ops_sup_total_point",
                                  compute="_compute_value_point")
    
    @api.depends('ops_sup_total_point', 'senior_mgt_total_point', 'opm_total_point')
    def _compute_value_point(self):
        for rec in self:
            # if rec.ops_sup_total_point or rec.senior_mgt_total_point or rec.opm_total_point:
            rec.opm_value_point = rec.opm_pool / rec.opm_total_point if rec.opm_total_point > 0 else 1
            rec.senior_mgt_value_point = rec.senior_management_pool / rec.senior_mgt_total_point if rec.senior_mgt_total_point > 0 else 1 
            rec.ops_sup_value_point = rec.ops_sub_pool / rec.ops_sup_total_point if rec.ops_sup_total_point > 0 else 1 
            # else:
            #     rec.ops_sup_value_point = 0
            #     rec.opm_value_point = 0
            #     rec.senior_mgt_value_point = 0

    @api.depends('opm_pool_split')
    def _compute_sup_pool_split(self):
        for rec in self:
            rec.sup_pool_split = 100.0 - (rec.opm_pool_split or 0.0)

    @api.depends('senior_management_sub_pool')
    def _compute_ops_sub_pool_pct(self):
        for rec in self:
            rec.ops_sub_pool_percentage = 100.0 - (rec.senior_management_sub_pool or 0.0)

    @api.depends('opm_pool_split', 'effective_pool')
    def _compute_pool_total(self):
        for rec in self:
            rec.opm_pool = (rec.opm_pool_split / 100.0) * rec.effective_pool if rec.effective_pool else 0.0

    @api.depends('sup_pool_split', 'effective_pool')
    def _compute_suppool_total(self):
        for rec in self:
            rec.sub_pool = (rec.sup_pool_split / 100.0) * rec.effective_pool if rec.effective_pool else 0.0

    @api.depends('senior_management_sub_pool', 'sub_pool')
    def _compute_senior_mgtpool_total(self):
        for rec in self:
            rec.senior_management_pool = (rec.senior_management_sub_pool / 100.0) * rec.sub_pool if rec.sub_pool else 0.0

    @api.depends('ops_sub_pool_percentage', 'sub_pool')
    def _compute_opssuppool_total(self):
        for rec in self:
            rec.ops_sub_pool = (rec.ops_sub_pool_percentage / 100.0) * rec.sub_pool if rec.sub_pool else 0.0

    # EFFECTIVE POOL (₦) [Funded × (0.6·CompanyMult + 0.4·DeptMult), capped]
    # OPM Pool Split %
    # SUP Pool Split %
    # OPM Pool (₦)
    # SUP Pool Total (₦)
    # SEN-MGT Sub-Pool % of SUP
    # OPS-SUP Sub-Pool %
    # SEN-MGT Pool (₦)
    # OPS-SUP Pool (₦)

    parameter_id = fields.Many2one(compute='_compute_parameter_id', comodel_name='kprl.bonus.parameter',
                                   string='Active Parameters')
    
    grade_level_ids = fields.Many2many(comodel_name='kprl.grade',
                                   string='Grade Level Applicable')
    employee_count = fields.Integer(string='Employees', help="Total employee on selected grades", 
                               compute='_compute_total_employee_on_grade', store=True)

    @api.depends('period_id.parameter_ids')
    def _compute_parameter_id(self):
        for rec in self:
            if rec.period_id:
                parameter_id = rec.period_id.parameter_ids.filtered(
                    lambda p: p.active)
                rec.parameter_id  = parameter_id and parameter_id[0].id or False
            else:
                rec.parameter_id = False

    computed_on = fields.Datetime(string='Computed On')
    computed_by = fields.Many2one('res.users', string='Computed By')
    notes = fields.Text(string='Notes')

    @api.depends('ebitda_margin')
    def _compute_gate_status(self):
        for rec in self:
            if rec.ebitda_margin >= 22.0:
                rec.gate_status = 'full'
            elif rec.ebitda_margin >= 18.0:
                rec.gate_status = 'partial'
            elif rec.ebitda_margin > 0:
                rec.gate_status = 'closed'
            else:
                rec.gate_status = 'closed'

    @api.depends('ebitda_margin', 'period_id')
    def _compute_auto_pool_rate(self):
        """Calculate auto pool rate using linear interpolation as per specification"""
        for rec in self:
            params = rec.period_id.parameter_ids if rec.period_id else None
            if not params:
                rec.auto_pool_rate = 0.0
                continue

            # Get parameters from specification
            min_rate = params.min_pool_rate / 100.0 if params.min_pool_rate else 0.00606
            max_rate = params.max_pool_rate / 100.0 if params.max_pool_rate else 0.017
            ebitda_floor = params.ebitda_scaling_start / 100.0 if params.ebitda_scaling_start else 0.12
            ebitda_target = params.ebitda_max_rate_threshold / 100.0 if params.ebitda_max_rate_threshold else 0.30

            actual_ebitda = rec.ebitda_margin / 100.0 if rec.ebitda_margin else 0.0

            # Linear interpolation formula from specification:
            # Auto Pool Rate = Pool Rate Min + [(Actual EBITDA - EBITDA Floor) / (EBITDA Target - EBITDA Floor)] × (Pool Rate Max - Pool Rate Min)
            if actual_ebitda <= ebitda_floor:
                rec.auto_pool_rate = min_rate
            elif actual_ebitda >= ebitda_target:
                rec.auto_pool_rate = max_rate
            else:
                interpolation_factor = (actual_ebitda - ebitda_floor) / (ebitda_target - ebitda_floor)
                rec.auto_pool_rate = min_rate + (interpolation_factor * (max_rate - min_rate))

    @api.depends('ebitda_margin', 'period_id')
    def _compute_gate_factor(self):
        """Calculate gate factor with continuous ramp for partial gate"""
        for rec in self:
            params = rec.period_id.parameter_ids if rec.period_id else None
            if not params:
                rec.gate_factor = 0.0
                continue

            partial_unlock = params.partial_gate_floor / 100.0 if params.partial_gate_floor else 0.18
            full_unlock = params.full_gate_floor / 100.0 if params.full_gate_floor else 0.22
            actual_ebitda = rec.ebitda_margin / 100.0 if rec.ebitda_margin else 0.0

            # Profitability Gate Factor with continuous ramp
            if actual_ebitda >= full_unlock:
                rec.gate_factor = 1.0  # Fully open
            elif actual_ebitda <= partial_unlock:
                rec.gate_factor = 0.0  # Closed
            else:
                # Linear ramp from 0 at partial to 1.0 at full
                rec.gate_factor = (actual_ebitda - partial_unlock) / (full_unlock - partial_unlock)
            
            # Update gate status based on continuous calculation
            if actual_ebitda >= full_unlock:
                rec.gate_status = 'full'
            elif actual_ebitda >= partial_unlock:
                rec.gate_status = 'partial'
            else:
                rec.gate_status = 'closed'

    @api.depends('period_id.company_kpi', 'period_id.parameter_ids.company_mult_baseline', 'period_id.parameter_ids.company_mult_k_factor')
    def _compute_company_performance_multiplier(self):
        for rec in self:
            company_kpi = rec.period_id.company_kpi if rec.period_id else 0.0
            params = rec.period_id.parameter_ids[:1] if rec.period_id else None
            baseline = params.company_mult_baseline if params and params.company_mult_baseline else 0.90
            k_factor = params.company_mult_k_factor if params and params.company_mult_k_factor else 0.20
            if company_kpi >= baseline:
                rec.company_performance_multiplier = 1.0 + ((company_kpi - baseline) * k_factor)
            else:
                rec.company_performance_multiplier = 1.0  # No boost below baseline

    @api.depends('period_id')
    def _compute_points_weighted_dept_multiplier(self):
        """Calculate points-weighted average of department KPI multipliers"""
        for rec in self:
            if not rec.period_id:
                rec.points_weighted_dept_multiplier = 1.0
                continue

            # Get all departments with their KPI multipliers for this period
            dept_kpis = self.env['kprl.dept.kpi.multiplier'].search([
                ('period_id', '=', rec.period_id.id)
            ])
            
            if not dept_kpis:
                rec.points_weighted_dept_multiplier = 1.0
                continue

            # Calculate weighted average by staff points
            total_weighted_mult = 0.0
            total_points = 0.0
            
            for dept_kpi in dept_kpis:
                # Get total points for employees in this department
                dept_employees = self.env['kprl.employee'].search([
                    ('department_id', '=', dept_kpi.department_id.id),
                    ('status', '=', 'active')
                ])
                dept_points = sum(emp.total_points for emp in dept_employees)
                
                if dept_points > 0:
                    total_weighted_mult += dept_kpi.multiplier * dept_points
                    total_points += dept_points
            
            rec.points_weighted_dept_multiplier = (total_weighted_mult / total_points) if total_points > 0 else 1.0

    @api.depends('ebitda_margin', 'period_id')


    @api.depends('period_id', 'period_id.department_ids')
    def _compute_points_weighted_dept_multiplier(self):
        """Calculate points-weighted average of department KPI multipliers"""
        for rec in self:
            if not rec.period_id:
                rec.points_weighted_dept_multiplier = 1.0
                continue

            # Get all departments with their KPI multipliers for this period
            dept_kpis = self.env['kprl.dept.kpi.multiplier'].search([
                ('period_id', '=', rec.period_id.id)
            ])
            
            if not dept_kpis:
                rec.points_weighted_dept_multiplier = 1.0
                continue

            # Calculate weighted average by staff points
            total_weighted_mult = 0.0
            total_points = 0.0
            
            for dept_kpi in dept_kpis:
                # Get total points for employees in this department
                dept_employees = self.env['kprl.employee'].search([
                    ('department_id', '=', dept_kpi.department_id.id),
                    ('status', '=', 'active')
                ])
                dept_points = sum(emp.total_points for emp in dept_employees)
                
                if dept_points > 0:
                    total_weighted_mult += dept_kpi.multiplier * dept_points
                    total_points += dept_points
            
            rec.points_weighted_dept_multiplier = (total_weighted_mult / total_points) if total_points > 0 else 1.0
    
    @api.depends('grade_level_ids')
    def _compute_total_employee_on_grade(self):
        for rec in self:
            if rec.grade_level_ids:
                emp = 0
                for g in rec.grade_level_ids:
                    emps = self.env['kprl.employee'].search_count([
                        ('grade_id', '=', g.id),
                    ])
                    emp += emps
                rec.employee_count = emp
            else:
                rec.employee_count = 0

    @api.depends('period_id')
    def _compute_headcount(self):
        for rec in self:
            if rec.period_id:
                rec.headcount = self.env['kprl.bonus.payout'].search_count([
                    ('period_id', '=', rec.period_id.id),
                ])
            else:
                rec.headcount = 0

    def action_compute(self):
        self.ensure_one()
        params = self.period_id.parameter_ids[:1] if self.period_id else None
        # SKU source Sec4→5A: BasePool = Σ contributions, not revenue_target
        pool_lines = self.env['kprl.product.pool'].search([('period_id','=',self.period_id.id)])
        base_pool = sum(pool_lines.mapped('pool_contribution')) if pool_lines else 0.0
        quarterly_rev = sum(pool_lines.mapped('quantity_revenue')) if pool_lines else (self.period_id.revenue_target or 0.0)
        self.quarterly_revenue = quarterly_rev
        self.pool_contribution = base_pool
        self.ebitda_margin = self.period_id.ebitda_margin
        funded_pool = base_pool * self.gate_factor * self.gmp_factor
        performance_blend = (0.6 * self.company_performance_multiplier) + (0.4 * self.points_weighted_dept_multiplier)
        effective = funded_pool * performance_blend
        # Cap Sec5I: Effective ≤ 12%*EBITDA
        ebitda_amt = quarterly_rev * (self.ebitda_margin/100.0) if quarterly_rev else 0.0
        cap_pct = (params.g_bonus_pool_cap_pct / 100.0) if params and getattr(params, 'g_bonus_pool_cap_pct', None) else 0.12
        cap = ebitda_amt * cap_pct
        self.effective_pool = min(effective, cap) if cap else effective

        payouts = self.env['kprl.bonus.payout'].search([
            ('period_id', '=', self.period_id.id),
        ])
        self.ops_payout = sum(p.gross_payable for p in payouts)
        
        # Calculate sales commission from sales engine
        sales_engines = self.env['kprl.sales.engine'].search([
            ('period_id', '=', self.period_id.id),
        ])
        self.sales_commission = sum(se.final_sales_payout for se in sales_engines)
        
        self.total_payout = self.ops_payout + self.sales_commission
        self.aip_pool = self.quarterly_revenue * (params.aip_annual_rate or 0.002)

        if self.quarterly_revenue:
            self.payout_as_pct_revenue = (self.total_payout / self.quarterly_revenue)
        self.pool_util_vs_ebitda_cap = self.payout_as_pct_revenue

        self.state = 'computed'
        self.computed_on = fields.Datetime.now()
        self.computed_by = self.env.user
    def action_finalize(self):
        self.action_compute()
        self.state = 'finalized'
    def action_reset(self):
        self.action_compute()
        self.state = 'draft'

