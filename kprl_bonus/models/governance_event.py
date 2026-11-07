from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GovernanceEvent(models.Model):
    _name = 'kprl.governance.event'
    _description = 'Governance Event (Malus/Clawback)'
    _order = 'create_date desc'

    name = fields.Char(string='Event Reference', compute='_compute_name',
                       store=True)
    ref = fields.Char(string='Ref', compute='_compute_ref', store=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)
    employee_id = fields.Many2one('kprl.employee', string='Employee')
    period_id = fields.Many2one('kprl.bonus.period', string='Period')
    trigger_type = fields.Selection([
        ('policy_breach', 'Policy Breach'),
        ('gmp_deviation', 'GMP Deviation'),
        ('late_reporting', 'Late Reporting'),
        ('kpi_data_dispute', 'KPI Data Dispute'),
        ('malus', 'Malus'),
        ('clawback', 'Clawback'),
        ('aip_param_change', 'AIP Parameter Change'),
    ], string='Trigger Type', required=True)
    trigger_description = fields.Char(string='Trigger Description')
    severity = fields.Selection([
        ('low', 'LOW'),
        ('minor', 'MINOR'),
        ('medium', 'MEDIUM'),
        ('major', 'MAJOR'),
        ('high', 'HIGH'),
        ('critical', 'CRITICAL'),
    ], string='Severity', default='minor')
    stage = fields.Selection([
        ('open', 'Open'),
        ('under_review', 'Under Review'),
        ('investigation', 'Under Investigation'),
        ('closed', 'Closed'),
    ], string='Stage', default='open')
    deduction_stage = fields.Selection([
        ('pre_pay', 'Malus (pre-pay)'),
        ('post_pay', 'Clawback (post-pay)'),
    ], string='Deduction Stage', default='pre_pay',
        help='Sheet timing: pre-pay malus reduces the payout; post-pay clawback recovers via deferred ledger only.')

    @api.onchange('trigger_type')
    def _onchange_deduction_stage(self):
        if self.trigger_type == 'clawback':
            self.deduction_stage = 'post_pay'
        elif self.trigger_type == 'malus':
            self.deduction_stage = 'pre_pay'

    @api.constrains('trigger_type', 'malus_amount')
    def _check_malus_amount_excel_only(self):
        for rec in self:
            if rec.trigger_type == 'malus' and (rec.malus_amount or 0.0) != 0.0:
                raise ValidationError(
                    'Fixed-amount malus is not part of the workbook: STAFF PAYOUT col AJ applies Malus_Pct only. '
                    'Enter the malus as Malus (%) on this event instead.')

    malus_pct = fields.Float(string='Malus (%)', digits=(5, 2))
    malus_amount = fields.Float(string='Malus (₦)', digits='Product Price')
    clawback_amount = fields.Float(string='Clawback Amount', digits='Product Price')
    description = fields.Text(string='Description', required=True)
    status = fields.Selection([
        ('open', 'OPEN'),
        ('pending', 'PENDING'),
        ('applied', 'APPLIED'),
        ('waived', 'WAIVED'),
        ('reversed', 'REVERSED'),
        ('closed', 'CLOSED'),
    ], string='Status', default='open')
    investigation_lead = fields.Char(string='Investigation Lead')
    evidence_ref = fields.Char(string='Evidence Ref')
    outcome = fields.Text(string='Outcome')
    next_action = fields.Char(string='Next Action')
    approver_id = fields.Many2one('res.users', string='Approver')
    closed_by = fields.Many2one('res.users', string='Closed By')
    closed_date = fields.Datetime(string='Closed Date')
    approver_notes = fields.Text(string='Approver Notes')

    @api.depends('trigger_type', 'employee_id', 'create_date')
    def _compute_name(self):
        for rec in self:
            emp = rec.employee_id.name or 'N/A'
            rec.name = f"{rec.trigger_type.upper()} - {emp}"

    def action_apply_clawback(self):
        """Post-pay clawback (GOVERNANCE LOG): forfeits deferred entries up to
        the clawback amount, oldest first; marks the event applied."""
        for rec in self:
            if rec.trigger_type != 'clawback':
                continue
            remaining = rec.clawback_amount or 0.0
            if rec.employee_id and rec.period_id:
                entries = self.env['kprl.deferred.ledger'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('period_id', '=', rec.period_id.id),
                    ('status', '=', 'deferred'),
                ], order='vest_date asc')
                for entry in entries:
                    if remaining <= 0.0:
                        break
                    entry.write({'clawback_event_id': rec.id})
                    entry.action_forfeit()
                    remaining -= entry.deferred_amount or 0.0
            rec.status = 'applied'

    @api.depends('create_date')
    def _compute_ref(self):
        for rec in self:
            if rec.create_date:
                year = rec.create_date.year
                seq = str(rec.id).zfill(3)
                rec.ref = f"GV-{year}-{seq}"
            else:
                rec.ref = f"GV-0000-{rec.id}"