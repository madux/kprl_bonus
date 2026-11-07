from odoo import models, fields, api


class TenureMultiplier(models.Model):
    _name = 'kprl.tenure.multiplier'
    _description = 'Tenure Multiplier'
    _order = 'years_of_service'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    years_of_service = fields.Float(string='Years of Service', required=True,
                                    help='Minimum years of service for this tier')
    multiplier = fields.Float(string='Multiplier', digits=(5, 4), required=True,
                              default=1.0, help='Bonus multiplier based on tenure')
    note = fields.Char(string='Note')

    @api.depends('years_of_service')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.years_of_service:.0f}+ yrs"
