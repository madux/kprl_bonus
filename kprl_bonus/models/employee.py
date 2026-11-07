import json
import logging

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    staff_id = fields.Char()

    @api.constrains('staff_id')
    def _check_staff_id_format(self):
        from .kprl_math import check_staff_id
        for rec in self:
            if rec.staff_id:
                try:
                    check_staff_id(rec.staff_id)
                except ValueError as exc:
                    raise ValidationError(str(exc))

class Employee(models.Model):
    _name = 'kprl.employee'
    _description = 'Employee Master'
    _order = 'employee_id'
    _rec_name = 'name'

    # _inherits = {"hr.employee": "employee_id"}

    employee_id = fields.Many2one(
        "hr.employee",
        string="HR Employee",
        required=False,
        ondelete="set null",
    )
    employee_id_num = fields.Integer(related='employee_id.id', string='Employee ID', readonly=True)

    kprl_number = fields.Char()
    staff_id = fields.Char(string='Staff ID', related='employee_id.staff_id', store=True, readonly=False)

    name = fields.Char(string='Employee Name', required=True)
    work_email = fields.Char()
    mobile_phone = fields.Char()

    def _log_grade_change(self, old_id, old_name, new_id, new_name):
        self.ensure_one()
        try:
            self.env['kprl.audit.trail'].sudo().create({
                'name': 'Grade change: %s [%s] %s -> %s' % (self.name or '', self.staff_id or '', old_name or 'None', new_name or 'None'),
                'employee_id': self.id,
                'grade_old_id': old_id or False,
                'grade_new_id': new_id or False,
                'detail': 'Pool=%s Track=%s' % (self.pool_type or '', self.track or ''),
                'category': 'user',
            })
        except Exception as exc:
            _logger.warning('KPRL grade audit skipped for %s: %s', self.name, exc)

    def _log_skill_change(self, old_val, new_val):
        self.ensure_one()
        try:
            self.env['kprl.audit.trail'].sudo().create({
                'name': 'Skill change: %s [%s] %s -> %s' % (self.name or '', self.staff_id or '', old_val or 0.0, new_val or 0.0),
                'employee_id': self.id,
                'detail': 'Manual skill premium points (sheet EM Skill)',
                'category': 'user',
            })
        except Exception as exc:
            _logger.warning('KPRL skill audit skipped for %s: %s', self.name, exc)
    @api.model_create_multi
    def create(self, vals_list):
        # Staff ID is a stored writable related (employee_id.staff_id).
        # Pop it up-front: the relation chain is not traversable until
        # employee_id is set, so letting super() handle it would drop it.
        from .kprl_math import normalize_staff_id
        staff_ids = [normalize_staff_id(vals.pop('staff_id', False)) for vals in vals_list]
        records = super().create(vals_list)

        for record, staff_id in zip(records, staff_ids):
            if record.employee_id:
                # Linked HR record supplied: push the Staff ID onto it.
                if staff_id:
                    record.employee_id.staff_id = staff_id
            else:
                hr_employee = self.env["hr.employee"].create({
                    "name": record.name,
                    "work_email": record.work_email,
                    "mobile_phone": record.mobile_phone,
                    "staff_id": staff_id or record.staff_id or False,
                })
                record.employee_id = hr_employee.id
            if not record.staff_id:
                raise ValidationError('Staff ID is required.')

        for record in records:
            if record.grade_id:
                record._log_grade_change(False, '', record.grade_id.id, record.grade_id.name or '')
        return records

    def write(self, vals):
        if 'staff_id' in vals and not vals['staff_id']:
            raise ValidationError('Staff ID is required and cannot be cleared.')
        if vals.get('staff_id'):
            from .kprl_math import normalize_staff_id
            vals['staff_id'] = normalize_staff_id(vals['staff_id'])
        old_grades = {}
        if 'grade_id' in vals:
            for rec in self:
                old_grades[rec.id] = (rec.grade_id.id, rec.grade_id.name or '')
        old_skill = {}
        if 'skill_premium_pts' in vals:
            for rec in self:
                old_skill[rec.id] = rec.skill_premium_pts or 0.0
        res = super().write(vals)
        if 'staff_id' in vals:
            for rec in self:
                if rec.employee_id and rec.employee_id.staff_id != vals['staff_id']:
                    rec.employee_id.staff_id = vals['staff_id']
        if 'grade_id' in vals:
            for rec in self:
                old_id, old_name = old_grades.get(rec.id, (False, ''))
                new_id = rec.grade_id.id if rec.grade_id else False
                if old_id != new_id:
                    rec._log_grade_change(old_id, old_name, new_id, rec.grade_id.name or '')
        if 'skill_premium_pts' in vals:
            for rec in self:
                if (old_skill.get(rec.id, 0.0) or 0.0) != (rec.skill_premium_pts or 0.0):
                    rec._log_skill_change(old_skill.get(rec.id, 0.0) or 0.0, rec.skill_premium_pts or 0.0)
        return res

    @api.constrains('staff_id')
    def _check_staff_id_format(self):
        from .kprl_math import check_staff_id
        for rec in self:
            if rec.staff_id:
                try:
                    check_staff_id(rec.staff_id)
                except ValueError as exc:
                    raise ValidationError(str(exc))

    @api.constrains('staff_id')
    def _check_staff_id_unique(self):
        for rec in self:
            if not rec.staff_id:
                continue
            dup = self.search([
                ('id', '!=', rec.id),
                ('staff_id', '=', rec.staff_id),
            ], limit=1)
            if dup:
                raise ValidationError(
                    'Staff ID %s is already used by %s.' % (rec.staff_id, dup.name))

    SENIOR_GRADE_CODES = ('SENMGT', 'TIER1', 'TIER2')

    @api.constrains('grade_id', 'status')
    def _check_grade_required_on_active(self):
        for rec in self:
            if rec.status == 'active' and not rec.grade_id:
                raise ValidationError('Grade is required for active employees.')

    @api.constrains('pool_type', 'status')
    def _check_pool_type_required_on_active(self):
        for rec in self:
            if rec.status == 'active' and not rec.pool_type:
                raise ValidationError('Pool Type is required (OPM - SUP-POOL - SALES).')

    def _is_senior_grade(self, grade):
        if not grade:
            return False
        if grade.is_senior_mgmt_tier:
            return True
        return (grade.code or '') in self.SENIOR_GRADE_CODES

    @api.depends('pool_type', 'grade_id', 'grade_id.code', 'grade_id.is_senior_mgmt_tier')
    def _compute_subpool_from_grade(self):
        Subpool = self.env['kprl.subpool']
        codes = {}
        for code in ('OPM', 'SENMGT', 'OPSSUP', 'SALES'):
            codes[code] = Subpool.search([('code', '=', code)], limit=1)
        for rec in self:
            pool = rec.pool_type or 'OPM'
            if pool == 'SALES':
                rec.subpool_id = codes['SALES'].id if codes['SALES'] else False
            elif pool == 'SUP':
                if rec._is_senior_grade(rec.grade_id):
                    rec.subpool_id = codes['SENMGT'].id if codes['SENMGT'] else False
                else:
                    rec.subpool_id = codes['OPSSUP'].id if codes['OPSSUP'] else False
            else:
                rec.subpool_id = codes['OPM'].id if codes['OPM'] else False

    @api.onchange('grade_id')
    def _onchange_suggest_skill(self):
        for rec in self:
            if not (rec.skill_premium_pts or 0.0) and rec.grade_id:
                rec.skill_premium_pts = rec.grade_id.suggested_skill or 0.0

    @api.onchange('is_sales', 'sales_role')
    def _onchange_suggest_track(self):
        for rec in self:
            if rec.is_sales and rec.sales_role and rec.sales_role != 'none':
                rec.track = rec.track or 'sales'
            else:
                rec.track = rec.track or 'ops'

    @api.depends('base_grade_points', 'skill_premium_pts')
    def _compute_total_points_emp(self):
        for rec in self:
            rec.total_points = (rec.base_grade_points or 0.0) + (rec.skill_premium_pts or 0.0)

    # related fields from hr.employee
    # employee_id = fields.Char(string='Employee ID', required=True) 
    department_id = fields.Many2one('kprl.department', string='Department')
    # Base Pts = pure grade lookup (GradePtsTbl col 2). The sheet has an unused
    # Base Pts Override column (all 57 rows empty): deliberately not ported.
    # Payout Base pulls from EM by ID with IFERROR 0, mirrored by relateds + or-0.0 guards.
    grade_id = fields.Many2one('kprl.grade', string='Grade')
    job_title = fields.Char(string='Job Title')
    pool_type = fields.Selection([
        ('OPM', 'OPM'),
        ('SUP', 'SUP-POOL'),
        ('SALES', 'SALES'),
    ], string='Pool Type', default='OPM',
        help='Per-employee pool class (not department-derived).')
    track = fields.Selection([
        ('ops', 'Ops'),
        ('sales', 'Sales'),
        ('both', 'Ops+Sales'),
    ], string='Track', default='ops',
        help='Ops, Sales, or both (GM-NSM dual leg).')
    subpool_id = fields.Many2one('kprl.subpool', string='Sub-Pool',
        compute='_compute_subpool_from_grade', store=True, readonly=True,
        help='Derived: OPM-OPM, SUP-senior-SENMGT, SUP-other-OPSSUP, SALES-SALES.')
    employment_date = fields.Date(string='Employment Date',
        help='Synced automatically from the PMS API (employment_date, YYYY-MM-DD). Not entered by hand.')
    tenure_years = fields.Float(string='Tenure (Years)', compute='_compute_tenure',
                                store=True,
        help='Auto-derived from Employment Date. Drives the tenure multiplier 1 + MIN(0.12, INT(yrs/3) * 0.03).')
    manager_id = fields.Many2one('kprl.employee', string='Reporting Manager')
    status = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('inactive', 'Inactive'),
        ('draft', 'Draft'),
    ], string='Status', default='active', required=True)
    is_sales = fields.Boolean(string='Sales Role', default=False)
    sales_role = fields.Selection([
        ('gm', 'GM'),
        ('nsm', 'NSM'),
        ('headtech', 'Head Tech'),
        ('rsm', 'RSM'),
        ('asm', 'ASM'),
        ('rsm_asm', 'RSM + ASM'),
        ('none', 'None'),
    ], string='Sales Role', default='none')
    territory_id = fields.Many2one('kprl.territory', string='Territory')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    is_active = fields.Boolean(string='Is Active', default=True)
    active = fields.Boolean(string='Active', default=True)
    image = fields.Binary(string='Photo', attachment=True)

    user_role = fields.Char(string='User Role', compute='_compute_user_role')

    @api.depends_context('uid')
    def _compute_user_role(self):
        user = self.env.user
        if user.has_group('base.group_system'):
            role = 'Administrator'
        elif user.has_group('kprl_bonus.group_kprl_ceo'):
            role = 'CEO / Superadmin'
        elif user.has_group('kprl_bonus.group_kprl_exec_director'):
            role = 'Exec Director'
        elif user.has_group('kprl_bonus.group_kprl_finance'):
            role = 'Finance'
        elif user.has_group('kprl_bonus.group_kprl_admin'):
            role = 'Admin'
        elif user.has_group('kprl_bonus.group_kprl_hr'):
            role = 'HR'
        elif user.has_group('kprl_bonus.group_kprl_user'):
            role = 'Users / Employee'
        else:
            role = 'Guest'
        for rec in self:
            rec.user_role = role

    # _sql_constraints = [
    #     ('employee_id_unique', 'UNIQUE(employee_id)', 'Employee ID must be unique!'),
    # ]

    # ── UI Helper ──
    initials = fields.Char(string='Initials', compute='_compute_initials', store=True)

    # ── Grade-related (related from grade_id) ──
    grade_code = fields.Char(related='grade_id.code', string='Grade Code', store=True)
    subpool_name = fields.Char(related='subpool_id.name', string='Sub-Pool', store=True)
    subpool_code = fields.Char(related='subpool_id.code', string='Sub-Pool Code', store=True)
    base_grade_points = fields.Float(related='grade_id.yp_points', string='Base Grade Points', store=True)
    skill_premium_pts = fields.Float(string='Skill Premium (pts)', digits=(5, 1), default=0.0,
        help='Manual per-employee skill points (sheet EM Skill). Adds to Base at the subpool rate; never capped.')
    total_points = fields.Float(string='Total Points', compute='_compute_total_points_emp', store=True,
        help='Base Grade Points + manual Skill Premium.')
    grade_deferral_rate = fields.Float(related='grade_id.deferral_rate', string='Grade Deferral Rate', store=True)
    aip_eligible = fields.Boolean(related='grade_id.aip_eligible', string='AIP Eligible', store=True)
    appraisal_base_score = fields.Float(related='grade_id.appraisal_base_score', string='Appraisal Pass Mark', store=True)
    grade_name = fields.Char(related='grade_id.name', string='Grade Name', store=True)

    # ── Latest Payout (computed from kprl.bonus.payout) ──
    latest_payout_id = fields.Many2one('kprl.bonus.payout', string='Latest Payout',
                                    compute='_compute_latest_payout', store=False)
    payout_period_name = fields.Char(related='latest_payout_id.period_id.name', string='Payout Period', store=False)
    base_eligible = fields.Float(related='latest_payout_id.base_eligible', string='Base Eligible', store=False)
    dept_kpi_mult = fields.Float(related='latest_payout_id.dept_kpi_mult', string='Dept KPI Mult', store=False)
    appraisal_mult = fields.Float(related='latest_payout_id.appraisal_mult', string='Appraisal Mult', store=False)
    behavioural_mult = fields.Float(related='latest_payout_id.behavioural_mult', string='Behavioural Mult', store=False)
    exception_premium = fields.Float(related='latest_payout_id.exception_premium', string='Exception Premium', store=False)
    proration_factor = fields.Float(related='latest_payout_id.proration_factor', string='Proration', store=False)
    tenure_mult_payout = fields.Float(related='latest_payout_id.tenure_mult', string='Tenure Mult', store=False)
    gmp_factor = fields.Float(related='latest_payout_id.gmp_factor', string='GMP Factor', store=False)
    malus_amount = fields.Float(related='latest_payout_id.malus_amount', string='Malus', store=False)
    gross_payable = fields.Float(related='latest_payout_id.gross_payable', string='Gross Payable', store=False)
    deferred_amount = fields.Float(related='latest_payout_id.deferred_amount', string='Deferred Amount', store=False)
    net_immediate = fields.Float(related='latest_payout_id.net_immediate', string='Bonus after Deferral', store=False)
    floor_check = fields.Boolean(related='latest_payout_id.floor_check', string='Floor Check', store=False)
    deferral_rate_payout = fields.Float(related='latest_payout_id.deferral_rate', string='Deferral Rate', store=False)
    # behaviour_05 = fields.Float(related='latest_payout_id.behaviour_05', string='Behavioural /25', store=False)
    behaviour_05 = fields.Float(default=23, string='Behavioural /25', store=False)
    appraisal_score_payout = fields.Float(related='latest_payout_id.appraisal_score', string='Appraisal Score', store=False)
    appraisal_max = fields.Float(related='latest_payout_id.appraisal_max', string='Appraisal Max', store=False)
    behaviour_max = fields.Float(related='latest_payout_id.behaviour_max', string='Behaviour Max', store=False)

    # ── One2many for inline lists in tabs ──
    payout_ids = fields.One2many('kprl.bonus.payout', 'employee_id', string='Payout History')
    deferred_ids = fields.One2many('kprl.deferred.ledger', 'employee_id', string='Deferred Records')
    performance_ids = fields.One2many('kprl.performance.input', 'employee_id', string='Performance Records')

    # ── Latest Performance (computed) ──
    latest_appraisal_score = fields.Float(string='Latest Appraisal Score',
                                        compute='_compute_latest_performance', store=False)
    latest_behaviour_score = fields.Float(string='Latest Behaviour Score',
                                        compute='_compute_latest_performance', store=False)
    latest_potential_score = fields.Float(string='Latest Potential Score',
                                        compute='_compute_latest_performance', store=False)
    latest_current_score = fields.Float(string='Latest Current Score',
                                        compute='_compute_latest_performance', store=False)
    dept_kpi_score = fields.Float(string='Dept KPI Score',
                                compute='_compute_latest_performance', store=False)
    dept_kpi_score_max = fields.Float(string='Dept KPI Max', compute='_compute_latest_performance', store=False)

    # ── Deferred summary (computed) ──
    total_deferred = fields.Float(string='Total Deferred', compute='_compute_deferred_summary', store=False)
    total_vested = fields.Float(string='Total Vested', compute='_compute_deferred_summary', store=False)
    total_forfeited = fields.Float(string='Total Forfeited', compute='_compute_deferred_summary', store=False)
    deferred_count = fields.Integer(string='Deferred Count', compute='_compute_deferred_summary', store=False)

    # ── Payout history summary (computed) ──
    total_paid = fields.Float(string='Total Paid', compute='_compute_payout_summary', store=False)
    total_gross_all = fields.Float(string='Total Gross (All)', compute='_compute_payout_summary', store=False)
    payout_count = fields.Integer(string='Payout Count', compute='_compute_payout_summary', store=False)
    
    @api.depends('employment_date')
    def _compute_tenure(self):
        today = date.today()
        for rec in self:
            if rec.employment_date:
                delta = today - rec.employment_date
                rec.tenure_years = round(delta.days / 365.25, 2)
            else:
                rec.tenure_years = 0.0

    def _tenure_bracket_years(self):
        self.ensure_one()
        return int(self.tenure_years or 0.0)

    def open_simulation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/kprl/simulate/%d' % self.id,
            'target': 'self',
        }

    def action_fetch_from_api(self):
        """Fetch this employee's current record from the appraisal API.

        Syncs master data (name, work email, phone, department) plus the
        appraisal score into the active period's performance input.
        API URL/token come from the most recent KPI Store record."""
        self.ensure_one()
        if not self.staff_id:
            raise ValidationError('Set a Staff ID before fetching from the API.')
        store_model = self.env['kprl.kpi.store']
        cfg = store_model.search([], order='create_date desc, id desc', limit=1)
        api_url = cfg.api_url if cfg else False
        token = cfg.token if cfg else False
        _logger.info(
            "KPRL Employee %s: fetching %s from appraisal API",
            self.id, self.staff_id,
        )
        _result, _raw, data, numbering = store_model._fetch_with_fallback(
            api_url, token, self.staff_id, False,
        )
        if not data:
            raise ValidationError(
                f"No appraisal record found for '{self.staff_id}'. "
                "Fix the Staff ID to match PMS numbering. "
                + store_model._numbering_hint(numbering)
            )
        rec = next(
            (r for r in data
             if isinstance(r, dict) and store_model._numbers_equal(r.get("employee_number"), self.staff_id)),
            None,
        )
        if not rec and len(data) == 1 and isinstance(data[0], dict):
            rec = data[0]
        if not rec:
            raise ValidationError(
                f"Appraisal API returned %d record(s) but none matches '{self.staff_id}'. "
                % len(data)
                + "Fix the Staff ID to match PMS numbering. "
                + store_model._numbering_hint(
                    store_model._numbering_sample(data))
            )
        _logger.info(
            "KPRL Employee %s: API record=%s",
            self.staff_id, json.dumps(rec, default=str)[:3000],
        )
        vals = {}
        if rec.get("employee_name"):
            vals["name"] = rec["employee_name"]
        if rec.get("work_email"):
            vals["work_email"] = rec["work_email"]
        if rec.get("phone"):
            vals["phone"] = rec["phone"]
        if rec.get("department_name"):
            _hr_dep, kprl_dep = store_model.get_department(rec["department_name"])
            vals["department_id"] = kprl_dep
        if rec.get("job_title"):
            vals["job_title"] = rec["job_title"]
        if rec.get("grade_code") or rec.get("grade_name"):
            grade = store_model._resolve_grade(rec.get("grade_code"), rec.get("grade_name"))
            if not grade:
                raise ValidationError(
                    "Staff %s: PMS grade code=%r name=%r not found in Odoo grades. "
                    "Update PMS grade_name/grade_code, then re-sync." % (
                        self.staff_id, rec.get("grade_code"), rec.get("grade_name")))
            vals["grade_id"] = grade.id
        if rec.get("manager_staff_number"):
            mgr = store_model._resolve_manager(rec.get("manager_staff_number"), self.id)
            if not mgr:
                raise ValidationError(
                    "Staff %s: manager %r not found. Sync the manager first or fix "
                    "PMS manager_staff_number, then re-sync." % (
                        self.staff_id, rec.get("manager_staff_number")))
            vals["manager_id"] = mgr.id
        from .kprl_math import parse_pms_employment_date
        hired = parse_pms_employment_date(rec.get("employment_date"))
        if hired:
            vals["employment_date"] = hired
        elif rec.get("employment_date") not in (None, "", False):
            _logger.warning(
                "KPRL Employee %s: unparseable employment_date=%r; kept existing.",
                self.staff_id, rec.get("employment_date"))
        if vals:
            self.write(vals)
        period = self.env['kprl.bonus.period'].search(
            [('state', '=', 'active')], limit=1)
        if period:
            perf = self.env['kprl.performance.input'].search([
                ('employee_id', '=', self.id),
                ('period_id', '=', period.id),
            ], limit=1)
            _pot, _cur, _behav25 = store_model._behaviour_scores_from_pms(rec)
            score_vals = {
                'period_id': period.id,
                'employee_id': self.id,
                'appraisal_score': rec.get('average_aggregate', 0.0),
                'retain_score': rec.get('overall_score', 0.0),
                'potential_assessment_score': _pot,
                'current_assessment_score': _cur,
                'team_pct': _behav25,
            }
            if perf:
                perf.write(score_vals)
            else:
                self.env['kprl.performance.input'].create(score_vals)
            msg = f'{self.staff_id} synced; score pushed to {period.name}.'
        else:
            msg = f'{self.staff_id} synced; no active period, score skipped.'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Records',
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'kprl.employee',
                    'res_id': self.id,
                    'views': [[False, 'form']],
                    'target': 'current',
                },
            },
        }
    @api.depends('name')
    def _compute_initials(self):
        for rec in self:
            if rec.name:
                parts = rec.name.strip().split()
                rec.initials = (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else parts[0][0].upper()
            else:
                rec.initials = '??'

    def _compute_latest_payout(self):
        for rec in self:
            latest = self.env['kprl.bonus.payout'].search(
                [('employee_id', '=', rec.id)], order='period_end desc', limit=1)
            rec.latest_payout_id = latest

    def _compute_latest_performance(self):
        for rec in self:
            perf = self.env['kprl.performance.input'].search(
                [('employee_id', '=', rec.id)], order='period_end desc', limit=1)
            rec.latest_appraisal_score = perf.appraisal_score if perf else 0.0
            rec.latest_behaviour_score = perf.team_pct if perf else 0.0
            rec.latest_potential_score = perf.potential_assessment_score if perf else 0.0
            rec.latest_current_score = perf.current_assessment_score if perf else 0.0
            # dept KPI score from latest dept multiplier
            if rec.department_id:
                dept_kpi = self.env['kprl.dept.kpi.multiplier'].search(
                    [('department_id', '=', rec.department_id.id)],
                    order='period_end desc', limit=1)
                rec.dept_kpi_score = dept_kpi.kpi_score if dept_kpi else 0.0
                rec.dept_kpi_score_max = dept_kpi.kpi_score_max if dept_kpi else 100.0
            else:
                rec.dept_kpi_score = 0.0
                rec.dept_kpi_score_max = 100.0

    def _compute_deferred_summary(self):
        for rec in self:
            records = self.env['kprl.deferred.ledger'].search([('employee_id', '=', rec.id)])
            rec.total_deferred = sum(r.deferred_amount for r in records if r.status == 'deferred')
            rec.total_vested = sum(r.deferred_amount for r in records if r.status == 'vested')
            rec.total_forfeited = sum(r.deferred_amount for r in records if r.status == 'forfeited')
            rec.deferred_count = len(records)

    def _compute_payout_summary(self):
        for rec in self:
            records = self.env['kprl.bonus.payout'].search([('employee_id', '=', rec.id)])
            rec.total_paid = sum(r.net_immediate for r in records if r.state == 'paid')
            rec.total_gross_all = sum(r.gross_payable for r in records)
            rec.payout_count = len(records)