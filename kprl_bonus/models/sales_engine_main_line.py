from odoo import models, fields, api

class KprlTerritoryEngineLines(models.Model):
    _name = 'kprl.territory.engine.lines'
    _description = 'KPRL Territory Engine Lines'

    territory_engine_id = fields.Many2one(
        'kprl.territory.engine',
        string='Territory Engine',
        required=True,
        ondelete='cascade'
    )

    employee_id = fields.Many2one(
        'kprl.employee',
        string='Employee'
    )

    role_id = fields.Many2one(
        'kprl.role.parameter',
        string='Role'
    )

    territory_id = fields.Many2one(
        'kprl.territory',
        string='Territory'
    )

    own_sales = fields.Float(
        string='Own Sales'
    )

    own_retrival = fields.Float(
        string='Own Retrival',
    )

    territory_sales = fields.Float(
        string='Territory Sales',
        compute='_compute_territory_sales',
        store=True,
        help="Gets all the sum of all lines with same territory. ie if employee with the same own sales in NW territory, sum of the both"
    )

    @api.depends(
        'employee_id',
        'territory_id',
        'own_sales',
        'territory_engine_id.kprl_employee_engine_line_ids',
    )
    def _compute_territory_sales(self):
        '''Gets all the sum of all lines with same territory'''
        for line in self:
            if not line.employee_id:
                line.territory_sales = 0.0
                continue

            if not line.territory_id:
                line.territory_sales = 0.0
                continue

            # Get all lines belonging to the same Territory Engine
            engine_lines = line.territory_engine_id.kprl_employee_engine_line_ids

            # Sum Own Sales for all employees in the same territory
            line.territory_sales = sum(
                engine_lines.filtered(
                    lambda l: l.territory_id == line.territory_id
                ).mapped('own_sales')
            )

    @api.onchange("employee_id")
    def changeOfEmployee(self):
        '''get staff sales performance'''
        emp = self.employee_id
        if emp:
            self.own_sales= emp.own_sales
            self.own_retrival= emp.own_retrival
            self.own_target= emp.own_target
        else:
            self.own_sales= ''
            self.own_retrival= ''
            self.own_target= ''

    territory_retrival = fields.Float(
        string='Territory Retrival',
        compute='_compute_territory_retrival',
        store=True,
    )

    @api.depends(
        'employee_id',
        'territory_id',
        'own_retrival',
        'territory_engine_id.kprl_employee_engine_line_ids',
    )
    def _compute_territory_retrival(self):
        for engine in self.mapped('territory_engine_id'):
            territory_totals = {}

            for line in engine.kprl_employee_engine_line_ids:
                if line.territory_id:
                    territory_totals.setdefault(line.territory_id.id, 0.0)
                    territory_totals[line.territory_id.id] += line.own_retrival

            for line in engine.kprl_employee_engine_line_ids:
                if not line.employee_id or not line.territory_id:
                    line.territory_retrival = 0.0
                    line.territory_engine_id.total_territory_retrival = line.territory_retrival
                else:
                    line.territory_retrival = territory_totals.get(
                        line.territory_id.id,
                        0.0
                    )
                    line.territory_engine_id.total_territory_retrival = line.territory_retrival


    sales_attain = fields.Float(
        string='Sales Attain',
        compute='_compute_sales_attain',
        store=True,
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'own_sales',
        'own_target',
        'territory_sales',
        'territory_id',
        'territory_engine_id.national_actual_sales',
        'territory_engine_id.national_sales_target',
    )
    def _compute_sales_attain(self):
        for line in self:
            line.sales_attain = 0.0

            if not line.employee_id:
                continue

            role = line.role_id.role if line.role_id else False

            # GM / NSM / Head Tech
            if role in ('gm', 'nsm', 'headtech'):
                national_sales = (
                    line.territory_engine_id.national_actual_sales
                    if line.territory_engine_id
                    else 0.0
                )

                national_target = (
                    line.territory_engine_id.national_sales_target
                    if line.territory_engine_id
                    else 0.0
                )

                if national_target:
                    line.sales_attain = national_sales / national_target

            # RSM / RSM + ASM
            elif role in ('rsm', 'rsm_asm'):
                territory_target = (
                    line.territory_id.eff_target
                    if line.territory_id
                    else 0.0
                )

                if territory_target:
                    line.sales_attain = (
                        line.territory_sales / territory_target
                    )

            # ASM and all other roles
            else:
                if line.own_target:
                    line.sales_attain = (
                        line.own_sales / line.own_target
                    )

    period_id = fields.Many2one(
            'kprl.bonus.period',
            string='Period',
            required=True, 
            related="territory_engine_id.period_id"
        )

    retrival_rate = fields.Float(
        string='Retrival Rate',
        compute='_compute_retrival_rate',
        store=True,
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'own_retrival',
        'own_sales',
        'territory_retrival',
        'territory_sales',
        'territory_engine_id.national_actual_retrivals',
        'territory_engine_id.national_actual_sales',
    )
    def _compute_retrival_rate(self):
        for line in self:
            line.retrival_rate = 0.0

            if not line.employee_id:
                continue

            role = line.role_id.role if line.role_id else False

            # GM / NSM / Head Tech
            if role in ('gm', 'nsm', 'headtech'):
                national_retrival = (
                    line.territory_engine_id.national_actual_retrivals
                    if line.territory_engine_id
                    else 0.0
                )

                national_sales = (
                    line.territory_engine_id.national_actual_sales
                    if line.territory_engine_id
                    else 0.0
                )

                if national_sales:
                    line.retrival_rate = (
                        national_retrival / national_sales
                    )

            # RSM / RSM + ASM
            elif role in ('rsm', 'rsm_asm'):
                if line.territory_sales:
                    line.retrival_rate = (
                        line.territory_retrival /
                        line.territory_sales
                    )

            # Other roles including ASM
            else:
                if line.own_sales:
                    line.retrival_rate = (
                        line.own_retrival /
                        line.own_sales
                    )

            # Update parent Territory Engine total
            if line.territory_engine_id:
                line.territory_engine_id.total_retrival_rate = (
                    line.retrival_rate
                )

    sales_gate = fields.Float(
        string='Sales Gate',
        compute='_compute_sales_gate',
        store=True,
    )

    @api.depends(
        'employee_id',
        'min_sales',
        'sales_floor',
        'sales_attain',
    )
    def _compute_sales_gate(self):
        for line in self:
            line.sales_gate = 0.0

            if not line.employee_id:
                continue

            min_sales = line.min_sales
            sales_floor = line.sales_floor
            sales_attain = line.sales_attain

            # Excel:
            # IF(AG18<=AF18,
            #       IF(K18>=AG18,1,0),
            #       IFERROR(
            #           MEDIAN(
            #               0,
            #               (K18-AF18)/(AG18-AF18),
            #               1
            #           ),
            #           0
            #       )
            # )

            if min_sales <= sales_floor:

                if sales_attain >= min_sales:
                    line.sales_gate = 1.0
                else:
                    line.sales_gate = 0.0

            else:
                denominator = min_sales - sales_floor

                if denominator:
                    value = (
                        (sales_attain - sales_floor)
                        / denominator
                    )

                    # Equivalent to Excel MEDIAN(0, value, 1)
                    line.sales_gate = max(0.0, min(value, 1.0))
                else:
                    line.sales_gate = 0.0

            # Update parent engine total/helper field
            if line.territory_engine_id:
                line.territory_engine_id.total_sales_gate = line.sales_gate

    retrival_gate = fields.Float(
        string='Retrival Gate',
        compute='_compute_retrival_gate',
        store=True,
    )

    @api.depends(
        'employee_id',
        'min_retrival',
        'retrival_floor',
        'retrival_rate',
    )
    def _compute_retrival_gate(self):
        for line in self:
            line.retrival_gate = 0.0

            if not line.employee_id:
                continue

            min_retrival = line.min_retrival
            retrival_floor = line.retrival_floor
            retrival_rate = line.retrival_rate

            # Equivalent to:
            # IF(AI18<=AH18,
            #     IF(L18>=AI18,1,0),
            #     IFERROR(
            #         MEDIAN(
            #             0,
            #             (L18-AH18)/(AI18-AH18),
            #             1
            #         ),
            #         0
            #     )
            # )

            if min_retrival <= retrival_floor:

                if retrival_rate >= min_retrival:
                    line.retrival_gate = 1.0
                else:
                    line.retrival_gate = 0.0

            else:
                denominator = min_retrival - retrival_floor

                if denominator:
                    value = (
                        (retrival_rate - retrival_floor)
                        / denominator
                    )

                    # Equivalent to Excel:
                    # MEDIAN(0, value, 1)
                    line.retrival_gate = max(
                        0.0,
                        min(value, 1.0)
                    )
                else:
                    line.retrival_gate = 0.0

            # Update parent Territory Engine
            if line.territory_engine_id:
                line.territory_engine_id.total_retrival_gate = (
                    line.retrival_gate
                )

    eff_pool_share = fields.Float(
        string='Eff Pool Share',
        compute='_compute_eff_pool_share',
        store=True,
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'territory_engine_id.period_id',
    )
    def _compute_eff_pool_share(self):
        RoleShareLine = self.env['kprl.role.share.lines']

        for line in self:
            line.eff_pool_share = 0.0

            if not line.employee_id:
                continue

            if not line.territory_engine_id:
                continue

            period = line.territory_engine_id.period_id

            if not period:
                continue

            role = line.role_id.role if line.role_id else False

            if not role:
                continue

            # Get the configured share for the current period and role
            def get_share(role_code):
                share_line = RoleShareLine.search([
                    ('period_id', '=', period.id),
                    ('role_id.role', '=', role_code),
                ], limit=1)

                return share_line.share_rate if share_line else 0.0

            # GM
            if role == 'gm':
                line.eff_pool_share = get_share('gm')

            # NSM
            elif role == 'nsm':
                line.eff_pool_share = get_share('nsm')

            # Head Tech
            elif role == 'headtech':
                line.eff_pool_share = get_share('headtech')

            # RSM
            elif role == 'rsm':
                line.eff_pool_share = get_share('rsm')

            # ASM
            elif role == 'asm':
                line.eff_pool_share = get_share('asm')

            # RSM + ASM
            elif role == 'rsm_asm':
                rsm_share = get_share('rsm')
                asm_share = get_share('asm')

                # DualFactor comes from configuration
                dual_factor_line = RoleShareLine.search([
                    ('period_id', '=', period.id),
                ], limit=1)

                dual_factor = (
                    dual_factor_line.dual_factor
                    if dual_factor_line
                    else 1.0
                )

                line.eff_pool_share = (
                    (rsm_share + asm_share) * dual_factor
                )

            # Update parent engine helper/total field
            if line.territory_engine_id:
                line.territory_engine_id.total_eff_pool_share = (
                    line.eff_pool_share
                )

    commission_sales = fields.Float(
        string='Commission Sales',
        compute='_compute_commission_sales',
        store=True,
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'own_sales',
        'territory_sales',
        'territory_engine_id.national_actual_sales',
        'territory_engine_id.sales_commission_rate',
        'territory_engine_id.period_id',
    )
    def _compute_commission_sales(self):
        RoleShareLine = self.env['kprl.role.share.lines']

        for engine in self.mapped('territory_engine_id'):
            lines = engine.kprl_employee_engine_line_ids
            engine.commission_sales = 0.0

            if not engine.period_id:
                for line in lines:
                    line.commission_sales = 0.0
                continue

            # Get role share configuration for this bonus period
            share_lines = RoleShareLine.search([
                ('period_id', '=', engine.period_id.id),
            ])

            shares = {
                share.role_id.role: share.share_rate
                for share in share_lines
                if share.role_id
            }

            # Dual factor
            dual_factor = (
                share_lines[:1].dual_factor
                if share_lines
                else 1.0
            )

            national_sales = engine.national_actual_sales or 0.0
            sales_commission_rate = engine.sales_commission_rate or 0.0

            for line in lines:
                line.commission_sales = 0.0

                if not line.employee_id or not line.role_id:
                    continue

                role = line.role_id.role

                if role == 'gm':
                    commission_base = (
                        national_sales * shares.get('gm', 0.0)
                    )

                elif role == 'nsm':
                    commission_base = (
                        national_sales * shares.get('nsm', 0.0)
                    )

                elif role == 'headtech':
                    commission_base = (
                        national_sales * shares.get('headtech', 0.0)
                    )

                elif role == 'rsm':
                    commission_base = (
                        line.territory_sales * shares.get('rsm', 0.0)
                    )

                elif role == 'asm':
                    commission_base = (
                        line.own_sales * shares.get('asm', 0.0)
                    )

                elif role == 'rsm_asm':
                    commission_base = (
                        (
                            line.territory_sales * shares.get('rsm', 0.0)
                            +
                            line.own_sales * shares.get('asm', 0.0)
                        )
                        * dual_factor
                    )

                else:
                    commission_base = 0.0

                line.commission_sales = (
                    commission_base * sales_commission_rate
                )

                # Update parent total field
                if line.territory_engine_id:
                    line.territory_engine_id.total_commission_sales = (
                        line.commission_sales
                    )

     
    commission_retrival = fields.Float(
        string='Commission Retrival',
        compute='_compute_commission_retrival',
        store=True,
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'own_retrival',
        'territory_retrival',
        'territory_engine_id.national_actual_retrivals',
        'territory_engine_id.retrival_commission_rate',
        'territory_engine_id.period_id',
    )
    def _compute_commission_retrival(self):
        RoleShareLine = self.env['kprl.role.share.lines']

        for engine in self.mapped('territory_engine_id'):
            lines = engine.kprl_employee_engine_line_ids

            if not engine.period_id:
                for line in lines:
                    line.commission_retrival = 0.0
                continue

            # Load share configuration once for this period
            share_lines = RoleShareLine.search([
                ('period_id', '=', engine.period_id.id)
            ])

            shares = {
                share.role_id.role: share.share_rate
                for share in share_lines
                if share.role_id
            }

            dual_factor = share_lines[:1].dual_factor if share_lines else 1.0

            national_retrival = engine.national_actual_retrivals or 0.0
            retr_comm_rate = engine.retrival_commission_rate or 0.0

            for line in lines:
                line.commission_retrival = 0.0

                if not line.employee_id or not line.role_id:
                    continue

                role = line.role_id.role

                # Determine commission base
                if role == 'gm':
                    commission_base = national_retrival * shares.get('gm', 0.0)

                elif role == 'nsm':
                    commission_base = national_retrival * shares.get('nsm', 0.0)

                elif role == 'headtech':
                    commission_base = national_retrival * shares.get('headtech', 0.0)

                elif role == 'rsm':
                    commission_base = (
                        line.territory_retrival * shares.get('rsm', 0.0)
                    )

                elif role == 'asm':
                    commission_base = (
                        line.own_retrival * shares.get('asm', 0.0)
                    )

                elif role == 'rsm_asm':
                    commission_base = (
                        (
                            line.territory_retrival * shares.get('rsm', 0.0)
                            + line.own_retrival * shares.get('asm', 0.0)
                        ) * dual_factor
                    )

                else:
                    commission_base = 0.0

                # Final commission
                line.commission_retrival = commission_base * retr_comm_rate

                # Update parent helper field
                line.territory_engine_id.total_commission_retrival = (
                    line.commission_retrival
                )

    gross_commission = fields.Float(
        string='Gross Commission'
    )

    eligible_commission = fields.Float(
        string='Eligible Commission'
    )

    prod_know = fields.Float(
        string='Prod Know'
    )

    call_rep = fields.Float(
        string='Call Rep'
    )

    coverage = fields.Float(
        string='Coverage'
    )

    new_cust = fields.Float(
        string='New Cust'
    )

    kpi_mult = fields.Float(
        string='KPI Mult'
    )

    yrs = fields.Float(
        string='Yrs'
    )

    tenure_mult = fields.Float(
        string='Tenure Mult'
    )

    sales_payout = fields.Float(
        string='SALES PAYOUT'
    )

    sub_base = fields.Float(
        string='Sub-base (helper)'
    )

    accel_factor = fields.Float(
        string='Accel Factor'
    )

    pk_effective = fields.Float(
        string='PK (effective)'
    )

    rsm_territory_key = fields.Float(
        string='RSM TerritoryKey'
    )

    sales_floor = fields.Float(
        string='Sales Floor'
    )
    min_sales = fields.Float(
        string='Min Sales'
    )

    retrival_floor = fields.Float(
        string='Retrival Floor'
    )

    min_retrival = fields.Float(
        string='Min Retrival'
    )

    own_target = fields.Float(
        string='Own Target'
    )