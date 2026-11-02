from odoo import models, fields, api


class ProductPool(models.Model):
    _name = 'kprl.product.pool'
    _description = 'Product Pool Contribution'
    _rec_name = 'product_id'

    product_id = fields.Many2one('kprl.product', string='Product',
                                 required=True)
    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    quantity_units = fields.Float(string='Quantity Units', digits='Product UoM')
    unit_price = fields.Float(string='Unit Price', digits='Product Price')
    sku_rate = fields.Float(string='SKU Rate (%)', digits=(5, 4))
    quantity_revenue = fields.Float(string='Quantity Revenue',
                                    digits='Product Price',
                                    compute='_compute_revenue', store=True)
    pool_contribution = fields.Float(string='Pool Contribution',
                                     digits='Product Price',
                                     compute='_compute_pool_contrib', store=True)

    quarterly_revenue = fields.Float(string='Quarterly Revenue', digits=(5, 2), compute='_compute_quarterly_revenue')

    _sql_constraints = [
        ('product_period_unique', 'UNIQUE(product_id, period_id)',
         'A product can only have one pool entry per period!'),
    ]

    @api.depends('quantity_units', 'unit_price')
    def _compute_revenue(self):
        for rec in self:
            rec.quantity_revenue = rec.quantity_units * rec.unit_price

    @api.depends('quantity_revenue', 'sku_rate')
    def _compute_pool_contrib(self):
        for rec in self:
            rec.pool_contribution = rec.quantity_revenue * (rec.sku_rate / 100.0)

    @api.depends('quantity_units', 'unit_price')
    def _compute_quarterly_revenue(self):
        for record in self:
            record.quarterly_revenue = record.quantity_units * record.unit_price