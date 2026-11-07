from odoo import models, fields, api


class DeferredLedger(models.Model):
    _name = 'kprl.deferred.ledger'
    _description = 'Deferred Bonus Ledger'
    _order = 'vest_date, employee_id'

    employee_id = fields.Many2one('kprl.employee', string='Employee',
                                  required=True)
    period_id = fields.Many2one('kprl.bonus.period', string='Period')
    grade_id = fields.Many2one(related='employee_id.grade_id', string='Grade',
                               store=True)

    calculated_bonus = fields.Float(string='Calculated Bonus', digits='Product Price')
    deferral_rate = fields.Float(string='Deferral Rate (%)', digits=(5, 4))
    deferred_amount = fields.Float(string='Deferred Amount', digits='Product Price')
    vest_date = fields.Date(string='Vesting Date')
    status = fields.Selection([
        ('deferred', 'Deferred'),
        ('vested', 'Vested'),
        ('forfeited', 'Forfeited'),
    ], string='Status', default='deferred', required=True)
    is_senior_mgmt = fields.Boolean(string='Senior Management', default=False)
    note = fields.Text(string='Notes')
    aip_pool_id = fields.Many2one('kprl.aip.pool', string='AIP Pool')
    clawback_event_id = fields.Many2one('kprl.governance.event', string='Clawback Event', readonly=True,
        help='Governance event whose forfeit action consumed this entry. Blank on older rows.')
    source = fields.Selection([('quarterly', 'Quarterly'), ('aip', 'AIP')], string='Source', default='quarterly')

    def action_vest(self):
        self.status = 'vested'

    def action_forfeit(self):
        self.status = 'forfeited'