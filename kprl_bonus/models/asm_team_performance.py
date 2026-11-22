from odoo import fields, models


class AsmTeamPerformance(models.TransientModel):
    _name = 'kprl.asm.team.performance'
    _description = 'Regional ASM Sales and Retrieval'
    _order = 'employee_id'

    period_id = fields.Many2one(
        'kprl.bonus.period',
        string='Quarter',
        readonly=True,
    )
    manager_id = fields.Many2one(
        'kprl.employee',
        string='Regional RSM',
        readonly=True,
    )
    asm_id = fields.Many2one(
        'kprl.employee',
        string='Reporting ASM',
        readonly=True,
    )
    employee_id = fields.Many2one(
        'kprl.employee',
        string='Employee',
        readonly=True,
    )
    asm_grouping = fields.Char(
        string='ASM Grouping',
        readonly=True,
    )
    department_id = fields.Many2one(
        'kprl.department',
        string='Department',
        readonly=True,
    )
    performance_input_found = fields.Boolean(
        string='Quarter Input Available',
        readonly=True,
    )
    own_target = fields.Float(
        string='Quarterly Target',
        digits='Product Price',
        readonly=True,
    )
    own_sales = fields.Float(
        string='Sales Generated',
        digits='Product Price',
        readonly=True,
    )
    own_retrievals = fields.Float(
        string='Retrievals Generated',
        digits='Product Price',
        readonly=True,
    )
