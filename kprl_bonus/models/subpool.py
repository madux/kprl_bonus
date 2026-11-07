from odoo import models, fields, api


class Subpool(models.Model):
    _name = 'kprl.subpool'
    _description = 'Bonus Sub-Pool'
    _order = 'name'

    name = fields.Char(string='Sub-Pool Name', required=True)
    code = fields.Char(string='Code')
    pool_share_pct = fields.Float(string='Default Pool Share (%)', digits=(5, 2))
    min_share_pct = fields.Float(string='Min Share (%)', digits=(5, 2), default=0.0)
    max_share_pct = fields.Float(string='Max Share (%)', digits=(5, 2), default=100.0)
    is_active = fields.Boolean(string='Active', default=True)
    note = fields.Text(string='Description')
