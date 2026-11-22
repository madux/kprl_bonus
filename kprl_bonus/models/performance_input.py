from odoo import models, fields, api


class PerformanceInput(models.Model):
    _name = 'kprl.performance.input'
    _description = 'Employee Performance Input'
    _rec_name = 'employee_id'

    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    employee_id = fields.Many2one('kprl.employee', string='Employee',
                                  required=True)
    department_id = fields.Many2one(related='employee_id.department_id',
                                    string='Department', store=True)
    period_end = fields.Date(related='period_id.date_end', store=True, index=True)

    appraisal_score = fields.Float(string='Appraisal Score', digits=(5, 2))
    retain_score = fields.Float(string='Retain Score', digits=(5, 2))
    own_target = fields.Float(string='Own Target', digits='Product Price')
    own_sales = fields.Float(string='Own Sales', digits='Product Price')
    own_revenue = fields.Float(string='Own Revenue', digits='Product Price')
    own_retrievals = fields.Float(string='Own Retrievals', digits='Product Price')
    prod_pct = fields.Float(string='Productivity (%)', digits=(5, 2))
    call_pct = fields.Float(string='Call Rate (%)', digits=(5, 2))
    present_pct = fields.Float(string='Presentation (%)', digits=(5, 2))
    team_pct = fields.Float(string='Behaviour (/25)', digits=(5, 2),
        help='Behavioural score out of 25 (workbook column Behav /25). Drives the behaviour multiplier.')
    potential_assessment_score = fields.Float(string='Potential Assessment', digits=(5, 2),
        help='PMS potential assessment score per employee (raw value as returned by the PMS API).')
    current_assessment_score = fields.Float(string='Current Assessment', digits=(5, 2),
        help='PMS current assessment score per employee (raw value as returned by the PMS API).')
    prod_know = fields.Float(
            string='Prod Know'
        )
    kpi_mult_floor = fields.Float(
                string='Multi Floor',
                default=0.80
            )
    kpi_mult_range = fields.Float(
                string='Multi Range', 
                default=0.40
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

    pk_norm = fields.Selection(
        [
            ('on', 'On'),
            ('off', 'Off'),
        ],
        string='Product Knowledge Normalization',
        default='off',
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
    
    # Territory data for RSM calculations
    territory_sales = fields.Float(string='Territory Sales', digits='Product Price',
                                   help='Total territory sales for RSM calculations')
    territory_retrievals = fields.Float(string='Territory Retrievals', digits='Product Price',
                                        help='Total territory retrievals for RSM calculations')
    territory_target = fields.Float(string='Territory Target', digits='Product Price',
                                   help='Territory target for RSM calculations')

    accel_kick_in = fields.Float(
        string='Acceleration Kick-In',
        default=1.0,
        digits=(5, 4),
        help='Sales attainment level at which the accelerated payout cap applies.',
    )

    cap_stretch = fields.Float(
        string='Stretch Cap',
        default=0.0,
        digits=(16, 2),
        help='Maximum sales payout allowed when sales attainment exceeds the acceleration kick-in.',
    )

    cap_indiv_max = fields.Float(
        string='Individual Maximum Cap',
        default=0.0,
        digits=(16, 2),
        help='Maximum individual sales payout before reaching the acceleration kick-in.',
    )

    lead_premium = fields.Float(
        string='Lead Premium',
        default=0.0,
        digits=(16, 2),
        help='Premium applied to the highest ASM sub-base for RM and RSM+ASM roles.',
    )
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('employee_period_unique', 'UNIQUE(employee_id, period_id)',
         'An employee can only have one performance record per period!'),
    ]
