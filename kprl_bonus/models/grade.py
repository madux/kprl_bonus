import logging

_logger = logging.getLogger(__name__)

from odoo import models, fields, api


class Grade(models.Model):
    _name = 'kprl.grade'
    _description = 'Employee Grade'
    _order = 'sequence'

    name = fields.Char(string='Grade Name', required=True)
    code = fields.Char(string='Grade Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    yp_points = fields.Float(string='Base Points (Base Premium)', digits=(5, 1),
                             help='Base grade points for bonus calculation')
    diff_points = fields.Float(string='Diff Points', digits=(5, 1),
                               help='Differentiation points adjustment')
    skill_max = fields.Float(string='Skill Max', digits=(5, 1), default=0.0,
                             help='Informational ceiling from GradePtsTbl col C. Never enforced; live rows exceed it.')
    suggested_skill = fields.Float(string='Suggested Skill', digits=(5, 1), default=0.0,
                             help='Entry convenience only: fills new skill blanks on grade selection. Never enforced, never a cap.')
    total_points = fields.Float(string='Total Points', digits=(5, 1),
                                compute='_compute_total_points', store=True)
    deferral_rate = fields.Float(string='Deferral Rate (%)', digits=(5, 2))
    subpool_id = fields.Many2one('kprl.subpool', string='Sub-Pool',
        help='Legacy default sub-pool for this grade. The live sub-pool is derived on the employee from (pool_type + senior flag); this field is kept as fallback/reference only.')
    aip_eligible = fields.Boolean(string='AIP Eligible', default=False)
    is_senior_mgmt_tier = fields.Boolean(
        string='Senior Mgmt Tier', default=False,
        help='SEN-MGT band flag: exactly Senior Management - Tier 1 - Tier 2 per the sheet sub-pool and deferral formulas (Tier 3 falls through to OPS-SUP with zero deferral). Do not derive from grade name.')
    governance_note = fields.Text(string='Governance Notes')
    appraisal_base_score = fields.Float(string='Appraisal Pass Mark (%)', default =65, help="each grade should have an appraisal park mark")

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Grade code must be unique!'),
    ]

    @api.depends('yp_points')
    def _compute_total_points(self):
        for rec in self:
            rec.total_points = rec.yp_points or 0.0

    # Workbook GradePtsTbl truth (REFERENCE TABLES cols A-E, by grade code).
    # The system owns these values; hand edits are repaired via action_reset_to_workbook.
    # Skill Max ships 0.0 until the col-C numbers arrive; never enforced.
    GRADE_DEFAULTS = {
        'SENMGT': {'name': 'Senior Management', 'yp': 10.0, 'aip': True, 'subpool': 'SENMGT', 'senior': True, 'seq': 10, 'skill': 2.0, 'deferral': 20.0},
        'TIER1': {'name': 'Senior Managers - Tier 1', 'yp': 8.0, 'aip': True, 'subpool': 'SENMGT', 'senior': True, 'seq': 20, 'skill': 1.0, 'deferral': 20.0},
        'TIER2': {'name': 'Senior Managers - Tier 2', 'yp': 7.0, 'aip': True, 'subpool': 'SENMGT', 'senior': True, 'seq': 30, 'skill': 1.0, 'deferral': 20.0},
        'TIER3': {'name': 'Senior Managers - Tier 3', 'yp': 6.0, 'aip': False, 'subpool': 'OPM', 'senior': False, 'seq': 40},
        'LEAD1': {'name': 'Team Leads - Tier 1', 'yp': 5.0, 'aip': False, 'subpool': 'OPM', 'senior': False, 'seq': 50},
        'ALEAD': {'name': 'Ast. Team Leads', 'yp': 4.0, 'aip': False, 'subpool': 'OPM', 'senior': False, 'seq': 60},
        'ASMGR': {'name': 'Asst. Manager', 'yp': 2.0, 'aip': False, 'subpool': 'OPM', 'senior': False, 'seq': 70},
        'MGR': {'name': 'Manager', 'yp': 3.0, 'aip': False, 'subpool': 'OPM', 'senior': False, 'seq': 80},
        'SUP1': {'name': '1st Level Supervisor', 'yp': 2.0, 'aip': False, 'subpool': 'OPSSUP', 'senior': False, 'seq': 90},
        'SUP2': {'name': '2nd Level Supervisor', 'yp': 1.5, 'aip': False, 'subpool': 'OPSSUP', 'senior': False, 'seq': 100},
        'JUNIOR': {'name': 'Junior Staff', 'yp': 1.0, 'aip': False, 'subpool': 'OPSSUP', 'senior': False, 'seq': 110},
        'HYGIENE': {'name': 'Hygiene Staff', 'yp': 0.5, 'aip': False, 'subpool': 'OPSSUP', 'senior': False, 'seq': 120},
    }

    def action_reset_to_workbook(self):
        for rec in self:
            vals = self.GRADE_DEFAULTS.get((rec.code or '').strip().upper())
            if not vals:
                continue
            old_yp = rec.yp_points or 0.0
            sub = self.env['kprl.subpool'].search([('code', '=', vals['subpool'])], limit=1)
            rec.write({
                'name': vals['name'],
                'sequence': vals['seq'],
                'yp_points': vals['yp'],
                'aip_eligible': vals['aip'],
                'subpool_id': sub.id if sub else False,
                'is_senior_mgmt_tier': vals['senior'],
                'suggested_skill': vals.get('skill', 0.0),
                'deferral_rate': vals.get('deferral', 0.0),
            })
            try:
                self.env['kprl.audit.trail'].sudo().create({
                    'name': 'Grade reset: %s base %s -> %s' % (rec.code or '', old_yp, vals['yp']),
                    'detail': 'Workbook-defaults repair (GradePtsTbl truth).',
                    'category': 'system',
                })
            except Exception as exc:
                _logger.warning('Grade reset audit skipped for %s: %s', rec.code, exc)
        return True