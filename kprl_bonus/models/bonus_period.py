from odoo import models, fields, api


class BonusPeriod(models.Model):
    _name = 'kprl.bonus.period'
    _description = 'Bonus Period'
    _order = 'date_start desc'

    name = fields.Char(string='Period Name', required=True)
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', required=True)
    revenue_target = fields.Float(string='Revenue Target', digits='Product Price')
    net_rev_target = fields.Float(string='Net Revenue Target', digits='Product Price')
    ebitda_margin = fields.Float(string='EBITDA Margin (%)', digits=(5, 2))
    company_kpi = fields.Float(string='Company KPI Score', digits=(5, 4))
    description = fields.Text(string='Notes')

    parameter_ids = fields.One2many('kprl.bonus.parameter', 'period_id', string='Bonus Parameters')
    engine_ids = fields.One2many('kprl.bonus.engine', 'period_id', string='Bonus Engine Runs')
    performance_ids = fields.One2many('kprl.performance.input', 'period_id', string='Performance Inputs')
    payout_ids = fields.One2many('kprl.bonus.payout', 'period_id', string='Payout Lines')
    product_pool_ids = fields.One2many('kprl.product.pool', 'period_id', string='Product Pool')
    territory_payout_ids = fields.One2many('kprl.territory.payout', 'period_id', string='Territory Payouts')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Period name must be unique!'),
    ]

    def action_activate(self):
        self.state = 'active'

    def action_close(self):
        self.state = 'closed'

    def action_draft(self):
        self.state = 'draft'
