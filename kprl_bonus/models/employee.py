from odoo import models, fields, api
from datetime import date


class Employee(models.Model):
    _name = 'kprl.employee'
    _description = 'Employee Master'
    _order = 'employee_id'
    _rec_name = 'name'

    name = fields.Char(string='Employee Name', required=True)
    employee_id = fields.Char(string='Employee ID', required=True)
    department_id = fields.Many2one('kprl.department', string='Department')
    grade_id = fields.Many2one('kprl.grade', string='Grade')
    job_title = fields.Char(string='Job Title')
    subpool_id = fields.Many2one('kprl.subpool', string='Sub-Pool')
    date_hired = fields.Date(string='Date Hired')
    tenure_years = fields.Float(string='Tenure (Years)', compute='_compute_tenure',
                                store=True)
    manager_id = fields.Many2one('kprl.employee', string='Reporting Manager')
    status = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('inactive', 'Inactive'),
        ('draft', 'Draft'),
    ], string='Status', default='active', required=True)
    is_sales = fields.Boolean(string='Sales Role', default=False)
    sales_role = fields.Selection([
        ('gm', 'GM'),
        ('nsm', 'NSM'),
        ('headtech', 'Head Tech'),
        ('rsm', 'RSM'),
        ('asm', 'ASM'),
        ('rsm_asm', 'RSM + ASM'),
        ('none', 'None'),
    ], string='Sales Role', default='none')
    territory_id = fields.Many2one('kprl.territory', string='Territory')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    is_active = fields.Boolean(string='Active', default=True)
    image = fields.Binary(string='Photo', attachment=True)

    _sql_constraints = [
        ('employee_id_unique', 'UNIQUE(employee_id)', 'Employee ID must be unique!'),
    ]

    @api.depends('date_hired')
    def _compute_tenure(self):
        today = date.today()
        for rec in self:
            if rec.date_hired:
                delta = today - rec.date_hired
                rec.tenure_years = round(delta.days / 365.25, 2)
            else:
                rec.tenure_years = 0.0

    def open_simulation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'website_page',
            'params': {'url': '/kprl/simulate/%d' % self.id},
        }
