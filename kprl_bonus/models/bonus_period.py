from odoo import models, fields, api
from odoo.exceptions import UserError


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
    # Workbook B20 source: margin is DERIVED from naira amounts, never typed.
    # Period name is the unique key (see name_unique); margin = EBITDA / revenue.
    ebitda_amount = fields.Float(
        string='Quarterly EBITDA/Profit Amount', digits='Product Price',
        help='Quarterly EBITDA/profit amount in naira. Required before any gate computation.')
    revenue_amount = fields.Float(
        string='Revenue Amount (NGN)', digits='Product Price',
        help='Actual revenue for the quarter in naira. Required before any gate computation.')
    ebitda_margin = fields.Float(
        string='EBITDA Margin (%)', digits=(5, 2),
        compute='_compute_ebitda_margin', store=True, readonly=True,
        help='Auto-computed: Quarterly EBITDA/Profit Amount / Revenue Amount * 100. Do not type a %.')
    ebitda_data_complete = fields.Boolean(
        string='EBITDA Data Complete', compute='_compute_ebitda_margin', store=True,
        help='True when revenue > 0 and EBITDA amount is set.')
    company_kpi = fields.Float(string='Company KPI Score (%)', digits=(5, 2))
    description = fields.Text(string='Notes')
    sla_results_date = fields.Date(
        string='SLA Results Date', readonly=True, copy=False,
        help='System-generated when the period is closed.')
    sla_payout_date = fields.Date(string='SLA Payout Date')

    parameter_ids = fields.One2many('kprl.bonus.parameter', 'period_id', string='Bonus Parameters')
    engine_ids = fields.One2many('kprl.bonus.engine', 'period_id', string='Bonus Engine Runs')
    performance_ids = fields.One2many('kprl.performance.input', 'period_id', string='Performance Inputs')
    payout_ids = fields.One2many('kprl.bonus.payout', 'period_id', string='Payout Lines')
    product_pool_ids = fields.One2many('kprl.product.pool', 'period_id', string='Product Pool')
    dept_kpi_ids = fields.One2many('kprl.dept.kpi.multiplier', 'period_id',
                                   string='Department KPI Multipliers')
    territory_payout_ids = fields.One2many('kprl.territory.payout', 'period_id', string='Territory Payouts')
    sales_territory_engine_ids = fields.One2many('kprl.territory.engine', 'period_id', string='Sales Engine')
    sales_territory_engine_line_ids = fields.One2many('kprl.territory.engine', 'period_id', string='Sales Engine Lines')
    
    # National sales targets and actuals for sales commission calculations
    national_sales_target = fields.Float(string='National Quarterly Sales Target', digits='Product Price')
    national_retrieval_target = fields.Float(string='National Quarterly Retrieval Target', digits='Product Price')
    national_actual_sales = fields.Float(string='National Actual Sales', digits='Product Price',
                                        compute='_compute_national_actuals', store=True)
    national_actual_retrievals = fields.Float(string='National Actual Retrievals', digits='Product Price',
                                             compute='_compute_national_actuals', store=True)

    sla_status = fields.Char(string='SLA Status', compute='_compute_sla_status')

    @api.depends('ebitda_amount', 'revenue_amount')
    def _compute_ebitda_margin(self):
        for rec in self:
            rev = rec.revenue_amount or 0.0
            has_amount = rev > 0 and rec.ebitda_amount is not None and rec.ebitda_amount is not False
            if has_amount:
                rec.ebitda_margin = (rec.ebitda_amount / rev) * 100.0
                rec.ebitda_data_complete = True
            else:
                # Backward-compat: periods created before amounts existed keep
                # their hand-entered margin instead of being wiped to 0.
                # New periods with no amounts stay incomplete -> engine blocks.
                if rec.ebitda_margin:
                    rec.ebitda_data_complete = True
                else:
                    rec.ebitda_margin = 0.0
                    rec.ebitda_data_complete = False

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

    # Children that belong to exactly one period, deleted with it, in
    # dependency order (later entries may be referenced by earlier ones).
    # Lines of kprl.payout.run / kprl.territory.engine go via ondelete=cascade.
    _PERIOD_CHILD_MODELS = (
        'kprl.bonus.payout.report',
        'kprl.payout.run',
        'kprl.deferred.ledger',
        'kprl.bonus.payout',
        'kprl.bonus.engine',
        'kprl.territory.engine',
        'kprl.territory.payout',
        'kprl.performance.input',
        'kprl.product.pool',
        'kprl.dept.kpi.multiplier',
        'kprl.kpi.store',
        'kprl.asm.team.performance',
        'kprl.bonus.parameter',
    )

    def unlink(self):
        """Delete a period together with everything computed for it.

        Guard: a Closed period is treated as real payroll history and is
        refused - set it back to Draft first if it really is test data.
        Governance events are NOT deleted (they can span periods); their
        period link is cleared by the database (ondelete set null).
        """
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')
        closed = self.filtered(lambda p: p.state == 'closed')
        if closed:
            raise UserError(
                'Period %s is Closed and is kept as payroll history. '
                'Set it back to Draft first if it is test data, then delete.'
                % ', '.join(closed.mapped('name')))
        for model_name in self._PERIOD_CHILD_MODELS:
            if model_name not in self.env:
                continue
            Model = self.env[model_name].sudo().with_context(active_test=False)
            if 'period_id' not in Model._fields:
                continue
            recs = Model.search([('period_id', 'in', self.ids)])
            if not recs:
                continue
            if model_name == 'kprl.payout.run':
                # Approved/locked runs are immutable by design; release them
                # (state is a write-allowed key) so the cascade can proceed.
                recs.write({'state': 'draft'})
            recs.unlink()
        return super().unlink()

    def action_activate(self):
        self.state = 'active'

    def action_close(self):
        self.write({
            'state': 'closed',
            'sla_results_date': fields.Date.context_today(self),
        })

    def action_draft(self):
        self.write({'state': 'draft', 'sla_results_date': False})

    def action_export_ledger_excel(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/kprl/ledger/%d/xlsx' % self.id,
            'target': 'new',
        }