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
