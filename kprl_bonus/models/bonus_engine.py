from odoo import models, fields, api
from datetime import date


class BonusEngine(models.Model):
    _name = 'kprl.bonus.engine'
    _description = 'Bonus Engine Run'
    _rec_name = 'period_id'
    _order = 'period_id desc, create_date desc'

    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('finalized', 'Finalized'),
    ], string='Status', default='draft', required=True)

    quarterly_revenue = fields.Float(string='Quarterly Revenue',
                                     digits='Product Price')
    net_revenue = fields.Float(string='Net Revenue', digits='Product Price')
    pool_contribution = fields.Float(string='Pool Contribution',
                                     digits='Product Price')

    gate_status = fields.Selection([
        ('closed', 'Closed (< 18%)'),
        ('partial', 'Partial (18%-22%)'),
        ('full', 'Full (>= 22%)'),
    ], string='Profitability Gate', compute='_compute_gate_status', store=True)
    ebitda_margin = fields.Float(string='EBITDA Margin (%)', digits=(5, 2))
    gate_factor = fields.Float(string='Gate Factor', digits=(5, 4),
                               compute='_compute_gate_factor', store=True)

    gmp_status = fields.Selection([
        ('clean', 'Clean'),
        ('non_compliant', 'Non-Compliant'),
    ], string='GMP Status', default='clean')
    gmp_factor = fields.Float(string='GMP Factor', digits=(5, 4), default=1.0)

    company_kpi_score = fields.Float(string='Company KPI Score', digits=(5, 4))
    effective_pool = fields.Float(string='Effective Bonus Pool',
                                  digits='Product Price')
    proration_factor = fields.Float(string='Proration Factor', digits=(5, 4),
                                    default=1.0)
    total_payout = fields.Float(string='Total Quarterly Payout',
                                digits='Product Price')
    ops_payout = fields.Float(string='Ops Payout', digits='Product Price')
    sales_commission = fields.Float(string='Sales Commission',
                                    digits='Product Price')
    payout_as_pct_revenue = fields.Float(string='Payout as % of Revenue',
                                         digits=(5, 4))
    pool_util_vs_ebitda_cap = fields.Float(string='Pool Util. vs EBITDA Cap',
                                           digits=(5, 4))
    headcount = fields.Integer(string='Headcount Eligible',
                               compute='_compute_headcount', store=True)
    aip_pool = fields.Float(string='AIP Pool (Annual)', digits='Product Price')

    parameter_id = fields.Many2one(related='period_id.parameter_ids',
                                   string='Active Parameters')

    computed_on = fields.Datetime(string='Computed On')
    computed_by = fields.Many2one('res.users', string='Computed By')
    notes = fields.Text(string='Notes')

    @api.depends('ebitda_margin')
    def _compute_gate_status(self):
        for rec in self:
            if rec.ebitda_margin >= 22.0:
                rec.gate_status = 'full'
            elif rec.ebitda_margin >= 18.0:
                rec.gate_status = 'partial'
            elif rec.ebitda_margin > 0:
                rec.gate_status = 'closed'
            else:
                rec.gate_status = 'closed'

    @api.depends('gate_status')
    def _compute_gate_factor(self):
        for rec in self:
            params = rec.period_id.parameter_ids
            if rec.gate_status == 'full':
                rec.gate_factor = params.max_pool_rate if params else 0.02
            elif rec.gate_status == 'partial':
                rec.gate_factor = params.partial_gate_floor if params else 0.0025
            else:
                rec.gate_factor = params.min_pool_rate if params else 0.0

    @api.depends('period_id')
    def _compute_headcount(self):
        for rec in self:
            if rec.period_id:
                rec.headcount = self.env['kprl.bonus.payout'].search_count([
                    ('period_id', '=', rec.period_id.id),
                ])
            else:
                rec.headcount = 0

    def action_compute(self):
        self.ensure_one()
        params = self.period_id.parameter_ids
        self.quarterly_revenue = self.period_id.revenue_target
        self.ebitda_margin = self.period_id.ebitda_margin

        effective_rate = self.gate_factor * self.gmp_factor
        self.effective_pool = self.quarterly_revenue * effective_rate
        self.pool_contribution = self.effective_pool

        payouts = self.env['kprl.bonus.payout'].search([
            ('period_id', '=', self.period_id.id),
        ])
        self.ops_payout = sum(p.gross_payable for p in payouts)
        self.sales_commission = self.ops_payout * 0.0
        self.total_payout = self.ops_payout + self.sales_commission
        self.aip_pool = self.quarterly_revenue * (params.aip_annual_rate or 0.002)

        if self.quarterly_revenue:
            self.payout_as_pct_revenue = (self.total_payout / self.quarterly_revenue)
        self.pool_util_vs_ebitda_cap = self.payout_as_pct_revenue

        self.state = 'computed'
        self.computed_on = fields.Datetime.now()
        self.computed_by = self.env.user

    def action_finalize(self):
        self.state = 'finalized'

    def action_reset(self):
        self.state = 'draft'
