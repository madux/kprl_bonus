from odoo import models, fields, api


class TerritoryPayout(models.Model):
    _name = 'kprl.territory.payout'
    _description = 'Territory Payout'
    _rec_name = 'territory_id'

    territory_id = fields.Many2one('kprl.territory', string='Territory',
                                   required=True)
    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    effective_target = fields.Float(string='Effective Target',
                                    digits='Product Price')
    achievement_pct = fields.Float(string='Achievement (%)', digits=(5, 2))
    commission_payable = fields.Float(string='Commission Payable',
                                      digits='Product Price')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ], string='Status', default='draft')

    _sql_constraints = [
        ('territory_period_unique', 'UNIQUE(territory_id, period_id)',
         'A territory can only have one payout per period!'),
    ]
