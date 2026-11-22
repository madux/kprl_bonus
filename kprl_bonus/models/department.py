from odoo import models, fields, api


class Department(models.Model):
    _name = 'kprl.department'
    _description = 'Department'
    _order = 'name'

    name = fields.Char(string='Department Name', required=True)
    code = fields.Char(string='Code')
    manager_id = fields.Many2one('kprl.employee', string='Department Manager')
    kpi_multiplier = fields.Float(string='Default KPI Multiplier', digits=(5, 4),
                                  default=1.0)
    gmp_status = fields.Selection([
        ('clean', 'Clean'),
        ('minor', 'Minor'),
        ('major', 'Major'),
        ('critical', 'Critical'),
    ], string='Standing GMP Status', default='clean',
        help='Workbook REFERENCE TABLES col G: standing status copied onto new per-period Dept KPI rows.')
    gmp_self_reported = fields.Boolean(string='GMP Self-Reported', default=False,
        help='Workbook REFERENCE TABLES col H: halves the GMP penalty when set.')
    is_active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Department name must be unique!'),
    ]
