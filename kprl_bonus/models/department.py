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
    is_active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Department name must be unique!'),
    ]
