from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BonusPayout(models.Model):
    _name = 'kprl.bonus.payout'
    _description = 'Employee Bonus Payout'
    _rec_name = 'employee_id'
    _order = 'employee_id'

    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    employee_id = fields.Many2one('kprl.employee', string='Employee',
                                  required=True)
    department_id = fields.Many2one('kprl.department', related='employee_id.department_id',
                                    string='Department', store=True)
    grade_id = fields.Many2one('kprl.grade', related='employee_id.grade_id',
                               string='Grade', store=True)
    subpool_id = fields.Many2one('kprl.subpool', related='employee_id.subpool_id',
                                 string='Sub-Pool', store=True)

    base_eligible = fields.Float(string='Base Eligible (₦)', digits='Product Price', compute="compute_base_eligible", help="rec.total_points * rec.value_point")
    dept_kpi_mult = fields.Float(string='Dept KPI Multiplier', digits=(5, 4),
                                 default=1.0)
    appraisal_mult = fields.Float(string='Appraisal Multiplier', digits=(5, 4),
                                  default=0.0, compute="compute_appraisal_mult")
    behavioural_mult = fields.Float(string='Behavioural Multiplier', digits=(5, 4),
                                    default=1.0)
    period_end = fields.Date(related='period_id.date_end', store=True, index=True)
    
    @api.depends('employee_id', 'appraisal_score')
    def compute_appraisal_mult(self):
        for rec in self:
            if not rec.employee_id:
                rec.appraisal_mult = 0.0
                continue
            raw = rec.appraisal_score or 0.0
            score = raw / 100.0
            if score < 0.65:
                rec.appraisal_mult = 0.0
            elif score < 0.75:
                rec.appraisal_mult = 0.6 + (score - 0.65) * 0.15
            elif score < 0.90:
                rec.appraisal_mult = 0.75 + (score - 0.75) * 1.0
            elif score < 1.10:
                rec.appraisal_mult = 0.90 + (score - 0.90) * 2.0
            else:
                rec.appraisal_mult = 1.10

    exception_premium = fields.Float(string='Exception Premium (₦)',
                                     digits='Product Price')
    proration_factor = fields.Float(string='Proration', digits=(5, 4), default=1.0)
    tenure_mult = fields.Float(string='Tenure Multiplier', digits=(5, 4), default=1.0, help="(rec.employee_id.tenure_years / 3) * 0.03",)
                            #    compute='_compute_tenure_mult',)
    gmp_factor = fields.Float(string='GMP Factor', digits=(5, 4), default=1.0)
    malus_amount = fields.Float(string='Malus (₦)', digits='Product Price')

    gross_payable = fields.Float(string='Gross Payable (₦)', digits='Product Price',
                                 compute='_compute_gross_payable', store=True)
    payable = fields.Float(string='Payable (₦)', digits='Product Price',
                                 compute='_compute_payable', store=True)
    
    tenure_enhance = fields.Float(string='Tenure EHN',
                                 compute='_compute_tenure_enhance', store=True)
    
    tenure_years = fields.Float(string='Tenure years', store=True, related='employee_id.tenure_years', compute='_compute_tenure_mult')
    deferral_rate = fields.Float(string='Deferral Rate (%)', digits=(5, 4), compute='_compute_deferred_rate', default=0.0)
    # appraisal_score = fields.Float(
    #     string='Appraisal Score (%)', digits=(5, 4),
    #     compute='_compute_appraisal_score', store=True,
    # )

       # change appraisal_score BACK to a regular stored field:
    appraisal_score = fields.Float(string='Appraisal Score (%)', digits=(5, 4))

    adjusted_amount = fields.Float(string='Adjusted (₦)', digits=(5, 4), compute='_compute_adjusted')
    behaviour_05 = fields.Float(string='Behavioure /25', digits=(5, 4), default=23)
    appraisal_max = fields.Float(string='Appraisal Max', default=1.0)
    behaviour_max = fields.Float(string='Behaviour Max', default=25.0)
    
    deferred_amount = fields.Float(string='Deferred Amount (₦)',
                                   digits='Product Price', help="rec.final_floor * (rec.deferral_rate / 100.0)",
                                   compute='_compute_deferred', store=True)
    net_immediate = fields.Float(string='Net Immediate (₦)',
                                 digits='Product Price',
                                 compute='_compute_deferred', store=True, help="rec.final_floor - rec.deferred_amount")
    quarterly_amount = fields.Float(string='Quarterly Payout (₦)',
                                 digits='Product Price', help="rec.gross_payable - rec.deferred_amount",
                                 compute='_compute_deferred', store=True)
    final_floor = fields.Float(string='Final + Floor (₦)',
                                 digits='Product Price',
                                 compute='_compute_tenure_enhance', store=True)
    floor_check = fields.Boolean(string='Floor Check Pass', default=True)
    cap_check = fields.Boolean(string='Cap Check Pass', default=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ], string='Status', default='draft')

    _sql_constraints = [
        ('employee_period_unique', 'UNIQUE(employee_id, period_id)',
         'An employee can only have one payout per period!'),
    ]
    value_point = fields.Float(string='Value Point (₦)',
                                   digits='Product Price',
                                   compute='_compute_value_point', store=True)

    total_points = fields.Float(string='Total Point (₦)',
                                   digits='Product Price',
                                   compute='_compute_total_point', store=True)
    
    @api.depends(
        'value_point',
        'total_points'
    )
    def compute_base_eligible(self):
        for rec in self:
            vl_point = rec.grade_id.total_points 
            rec.base_eligible = vl_point * rec.value_point

    @api.depends(
        'employee_id.grade_id',
        'grade_id'
    )
    def _compute_total_point(self):
        for rec in self:
            rec.total_points = rec.grade_id.total_points

    @api.depends(
        'tenure_mult',
        'payable'
    )
    @api.depends('payable', 'tenure_mult')
    def _compute_tenure_enhance(self):
        for rec in self:
            payable_tenured = rec.payable * rec.tenure_mult
            # Floor Sec6 Step16: Hygiene 20k (B47) / Junior 30k (B48)
            grade_name = (rec.employee_id.grade_id.name or '').upper()
            is_hygiene = 'HYGIENE' in grade_name
            is_junior = 'JUNIOR' in grade_name
            floor = 0.0
            if is_hygiene:
                floor = 20000.0
                if rec.period_id.parameter_ids:
                    floor = rec.period_id.parameter_ids[0].minimum_floor or 20000.0
            elif is_junior:
                floor = 30000.0
                if rec.period_id.parameter_ids:
                    floor = rec.period_id.parameter_ids[0].maximum_cap or 30000.0
            rec.tenure_enhance = payable_tenured
            rec.final_floor = max(payable_tenured, floor)

    @api.depends('gross_payable', 'proration_factor')
    def _compute_payable(self):
        for rec in self:
            rec.payable = rec.gross_payable * rec.proration_factor

    @api.depends('base_eligible', 'dept_kpi_mult', 'appraisal_mult', 'behavioural_mult', 'exception_premium', 'malus_amount')
    def _compute_gross_payable(self):
        for rec in self:
            # Spec Sec6 Step12: Adjusted = Base * Dept * Apprais * Behav
            # Behav 23/25 -> 1.084, so we derive it if empty
            if rec.behaviour_05:
                behav = 0.80 + (rec.behaviour_05 / 25.0) * 0.20
            else:
                behav = rec.behavioural_mult or 1.0
            adjusted = rec.base_eligible * rec.dept_kpi_mult * rec.appraisal_mult * behav
            rec.adjusted_amount = adjusted
            # Spec Step13: Exception = 10% of Adjusted if exceptional
            exc = adjusted * 0.10 if rec.appraisal_mult >= 1.10 else 0.0
            if rec.exception_premium and rec.exception_premium > exc:
                exc = rec.exception_premium
            rec.gross_payable = max(adjusted + exc - (rec.malus_amount or 0.0), 0.0)
    @api.depends('period_id', 'employee_id', 'gross_payable', 'deferral_rate')
    def _compute_deferred(self):
        for rec in self:
            rec.deferred_amount = rec.final_floor * (rec.deferral_rate / 100.0)
            rec.net_immediate = rec.final_floor - rec.deferred_amount
            rec.quarterly_amount = rec.gross_payable - rec.deferred_amount

    @api.depends('employee_id', 'employee_id.grade_id.subpool_id')
    def _compute_deferred_rate(self):
        for rec in self:
            employee_pool_rate = 20 if rec.employee_id.grade_id.subpool_id.code == 'SENMGT' else 0.0
            rec.deferral_rate = employee_pool_rate 

    @api.depends('behavioural_mult', 'appraisal_mult', 'dept_kpi_mult', 'base_eligible')
    def _compute_adjusted(self):
        for rec in self:
            rec.adjusted_amount = rec.behavioural_mult * rec.appraisal_mult * rec.dept_kpi_mult * rec.base_eligible

    def action_approve(self):
        self.state = 'approved'

    def action_paid(self):
        self.state = 'paid'

    @api.onchange('employee_id', 'period_id')
    def _onchange_fetch_appraisal(self):
        if self.employee_id and self.period_id:
            perf = self.env['kprl.performance.input'].search([
                ('employee_id', '=', self.employee_id.id),
                ('period_id', '=', self.period_id.id),
            ], limit=1)
            if perf:
                self.appraisal_score = perf.appraisal_score

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('appraisal_score') and vals.get('employee_id') and vals.get('period_id'):
                perf = self.env['kprl.performance.input'].search([
                    ('employee_id', '=', vals['employee_id']),
                    ('period_id', '=', vals['period_id']),
                ], limit=1)
                if perf:
                    vals['appraisal_score'] = perf.appraisal_score
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'employee_id' in vals or 'period_id' in vals:
            for rec in self:
                if rec.employee_id and rec.period_id:
                    perf = self.env['kprl.performance.input'].search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('period_id', '=', rec.period_id.id),
                    ], limit=1)
                    if perf:
                        rec.appraisal_score = perf.appraisal_score
        return res
    governance_event_ids = fields.Many2many(
    'kprl.governance.event',
    compute='_compute_governance_events',
    string='Governance Events'
)

    total_governance_deduction = fields.Float(
        string='Total Governance Deduction',
        compute='_compute_governance_events',
        store=False
    )

    @api.depends('employee_id', 'period_id')
    def _compute_governance_events(self):
        for rec in self:
            if rec.employee_id and rec.period_id:
                events = self.env['kprl.governance.event'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('period_id', '=', rec.period_id.id),
                    ('trigger_type', 'in', ('malus', 'clawback')),
                ])
                rec.governance_event_ids = events
                rec.total_governance_deduction = sum(
                    events.mapped('malus_amount') + events.mapped('clawback_amount')
                )
            else:
                rec.governance_event_ids = self.env['kprl.governance.event']
                rec.total_governance_deduction = 0.0