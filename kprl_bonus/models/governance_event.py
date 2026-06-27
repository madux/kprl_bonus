from odoo import models, fields, api


class GovernanceEvent(models.Model):
    _name = 'kprl.governance.event'
    _description = 'Governance Event (Malus/Clawback)'
    _order = 'create_date desc'

    name = fields.Char(string='Event Reference', compute='_compute_name',
                       store=True)
    employee_id = fields.Many2one('kprl.employee', string='Employee')
    period_id = fields.Many2one('kprl.bonus.period', string='Period')
    trigger_type = fields.Selection([
        ('malus', 'Malus'),
        ('clawback', 'Clawback'),
    ], string='Trigger Type', required=True)
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Severity', default='medium')
    stage = fields.Selection([
        ('open', 'Open'),
        ('investigation', 'Under Investigation'),
        ('resolved', 'Resolved'),
    ], string='Stage', default='open')
    malus_pct = fields.Float(string='Malus (%)', digits=(5, 2))
    clawback_amount = fields.Float(string='Clawback Amount', digits='Product Price')
    description = fields.Text(string='Description', required=True)
    status = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], string='Status', default='open')
    closed_by = fields.Many2one('res.users', string='Closed By')
    closed_date = fields.Datetime(string='Closed Date')
    approver_notes = fields.Text(string='Approver Notes')

    @api.depends('trigger_type', 'employee_id', 'create_date')
    def _compute_name(self):
        for rec in self:
            emp = rec.employee_id.name or 'N/A'
            rec.name = f"{rec.trigger_type.upper()} - {emp}"
