# from odoo import models, fields, api


# class Territory(models.Model):
#     _name = 'kprl.territory'
#     _description = 'Sales Territory'
#     _order = 'name'

#     name = fields.Char(string='Territory Name', required=True)
#     code = fields.Char(string='Code')
#     rsm_id = fields.Many2one('kprl.employee', string='RSM',
#                              domain=[('sales_role', '=', 'rsm')])
#     rsm_target = fields.Float(string='RSM Target', digits='Product Price')
#     team_target = fields.Float(string='Team Target', digits='Product Price')
#     source = fields.Char(string='Source')
#     effective_target = fields.Float(string='Effective Target', digits='Product Price')
#     achieve_pct = fields.Float(string='Achievement (%)', digits=(5, 2),
#                                compute='_compute_achieve_pct', store=True)
#     is_active = fields.Boolean(string='Active', default=True)

#     @api.depends('effective_target', 'rsm_target', 'team_target')
#     def _compute_achieve_pct(self):
#         for rec in self:
#             base = rec.effective_target or rec.rsm_target or rec.team_target or 1.0
#             rec.achieve_pct = 0.0

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

    # ── New fields for dashboard ───────────────────────────────
    payout_ids = fields.One2many('kprl.territory.payout', 'territory_id',
                                 string='Payouts')
    payout_count = fields.Integer(string='Payout Records',
                                  compute='_compute_payout_stats')
    total_commission = fields.Float(string='Total Commission',
                                    compute='_compute_payout_stats',
                                    digits='Product Price')
    total_target = fields.Float(string='Total Target',
                                compute='_compute_payout_stats',
                                digits='Product Price')
    latest_achievement = fields.Float(string='Latest Achievement',
                                      compute='_compute_payout_stats',
                                      digits=(5, 2))
    gate_status = fields.Char(string='Gate Status',
                              compute='_compute_payout_stats')
    retrieval_rate = fields.Float(string='Retrieval Rate',
                                  compute='_compute_payout_stats',
                                  digits=(5, 2))
    latest_period = fields.Char(string='Latest Period',
                                compute='_compute_payout_stats')

    @api.depends('effective_target', 'rsm_target', 'team_target')
    def _compute_achieve_pct(self):
        for rec in self:
            base = rec.effective_target or rec.rsm_target or rec.team_target or 1.0
            rec.achieve_pct = 0.0

    @api.depends('payout_ids', 'payout_ids.commission_payable',
                 'payout_ids.achievement_pct', 'payout_ids.effective_target')
    def _compute_payout_stats(self):
        for rec in self:
            payouts = rec.payout_ids
            rec.payout_count = len(payouts)
            rec.total_commission = sum(p.commission_payable for p in payouts)
            rec.total_target = sum(p.effective_target for p in payouts)
            if payouts:
                latest = payouts[-1]
                rec.latest_achievement = latest.achievement_pct
                rec.gate_status = 'PASS' if latest.achievement_pct >= 100 else 'REVIEW'
                rec.retrieval_rate = min(latest.achievement_pct, 100.0)
                rec.latest_period = latest.period_id.name if latest.period_id else '—'
            else:
                rec.latest_achievement = 0.0
                rec.gate_status = 'NO DATA'
                rec.retrieval_rate = 0.0
                rec.latest_period = '—'
    def action_view_payouts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Payouts - {self.name}',
            'res_model': 'kprl.territory.payout',
            'view_mode': 'tree,form',
            'domain': [('territory_id', '=', self.id)],
            'context': {'default_territory_id': self.id},
        }