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
    
    @api.depends('employee_id', 'appraisal_score')
    def compute_appraisal_mult(self):
        """
        Calculate performance factor based on appraisal score.

        Args:
            employee: Employee record or any truthy value.
            appraisal_score (float): Appraisal score as a decimal (e.g. 0.82 for 82%).

        Returns:
            float or None
        """
        for rec in self:
            employee = rec.employee_id
            appraisal_score = rec.appraisal_score
            result = 0
            if not employee:
                result = None

            if appraisal_score < 0.65:
                result = 0.0

            elif appraisal_score in range (60, 75):
                result = 0.6 + (appraisal_score - 0.65) * 0.15

            elif appraisal_score >= 0.75 and appraisal_score < 0.90:
                result = 0.75 + (appraisal_score - 0.75) * 1.0
            elif appraisal_score >= 0.90 and appraisal_score < 1.1:
                result = 0.90 + (appraisal_score - 0.90) * 2.0

            elif appraisal_score >= 1.1: 
                result = 1.10
            rec.appraisal_mult = result

    exception_premium = fields.Float(string='Exception Premium (₦)',
                                     digits='Product Price')
    proration_factor = fields.Float(string='Proration', digits=(5, 4), default=1.0)
    tenure_mult = fields.Float(string='Tenure Multiplier', digits=(5, 4), default=1.0, help="(rec.employee_id.tenure_years / 3) * 0.03",
                               compute='_compute_tenure_mult',)
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
    appraisal_score = fields.Float(string='Appraisal Score (%)', digits=(5, 4))
    adjusted_amount = fields.Float(string='Adjusted (₦)', digits=(5, 4), compute='_compute_adjusted')
    behaviour_05 = fields.Float(string='Behavioure /25', digits=(5, 4), default=23)
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
    def _compute_tenure_enhance(self):
        for rec in self:
            rec.tenure_enhance = rec.payable * rec.tenure_mult
            rec.final_floor = rec.payable * rec.tenure_mult
    
    @api.depends(
        'employee_id.tenure_years'
    )
    def _compute_tenure_mult(self):
        for rec in self:
            rec.tenure_mult = (rec.employee_id.tenure_years / 3) * 0.03
            rec.tenure_years = rec.employee_id.tenure_years
            
    @api.depends(
        'proration_factor',
        'gross_payable'
    )
    def _compute_payable(self):
        for rec in self:
            rec.payable = rec.gross_payable * rec.proration_factor

    @api.depends(
        'employee_id.grade_id.subpool_id.code',
        'period_id',
        'period_id.engine_ids.senior_mgt_value_point',
        'period_id.engine_ids.ops_sup_value_point',
        'period_id.engine_ids.opm_value_point',
        'base_eligible',
    )
    def _compute_value_point(self):
        grade_mapping = {
            'SENMGT': 'senior_mgt_value_point',
            'OPM': 'opm_value_point',
            'OPSSUP': 'ops_sup_value_point',
        }

        for rec in self:
            rec.value_point = 0.0

            if not rec.employee_id or not rec.period_id:
                continue

            engine = rec.period_id.engine_ids[:1]
            if not engine:
                continue
            # else:
            #     raise ValidationError()
            grade_code = rec.employee_id.grade_id.subpool_id.code # or rec.employee_id.grade_id.code or ''
            field_name = grade_mapping.get(grade_code, 'opm_value_point')

            rec.value_point = getattr(engine, field_name)

    @api.depends('base_eligible', 'dept_kpi_mult', 'appraisal_mult',
                 'behavioural_mult', 'exception_premium', 'proration_factor',
                 'tenure_mult', 'gmp_factor', 'malus_amount')
    def _compute_gross_payable(self):
        for rec in self:
            gross = (rec.base_eligible *
                     rec.dept_kpi_mult *
                     rec.appraisal_mult *
                     rec.behavioural_mult *
                     rec.proration_factor *
                     rec.tenure_mult *
                     rec.gmp_factor)
            gross += rec.exception_premium
            gross -= rec.malus_amount
            rec.gross_payable = max(gross, 0.0)

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
