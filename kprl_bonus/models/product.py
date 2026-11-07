from odoo import models, fields, api


class Product(models.Model):
    _name = 'kprl.product'
    _description = 'Product SKU for Bonus Pool'
    _order = 'name'

    category_id = fields.Many2one('product.category', string='Product Category')
    name = fields.Char(string='Product Name', required=True)
    code = fields.Char(string='SKU Code')
    category = fields.Char(string='Category')
    unit_price = fields.Float(string='Unit Price', digits='Product Price')
    sku_rate = fields.Float(string='SKU Rate (%)', digits=(5, 4),
                            help='Percentage of unit price contributing to bonus pool')
   
    margin_pct = fields.Float(string='Margin (%)', digits=(5, 2))
    is_active = fields.Boolean(string='Active', default=True)

            