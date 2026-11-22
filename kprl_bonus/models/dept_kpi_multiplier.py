from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DeptKpiMultiplier(models.Model):
    _name = 'kprl.dept.kpi.multiplier'
    _description = 'Department KPI Multiplier'
    _rec_name = 'department_id'

    department_id = fields.Many2one('kprl.department', string='Department',
                                    required=True)
    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    kpi_score = fields.Float(string='KPI Score (%)', digits=(5, 2))
    kpi_score_max = fields.Float(string='KPI Score Max', default=100.0)

    multiplier = fields.Float(string='KPI Multiplier', digits=(5, 4), default=1.0, compute='_compute_multiplier', store=True)
    gmp_status = fields.Selection([
        ('clean', 'Clean'),
        ('minor', 'Minor'),
        ('major', 'Major'),
        ('critical', 'Critical'),
        ('non_compliant', 'Non-Compliant (legacy)'),
    ], string='GMP Status', default='clean',
        help='Dept GMP finding severity. Clean = no cut. Minor/Major/Critical cut the dept bonus by 5%/20%/40%. Fixed list only; any other value is rejected, never silently treated as Critical.')
    self_flag = fields.Boolean(string='Self-Reported',
        help='Issue was self-reported. The penalty is multiplied by the retained share (parameter default 0.5, so the cut is halved per status). No effect when status is Clean.')
    def_factor = fields.Float(string='GMP Factor (Dept)', digits=(5, 4), default=1.0,
                              compute='_compute_def_factor', store=True, readonly=False,
                              help='Dept GMP factor: 1 - penalty x (retained share if self-reported, else 1). Penalties: Clean 0, Minor 0.05, Major 0.20, Critical 0.40. Feeds the company-wide banded mean.')
    notes = fields.Text(string='Notes')
    period_end = fields.Date(related='period_id.date_end', store=True, index=True)

    _sql_constraints = [
        ('dept_period_unique', 'UNIQUE(department_id, period_id)',
         'A department can only have one KPI multiplier per period!'),
    ]

    @api.depends('kpi_score', 'kpi_score_max')
    def _compute_multiplier(self):
        from .kprl_math import score_to_multiplier
        for rec in self:
            s = rec.kpi_score or 0.0
            # Excel parity: zero/blank scores flow through the curve
            # (0 < 0.6 -> 0.7). No neutral 1.0 special-case.
            # Scores ≤ 1 are already fractions (workbook convention);
            # larger values are treated as 0-100 and divided by the max.
            if s <= 1.0:
                frac = s
            else:
                mx = rec.kpi_score_max or 100.0
                frac = s / (mx if mx > 1.0 else 100.0)
            rec.multiplier = score_to_multiplier(frac)

    @api.depends('gmp_status', 'self_flag', 'period_id.parameter_ids.g_gmp_self_report_relief')
    def _compute_def_factor(self):
        from .kprl_math import dept_gmp_factor
        for rec in self:
            st = rec.gmp_status or 'clean'
            if st == 'non_compliant':
                st = 'major'
            params = rec.period_id.parameter_ids[:1] if rec.period_id else False
            relief = params.g_gmp_self_report_relief if params and params.g_gmp_self_report_relief else 0.5
            try:
                rec.def_factor = dept_gmp_factor(st, rec.self_flag, relief)
            except ValueError as e:
                raise ValidationError(
                    'Invalid GMP Status on %s: %s. Use Clean / Minor / Major / Critical.'
                    % (rec.department_id.name if rec.department_id else 'department', e))

    @api.model
    def create(self, vals):
        if 'gmp_status' not in vals and vals.get('department_id'):
            dept = self.env['kprl.department'].browse(vals['department_id'])
            if dept.exists():
                vals = dict(vals, gmp_status=dept.gmp_status or 'clean',
                            self_flag=vals.get('self_flag', dept.gmp_self_reported or False))
        return super().create(vals)
