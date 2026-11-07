from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleTerritoryConfig(models.Model):
    _name = 'sale.territory.config'
    _description = 'Sales Territory Configuration'
    _order = 'territory_id'

    territory_engine_id = fields.Many2one(
        'kprl.territory.engine',
        string='Territory Engine',
        required=True,
        ondelete='cascade',
        index=True,
    )

    territory_id = fields.Many2one(
        'kprl.territory',
        string='Territory',
        required=True,
        index=True,
    )

    accel_kick_in = fields.Float(
        string='Acceleration Kick-In',
        default=1.0,
        digits=(5, 4),
    )
    accel_max = fields.Float(
            string='Maximum Acceleration ',
            default=1.0,
            digits=(5, 4),
        )
    
    cap_stretch = fields.Float(
        string='Stretch Cap',
        default=0.0,
        digits=(16, 2),
    )

    cap_indiv_max = fields.Float(
        string='Individual Maximum Cap',
        default=0.0,
        digits=(16, 2),
    )

    lead_premium = fields.Float(
        string='Lead Premium',
        default=0.0,
        digits=(16, 2),
    )
    accel_boost = fields.Float(
        string='Acceleration Boost',
        default=0.0,
        digits=(5, 4),
        help='Acceleration boost applied when Sales Attain exceeds the Acceleration Kick-In threshold.',
    )

    _sql_constraints = [
        (
            'territory_engine_territory_unique',
            'unique(territory_engine_id, territory_id)',
            'A territory configuration can only be defined once for the same Territory Engine.',
        ),
    ]