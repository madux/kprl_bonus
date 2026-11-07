from odoo import models, fields, api


class RiskRegister(models.Model):
    _name = 'kprl.risk.register'
    _description = 'Risk Register'
    _order = 'create_date desc'
    _rec_name = 'risk_description'

    ref = fields.Char(string='Risk Ref', compute='_compute_ref', store=True)
    date = fields.Date(string='Date Identified', default=fields.Date.context_today)
    risk_description = fields.Text(string='Risk Description', required=True)
    category = fields.Char(string='Category')
    impact = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Impact', default='medium')
    likelihood = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Likelihood', default='medium')
    rating = fields.Char(string='Risk Rating', compute='_compute_rating',
                         store=True)
    control_owner = fields.Char(string='Control Owner')
    risk_owner = fields.Char(string='Risk Owner')
    mitigation = fields.Text(string='Mitigation Plan')
    notes = fields.Text(string='Notes')
    status = fields.Selection([
        ('open', 'Open'),
        ('monitoring', 'Monitoring'),
        ('closed', 'Closed'),
    ], string='Status', default='open')

    @api.depends('create_date')
    def _compute_ref(self):
        for rec in self:
            if rec.create_date:
                year = rec.create_date.year
                seq = str(rec.id).zfill(3)
                rec.ref = f"RSK-{year}-{seq}"
            else:
                rec.ref = f"RSK-0000-{rec.id}"

    @api.depends('impact', 'likelihood')
    def _compute_rating(self):
        matrix = {
            ('low', 'low'): 'Low',
            ('low', 'medium'): 'Low',
            ('low', 'high'): 'Medium',
            ('medium', 'low'): 'Low',
            ('medium', 'medium'): 'Medium',
            ('medium', 'high'): 'High',
            ('high', 'low'): 'Medium',
            ('high', 'medium'): 'High',
            ('high', 'high'): 'Critical',
            ('critical', 'low'): 'High',
            ('critical', 'medium'): 'Critical',
            ('critical', 'high'): 'Critical',
        }
        for rec in self:
            rec.rating = matrix.get((rec.impact, rec.likelihood), 'Medium')