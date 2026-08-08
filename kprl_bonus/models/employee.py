from odoo import models, fields, api
from datetime import date

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    staff_id = fields.Char()
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
        ondelete="cascade",
    )
    employee_id_num = fields.Integer(related='employee_id.id', string='Employee ID', readonly=True)

    kprl_number = fields.Char()
    staff_id = fields.Char(string='Staff ID', required=True)

    name = fields.Char(string='Employee Name', required=True)
    work_email = fields.Char()
    mobile_phone = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            hr_employee = self.env["hr.employee"].create({
                "name": record.name,
                "work_email": record.work_email,
                "mobile_phone": record.mobile_phone,
                "staff_id": record.staff_id,
            })

            record.employee_id = hr_employee.id

        return records
    # related fields from hr.employee
    # employee_id = fields.Char(string='Employee ID', required=True) 
    department_id = fields.Many2one('kprl.department', string='Department')
    grade_id = fields.Many2one('kprl.grade', string='Grade')
    job_title = fields.Char(string='Job Title')
    subpool_id = fields.Many2one('kprl.subpool', string='Sub-Pool')
    date_hired = fields.Date(string='Date Hired')
    tenure_years = fields.Float(string='Tenure (Years)', compute='_compute_tenure',
                                store=True)
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
    is_active = fields.Boolean(string='Active', default=True)
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

    _sql_constraints = [
        ('employee_id_unique', 'UNIQUE(employee_id)', 'Employee ID must be unique!'),
    ]

    # ── UI Helper ──
    initials = fields.Char(string='Initials', compute='_compute_initials', store=True)

    # ── Grade-related (related from grade_id) ──
    grade_code = fields.Char(related='grade_id.code', string='Grade Code', store=True)
    subpool_name = fields.Char(related='grade_id.subpool_id.name', string='Sub-Pool', store=True)
    subpool_code = fields.Char(related='grade_id.subpool_id.code', string='Sub-Pool Code', store=True)
    base_grade_points = fields.Float(related='grade_id.yp_points', string='Base Grade Points', store=True)
    skill_premium_pts = fields.Float(related='grade_id.skill_premium', string='Skill Premium (pts)', store=True)
    total_points = fields.Float(related='grade_id.total_points', string='Total Points', store=True)
    token_rate = fields.Float(related='grade_id.token_rate', string='Token Rate (/pt)', store=True)
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
    net_immediate = fields.Float(related='latest_payout_id.net_immediate', string='Net Immediate', store=False)
    floor_check = fields.Boolean(related='latest_payout_id.floor_check', string='Floor Check', store=False)
    deferral_rate_payout = fields.Float(related='latest_payout_id.deferral_rate', string='Deferral Rate', store=False)
    behaviour_05 = fields.Float(related='latest_payout_id.behaviour_05', string='Behavioural /25', store=False)
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
    
    @api.depends('date_hired')
    def _compute_tenure(self):
        today = date.today()
        for rec in self:
            if rec.date_hired:
                delta = today - rec.date_hired
                rec.tenure_years = round(delta.days / 365.25, 2)
            else:
                rec.tenure_years = 0.0

    def open_simulation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/kprl/simulate/%d' % self.id,
            'target': 'self',
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