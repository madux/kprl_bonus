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
#             
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
    target_source = fields.Selection([('rsm', 'RSM Target'), ('team', 'Team Target')], string='Effective Target Source', default='rsm')
    effective_target = fields.Float(string='Effective Target', digits='Product Price', compute='_compute_effective_target', store=True, readonly=False)
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

    @api.depends('rsm_target', 'team_target', 'target_source')
    def _compute_effective_target(self):
        for rec in self:
            if rec.target_source == 'team':
                rec.effective_target = rec.team_target or 0.0
            else:
                rec.effective_target = rec.rsm_target or rec.team_target or 0.0

    @api.depends('effective_target', 'rsm_target', 'team_target')
    def _compute_achieve_pct(self):
        """DASHBOARD N: team sales ÷ effective target, from the latest
        territory-engine lines (falls back to territory payouts)."""
        Line = self.env['kprl.territory.engine.lines']
        for rec in self:
            base = rec.effective_target or rec.rsm_target or rec.team_target or 0.0
            attained = 0.0
            latest_line = Line.search([('territory_id', '=', rec.id)], order='id desc', limit=1)
            if latest_line and latest_line.territory_engine_id:
                peers = latest_line.territory_engine_id.kprl_employee_engine_line_ids.filtered(
                    lambda l: l.territory_id == rec)
                attained = sum(peers.mapped('own_sales'))
                if not base:
                    engine = latest_line.territory_engine_id
                    base = sum(engine.kprl_employee_engine_line_ids.filtered(
                        lambda l: l.territory_id == rec).mapped('own_target'))
            elif rec.payout_ids:
                attained = sum(rec.payout_ids.mapped('commission_payable'))
                if not base:
                    base = rec.payout_ids[-1].effective_target or 0.0
            rec.achieve_pct = (attained / base * 100.0) if base else 0.0

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