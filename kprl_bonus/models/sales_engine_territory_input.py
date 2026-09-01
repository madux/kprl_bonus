from odoo import models, fields, api


class sales_engine_territory_input(models.Model):
    _name = 'sales_engine.territory_input'
    _description = 'Sales Sale engine territory input'
    
    _rec_name = 'employee_id'
    _order = 'period_id desc, employee_id'

    period_id = fields.Many2one('kprl.bonus.period', string='Period', required=True)
     
    role_type = fields.Selection([
        ('gm', 'GM'),
        ('nsm', 'NSM'),
        ('headtech', 'Head Tech'),
        ('rsm', 'RSM'),
        ('asm', 'ASM'),
        ('rsm_asm', 'RSM + ASM'),
    ], string='Role Type', store=True)
    territory_id = fields.Many2one('kprl.territory', string='Territory', 
                                  related='employee_id.territory_id', store=True,
                                  required=True)

    # Performance inputs
    own_target = fields.Float(string='Own Target', digits='Product Price', compute="employee_performance_input")
    own_sales = fields.Float(string='Own Sales', digits='Product Price', compute="employee_performance_input")
    own_retrievals = fields.Float(string='Own Retrievals', digits='Product Price', compute="employee_performance_input")
    territory_sales = fields.Float(string='Territory Sales', digits='Product Price', compute="employee_performance_input")
    territory_retrievals = fields.Float(string='Territory Retrievals', digits='Product Price', compute="employee_performance_input")
    territory_target = fields.Float(string='Territory Target', digits='Product Price', compute="employee_performance_input")

    @api.depends('period_id', 'employee_id')
    def employee_performance_input(self):
        perf_input = self.env['kprl.performance.input'].sudo()
        employee_perf_input=perf_input.search([('period_id', '=', self.period_id.id), ('employee_id', '=', self.employee_id.id)], limit=1)

        self.own_target = employee_perf_input.own_target
        self.own_sales = employee_perf_input.own_sales
        self.own_retrievals = employee_perf_input.own_retrievals
    # Attainment calculations
    sales_attainment = fields.Float(string='Sales Attainment (%)', digits=(5, 4),
                                   compute='_compute_attainment', store=True)
    retrieval_rate = fields.Float(string='Retrieval Rate (%)', digits=(5, 4),
                                  compute='_compute_attainment', store=True)

    # Gate calculations
    sales_gate = fields.Float(string='Sales Gate', digits=(5, 4),
                             compute='_compute_gates', store=True)
    retrieval_gate = fields.Float(string='Retrieval Gate', digits=(5, 4),
                                 compute='_compute_gates', store=True)

    # Commission calculations
    effective_pool_share = fields.Float(string='Effective Pool Share', digits=(5, 4),
                                       compute='_compute_commission', store=True)
    comm_sales = fields.Float(string='Commission Sales (₦)', digits='Product Price',
                             compute='_compute_commission', store=True)
    comm_retrieval = fields.Float(string='Commission Retrieval (₦)', digits='Product Price',
                                  compute='_compute_commission', store=True)
    gross_commission = fields.Float(string='Gross Commission (₦)', digits='Product Price',
                                   compute='_compute_commission', store=True)
    eligible_commission = fields.Float(string='Eligible Commission (₦)', digits='Product Price',
                                      compute='_compute_eligible_commission', store=True)

    # KPI calculations
    product_knowledge_score = fields.Float(string='Product Knowledge', digits=(5, 4))
    call_report_compliance = fields.Float(string='Call Report Compliance', digits=(5, 4))
    customer_coverage_rate = fields.Float(string='Customer Coverage', digits=(5, 4))
    new_customer_acquisition = fields.Float(string='New Customer Acquisition', digits=(5, 4))
    
    weighted_kpi_score = fields.Float(string='Weighted KPI Score', digits=(5, 4),
                                      compute='_compute_kpi_multiplier', store=True)
    kpi_multiplier = fields.Float(string='KPI Multiplier', digits=(5, 4),
                                 compute='_compute_kpi_multiplier', store=True)

    # Final calculations
    tenure_multiplier = fields.Float(string='Tenure Multiplier', digits=(5, 4),
                                    compute='_compute_tenure_multiplier', store=True)
    accelerator_factor = fields.Float(string='Accelerator Factor', digits=(5, 4),
                                     compute='_compute_accelerator', store=True)
    final_sales_payout = fields.Float(string='Final Sales Payout (₦)', digits='Product Price',
                                     compute='_compute_final_payout', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('finalized', 'Finalized'),
    ], string='Status', default='draft')

    _sql_constraints = [
        ('employee_period_unique', 'UNIQUE(employee_id, period_id)',
         'An employee can only have one sales engine record per period!'),
    ]

    @api.depends('own_sales', 'own_target', 'territory_sales', 'territory_target',
                 'own_retrievals', 'territory_retrievals', 'role_type')
    def _compute_attainment(self):
        for rec in self:
            if rec.role_type in ['rsm', 'rsm_asm']:
                # RSM uses territory figures
                base_target = rec.territory_target or 1.0
                base_sales = rec.territory_sales or 0.0
                base_retrievals = rec.territory_retrievals or 0.0
            elif rec.role_type in ['gm', 'nsm', 'headtech']:
                # Top management uses national figures (from period)
                base_target = rec.period_id.national_sales_target or 1.0
                base_sales = rec.period_id.national_actual_sales or 0.0
                base_retrievals = rec.period_id.national_actual_retrievals or 0.0
            else:
                # ASM uses personal figures
                base_target = rec.own_target or 1.0
                base_sales = rec.own_sales or 0.0
                base_retrievals = rec.own_retrievals or 0.0

            rec.sales_attainment = (base_sales / base_target) if base_target > 0 else 0.0
            rec.retrieval_rate = (base_retrievals / base_sales) if base_sales > 0 else 0.0

    @api.depends('sales_attainment', 'retrieval_rate', 'role_type', 'period_id')
    def _compute_gates(self):
        for rec in self:
            # Get role parameters from period's parameter configuration
            params = rec.period_id.parameter_ids if rec.period_id else None
            if not params:
                rec.sales_gate = 0.0
                rec.retrieval_gate = 0.0
                continue

            # Get role-specific thresholds
            role_params = self._get_role_parameters(rec.role_type, params)
            sales_floor = role_params.get('sales_floor', 0.65)
            sales_min = role_params.get('sales_min', 0.70)
            retr_floor = role_params.get('retr_floor', 0.70)
            retr_min = role_params.get('retr_min', 0.70)

            # Sales gate calculation (ramp logic)
            if rec.sales_attainment < sales_floor:
                rec.sales_gate = 0.0
            elif sales_floor <= rec.sales_attainment < sales_min:
                rec.sales_gate = (rec.sales_attainment - sales_floor) / (sales_min - sales_floor)
            else:
                rec.sales_gate = 1.0

            # Retrieval gate calculation (secondary gate)
            if rec.retrieval_rate < retr_floor:
                rec.retrieval_gate = 0.0
            elif retr_floor <= rec.retrieval_rate < retr_min:
                rec.retrieval_gate = (rec.retrieval_rate - retr_floor) / (retr_min - retr_floor)
            else:
                rec.retrieval_gate = 1.0

    def _get_role_parameters(self, role_type, params):
        """Get role-specific parameters from the parameter configuration"""
        # Primary source: Control Panel B34-B39 (Section C) — Finance + HR Director
        if params:
            # Map B34-B39 to role-specific mins per Sec1C
            if role_type in ('gm', 'nsm', 'headtech'):
                sales_min = (params.b34_top_mgmt_min_sales_attainment / 100.0) if getattr(params, 'b34_top_mgmt_min_sales_attainment', None) else 0.65
                retr_min = (params.b35_top_mgmt_min_retrieval_rate / 100.0) if getattr(params, 'b35_top_mgmt_min_retrieval_rate', None) else 0.75
            elif role_type == 'rsm':
                sales_min = (params.b36_rsm_min_territory_sales_attainment / 100.0) if getattr(params, 'b36_rsm_min_territory_sales_attainment', None) else 0.75
                retr_min = (params.b37_rsm_min_territory_retrieval_rate / 100.0) if getattr(params, 'b37_rsm_min_territory_retrieval_rate', None) else 0.75
            elif role_type == 'asm':
                sales_min = (params.b38_asm_min_personal_sales_attainment / 100.0) if getattr(params, 'b38_asm_min_personal_sales_attainment', None) else 0.70
                retr_min = (params.b39_asm_min_personal_retrieval_rate / 100.0) if getattr(params, 'b39_asm_min_personal_retrieval_rate', None) else 0.70
            elif role_type == 'rsm_asm':
                # RSM+ASM dual uses RSM thresholds per Sec K (same as B36/B37)
                sales_min = (params.b36_rsm_min_territory_sales_attainment / 100.0) if getattr(params, 'b36_rsm_min_territory_sales_attainment', None) else 0.75
                retr_min = (params.b37_rsm_min_territory_retrieval_rate / 100.0) if getattr(params, 'b37_rsm_min_territory_retrieval_rate', None) else 0.75
            else:
                sales_min = retr_min = None
            if sales_min is not None:
                # Floors from Control Panel H/K (Sec H v9, K v15)
                if role_type in ('gm', 'nsm', 'headtech'):
                    sales_floor = (params.h1_top_mgmt_sales_floor / 100.0) if getattr(params, 'h1_top_mgmt_sales_floor', None) else 0.50
                    retr_floor = (params.h4_top_mgmt_retrieval_floor / 100.0) if getattr(params, 'h4_top_mgmt_retrieval_floor', None) else 0.65
                elif role_type == 'rsm':
                    sales_floor = (params.h2_rsm_sales_floor / 100.0) if getattr(params, 'h2_rsm_sales_floor', None) else 0.65
                    retr_floor = (params.h5_rsm_retrieval_floor / 100.0) if getattr(params, 'h5_rsm_retrieval_floor', None) else 0.70
                elif role_type == 'asm':
                    sales_floor = (params.h3_asm_sales_floor / 100.0) if getattr(params, 'h3_asm_sales_floor', None) else 0.65
                    retr_floor = (params.h6_asm_retrieval_floor / 100.0) if getattr(params, 'h6_asm_retrieval_floor', None) else 0.70
                elif role_type == 'rsm_asm':
                    sales_floor = (params.k3_dual_sales_floor / 100.0) if getattr(params, 'k3_dual_sales_floor', None) else 0.65
                    retr_floor = (params.k4_dual_retrieval_floor / 100.0) if getattr(params, 'k4_dual_retrieval_floor', None) else 0.70
                else:
                    sales_floor = retr_floor = 0.65
                role_param = self.env['kprl.role.parameter'].search([('role', '=', role_type)], limit=1)
                if role_param:
                    # Role table pool_share still authoritative per Sec B/Table5
                    return {
                        'sales_floor': sales_floor,
                        'sales_min': sales_min,
                        'retr_floor': retr_floor,
                        'retr_min': retr_min,
                        'pool_share': (role_param.pool_share or 0.0) / 100.0 if role_param.pool_share else 0.0
                    }
        # Fallback: role parameter table only
        role_param = self.env['kprl.role.parameter'].search([
            ('role', '=', role_type)
        ], limit=1)
        if role_param:
            return {
                'sales_floor': role_param.sales_floor or 0.65,
                'sales_min': role_param.min_sales_attainment or 0.70,
                'retr_floor': role_param.retr_floor or 0.70,
                'retr_min': role_param.min_retrieval_rate or 0.70,
                'pool_share': (role_param.pool_share or 0.0) / 100.0 if role_param.pool_share else 0.0
            }
        
        # Fallback to hardcoded values from specification
        role_param_map = {
            'gm': {
                'sales_floor': 0.50, 'sales_min': 0.65,
                'retr_floor': 0.65, 'retr_min': 0.75,
                'pool_share': 0.10
            },
            'nsm': {
                'sales_floor': 0.50, 'sales_min': 0.65,
                'retr_floor': 0.65, 'retr_min': 0.75,
                'pool_share': 0.08
            },
            'headtech': {
                'sales_floor': 0.50, 'sales_min': 0.65,
                'retr_floor': 0.65, 'retr_min': 0.75,
                'pool_share': 0.05
            },
            'rsm': {
                'sales_floor': 0.65, 'sales_min': 0.75,
                'retr_floor': 0.70, 'retr_min': 0.75,
                'pool_share': 0.22
            },
            'rsm_asm': {
                'sales_floor': 0.65, 'sales_min': 0.75,
                'retr_floor': 0.70, 'retr_min': 0.75,
                'pool_share': 0.4235  # Derived from dual role factor
            },
            'asm': {
                'sales_floor': 0.65, 'sales_min': 0.70,
                'retr_floor': 0.70, 'retr_min': 0.70,
                'pool_share': 0.55
            },
        }
        return role_param_map.get(role_type, {})

    @api.depends('period_id', 'role_type', 'sales_gate', 'retrieval_gate')
    def _compute_commission(self):
        for rec in self:
            params = rec.period_id.parameter_ids if rec.period_id else None
            if not params:
                rec.effective_pool_share = 0.0
                rec.comm_sales = 0.0
                rec.comm_retrieval = 0.0
                rec.gross_commission = 0.0
                continue

            role_params = self._get_role_parameters(rec.role_type, params)
            pool_share = role_params.get('pool_share', 0.0)
            rec.effective_pool_share = pool_share

            # Get national sales and retrievals from period
            national_sales = rec.period_id.national_actual_sales or 0.0
            national_retrievals = rec.period_id.national_actual_retrievals or 0.0

            # Commission rates from parameters
            sales_comm_rate = params.sales_commission_rate / 100.0 if params.sales_commission_rate else 0.003
            retr_comm_rate = params.retrieval_commission_rate / 100.0 if params.retrieval_commission_rate else 0.007

            # Calculate commission components
            rec.comm_sales = national_sales * pool_share * sales_comm_rate
            rec.comm_retrieval = national_retrievals * pool_share * retr_comm_rate
            rec.gross_commission = rec.comm_sales + rec.comm_retrieval

    @api.depends('comm_sales', 'comm_retrieval', 'sales_gate', 'retrieval_gate')
    def _compute_eligible_commission(self):
        for rec in self:
            # Sales gate is master entry gate - if zero, both legs are killed
            if rec.sales_gate == 0.0:
                rec.eligible_commission = 0.0
            else:
                # Retrieval gate is secondary and only applies to retrieval leg
                eligible_sales = rec.comm_sales * rec.sales_gate
                eligible_retr = rec.comm_retrieval * rec.sales_gate * rec.retrieval_gate
                rec.eligible_commission = eligible_sales + eligible_retr

    @api.depends('product_knowledge_score', 'call_report_compliance',
                 'customer_coverage_rate', 'new_customer_acquisition', 'period_id')
    def _compute_kpi_multiplier(self):
        for rec in self:
            params = rec.period_id.parameter_ids if rec.period_id else None
            
            # KPI weights from parameters (with defaults from specification)
            pk_weight = params.sales_pk_weight / 100.0 if params and params.sales_pk_weight else 0.40
            call_weight = params.sales_call_weight / 100.0 if params and params.sales_call_weight else 0.10
            cov_weight = params.sales_coverage_weight / 100.0 if params and params.sales_coverage_weight else 0.30
            new_weight = params.sales_new_cust_weight / 100.0 if params and params.sales_new_cust_weight else 0.20

            # Calculate weighted KPI score
            weighted_score = (
                (rec.product_knowledge_score or 0.0) * pk_weight +
                (rec.call_report_compliance or 0.0) * call_weight +
                (rec.customer_coverage_rate or 0.0) * cov_weight +
                (rec.new_customer_acquisition or 0.0) * new_weight
            )
            rec.weighted_kpi_score = weighted_score

            # KPI Multiplier = J1 + (Weighted KPI Score × J2)
            # Get parameters with defaults from specification
            kpi_floor = params.kpi_multiplier_floor if params else 0.80
            kpi_range = params.kpi_multiplier_range if params else 0.40
            
            kpi_mult = kpi_floor + (weighted_score * kpi_range)
            # Clamp to range
            rec.kpi_multiplier = max(kpi_floor, min(kpi_floor + kpi_range, kpi_mult))

    @api.depends('employee_id')
    def _compute_tenure_multiplier(self):
        for rec in self:
            tenure_years = rec.employee_id.tenure_years or 0.0
            
            # Use the tenure multiplier lookup table
            tenure_records = self.env['kprl.tenure.multiplier'].search([
                ('years_of_service', '<=', tenure_years)
            ], order='years_of_service desc', limit=1)
            
            if tenure_records:
                rec.tenure_multiplier = tenure_records.multiplier
            else:
                # Fallback to specification lookup table
                if tenure_years < 3:
                    rec.tenure_multiplier = 1.00
                elif tenure_years < 6:
                    rec.tenure_multiplier = 1.03
                elif tenure_years < 9:
                    rec.tenure_multiplier = 1.06
                elif tenure_years < 12:
                    rec.tenure_multiplier = 1.09
                elif tenure_years < 15:
                    rec.tenure_multiplier = 1.12
                else:
                    rec.tenure_multiplier = 1.12  # Cap at 15+ years

    @api.depends('sales_attainment', 'period_id')
    def _compute_accelerator(self):
        for rec in self:
            params = rec.period_id.parameter_ids if rec.period_id else None
            if not params:
                rec.accelerator_factor = 1.0
                return

            # Accelerator params from Control Panel I (Sec I v10)
            kick_in = (params.i1_accelerator_kick_in / 100.0) if getattr(params, 'i1_accelerator_kick_in', None) else 1.00
            ceiling = (params.i2_accelerator_ceiling / 100.0) if getattr(params, 'i2_accelerator_ceiling', None) else 1.50
            boost = (params.i3_accelerator_boost / 100.0) if getattr(params, 'i3_accelerator_boost', None) else 0.50
            
            if rec.sales_attainment < kick_in:
                rec.accelerator_factor = 1.0
            elif rec.sales_attainment >= ceiling:
                rec.accelerator_factor = 1.5
            else:
                # Linear ramp from 1.0 to 1.5
                rec.accelerator_factor = 1.0 + ((rec.sales_attainment - kick_in) / (ceiling - kick_in)) * boost

    @api.depends('eligible_commission', 'kpi_multiplier', 'tenure_multiplier', 'accelerator_factor')
    def _compute_final_payout(self):
        for rec in self:
            rec.final_sales_payout = (
                rec.eligible_commission *
                rec.kpi_multiplier *
                rec.tenure_multiplier *
                rec.accelerator_factor
            )

    def action_compute(self):
        """Compute all sales engine calculations"""
        for rec in self:
            rec._compute_attainment()
            rec._compute_gates()
            rec._compute_commission()
            rec._compute_eligible_commission()
            rec._compute_kpi_multiplier()
            rec._compute_tenure_multiplier()
            rec._compute_accelerator()
            rec._compute_final_payout()
            rec.state = 'computed'

    def action_finalize(self):
        self.action_compute()
        self.state = 'finalized'

    @api.onchange('employee_id', 'period_id')
    def _onchange_fetch_performance(self):
        """Fetch performance data when employee or period changes"""
        if self.employee_id and self.period_id:
            perf = self.env['kprl.performance.input'].search([
                ('employee_id', '=', self.employee_id.id),
                ('period_id', '=', self.period_id.id),
            ], limit=1)
            if perf:
                self.own_target = perf.own_target
                self.own_sales = perf.own_sales
                self.own_retrievals = perf.own_retrievals
                self.territory_sales = perf.territory_sales
                self.territory_retrievals = perf.territory_retrievals
                self.territory_target = perf.territory_target
                self.product_knowledge_score = perf.product_knowledge_score
                self.call_report_compliance = perf.call_report_compliance
                self.customer_coverage_rate = perf.customer_coverage_rate
                self.new_customer_acquisition = perf.new_customer_acquisition