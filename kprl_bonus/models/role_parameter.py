from odoo import models, fields, api


class RoleParameter(models.Model):
    _name = 'kprl.role.parameter'
    _description = 'Sales Role Parameters'
    _rec_name = 'role'

    role = fields.Selection([
        ('gm', 'GM'),
        ('nsm', 'NSM'),
        ('headtech', 'Head Tech'),
        ('rsm', 'RSM'),
        ('asm', 'ASM'),
        ('rsm_asm', 'RSM + ASM'),
    ], string='Sales Role', required=True)
    sales_floor = fields.Float(
        string='Sales Floor',
        default=0.0,
        digits=(5, 4),
        help=(
            "Minimum Sales Attainment Floor configured for this role. "
            "This value is used by the Territory Engine to calculate "
            "the Sales Gate.\n\n"
            "Excel equivalent:\n"
            "INDEX(RP_SalesFloor, MATCH(Role, RP_Role, 0))"
        ),
    )
    # Gate thresholds according to specification
     
    min_sales_attainment = fields.Float(string='Min Sales Attainment', digits=(5, 4),
                                       help='Full credit point for sales attainment')
    retr_floor = fields.Float(string='Retrieval Entry Floor', digits=(5, 4),
                              help='Minimum retrieval rate for entry gate (ramp start)')
    min_retrieval_rate = fields.Float(string='Min Retrieval Rate', digits=(5, 4),
                                      help='Full credit point for retrieval rate')
    
    # Pool shares
    pool_share = fields.Float(string='Pool Share (%)', digits=(5, 4),
                             help='Effective share of gross commission pot')
    
    # Legacy fields (for backward compatibility)
    sales_eligibility = fields.Float(string='Sales Eligibility (%)', digits=(5, 2))
    retrieval_eligibility = fields.Float(string='Retrieval Eligibility (%)',
                                         digits=(5, 2))
    sales_commission_rate = fields.Float(string='Sales Commission Rate (%)',
                                         digits=(5, 4))
    product_pool_share = fields.Float(string='Product Pool Share (%)', digits=(5, 4))
    commission_share = fields.Float(string='Commission Share (%)', digits=(5, 4))
    dual_role_cap = fields.Float(string='Dual Role Cap (%)', digits=(5, 2))
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('role_unique', 'UNIQUE(role)', 'Each role can only have one parameter set!'),
    ]
