from odoo import models, fields, api


class KprlTerritoryEngine(models.Model):
    _name = 'kprl.territory.engine'
    _description = 'KPRL Territory Engine'

    period_id = fields.Many2one(
        'kprl.bonus.period',
        string='Period',
        required=True
    )

    national_actual_sales = fields.Float(
        string='National Actual Sales',
        compute='_compute_engine_totals',
        store=True
    )

    national_actual_retrivals = fields.Float(
        string='National Actual Retrivals',
        compute='_compute_engine_totals',
        store=True
    )

    national_sales_target = fields.Float(
        string='National Sales Target',
        compute='_compute_engine_totals',
        store=True
    )

    sales_commission_rate = fields.Float(
        string='Sales Commission Rate',
        default=0.30
    )

    total_sales_attain = fields.Float(
        string='Total Sales Attain'
    )

    total_retrival_rate = fields.Float(
        string='Total Retrival Rate'
    )

    total_sales_gate = fields.Float(
        string='Total Sales Gate'
    )

    total_retrival_gate = fields.Float(
        string='Total Retrival Gate'
    )

    total_eff_pool_share = fields.Float(
        string='Total Eff Pool Share'
    )

    total_commission_sales = fields.Float(
        string='Total Commission Sales',
        compute='_compute_engine_totals',
        store=True
    )

    total_commission_retrival = fields.Float(
        string='Total Commission Retrival',
        compute='_compute_engine_totals',
        store=True
    )

    total_prod_know = fields.Float(
        string='Total Prod Know'
    )

    total_call_rep = fields.Float(
        string='Total Call Rep'
    )

    total_coverage = fields.Float(
        string='Total Coverage'
    )

    total_new_cust = fields.Float(
        string='Total New Cust'
    )

    total_kpi_mult = fields.Float(
        string='Total KPI Mult'
    )

    total_yrs = fields.Float(
        string='Total Yrs'
    )

    total_tenure_mult = fields.Float(
        string='Total Tenure Mult'
    )


    total_sub_base = fields.Float(
        string='Total Sub-base (Helper)'
    )

    total_accel_factor = fields.Float(
        string='Total Accel Factor'
    )

    total_pk_effective = fields.Float(
        string='Total PK (Effective)'
    )

    total_rsm_territory_key = fields.Float(
        string='Total RSM Territory Key'
    )

    total_sales_floor = fields.Float(
        string='Total Sales Floor'
    )

    total_min_sales = fields.Float(
        string='Total Min Sales'
    )

    total_retrival_floor = fields.Float(
        string='Total Retrival Floor'
    )

    total_min_retrival = fields.Float(
        string='Total Min Retrival'
    )

    total_own_target = fields.Float(
        string='Total Own Target'
    )
    total_territory_retrival = fields.Float(
            string='Total Territory Retrival'
        )

    retrival_commission_rate = fields.Float(
        string='Retrival Commission Rate',
        default=0.70
    )

    total_gross_commission = fields.Float(
        string='Total Gross Commission',
        compute='_compute_engine_totals',
        store=True
    )

    total_eligible_commission = fields.Float(
        string='Total Eligible Commission',
        compute='_compute_engine_totals',
        store=True
    )

    total_sales_payout = fields.Float(
        string='TOTAL SALES PAYOUT',
        compute='_compute_engine_totals',
        store=True
    )

    kprl_employee_engine_line_ids = fields.One2many(
        'kprl.territory.engine.lines',
        'territory_engine_id',
        string='Employee Engine Lines'
    )
    sale_territory_config_ids = fields.One2many(
        'sale.territory.config',
        'territory_engine_id',
        string='Sales Territory Configuration',
    )

    @api.depends(
        'kprl_employee_engine_line_ids.own_sales',
        'kprl_employee_engine_line_ids.own_retrival',
        'kprl_employee_engine_line_ids.own_target',
        'kprl_employee_engine_line_ids.gross_commission',
        'kprl_employee_engine_line_ids.eligible_commission',
        'kprl_employee_engine_line_ids.sales_payout',
        'kprl_employee_engine_line_ids.commission_sales',
        'kprl_employee_engine_line_ids.commission_retrival',
    )
    def _compute_engine_totals(self):
        for record in self:
            lines = record.kprl_employee_engine_line_ids

            record.national_actual_sales = sum(lines.mapped('own_sales'))
            record.national_actual_retrivals = sum(lines.mapped('own_retrival'))
            record.national_sales_target = sum(lines.mapped('own_target'))
            record.total_gross_commission = sum(
                lines.mapped('gross_commission')
            )
            record.total_eligible_commission = sum(
                lines.mapped('eligible_commission')
            )
            record.total_sales_payout = sum(
                lines.mapped('sales_payout')
            )
            record.total_commission_sales = sum(
                lines.mapped('commission_sales')
            )
            record.total_commission_retrival = sum(
                lines.mapped('commission_retrival')
            )
    kprl_role_share_line_ids = fields.One2many(
            'kprl.role.share.lines',
            'role_share_line_id',
            string='Role share Lines'
        )

class KprlRoleShareLine(models.Model):
    _name = 'kprl.role.share.lines'
    _description = 'KPRL Role Share Lines'

    period_id = fields.Many2one(
        'kprl.bonus.period',
        string='Bonus Period',
        required=True,
        ondelete='cascade',
    )

    role_share_line_id = fields.Many2one(
            'kprl.territory.engine',
            string='Bonus Period',
            required=True,
            ondelete='cascade',
        )

    role_id = fields.Many2one(
        'kprl.role.parameter',
        string='Role',
        required=True,
    )

    share_rate = fields.Float(
        string='Share Rate',
        required=True,
    )

    dual_factor = fields.Float(
        string='Dual Factor',
        default=1.0,
    )