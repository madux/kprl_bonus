from odoo import models, fields, api


class Grade(models.Model):
    _name = 'kprl.grade'
    _description = 'Employee Grade'
    _order = 'sequence'

    name = fields.Char(string='Grade Name', required=True)
    code = fields.Char(string='Grade Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    yp_points = fields.Float(string='Your Points (YP)', digits=(5, 1),
                             help='Base grade points for bonus calculation')
    diff_points = fields.Float(string='Diff Points', digits=(5, 1),
                               help='Differentiation points adjustment')
    skill_premium = fields.Float(string='Skill Premium', digits=(5, 1),
                                 help='Additional points for specialized skills')
    total_points = fields.Float(string='Total Points', digits=(5, 1),
                                compute='_compute_total_points', store=True)
    token_rate = fields.Float(string='Token Rate (₦/pt)', digits='Product Price')
    deferral_rate = fields.Float(string='Deferral Rate (%)', digits=(5, 2))
    subpool_id = fields.Many2one('kprl.subpool', string='Sub-Pool')
    aip_eligible = fields.Boolean(string='AIP Eligible', default=False)
    governance_note = fields.Text(string='Governance Notes')

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Grade code must be unique!'),
    ]

    @api.depends('yp_points', 'diff_points', 'skill_premium')
    def _compute_total_points(self):
        for rec in self:
            rec.total_points = rec.yp_points + rec.diff_points + rec.skill_premium
