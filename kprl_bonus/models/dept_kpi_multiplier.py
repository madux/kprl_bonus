from odoo import models, fields, api


class DeptKpiMultiplier(models.Model):
    _name = 'kprl.dept.kpi.multiplier'
    _description = 'Department KPI Multiplier'
    _rec_name = 'department_id'

    department_id = fields.Many2one('kprl.department', string='Department',
                                    required=True)
    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    kpi_score = fields.Float(string='KPI Score', digits=(5, 4))
    kpi_score_max = fields.Float(string='KPI Score Max', default=100.0)

    multiplier = fields.Float(string='KPI Multiplier', digits=(5, 4), default=1.0)
    weight = fields.Float(string='Weight (%)', digits=(5, 2), default=100.0)
    gmp_status = fields.Selection([
        ('clean', 'Clean'),
        ('non_compliant', 'Non-Compliant'),
    ], string='GMP Status', default='clean')
    self_flag = fields.Boolean(string='Self Flag')
    def_factor = fields.Float(string='Definition Factor', digits=(5, 4), default=1.0)
    notes = fields.Text(string='Notes')
    period_end = fields.Date(related='period_id.date_end', store=True, index=True)

    _sql_constraints = [
        ('dept_period_unique', 'UNIQUE(department_id, period_id)',
         'A department can only have one KPI multiplier per period!'),
    ]
