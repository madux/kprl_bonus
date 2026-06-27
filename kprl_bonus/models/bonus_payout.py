from odoo import models, fields, api


class BonusPayout(models.Model):
    _name = 'kprl.bonus.payout'
    _description = 'Employee Bonus Payout'
    _rec_name = 'employee_id'
    _order = 'employee_id'

    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    employee_id = fields.Many2one('kprl.employee', string='Employee',
                                  required=True)
    department_id = fields.Many2one(related='employee_id.department_id',
                                    string='Department', store=True)
    grade_id = fields.Many2one(related='employee_id.grade_id',
                               string='Grade', store=True)
    subpool_id = fields.Many2one(related='employee_id.subpool_id',
                                 string='Sub-Pool', store=True)

    base_eligible = fields.Float(string='Base Eligible (₦)', digits='Product Price')
    dept_kpi_mult = fields.Float(string='Dept KPI Multiplier', digits=(5, 4),
                                 default=1.0)
    appraisal_mult = fields.Float(string='Appraisal Multiplier', digits=(5, 4),
                                  default=1.0)
    behavioural_mult = fields.Float(string='Behavioural Multiplier', digits=(5, 4),
                                    default=1.0)
    exception_premium = fields.Float(string='Exception Premium (₦)',
                                     digits='Product Price')
    proration_factor = fields.Float(string='Proration', digits=(5, 4), default=1.0)
    tenure_mult = fields.Float(string='Tenure Multiplier', digits=(5, 4), default=1.0)
    gmp_factor = fields.Float(string='GMP Factor', digits=(5, 4), default=1.0)
    malus_amount = fields.Float(string='Malus (₦)', digits='Product Price')

    gross_payable = fields.Float(string='Gross Payable (₦)', digits='Product Price',
                                 compute='_compute_gross_payable', store=True)
    deferral_rate = fields.Float(string='Deferral Rate (%)', digits=(5, 4))
    deferred_amount = fields.Float(string='Deferred Amount (₦)',
                                   digits='Product Price',
                                   compute='_compute_deferred', store=True)
    net_immediate = fields.Float(string='Net Immediate (₦)',
                                 digits='Product Price',
                                 compute='_compute_deferred', store=True)
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

    @api.depends('gross_payable', 'deferral_rate')
    def _compute_deferred(self):
        for rec in self:
            rec.deferred_amount = rec.gross_payable * (rec.deferral_rate / 100.0)
            rec.net_immediate = rec.gross_payable - rec.deferred_amount

    def action_approve(self):
        self.state = 'approved'

    def action_paid(self):
        self.state = 'paid'
