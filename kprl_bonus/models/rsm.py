from odoo import models, fields, api


class Rsm(models.Model):
    _name = 'kprl.rsm'
    _description = 'Regional Sales Manager'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('kprl.employee', string='RSM',
                                  domain=[('sales_role', '=', 'rsm')],
                                  required=True)
    territory_ids = fields.One2many('kprl.territory', 'rsm_id', string='Territories')
    total_target = fields.Float(string='Total Target', digits='Product Price',
                                compute='_compute_total_target', store=True)
    is_active = fields.Boolean(string='Active', default=True)

    @api.depends('territory_ids.rsm_target')
    def _compute_total_target(self):
        for rec in self:
            rec.total_target = sum(
                t.rsm_target for t in rec.territory_ids if t.rsm_target
            )
