from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError, UserError

class KprlTerritoryEngineLines(models.Model):
    _name = 'kprl.territory.engine.lines'
    _description = 'KPRL Territory Engine Lines'

    @api.constrains('territory_id', 'territory_engine_id')
    def _check_territory_configuration(self):
        for line in self:
            if not line.territory_engine_id or not line.territory_id:
                continue

            config = line.territory_engine_id.sale_territory_config_ids.filtered(
                lambda c: c.territory_id == line.territory_id
            )

            if not config:
                raise ValidationError(
                    'No Sales Territory Configuration exists for territory "%s".'
                    % line.territory_id.display_name
                )

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

    sales_role = fields.Selection(
        related='role_id.role',
        string='Sales Role',
        readonly=True,
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
        help='Selected-period sales for sales employees assigned to this territory.',
    )

    # Sales KPI fields (0-1 scale)
    product_knowledge_score = fields.Float(string='Product Knowledge Score', digits=(5, 2),
                                            help='Sales KPI: Product knowledge (0-1 scale)')
    call_report_compliance = fields.Float(string='Call Report Compliance', digits=(5, 2),
                                            help='Sales KPI: Call report compliance (0-1 scale)')
    customer_coverage_rate = fields.Float(string='Customer Coverage Rate', digits=(5, 2),
                                            help='Sales KPI: Customer coverage rate (0-1 scale)')
    new_customer_acquisition = fields.Float(string='New Customer Acquisition', digits=(5, 2),
                                            help='Sales KPI: New customer acquisition (0-1 scale)')
    
    @api.depends(
        'employee_id',
        'territory_id',
        'own_sales',
        'own_retrival',
        'territory_engine_id.kprl_employee_engine_line_ids',
        'territory_engine_id.period_id.performance_ids.employee_id',
        'territory_engine_id.period_id.performance_ids.own_sales',
        'territory_engine_id.period_id.performance_ids.own_retrievals',
        'territory_engine_id.period_id.performance_ids.employee_id.territory_id',
        'territory_engine_id.period_id.performance_ids.employee_id.pool_type',
        'territory_engine_id.period_id.performance_ids.employee_id.track',
    )
    def _compute_territory_sales(self):
        for engine in self.mapped('territory_engine_id'):
            totals = {}
            for territory in engine.kprl_employee_engine_line_ids.mapped(
                'territory_id'
            ):
                if territory:
                    totals[territory.id] = self._territory_actuals(
                        engine, territory
                    )[0]
            for line in engine.kprl_employee_engine_line_ids:
                line.territory_sales = (
                    totals.get(line.territory_id.id, 0.0)
                    if line.employee_id and line.territory_id
                    else 0.0
                )

    def _territory_actuals(self, engine, territory):
        territory_lines = engine.kprl_employee_engine_line_ids.filtered(
            lambda line: line.territory_id == territory
        )
        line_totals = {}
        for line in territory_lines.filtered('employee_id'):
            values = line_totals.setdefault(line.employee_id.id, [0.0, 0.0])
            values[0] += line.own_sales or 0.0
            values[1] += line.own_retrival or 0.0

        sales_employees = self.env['kprl.employee'].with_context(
            active_test=False
        ).search([
            ('territory_id', '=', territory.id),
            '|',
            ('pool_type', '=', 'SALES'),
            ('track', 'in', ('sales', 'both')),
        ])
        employee_ids = set(line_totals) | set(sales_employees.ids)
        if not employee_ids:
            return 0.0, 0.0

        performance_inputs = self.env['kprl.performance.input'].search([
            ('period_id', '=', engine.period_id.id),
            ('employee_id', 'in', list(employee_ids)),
        ]) if engine.period_id else self.env['kprl.performance.input']
        performance_by_employee = {
            performance.employee_id.id: performance
            for performance in performance_inputs
        }

        sales = retrievals = 0.0
        for employee_id in employee_ids:
            performance = performance_by_employee.get(employee_id)
            if performance:
                sales += performance.own_sales or 0.0
                retrievals += performance.own_retrievals or 0.0
            else:
                line_values = line_totals.get(employee_id, (0.0, 0.0))
                sales += line_values[0]
                retrievals += line_values[1]

        return sales, retrievals

    territory_sales_target = fields.Float(
        string='Territory Sales Target',
        compute='_compute_territory_sales_target',
        store=True,
        help='Workbook DASHBOARD K "Team Targets": sum of the Own Target of '
             'every sales employee in this territory for the selected period '
             '(SUMIF(SE_Terr, territory, SE_OwnTarget)).',
    )

    @api.depends(
        'employee_id',
        'territory_id',
        'own_target',
        'territory_engine_id.kprl_employee_engine_line_ids',
        'territory_engine_id.kprl_employee_engine_line_ids.own_target',
        'territory_engine_id.period_id.performance_ids.employee_id',
        'territory_engine_id.period_id.performance_ids.own_target',
        'territory_engine_id.period_id.performance_ids.employee_id.territory_id',
        'territory_engine_id.period_id.performance_ids.employee_id.pool_type',
        'territory_engine_id.period_id.performance_ids.employee_id.track',
    )
    def _compute_territory_sales_target(self):
        for line in self.filtered(lambda l: not l.territory_engine_id):
            line.territory_sales_target = 0.0
        for engine in self.mapped('territory_engine_id'):
            totals = {}
            for territory in engine.kprl_employee_engine_line_ids.mapped('territory_id'):
                if territory:
                    totals[territory.id] = self._territory_target_total(engine, territory)
            for line in engine.kprl_employee_engine_line_ids:
                line.territory_sales_target = (
                    totals.get(line.territory_id.id, 0.0)
                    if line.employee_id and line.territory_id
                    else 0.0
                )

    def _territory_target_total(self, engine, territory):
        """Same staff set as _territory_actuals; Performance Inputs win,
        the engine line's own_target is the fallback."""
        territory_lines = engine.kprl_employee_engine_line_ids.filtered(
            lambda line: line.territory_id == territory and line.employee_id
        )
        line_targets = {}
        for line in territory_lines:
            line_targets[line.employee_id.id] = (
                line_targets.get(line.employee_id.id, 0.0) + (line.own_target or 0.0))
        sales_employees = self.env['kprl.employee'].with_context(
            active_test=False
        ).search([
            ('territory_id', '=', territory.id),
            '|',
            ('pool_type', '=', 'SALES'),
            ('track', 'in', ('sales', 'both')),
        ])
        employee_ids = set(line_targets) | set(sales_employees.ids)
        if not employee_ids:
            return 0.0
        perfs = self.env['kprl.performance.input'].search([
            ('period_id', '=', engine.period_id.id),
            ('employee_id', 'in', list(employee_ids)),
        ]) if engine.period_id else self.env['kprl.performance.input']
        perf_by_emp = {p.employee_id.id: p for p in perfs}
        total = 0.0
        for employee_id in employee_ids:
            perf = perf_by_emp.get(employee_id)
            total += (perf.own_target or 0.0) if perf else line_targets.get(employee_id, 0.0)
        return total

    @api.onchange("employee_id")
    def onchange_employee(self):
        self.updateEmployee()

    def updateEmployee(self):
        '''get staff sales performance'''
        PerformanceInput = self.env['kprl.performance.input']
        emp = PerformanceInput.search([
            ('employee_id', '=', self.employee_id.id),
            ('period_id', '=', self.period_id.id),
        ], limit=1) if self.employee_id and self.period_id else PerformanceInput
        if emp:
            self.own_sales= emp.own_sales
            self.own_retrival= emp.own_retrievals
            self.own_target= emp.own_target
            self.call_rep= emp.call_rep
            self.coverage= emp.coverage
            self.new_cust= emp.new_cust
            self.prod_know= emp.prod_know
            self.call_report_compliance = emp.call_report_compliance
            self.customer_coverage_rate= emp.customer_coverage_rate
            self.product_knowledge_score= emp.product_knowledge_score
            self.new_customer_acquisition = emp.new_customer_acquisition
        else:
            self.own_sales= 0
            self.own_retrival= 0
            self.own_target= 0
            self.call_rep= 0
            self.coverage= 0
            self.new_cust = 0
            self.prod_know= 0
            self.call_report_compliance= 0 
            self.customer_coverage_rate= 0 
            self.product_knowledge_score= 0 
            self.new_customer_acquisition= 0

    def action_view_team_performance(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError('Select an employee before opening team performance.')
        if self.sales_role not in ('rsm', 'rsm_asm'):
            raise UserError(
                'Regional ASM performance is available from an RSM line.'
            )

        period = self.territory_engine_id.period_id
        if not period:
            raise UserError('Select a bonus period before opening team performance.')

        if not self.territory_id:
            raise UserError(
                '%s has no sales region assigned.'
                % self.employee_id.display_name
            )

        asm_lines = self.territory_engine_id.kprl_employee_engine_line_ids.filtered(
            lambda line: line.territory_id == self.territory_id
            and line.sales_role == 'asm'
            and line.employee_id != self.employee_id
        )
        if not asm_lines:
            raise UserError(
                'No ASM engine lines are assigned to %s for %s. '
                'Add the region ASMs to this quarter’s Territory Engine.'
                % (self.territory_id.display_name, period.display_name)
            )

        Employee = self.env['kprl.employee'].with_context(active_test=False)
        asm_team_ids = {}
        all_employee_ids = set()
        for asm_line in asm_lines:
            asm = asm_line.employee_id
            seen_ids = {asm.id}
            team_ids = {asm.id}
            frontier = Employee.search([
                ('manager_id', '=', asm.id),
                '|',
                ('territory_id', '=', False),
                ('territory_id', '=', self.territory_id.id),
            ])
            while frontier:
                new_ids = set(frontier.ids) - seen_ids
                if not new_ids:
                    break
                seen_ids.update(new_ids)
                team_ids.update(new_ids)
                frontier = Employee.search([
                    ('manager_id', 'in', list(new_ids)),
                    '|',
                    ('territory_id', '=', False),
                    ('territory_id', '=', self.territory_id.id),
                ])
            asm_team_ids[asm.id] = team_ids
            all_employee_ids.update(team_ids)

        performance_inputs = self.env['kprl.performance.input'].search([
            ('period_id', '=', period.id),
            ('employee_id', 'in', list(all_employee_ids)),
        ])
        performance_by_employee = {
            performance.employee_id.id: performance
            for performance in performance_inputs
        }

        report_values = []
        for asm_line in asm_lines.sorted('employee_id'):
            asm = asm_line.employee_id
            for employee_id in sorted(asm_team_ids[asm.id]):
                employee = Employee.browse(employee_id)
                performance = performance_by_employee.get(employee_id)
                if employee_id == asm.id and not performance:
                    target = asm_line.own_target
                    sales = asm_line.own_sales
                    retrievals = asm_line.own_retrival
                    input_found = False
                else:
                    target = performance.own_target if performance else 0.0
                    sales = performance.own_sales if performance else 0.0
                    retrievals = (
                        performance.own_retrievals if performance else 0.0
                    )
                    input_found = bool(performance)
                report_values.append({
                    'period_id': period.id,
                    'manager_id': self.employee_id.id,
                    'asm_id': asm.id,
                    'employee_id': employee_id,
                    'department_id': employee.department_id.id,
                    'asm_grouping': self.territory_id.display_name,
                    'performance_input_found': input_found,
                    'own_target': target,
                    'own_sales': sales,
                    'own_retrievals': retrievals,
                })
        report_rows = self.env['kprl.asm.team.performance'].create(report_values)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Regional ASM Sales & Retrieval - %s - %s' % (
                self.employee_id.display_name,
                period.display_name,
            ),
            'res_model': 'kprl.asm.team.performance',
            'view_mode': 'tree',
            'views': [(
                self.env.ref(
                    'kprl_bonus.view_kprl_asm_team_performance_tree'
                ).id,
                'tree',
            )],
            'domain': [('id', 'in', report_rows.ids)],
            'context': {
                'group_by': 'asm_id',
                'create': False,
                'edit': False,
                'delete': False,
            },
        }

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
        'territory_engine_id.period_id.performance_ids.employee_id',
        'territory_engine_id.period_id.performance_ids.own_sales',
        'territory_engine_id.period_id.performance_ids.own_retrievals',
        'territory_engine_id.period_id.performance_ids.employee_id.territory_id',
        'territory_engine_id.period_id.performance_ids.employee_id.pool_type',
        'territory_engine_id.period_id.performance_ids.employee_id.track',
    )
    def _compute_territory_retrival(self):
        for engine in self.mapped('territory_engine_id'):
            territory_totals = {}

            for territory in engine.kprl_employee_engine_line_ids.mapped(
                'territory_id'
            ):
                if territory:
                    territory_totals[territory.id] = self._territory_actuals(
                        engine, territory
                    )[1]

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
                    line.territory_id.effective_target
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
            raw_sales_rate = engine.sales_commission_rate or 0.0
            sales_commission_rate = raw_sales_rate / 100.0 if raw_sales_rate > 0.01 else raw_sales_rate

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
            raw_retr_rate = engine.retrival_commission_rate or 0.0
            retr_comm_rate = raw_retr_rate / 100.0 if raw_retr_rate > 0.01 else raw_retr_rate

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


    gross_commission = fields.Float(
        string='Gross Commission',
        compute='_compute_gross_commission',
        store=True,
    )

    @api.depends(
        'employee_id',
        'commission_sales',
        'commission_retrival',
    )
    def _compute_gross_commission(self):
        for line in self:
            line.gross_commission = 0.0

            if not line.employee_id:
                continue

            line.gross_commission = (
                (line.commission_sales or 0.0)
                + (line.commission_retrival or 0.0)
            )


    eligible_commission = fields.Float(
        string='Eligible Commission',
        compute='_compute_eligible_commission',
        store=True,
        help='''Eligible Commission = Sales Gate × (Commission Sales + Retrieval Gate × Commission Retrieval)'''
    )

    @api.depends(
        'employee_id',
        'sales_gate',
        'commission_sales',
        'retrival_gate',
        'commission_retrival',
    )
    def _compute_eligible_commission(self):
        for line in self:
            line.eligible_commission = 0.0

            if not line.employee_id:
                continue

            line.eligible_commission = (
                (line.sales_gate or 0.0)
                * (
                    (line.commission_sales or 0.0)
                    + (
                        (line.retrival_gate or 0.0)
                        * (line.commission_retrival or 0.0)
                    )
                )
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
        string='KPI Multiplier'
    )

    yrs = fields.Float(
        string='Years', 
        related="employee_id.tenure_years"
    )

    tenure_mult = fields.Float(
        string='Tenure Mult',
        compute='_compute_tenure_mult',
        store=True,
        digits=(5, 4),
        default=1,
        help="employee tenure_years (5 / 3) * 0.03"
    )

    @api.depends(
        'employee_id',
        'yrs',
    )
    def _compute_tenure_mult(self):
        for line in self:
            line.tenure_mult = 0.0

            if not line.employee_id:
                continue

            years = line.employee_id._tenure_bracket_years()

            # Excel:
            # 1 + MIN(0.12, INT(Yrs / 3) * 0.03)

            completed_3_year_periods = int(years / 3)

            tenure_increment = min(
                0.12,
                completed_3_year_periods * 0.03
            )

            line.tenure_mult = 1.0 + tenure_increment

            if line.territory_engine_id:
                line.territory_engine_id.total_tenure_mult = (
                    line.tenure_mult
                )

    sales_payout = fields.Float(
        string='Sales Payout',
        compute='_compute_sales_payout',
        store=True,
        help="""Normal Payout
                    =
                    Eligible Commission
                    × KPI Mult
                    × Tenure Mult
                    × Acceleration Factor
                    
                For Lead Premium Payout
                    =
                    Sales Gate
                    × Lead Premium
                    × Highest ASM Sub-base in Same Territory
                    
                Payout Before Cap
                    =
                    MAX(Normal Payout, Lead Premium Payout)
                    
                FINALLY
                Sales Payout
                =
                MIN(Payout Before Cap, Applicable Cap)
                
                LOGIC HERE IS 
                IF Sales Attain > Accel Kick-In
                    → Cap Stretch
                ELSE
                    → Cap Individual Max
                """
    )

    @api.depends(
        'employee_id',
        'sales_attain',
        'eligible_commission',
        'kpi_mult',
        'tenure_mult',
        'accel_factor',
        'sales_gate',
        'role_id',
        'role_id.role',
        'territory_id',
        'sub_base',

        # Territory configuration
        'territory_engine_id.sale_territory_config_ids',
        'territory_engine_id.sale_territory_config_ids.territory_id',
        'territory_engine_id.sale_territory_config_ids.accel_kick_in',
        'territory_engine_id.sale_territory_config_ids.cap_stretch',
        'territory_engine_id.sale_territory_config_ids.cap_indiv_max',
        'territory_engine_id.sale_territory_config_ids.lead_premium',

        # Required for MAXIFS equivalent
        'territory_engine_id.kprl_employee_engine_line_ids.territory_id',
        'territory_engine_id.kprl_employee_engine_line_ids.role_id',
        'territory_engine_id.kprl_employee_engine_line_ids.sub_base',
    )
    def _compute_sales_payout(self):
        for engine in self.mapped('territory_engine_id'):

            lines = engine.kprl_employee_engine_line_ids

            for line in lines:
                line.sales_payout = 0.0

                if not line.employee_id:
                    continue

                # ---------------------------------------------------------
                # Find configuration for this employee's territory
                # ---------------------------------------------------------
                config = engine.sale_territory_config_ids.filtered(
                    lambda c: c.territory_id == line.territory_id
                )[:1]

                if not config:
                    continue

                # ---------------------------------------------------------
                # Configuration values
                # ---------------------------------------------------------
                accel_kick_in = config.accel_kick_in or 0.0
                cap_stretch = config.cap_stretch or 0.0
                cap_indiv_max = config.cap_indiv_max or 0.0
                lead_premium = config.lead_premium or 0.0

                # ---------------------------------------------------------
                # Excel:
                #
                # IF(K18 > Accel_KickIn,
                #       Cap_Stretch,
                #       Cap_IndivMax)
                # ---------------------------------------------------------
                if line.sales_attain > accel_kick_in:
                    payout_cap = cap_stretch
                else:
                    payout_cap = cap_indiv_max

                # ---------------------------------------------------------
                # Excel:
                #
                # S18 * X18 * Z18 * AC18
                #
                # Eligible Commission
                # × KPI Mult
                # × Tenure Mult
                # × Accel Factor
                # ---------------------------------------------------------
                normal_payout = (
                    (line.eligible_commission or 0.0)
                    * (line.kpi_mult or 0.0)
                    * (line.tenure_mult or 0.0)
                    * (line.accel_factor or 0.0)
                )

                # ---------------------------------------------------------
                # Lead Premium
                # ---------------------------------------------------------
                lead_premium_payout = 0.0

                role = line.role_id.role if line.role_id else False

                # Your actual stored role value is used here.
                if role in ('rsm', 'rsm_asm'):

                    # Excel MAXIFS:
                    #
                    # MAX(
                    #   Sub-base
                    #   WHERE Territory = current Territory
                    #   AND Role = ASM
                    # )
                    # -----------------------------------------------------

                    asm_lines = lines.filtered(
                        lambda l:
                            l.territory_id == line.territory_id
                            and l.role_id
                            and l.role_id.role == 'asm'
                    )

                    max_asm_sub_base = max(
                        asm_lines.mapped('sub_base') or [0.0]
                    )

                    lead_premium_payout = (
                        (line.sales_gate or 0.0)
                        * lead_premium
                        * max_asm_sub_base
                    )

                # ---------------------------------------------------------
                # Excel:
                #
                # MAX(
                #     Normal Payout,
                #     Lead Premium Payout
                # )
                # ---------------------------------------------------------
                payout_before_cap = max(
                    normal_payout,
                    lead_premium_payout,
                )

                # ---------------------------------------------------------
                # Excel:
                #
                # MIN(
                #     Payout Before Cap,
                #     Payout Cap
                # )
                # ---------------------------------------------------------
                line.sales_payout = min(
                    payout_cap,
                    payout_before_cap,
                )


    sub_base = fields.Float(
        string='Sub-base',
        compute='_compute_sub_base',
        store=True,
        digits=(16, 2),
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'eligible_commission',
        'kpi_mult',
        'tenure_mult',
        'territory_id',
        'territory_engine_id.sale_territory_config_ids',
        'territory_engine_id.sale_territory_config_ids.territory_id',
        'territory_engine_id.sale_territory_config_ids.cap_indiv_max',
    )
    def _compute_sub_base(self):
        for line in self:
            line.sub_base = 0.0

            if not line.employee_id:
                continue

            role = line.role_id.role if line.role_id else False

            # Excel:
            # IF(D18="ASM", ...)
            if role != 'asm':
                continue

            # Get configuration for this employee's territory
            config = line.territory_engine_id.sale_territory_config_ids.filtered(
                lambda c: c.territory_id == line.territory_id
            )[:1]

            if not config:
                continue

            cap_indiv_max = config.cap_indiv_max or 0.0

            # Excel:
            # S18 * X18 * Z18
            base_amount = (
                (line.eligible_commission or 0.0)
                * (line.kpi_mult or 0.0)
                * (line.tenure_mult or 0.0)
            )

            # Excel:
            # MIN(Cap_IndivMax, S18*X18*Z18)
            line.sub_base = min(
                cap_indiv_max,
                base_amount,
            )

            # Update parent total
            if line.territory_engine_id:
                line.territory_engine_id.total_sub_base = line.sub_base

    accel_factor = fields.Float(
        string='Acceleration Factor',
        compute='_compute_accel_factor',
        store=True,
        digits=(5, 4),
        help="""e.g if Accel Kick-In = 1.00
        Accel Max     = 1.50
        Accel Boost   = 0.20
        Sales Attain = 1.25
        i.e (1.25 - 1.00) / (1.50 - 1.00)
        = 0.50
        Accel Factor = 1 + (0.20 × 0.50)
             = 1.10"""
    )

    @api.depends(
        'employee_id',
        'sales_attain',
        'territory_id',
        'territory_engine_id.sale_territory_config_ids',
        'territory_engine_id.sale_territory_config_ids.territory_id',
        'territory_engine_id.sale_territory_config_ids.accel_boost',
        'territory_engine_id.sale_territory_config_ids.accel_kick_in',
        'territory_engine_id.sale_territory_config_ids.accel_max',
    )
    def _compute_accel_factor(self):
        for line in self:
            line.accel_factor = 0.0

            if not line.employee_id:
                continue

            config = line.territory_engine_id.sale_territory_config_ids.filtered(
                lambda c: c.territory_id == line.territory_id
            )[:1]

            if not config:
                continue

            accel_boost = config.accel_boost or 0.0
            accel_kick_in = config.accel_kick_in or 0.0
            accel_max = config.accel_max or 0.0
            sales_attain = line.sales_attain or 0.0

            denominator = accel_max - accel_kick_in

            if not denominator:
                # Same idea as IFERROR protection for a zero denominator.
                median_value = 0.0
            else:
                value = (
                    sales_attain - accel_kick_in
                ) / denominator

                # Excel MEDIAN(0, value, 1)
                median_value = max(0.0, min(value, 1.0))

            line.accel_factor = (
                1.0 + (accel_boost * median_value)
            )

            if line.territory_engine_id:
                line.territory_engine_id.total_accel_factor = (
                    line.accel_factor
                )

    pk_effective = fields.Float(
        string='Effective Product Knowledge',
        compute='_compute_pk_effective',
        store=True,
        digits=(5, 2),
        help="""
    Controls how Product Knowledge is used in the KPI Multiplier calculation.

    ON:
    Product Knowledge scores are normalized across all employees in the
    current Territory Engine using:

        (Employee Prod Know - Minimum Prod Know)
        /
        (Maximum Prod Know - Minimum Prod Know)

    The result is restricted between 0 and 1.

    OFF:
    The original Product Knowledge score is used directly:

        PK Effective = Prod Know
    """,
    )

    @api.depends(
        'employee_id',
        'prod_know',
        'territory_engine_id.period_id',
        'territory_engine_id.kprl_employee_engine_line_ids.employee_id',
        'territory_engine_id.kprl_employee_engine_line_ids.prod_know',
    )
    def _compute_pk_effective(self):
        PerformanceInput = self.env['kprl.performance.input']

        for engine in self.mapped('territory_engine_id'):
            lines = engine.kprl_employee_engine_line_ids

            # Get performance configuration for this period
            performance = PerformanceInput.search([
                ('period_id', '=', engine.period_id.id),
            ], limit=1) if engine.period_id else False

            pk_norm = performance.pk_norm if performance else 'off'

            # Excel:
            # MINIFS(T, B, "?*")
            # MAXIFS(T, B, "?*")
            #
            # Only lines with an employee are considered.
            valid_lines = lines.filtered(
                lambda l: l.employee_id
            )

            prod_know_values = valid_lines.mapped('prod_know')

            min_prod_know = min(prod_know_values) if prod_know_values else 0.0
            max_prod_know = max(prod_know_values) if prod_know_values else 0.0

            denominator = max_prod_know - min_prod_know

            for line in lines:
                line.pk_effective = 0.0

                if not line.employee_id:
                    continue

                prod_know = line.prod_know or 0.0

                if pk_norm == 'on':
                    if denominator:
                        normalized_value = (
                            (prod_know - min_prod_know)
                            / denominator
                        )

                        # Excel MEDIAN(0, value, 1)
                        line.pk_effective = max(
                            0.0,
                            min(normalized_value, 1.0)
                        )
                    else:
                        # Equivalent to IFERROR(..., T18)
                        line.pk_effective = prod_know
                else:
                    # PK_Norm is not On
                    line.pk_effective = prod_know

                if line.territory_engine_id:
                    line.territory_engine_id.total_pk_effective = (
                        line.pk_effective
                    )

    rsm_territory_key = fields.Many2one(
        'kprl.territory',
        string='RSM Territory Key',
        compute='_compute_rsm_territory_key',
        store=True,
        help=(
            "RSM Territory Key is populated only when the employee's role "
            "is RSM or RSM + ASM. It uses the line's Territory.\n\n"
            "Calculation:\n"
            "• RSM (rsm) → RSM Territory Key = Territory\n"
            "• RSM + ASM (rsm_asm) → RSM Territory Key = Territory\n"
            "• All other roles → RSM Territory Key is empty."
        ),
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'territory_id',
    )
    def _compute_rsm_territory_key(self):
        for line in self:
            line.rsm_territory_key = False

            if not line.employee_id:
                continue

            role = line.role_id.role if line.role_id else False

            if role in ('rsm', 'rsm_asm'):
                line.rsm_territory_key = line.territory_id
    sales_floor = fields.Float(
        string='Sales Floor',
        compute='_compute_sales_floor',
        store=True,
        digits=(5, 4),
        help=(
            "Sales Floor is retrieved from the Role Parameter configuration "
            "using the employee's Sales Role.\n\n"
            "Calculation:\n"
            "• If Employee is empty → 0\n"
            "• Find the employee's Role in the Role Parameter configuration.\n"
            "• Return the Sales Floor configured for that Role.\n"
            "• If no matching Role is found → 0.\n\n"
            "Excel equivalent:\n"
            "IF(Employee='', '', "
            "IFERROR(INDEX(RP_SalesFloor, MATCH(Role, RP_Role, 0)), 0))"
        ),
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'role_id.sales_floor',
    )
    def _compute_sales_floor(self):
        for line in self:
            line.sales_floor = 0.0

            if not line.employee_id:
                continue

            if not line.role_id:
                continue

            line.sales_floor = line.role_id.sales_floor or 0.0
    min_sales = fields.Float(
        string='Minimum Sales',
        compute='_compute_min_sales',
        store=True,
        digits=(5, 4),
        help=(
            "Minimum Sales Attainment is retrieved from the employee's "
            "Sales Role configuration.\n\n"
            "Calculation:\n"
            "• If Employee is empty → 0\n"
            "• Find the employee's Sales Role in kprl.role.parameter.\n"
            "• Return the min_sales_attainment configured for that role.\n"
            "• If no role/configuration is found → 0.\n\n"
            "Excel equivalent:\n"
            "IF(Employee='', '', "
            "IFERROR(INDEX(RP_MinSales, MATCH(Role, RP_Role, 0)), 0))"
        ),
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'role_id.min_sales_attainment',
    )
    def _compute_min_sales(self):
        for line in self:
            line.min_sales = 0.0

            if not line.employee_id:
                continue

            if not line.role_id:
                continue

            line.min_sales = line.role_id.min_sales_attainment or 0.0

            if line.territory_engine_id:
                line.territory_engine_id.total_min_sales = line.min_sales

    retrival_floor = fields.Float(
        string='Retrival Floor',
        compute='_compute_retrival_floor',
        store=True,
        digits=(5, 4),
        help=(
            "Retrival Floor is retrieved from the employee's Sales Role "
            "configuration in kprl.role.parameter.\n\n"
            "Calculation:\n"
            "• If Employee is empty → 0\n"
            "• The employee's Sales Role is matched against the configured roles.\n"
            "• The retr_floor value configured for that role is returned.\n"
            "• If no role/configuration is found → 0.\n\n"
            "Excel equivalent:\n"
            "IF(Employee='', '', "
            "IFERROR(INDEX(RP_RetrFloor, MATCH(Role, RP_Role, 0)), 0))"
        ),
    )

    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'role_id.retr_floor',
    )
    def _compute_retrival_floor(self):
        for line in self:
            line.retrival_floor = 0.0

            if not line.employee_id:
                continue

            if not line.role_id:
                continue

            line.retrival_floor = line.role_id.retr_floor or 0.0

            if line.territory_engine_id:
                line.territory_engine_id.total_retrival_floor = (
                    line.retrival_floor
                )


    min_retrival = fields.Float(
        string='Minimum Retrival',
        compute='_compute_min_retrival',
        store=True,
        digits=(5, 4),
        help=(
            "Minimum Retrival Rate is retrieved from the employee's Sales Role "
            "configuration in kprl.role.parameter.\n\n"
            "Calculation:\n"
            "• If Employee is empty → 0.\n"
            "• The employee's Sales Role is matched against the configured roles.\n"
            "• The min_retrieval_rate configured for that role is returned.\n"
            "• If no role/configuration is found → 0.\n\n"
            "Excel equivalent:\n"
            "IF(Employee='', '', "
            "IFERROR(INDEX(RP_MinRetr, MATCH(Role, RP_Role, 0)), 0))"
        ),
    )
    @api.depends(
        'employee_id',
        'role_id',
        'role_id.role',
        'role_id.min_retrieval_rate',
    )
    def _compute_min_retrival(self):
        for line in self:
            line.min_retrival = 0.0

            if not line.employee_id:
                continue

            if not line.role_id:
                continue

            line.min_retrival = line.role_id.min_retrieval_rate or 0.0

            if line.territory_engine_id:
                line.territory_engine_id.total_min_retrival = (
                    line.min_retrival
                )

    own_target = fields.Float(
        string='Own Target'
    )

    kpi_mult = fields.Float(
        string='KPI Multiplier',
        compute='_compute_kpi_mult',
        store=True,
        digits=(5, 4),
    )

    @api.depends(
        'employee_id',
        'product_knowledge_score',
        'call_report_compliance',
        'customer_coverage_rate',
        'new_customer_acquisition',
        'call_rep',
        'coverage',
        'new_cust',
    )
    def _compute_kpi_mult(self):
        PerformanceInput = self.env['kprl.performance.input']

        for line in self:
            line.kpi_mult = 0.0

            if not line.employee_id:
                continue

            params = line.territory_engine_id.period_id.parameter_ids[:1] if line.territory_engine_id and line.territory_engine_id.period_id else False
            w_pk = (params.sales_pk_weight / 100.0) if params and params.sales_pk_weight else 0.40
            w_call = (params.sales_call_weight / 100.0) if params and params.sales_call_weight else 0.10
            w_cov = (params.sales_coverage_weight / 100.0) if params and params.sales_coverage_weight else 0.30
            w_new = (params.sales_new_cust_weight / 100.0) if params and params.sales_new_cust_weight else 0.20
            floor = params.kpi_multiplier_floor if params and params.kpi_multiplier_floor else 0.80
            rng = params.kpi_multiplier_range if params and params.kpi_multiplier_range else 0.40
            perf = PerformanceInput.search([('employee_id', '=', line.employee_id.id), ('period_id', '=', line.territory_engine_id.period_id.id)], limit=1) if line.territory_engine_id and line.territory_engine_id.period_id else False
            pk_norm_on = (params.pk_normalization_enabled if params else False) or ((perf.pk_norm == 'on') if perf else False)
            pk = line.product_knowledge_score or 0.0
            if pk_norm_on and line.territory_engine_id and line.territory_engine_id.period_id:
                peers = PerformanceInput.search([('period_id', '=', line.territory_engine_id.period_id.id)])
                vals = [pp.product_knowledge_score or 0.0 for pp in peers] + [pk]
                lo, hi = min(vals), max(vals)
                pk = ((pk - lo) / (hi - lo)) if hi > lo else pk
            weighted = (pk * w_pk) + ((line.call_report_compliance or 0.0) * w_call) + ((line.customer_coverage_rate or 0.0) * w_cov) + ((line.new_customer_acquisition or 0.0) * w_new)
            cap = floor + rng
            line.kpi_mult = max(floor, min(cap, floor + (weighted * rng)))
            if line.territory_engine_id:
                line.territory_engine_id.total_kpi_mult = line.kpi_mult