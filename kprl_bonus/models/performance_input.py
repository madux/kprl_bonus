from odoo import models, fields, api


class PerformanceInput(models.Model):
    _name = 'kprl.performance.input'
    _description = 'Employee Performance Input'
    _rec_name = 'employee_id'

    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    employee_id = fields.Many2one('kprl.employee', string='Employee',
                                  required=True)
    department_id = fields.Many2one(related='employee_id.department_id',
                                    string='Department', store=True)

    appraisal_score = fields.Float(string='Appraisal Score', digits=(5, 2))
    retain_score = fields.Float(string='Retain Score', digits=(5, 2))
    own_target = fields.Float(string='Own Target', digits='Product Price')
    own_sales = fields.Float(string='Own Sales', digits='Product Price')
    own_revenue = fields.Float(string='Own Revenue', digits='Product Price')
    prod_pct = fields.Float(string='Productivity (%)', digits=(5, 2))
    call_pct = fields.Float(string='Call Rate (%)', digits=(5, 2))
    present_pct = fields.Float(string='Presentation (%)', digits=(5, 2))
    team_pct = fields.Float(string='Team (%)', digits=(5, 2))

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('employee_period_unique', 'UNIQUE(employee_id, period_id)',
         'An employee can only have one performance record per period!'),
    ]
