from odoo import models, fields, api


class Territory(models.Model):
    _name = 'kprl.territory'
    _description = 'Sales Territory'
    _order = 'name'

    name = fields.Char(string='Territory Name', required=True)
    code = fields.Char(string='Code')
    rsm_id = fields.Many2one('kprl.employee', string='RSM',
                             domain=[('sales_role', '=', 'rsm')])
    rsm_target = fields.Float(string='RSM Target', digits='Product Price')
    team_target = fields.Float(string='Team Target', digits='Product Price')
    source = fields.Char(string='Source')
    effective_target = fields.Float(string='Effective Target', digits='Product Price')
    achieve_pct = fields.Float(string='Achievement (%)', digits=(5, 2),
                               compute='_compute_achieve_pct', store=True)
    is_active = fields.Boolean(string='Active', default=True)

    @api.depends('effective_target', 'rsm_target', 'team_target')
    def _compute_achieve_pct(self):
        for rec in self:
            base = rec.effective_target or rec.rsm_target or rec.team_target or 1.0
            rec.achieve_pct = 0.0
