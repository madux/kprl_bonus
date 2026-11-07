from odoo import models, fields, api

class AuditTrail(models.Model):
    _name = 'kprl.audit.trail'
    _description = 'Audit Trail Entry'
    _order = 'timestamp desc '

    name = fields.Char(string='Action', required=True)
    user_id = fields.Many2one('res.users', string='User',
                               default=lambda self: self.env.user)
    timestamp = fields.Datetime(string='Timestamp',
                                 default=fields.Datetime.now)
    event_id = fields.Many2one('kprl.governance.event',
                                string='Related Event')
    category = fields.Selection([
        ('system', 'System'),
        ('user', 'User Action'),
        ('approval', 'Approval'),
        ('investigation', 'Investigation'),
    ], string='Category', default='user')

    employee_id = fields.Many2one('kprl.employee', string='Employee', index=True)
    grade_old_id = fields.Many2one('kprl.grade', string='Old Grade')
    grade_new_id = fields.Many2one('kprl.grade', string='New Grade')
    detail = fields.Text(string='Details')