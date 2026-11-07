from odoo import models, fields, api
from datetime import date

from .kprl_math import score_to_multiplier, normalize_score, profitability_gate, DEFAULT_RAMP_START, DEFAULT_FULL_UNLOCK, company_gmp_band
from odoo.exceptions import ValidationError
from .compensation.grade_policy import clamp_skill_premium
from .compensation.operations import (
    value_per_point, weighted_department_multiplier, workbook_effective_pool,
)
from .compensation.multipliers import auto_pool_rate


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
        ('closed', 'LOCKED - no pool'),
        ('partial', 'PARTIAL'),
        ('full', 'FULLY OPEN'),
    ], string='Profitability Gate', compute='_compute_gate_status', store=True)
    ebitda_margin = fields.Float(string='EBITDA Margin (%)', digits=(5, 2))
    gate_factor = fields.Float(string='Gate Factor', digits=(5, 2),
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

    company_kpi_avg = fields.Float(string='Company KPI Factor (avg dept appraisal)', digits=(5, 4),
                                   compute='_compute_company_kpi_avg', store=True,
                                   help='Client formula: simple mean of dept-mean appraisal scores (0-1), all depts incl. sales. Depts with no appraised staff excluded.')
    company_gmp_avg = fields.Float(string='Company GMP Average (dept mean)', digits=(5, 4),
                                   compute='_compute_company_gmp_avg', store=True,
                                   help='Company-wide GMP status: simple mean of all dept GMP factors (def_factor) for the period.')
    company_gmp_band_factor = fields.Float(string='Company GMP Factor (banded)', digits=(5, 4),
                                           compute='_compute_company_gmp_avg', store=True,
                                           help='Company-wide Quarterly Incentive Pool band. Clean avg 1.0-0.9 -> 1.0; Minor avg 0.89-0.70 -> 0.8; Major avg 0.69-0.5 -> 0.4; Critical avg below 0.5 -> 0.0.')
    gmp_status = fields.Selection([
        ('clean', 'Clean'),
        ('non_compliant', 'Non-Compliant'),
    ], string='GMP Status', default='clean')
    gmp_factor = fields.Float(string='GMP Factor', digits=(5, 2), default=1.0,
                               compute='_compute_engine_gmp_factor', store=True, readonly=False)

    company_kpi_score = fields.Float(string='Company KPI Score (%)', digits=(5, 2),
                                     compute='_compute_company_kpi_score', store=True)
    effective_pool = fields.Float(string='EFFECTIVE POOL (₦)',
                                  digits='Product Price', help="Workbook formula: MIN(base pool × profitability gate × company GMP factor × (60% × company scorecard multiplier + 40% × points-weighted department multiplier), EBITDA cap).")
    proration_factor = fields.Float(string='Proration Factor', digits=(5, 2),
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
    qipm_pool = fields.Float(string='QIPM', digits='Product Price', readonly=True, help='Workbook annual AIP funded pool: annual revenue target × AIP rate, released only when full-year EBITDA meets the gate.')
    # company_kpi_score = fields.Float(string='Company KPI Score', digits=(5, 4)) duplicate field, already defined above
        # ── Grand Pool split ──
    opm_pool_split = fields.Float(
        string='Opm Share Pct (%)', digits=(5, 2), default=50,
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
    
    @api.depends('opm_pool', 'senior_management_pool', 'ops_sub_pool', 'ops_sup_total_point', 'senior_mgt_total_point', 'opm_total_point')
    def _compute_value_point(self):
        for rec in self:
            rec.opm_value_point = value_per_point(rec.opm_pool, rec.opm_total_point)
            rec.senior_mgt_value_point = value_per_point(
                rec.senior_management_pool, rec.senior_mgt_total_point)
            rec.ops_sup_value_point = value_per_point(
                rec.ops_sub_pool, rec.ops_sup_total_point)

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

    @api.depends('ebitda_margin', 'period_id.parameter_ids.partial_gate_floor',
                 'period_id.parameter_ids.full_gate_floor')
    def _compute_gate_status(self):
        for rec in self:
            params = rec.period_id.parameter_ids[:1] if rec.period_id else False
            full = params.full_gate_floor if params else 30.0
            partial = params.partial_gate_floor if params else 20.0
            if rec.ebitda_margin >= full:
                rec.gate_status = 'full'
            elif rec.ebitda_margin > partial:
                rec.gate_status = 'partial'
            else:
                rec.gate_status = 'closed'

    @api.depends('ebitda_margin', 'period_id.parameter_ids.min_pool_rate',
                 'period_id.parameter_ids.max_pool_rate',
                 'period_id.parameter_ids.ebitda_scaling_start',
                 'period_id.parameter_ids.ebitda_max_rate_threshold')
    def _compute_auto_pool_rate(self):
        """Mirror BONUS ENGINE B9, including its IFERROR fallback."""
        for rec in self:
            params = rec.period_id.parameter_ids[:1] if rec.period_id else False
            min_rate = (params.min_pool_rate / 100.0) if params else 0.008
            max_rate = (params.max_pool_rate / 100.0) if params else 0.018
            ebitda_floor = (params.ebitda_scaling_start / 100.0) if params else 0.15
            ebitda_target = (params.ebitda_max_rate_threshold / 100.0) if params else 0.40
            actual_ebitda = (rec.ebitda_margin or 0.0) / 100.0
            rec.auto_pool_rate = auto_pool_rate(
                actual_ebitda, min_rate, max_rate, ebitda_floor, ebitda_target)

    @api.depends('ebitda_margin', 'period_id.parameter_ids.partial_gate_floor',
                 'period_id.parameter_ids.full_gate_floor')
    def _compute_gate_factor(self):
        """Calculate gate factor with continuous ramp for partial gate"""
        for rec in self:
            params = rec.period_id.parameter_ids[:1] if rec.period_id else False
            partial_unlock = params.partial_gate_floor / 100.0 if params else DEFAULT_RAMP_START
            full_unlock = params.full_gate_floor / 100.0 if params else DEFAULT_FULL_UNLOCK
            actual_ebitda = rec.ebitda_margin / 100.0 if rec.ebitda_margin else 0.0

            # Profitability Gate Factor with continuous ramp
            if actual_ebitda >= full_unlock:
                rec.gate_factor = 1.0  # Fully open
            elif actual_ebitda <= partial_unlock:
                rec.gate_factor = 0.0  # Closed
            else:
                # Shared helper: ramp START pays 0, no cliff (rounded to 1 decimal for display)
                rec.gate_factor = profitability_gate(actual_ebitda, ramp_start=partial_unlock, full_unlock=full_unlock)
            
            # Update gate status based on continuous calculation
            if actual_ebitda >= full_unlock:
                rec.gate_status = 'full'
            elif actual_ebitda > partial_unlock:
                rec.gate_status = 'partial'
            else:
                rec.gate_status = 'closed'

    @api.depends('period_id.parameter_ids.l3_gmp_compliance_status', 'period_id.parameter_ids.g_company_gmp_self_reported', 'period_id.parameter_ids.g_gmp_self_report_relief')
    def _compute_engine_gmp_factor(self):
        """Engine GMP Factor from L3 company GMP status. Clean -> 1.0.
        Editable (readonly=False): manual edits persist until an L3 dependency changes."""
        from .kprl_math import company_gmp_factor
        for rec in self:
            params = rec.period_id.parameter_ids[:1] if rec.period_id else False
            if not params:
                # No params yet: keep existing manual value, default 1.0 on new records
                if rec.gmp_factor is False or rec.gmp_factor is None:
                    rec.gmp_factor = 1.0
                continue
            status = params.l3_gmp_compliance_status or 'clean'
            c_self = params.g_company_gmp_self_reported if hasattr(params, 'g_company_gmp_self_reported') else False
            relief = params.g_gmp_self_report_relief or 0.5
            try:
                rec.gmp_factor = company_gmp_factor(status, c_self, relief)
            except ValueError as exc:
                from odoo.exceptions import ValidationError as _VE
                raise _VE('Invalid company GMP status %r: use Clean / Minor / Major / Critical.' % (status,)) from exc

    @api.depends('period_id.parameter_ids.company_scorecard_total')
    def _compute_company_kpi_score(self):
        """BONUS ENGINE B37: weighted company scorecard, displayed as percent."""
        for rec in self:
            params = rec.period_id.parameter_ids[:1] if rec.period_id else False
            rec.company_kpi_score = round(
                (params.company_scorecard_total or 0.0) * 100.0, 2) if params else 0.0

    @api.depends('period_id.parameter_ids.company_scorecard_total')
    def _compute_company_performance_multiplier(self):
        """BONUS ENGINE B38 multiplier, driven by the company scorecard."""
        for rec in self:
            params = rec.period_id.parameter_ids[:1] if rec.period_id else False
            rec.company_performance_multiplier = score_to_multiplier(
                params.company_scorecard_total or 0.0) if params else score_to_multiplier(0.0)

    @api.depends('period_id', 'period_id.dept_kpi_ids.multiplier',
                 'period_id.payout_ids.employee_id.total_points',
                 'period_id.payout_ids.employee_id.department_id',
                 'period_id.payout_ids.employee_id.status')
    def _compute_points_weighted_dept_multiplier(self):
        """Mirror BONUS ENGINE B39 and STAFF PAYOUT AF/H, including IFERROR."""
        for rec in self:
            if not rec.period_id:
                rec.points_weighted_dept_multiplier = 1.0
                continue
            dept_kpis = self.env['kprl.dept.kpi.multiplier'].search([
                ('period_id', '=', rec.period_id.id)
            ])
            multipliers = {
                row.department_id.id: row.multiplier for row in dept_kpis
            }
            staff_points = [
                (line.employee_id.department_id.id,
                 line.employee_id.total_points)
                for line in rec.period_id.payout_ids
                if line.employee_id and line.employee_id.status == 'active'
            ]
            rec.points_weighted_dept_multiplier = weighted_department_multiplier(
                staff_points, multipliers)

    @api.depends('period_id',
                 'period_id.performance_ids.appraisal_score',
                 'period_id.performance_ids.employee_id.department_id',
                 'period_id.performance_ids.employee_id.status')
    def _compute_company_kpi_avg(self):
        '''Client formula: mean of dept-mean appraisal scores (0-1).
        All depts incl. sales. A dept mean covers active staff holding a
        performance row for the period; staff without rows are skipped and
        depts with no appraised staff are excluded. Retained as a reporting
        statistic; the workbook pool multiplier uses the company scorecard.'''
        from .kprl_math import normalize_score
        for rec in self:
            if not rec.period_id:
                rec.company_kpi_avg = 0.0
                continue
            dept_means = []
            for dept in self.env['kprl.department'].search([]):
                staff = self.env['kprl.employee'].search(
                    [('department_id', '=', dept.id), ('status', '=', 'active')])
                if not staff:
                    continue
                perfs = self.env['kprl.performance.input'].search(
                    [('period_id', '=', rec.period_id.id),
                     ('employee_id', 'in', staff.ids)])
                scores = [normalize_score(pf.appraisal_score)
                          for pf in perfs
                          if pf.appraisal_score not in (None, False)]
                if scores:
                    dept_means.append(sum(scores) / len(scores))
            rec.company_kpi_avg = (sum(dept_means) / len(dept_means)) if dept_means else 0.0

    @api.depends('period_id', 'period_id.dept_kpi_ids.def_factor')
    def _compute_company_gmp_avg(self):
        '''Reporting statistic: simple mean of department GMP factors, then
        banded. The workbook pool gate uses the company GMP status factor.'''
        for rec in self:
            if not rec.period_id:
                rec.company_gmp_avg = 0.0
                rec.company_gmp_band_factor = 0.0
                continue
            rows = self.env['kprl.dept.kpi.multiplier'].search(
                [('period_id', '=', rec.period_id.id)])
            if not rows:
                rec.company_gmp_avg = 0.0
                rec.company_gmp_band_factor = 0.0
                continue
            avg = sum(rows.mapped('def_factor')) / len(rows)
            rec.company_gmp_avg = avg
            try:
                rec.company_gmp_band_factor = company_gmp_band(avg)
            except ValueError:
                rec.company_gmp_band_factor = 0.0

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

    def action_generate_payouts(self):
        self.ensure_one()
        if not self.period_id:
            return 0
        Payout = self.env['kprl.bonus.payout']
        employees = self.env['kprl.employee'].search([('status', '=', 'active')])
        created = 0
        errors = []
        for emp in employees:
            exists = Payout.search([('employee_id', '=', emp.id), ('period_id', '=', self.period_id.id)], limit=1)
            if exists:
                continue
            try:
                Payout.create({'employee_id': emp.id, 'period_id': self.period_id.id})
                created += 1
            except Exception as exc:
                errors.append('%s: %s' % (emp.name or '', exc))
        if errors:
            raise ValidationError('Could not generate payouts: ' + '\n'.join(errors))
        return created

    def action_compute(self):
        self.ensure_one()
        params = self.period_id.parameter_ids[:1] if self.period_id else None
        if params:
            # Workbook BONUS ENGINE B42/B46 link to CONTROL PANEL split inputs.
            self.opm_pool_split = params.l4_opm_share_pct
            self.senior_management_sub_pool = params.senior_mgmt_share_pct
        # SKU source Sec4→5A: BasePool = Σ contributions, not revenue_target
        pool_lines = self.env['kprl.product.pool'].search([('period_id','=',self.period_id.id)])
        base_pool = sum(pool_lines.mapped('pool_contribution')) if pool_lines else 0.0
        quarterly_rev = sum(pool_lines.mapped('quantity_revenue')) if pool_lines else (self.period_id.revenue_target or 0.0)
        self.quarterly_revenue = quarterly_rev
        self.pool_contribution = base_pool
        if params and params.l1_pool_funding_method == 'ebitda':
            min_r = params.min_pool_rate / 100.0
            max_r = params.max_pool_rate / 100.0
            e_fl = params.ebitda_scaling_start / 100.0
            e_tg = params.ebitda_max_rate_threshold / 100.0
            e_now = (self.period_id.ebitda_margin or 0.0) / 100.0
            if (params.l2_manual_pool_rate_enabled
                    or params.l2_manual_pool_rate_override):
                rate = params.l2_manual_pool_rate_override / 100.0
            else:
                rate = auto_pool_rate(e_now, min_r, max_r, e_fl, e_tg)
            base_pool = (quarterly_rev or 0.0) * rate
            self.pool_contribution = base_pool
        if not self.period_id.revenue_amount and not self.period_id.ebitda_margin:
            raise ValidationError('EBITDA/revenue missing for active period: enter amounts on the period before computing.')
        self.ebitda_margin = self.period_id.ebitda_margin
        # Force fresh gate/GMP/KPI values (computed fields may hold stale stored values)
        self._compute_gate_factor()
        self._compute_engine_gmp_factor()
        if params:
            params._compute_company_scorecard()
        self._compute_company_kpi_avg()
        self._compute_company_gmp_avg()
        self._compute_company_kpi_score()
        self._compute_company_performance_multiplier()
        # Only create payout rows after the run is known to be computable.
        self.action_generate_payouts()
        self._compute_points_weighted_dept_multiplier()
        ebitda_amt = quarterly_rev * (self.ebitda_margin/100.0) if quarterly_rev else 0.0
        cap_pct = (params.g_bonus_pool_cap_pct / 100.0) if params else 0.10
        pool_result = workbook_effective_pool(
            base_pool, self.gate_factor, self.gmp_factor,
            self.company_performance_multiplier,
            self.points_weighted_dept_multiplier, ebitda_amt, cap_pct)
        self.effective_pool = pool_result['effective_pool']
        to_push = self.env['kprl.bonus.payout'].search([('period_id', '=', self.period_id.id)])
        if to_push:
            pools = {'OPM': self.opm_pool, 'SENMGT': self.senior_management_pool, 'OPSSUP': self.ops_sub_pool}
            totals = {}
            for pp in to_push:
                code = (pp.subpool_id.code or 'OPM')
                # Workbook BONUS ENGINE B54: SALES-pool staff sit in OPS-SUP.
                if code == 'SALES':
                    code = 'OPSSUP'
                # Workbook STAFF PAYOUT col H: total points = base pts + skill
                # premium (clamped by grade skill max). Never fall back to the
                # grade table alone: a blocked line still owns its base points.
                pts = float(pp.total_points or 0.0)
                if pts <= 0:
                    grade = pp.grade_id
                    base_pts = float(grade.yp_points or 0.0)
                    skill = float(pp.employee_id.skill_premium_pts or 0.0)
                    pts = base_pts + clamp_skill_premium(skill, grade.skill_max)
                totals[code] = totals.get(code, 0.0) + pts
            vmap = {}
            for code, pool_amt in pools.items():
                tot = totals.get(code, 0.0)
                vmap[code] = (pool_amt / tot) if tot else 1.0
            self.opm_total_point = totals.get('OPM', 0.0)
            self.senior_mgt_total_point = totals.get('SENMGT', 0.0)
            self.ops_sup_total_point = totals.get('OPSSUP', 0.0)
            for pp in to_push:
                pp._recalculate_from_engine()
            gross_sum = sum(to_push.mapped('gross_payable'))
            factor = min(1.0, (self.effective_pool / gross_sum)) if gross_sum else 1.0
            self.proration_factor = factor
            for pp in to_push:
                pp.write({'proration_factor': factor})
                pp._recalculate_from_engine()
                pp.ensure_deferred_entry()

        payouts = self.env['kprl.bonus.payout'].search([
            ('period_id', '=', self.period_id.id),
        ])
        self.ops_payout = sum(p.gross_payable for p in payouts)
        
        # Calculate sales commission from sales engine
        eng = self.env['kprl.territory.engine'].search([('period_id', '=', self.period_id.id)], limit=1)
        if eng:
            self.sales_commission = eng.total_sales_payout or sum(eng.kprl_employee_engine_line_ids.mapped('sales_payout'))
        else:
            self.sales_commission = sum(self.env['kprl.territory.engine.lines'].search([('territory_engine_id.period_id', '=', self.period_id.id)]).mapped('sales_payout'))
        self.total_payout = self.ops_payout + self.sales_commission
        # Workbook BONUS ENGINE B99 is the annual pool funded by the
        # full-year EBITDA gate. The annual AIP record owns those inputs.
        aip_pool = self.env['kprl.aip.pool'].search([
            ('year', '=', str(self.period_id.date_start.year)),
        ], limit=1) if self.period_id.date_start else self.env['kprl.aip.pool']
        self.qipm_pool = aip_pool.funded_pool if aip_pool else 0.0

        self.payout_as_pct_revenue = 0.0
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