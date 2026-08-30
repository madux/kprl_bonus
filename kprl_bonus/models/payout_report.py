from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date


class BonusPayoutReport(models.Model):
    _name = 'kprl.bonus.payout.report'
    _description = 'Payroll Payout Register'
    _rec_name = 'employee_id'
    _order = 'department_id, employee_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- Identity ---
    sequence = fields.Integer(string='#', compute='_compute_sequence', store=False)
    employee_id = fields.Many2one('kprl.employee', string='Emp ID', required=True, index=True)
    staff_id = fields.Char(string='Staff ID', related='employee_id.staff_id', store=True)
    employee_name = fields.Char(string='Staff Name', related='employee_id.name', store=True)
    department_id = fields.Many2one('hr.department', string='Department',
                                    related='employee_id.employee_id.department_id', store=True)
    kprl_department_id = fields.Many2one('kprl.department', string='KPRL Dept',
                                         related='employee_id.department_id', store=True)
    grade_id = fields.Many2one('kprl.grade', string='Grade / Role',
                               related='employee_id.grade_id', store=True)
    grade_code = fields.Char(string='Grade Code', related='grade_id.code', store=True)

    # --- Compensation Track ---
    comp_track = fields.Selection([
        ('ops', 'Ops'),
        ('sales', 'Sales'),
        ('both', 'Ops + Sales'),
    ], string='Track', compute='_compute_comp_track', store=True)

    # --- Financials ---
    ops_bonus = fields.Monetary(string='Ops Bonus (?)', currency_field='currency_id',
                                compute='_compute_financials', store=True)
    sales_commission = fields.Monetary(string='Sales Comm (?)', currency_field='currency_id',
                                       compute='_compute_financials', store=True)
    total_payout = fields.Monetary(string='TOTAL (?)', currency_field='currency_id',
                                   compute='_compute_total', store=True)

    # --- Meta ---
    aip_eligible = fields.Boolean(string='AIP Elig (Q4)',
                                  related='employee_id.aip_eligible', store=True)
    notes = fields.Text(string='Notes')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    period_id = fields.Many2one('kprl.bonus.period', string='Period', required=True, index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('exported', 'Exported'),
    ], string='Status', default='draft', tracking=True)

    # --- KPI Summary (computed, not stored) ---
    total_ops_payout = fields.Float(string='Total Ops Payout', compute='_compute_kpi_summary')
    headcount = fields.Integer(string='Headcount', compute='_compute_kpi_summary')
    total_sales_commission = fields.Float(string='Total Sales Commission', compute='_compute_kpi_summary')
    total_quarterly_payout = fields.Float(string='Total Quarterly Payout', compute='_compute_kpi_summary')
    payout_pct_revenue = fields.Float(string='Payout as % of Revenue', compute='_compute_kpi_summary')

    _sql_constraints = [
        ('employee_period_unique', 'UNIQUE(employee_id, period_id)',
         'An employee can only have one report entry per period!'),
    ]

    # ---- Computes ----

    @api.depends('employee_id', 'period_id')
    def _compute_comp_track(self):
        for rec in self:
            emp = rec.employee_id
            if emp.is_sales and emp.sales_role and emp.sales_role != 'none':
                # Check if they also have ops payout
                ops_payout = self.env['kprl.bonus.payout'].search_count([
                    ('employee_id', '=', emp.id),
                    ('period_id', '=', rec.period_id.id),
                ])
                rec.comp_track = 'both' if ops_payout else 'sales'
            else:
                rec.comp_track = 'ops'

    @api.depends('employee_id', 'period_id', 'comp_track')
    def _compute_financials(self):
        Payout = self.env['kprl.bonus.payout']
        TerritoryPayout = self.env['kprl.territory.payout']
        SalesEngine = self.env['kprl.sales.engine']
        for rec in self:
            rec.ops_bonus = 0.0
            rec.sales_commission = 0.0
            if not rec.employee_id or not rec.period_id:
                continue
            # Ops bonus from main payout
            payout = Payout.search([
                ('employee_id', '=', rec.employee_id.id),
                ('period_id', '=', rec.period_id.id),
            ], limit=1)
            if payout:
                rec.ops_bonus = payout.net_immediate or 0.0
            # Sales commission from sales engine (new implementation)
            emp = rec.employee_id
            if emp.is_sales and emp.sales_role and emp.sales_role != 'none':
                sales_engine = SalesEngine.search([
                    ('employee_id', '=', emp.id),
                    ('period_id', '=', rec.period_id.id),
                ], limit=1)
                if sales_engine:
                    rec.sales_commission = sales_engine.final_sales_payout or 0.0
            # Fallback to territory payout for backward compatibility
            if emp.is_sales:
                se = self.env['kprl.sales.engine'].search([('employee_id','=',emp.id),('period_id','=',rec.period_id.id)], limit=1)
                if se:
                    rec.sales_commission = se.final_sales_payout or 0.0
                elif emp.territory_id:
                    t_payout = self.env['kprl.territory.payout'].search([('territory_id','=',emp.territory_id.id),('period_id','=',rec.period_id.id)], limit=1)
                    rec.sales_commission = t_payout.commission_payable or 0.0 if t_payout else 0.0
                if t_payout:
                    rec.sales_commission = t_payout.commission_payable or 0.0

    @api.depends('ops_bonus', 'sales_commission')
    def _compute_total(self):
        for rec in self:
            rec.total_payout = (rec.ops_bonus or 0.0) + (rec.sales_commission or 0.0)

    @api.depends('employee_id')
    def _compute_sequence(self):
        all_recs = self.search([('period_id', '=', self[0].period_id.id)]) if self else self.env['kprl.bonus.payout.report']
        for i, rec in enumerate(self, start=1):
            rec.sequence = i

    def _compute_kpi_summary(self):
        """Compute summary KPIs for the current recordset."""
        for rec in self:
            domain = [('period_id', '=', rec.period_id.id)] if rec.period_id else []
            all_lines = self.search(domain) if rec.period_id else self
            rec.total_ops_payout = sum(all_lines.mapped('ops_bonus'))
            rec.total_sales_commission = sum(all_lines.mapped('sales_commission'))
            rec.total_quarterly_payout = sum(all_lines.mapped('total_payout'))
            rec.headcount = len(all_lines)
            # Revenue from period's engine
            revenue = 0.0
            if rec.period_id:
                engine = self.env['kprl.bonus.engine'].search([
                    ('period_id', '=', rec.period_id.id),
                ], limit=1)
                revenue = engine.quarterly_revenue or engine.net_revenue or 0.0
            rec.payout_pct_revenue = (rec.total_quarterly_payout / revenue * 100) if revenue else 0.0

    # ---- Actions ----

    def action_generate(self):
        """Generate report entries from existing payout data for the given period."""
        if not self._context.get('active_id') and not self.period_id:
            raise UserError('Please select a Bonus Period first.')
        period_id = self._context.get('active_id') or self.period_id.id
        period = self.env['kprl.bonus.period'].browse(period_id)
        if not period:
            raise UserError('Period not found.')

        # Remove existing entries for this period
        existing = self.search([('period_id', '=', period.id)])
        existing.unlink()

        # Get all payouts for this period
        payouts = self.env['kprl.bonus.payout'].search([('period_id', '=', period.id)])
        vals_list = []
        for payout in payouts:
            emp = payout.employee_id
            vals_list.append({
                'employee_id': emp.id,
                'period_id': period.id,
            })

        if vals_list:
            self.create(vals_list)

        # Also add sales-only employees who have territory payout but no ops payout
        t_payouts = self.env['kprl.territory.payout'].search([('period_id', '=', period.id)])
        for tp in t_payouts:
            if tp.territory_id:
                # Find sales employees in this territory
                sales_emp = self.env['kprl.employee'].search([
                    ('territory_id', '=', tp.territory_id.id),
                    ('is_sales', '=', True),
                ])
                for emp in sales_emp:
                    existing_entry = self.search([
                        ('employee_id', '=', emp.id),
                        ('period_id', '=', period.id),
                    ])
                    if not existing_entry:
                        self.create({
                            'employee_id': emp.id,
                            'period_id': period.id,
                        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kprl.bonus.payout.report',
            'view_mode': 'tree,form',
            'domain': [('period_id', '=', period.id)],
            'context': {'default_period_id': period.id},
        }

    def action_confirm(self):
        self.state = 'confirmed'

    def action_exported(self):
        self.state = 'exported'

    def action_print_pdf(self):
        return self.env.ref('kprl_bonus.action_report_payout_register').report_action(self)