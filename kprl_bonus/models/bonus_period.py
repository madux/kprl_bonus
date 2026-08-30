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
    revenue_target = fields.Float(string='Quaterly Revenue Target', digits='Product Price')
    net_rev_target = fields.Float(string='Net Revenue Target', digits='Product Price')
    ebitda_margin = fields.Float(string='EBITDA Margin (%)', digits=(5, 2))
    company_kpi = fields.Float(string='Company KPI Score', digits=(5, 4))
    description = fields.Text(string='Notes')
    sla_results_date = fields.Date(string='SLA Results Date')
    sla_payout_date = fields.Date(string='SLA Payout Date')

    parameter_ids = fields.One2many('kprl.bonus.parameter', 'period_id', string='Bonus Parameters')
    engine_ids = fields.One2many('kprl.bonus.engine', 'period_id', string='Bonus Engine Runs')
    performance_ids = fields.One2many('kprl.performance.input', 'period_id', string='Performance Inputs')
    payout_ids = fields.One2many('kprl.bonus.payout', 'period_id', string='Payout Lines')
    product_pool_ids = fields.One2many('kprl.product.pool', 'period_id', string='Product Pool')
    territory_payout_ids = fields.One2many('kprl.territory.payout', 'period_id', string='Territory Payouts')
    sales_engine_ids = fields.One2many('kprl.sales.engine', 'period_id', string='Sales Engine Runs')
    
    # National sales targets and actuals for sales commission calculations
    national_sales_target = fields.Float(string='National Quarterly Sales Target', digits='Product Price')
    national_retrieval_target = fields.Float(string='National Quarterly Retrieval Target', digits='Product Price')
    national_actual_sales = fields.Float(string='National Actual Sales', digits='Product Price',
                                        compute='_compute_national_actuals', store=True)
    national_actual_retrievals = fields.Float(string='National Actual Retrievals', digits='Product Price',
                                             compute='_compute_national_actuals', store=True)

    sla_status = fields.Char(string='SLA Status', compute='_compute_sla_status')

    @api.depends('sla_results_date', 'state')
    def _compute_sla_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == 'closed':
                rec.sla_status = 'COMPLETED'
            elif rec.sla_results_date and today > rec.sla_results_date:
                rec.sla_status = 'OVERDUE'
            else:
                rec.sla_status = 'ON TRACK'

    @api.depends('performance_ids.own_sales', 'performance_ids.own_retrievals')
    def _compute_national_actuals(self):
        for rec in self:
            # Sum of all sales staff's own sales and retrievals
            sales_staff_perfs = rec.performance_ids.filtered(
                lambda p: p.employee_id.is_sales and p.employee_id.sales_role != 'none'
            )
            rec.national_actual_sales = sum(p.own_sales for p in sales_staff_perfs)
            rec.national_actual_retrievals = sum(p.own_retrievals for p in sales_staff_perfs)

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Period name must be unique!'),
    ]

    def action_activate(self):
        self.state = 'active'

    def action_close(self):
        self.state = 'closed'

    def action_draft(self):
        self.state = 'draft'