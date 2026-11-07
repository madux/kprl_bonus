from odoo import models, fields, api
import datetime
from odoo.exceptions import ValidationError
from .kprl_math import behaviour_to_multiplier

class BonusPayout(models.Model):
    _name = 'kprl.bonus.payout'
    _description = 'Employee Bonus Payout'
    _rec_name = 'employee_id'
    _order = 'employee_id'

    period_id = fields.Many2one('kprl.bonus.period', string='Period',
                                required=True)
    employee_id = fields.Many2one('kprl.employee', string='Employee',
                                  required=True)
    department_id = fields.Many2one('kprl.department', related='employee_id.department_id',
                                    string='Department', store=True)
    grade_id = fields.Many2one('kprl.grade', related='employee_id.grade_id',
                               string='Grade', store=True)
    subpool_id = fields.Many2one('kprl.subpool', related='employee_id.subpool_id',
                                 string='Sub-Pool', store=True)

    base_eligible = fields.Float(string='Base Eligible (₦)', digits='Product Price', help="rec.total_points * rec.value_point")
    dept_kpi_mult = fields.Float(string='Dept KPI Multiplier', digits=(5, 3),
                                 default=1.0)
    appraisal_mult = fields.Float(string='Appraisal Multiplier', digits=(5, 3),
                                  default=0.0, store=True)
    behavioural_mult = fields.Float(string='Behavioural Multiplier', digits=(5, 3),
                                    default=1.0,
                                    store=True, readonly=False)
    behavioural_formula_value = fields.Float(
        string='Behavioural Formula Value', digits=(5, 3),
        compute='_compute_behavioural_formula', store=False, readonly=True,
        help='Live formula: 0.9 + (Behav over Max) x 0.2. Shown value differs from Behavioural Multiplier only under manual override.')
    period_end = fields.Date(related='period_id.date_end', store=True, index=True)
    
    @api.depends('behaviour_05', 'behaviour_max')
    def _compute_behavioural_formula(self):
        for rec in self:
            if rec.behaviour_05:
                rec.behavioural_formula_value = behaviour_to_multiplier(rec.behaviour_05, rec.behaviour_max or 25.0)
            else:
                rec.behavioural_formula_value = 1.0


    exception_premium = fields.Float(string='Exception Premium (₦)',
                                     digits='Product Price')
    proration_factor = fields.Float(string='Proration', digits=(5, 2), default=1.0)
    tenure_mult = fields.Float(string='Tenure Multiplier', digits=(5, 2), default=1.0, help="(rec.employee_id.tenure_years / 3) * 0.03",)
                            #    compute='_compute_tenure_mult',)
    gmp_factor = fields.Float(string='GMP Factor', digits=(5, 2), default=1.0)
    malus_amount = fields.Float(string='Malus (₦)', digits='Product Price')
    malus_pct = fields.Float(string='Malus (%)', digits=(5, 2), default=0.0)
    malus_pct_total = fields.Float(string='Total Malus (%)', digits=(5, 2), default=0.0)
    company_gmp_factor = fields.Float(string='Company GMP Factor', digits=(5, 2), default=1.0)

    gross_payable = fields.Float(
        string='Gross Bonus (₦)', digits='Product Price', store=True,
        help='Operations bonus before pool proration, tenure enhancement, floor, deferral, GMP/malus, and cap. '
             'Calculated as Base Eligible × Department KPI Multiplier × Appraisal Multiplier × '
             'Behavioural Multiplier, plus a 10% exception premium when appraisal is at least 90%. '
             'Sales and retrieval commissions are separate.')
    payable = fields.Float(string='Payable (₦)', digits='Product Price', store=True)
    
    tenure_enhance = fields.Float(string='Tenure EHN', store=True)
    
    tenure_years = fields.Float(string='Tenure years', store=True, related='employee_id.tenure_years')
    deferral_rate = fields.Float(string='Deferral Rate (%)', digits=(5, 4), default=0.0)
    # appraisal_score = fields.Float(
    #     string='Appraisal Score (%)', digits=(5, 4),
    #     compute='_compute_appraisal_score', store=True,
    # )

       # change appraisal_score BACK to a regular stored field:
    appraisal_score = fields.Float(string='Appraisal Score (%)', digits=(5, 2))

    adjusted_amount = fields.Float(string='Adjusted (₦)', digits=(5, 4))
    behaviour_05 = fields.Float(string='Behavioure /25', digits=(5, 1))
    appraisal_max = fields.Float(string='Appraisal Max', default=1.0)
    behaviour_max = fields.Float(string='Behaviour Max', default=25.0)
    
    deferred_amount = fields.Float(string='Deferred Amount (₦)',
                                   digits='Product Price', help="rec.final_floor * (rec.deferral_rate / 100.0)", store=True)
    net_immediate = fields.Float(string='Bonus after Deferral (₦)',
                                 digits='Product Price', store=True, help="rec.final_floor - rec.deferred_amount")
    quarterly_amount = fields.Float(string='Quarterly Payout (₦)',
                                 digits='Product Price', help="rec.final_floor - rec.deferred_amount", store=True)
    final_floor = fields.Float(string='Final + Floor (₦)',
                                 digits='Product Price', store=True)
    floor_check = fields.Boolean(string='Floor Check Pass', default=True)
    cap_check = fields.Boolean(string='Cap Check Pass', default=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ], string='Status', default='draft')

    _sql_constraints = [
        ('employee_period_unique', 'UNIQUE(employee_id, period_id)',
         'An employee can only have one payout per period!'),
    ]
    value_point = fields.Float(string='Value Point (₦)',
                                   digits='Product Price',
                                   default=0.0)

    total_points = fields.Float(string='Total Point (₦)',
                                   digits='Product Price', store=True)
    



    net_payable = fields.Float(string='Net Bonus (₦)', digits='Product Price', store=True,
                               help="v30 col AJ = MIN(cap, NetImmed × DeptGMP × (1−Malus) × QA/QC adj)")
    gross_commission = fields.Float(
        string='Gross Commission', digits='Product Price',
        compute='_compute_gross_commission', store=True, readonly=True,
        help='Sales plus retrieval commissions before KPI, accelerator, and payout cap.')
    taxable_gross_amount = fields.Float(
        string='Gross Taxable Amount', related='net_payable', store=True, readonly=True,
        help='Tax base for government withholding; this is the Net Bonus and does not add a separate tax calculation.')

    gov_tax_rate = fields.Float(
        string='Gov Tax Rate (%)', digits=(5, 2), default=0.0,
        help='Optional withholding rate applied AFTER Net Bonus. Zero means no tax.')
    gov_tax_amount = fields.Float(
        string='Gov Tax Amount', digits='Product Price',
        compute='_compute_gov_tax', store=True, readonly=True)
    take_home_pay = fields.Float(
        string='Take-Home Pay', digits='Product Price',
        compute='_compute_gov_tax', store=True, readonly=True,
        help='Net Bonus less gov tax. Equals Net Bonus when rate is zero.')

    @api.constrains('malus_amount')
    def _check_malus_amount_excel_only(self):
        for rec in self:
            if (rec.malus_amount or 0.0) != 0.0:
                raise ValidationError(
                    'Fixed-amount malus is not part of the workbook: STAFF PAYOUT col AJ applies Malus % only. '
                    'Enter the malus as Malus (%) instead (or as Malus_Pct on a governance event).')


    @api.depends('net_payable', 'gov_tax_rate')
    def _compute_gov_tax(self):
        for rec in self:
            tax = (rec.net_payable or 0.0) * (rec.gov_tax_rate or 0.0) / 100.0
            rec.gov_tax_amount = max(tax, 0.0)
            rec.take_home_pay = max((rec.net_payable or 0.0) - rec.gov_tax_amount, 0.0)

    @api.depends('sales_commission', 'retrieval_commission')
    def _compute_gross_commission(self):
        for rec in self:
            rec.gross_commission = (rec.sales_commission or 0.0) + (rec.retrieval_commission or 0.0)




    def ensure_deferred_entry(self):
        for rec in self:
            if not rec.employee_id or not rec.period_id or not (rec.deferred_amount or 0.0):
                continue
            existing = self.env['kprl.deferred.ledger'].search([('employee_id', '=', rec.employee_id.id), ('period_id', '=', rec.period_id.id)], limit=1)
            end = rec.period_id.date_end
            vest = (end + datetime.timedelta(days=730)) if end else datetime.date(2028, 3, 31)
            vals = {'employee_id': rec.employee_id.id, 'period_id': rec.period_id.id, 'calculated_bonus': rec.final_floor or 0.0, 'deferral_rate': rec.deferral_rate or 0.0, 'deferred_amount': rec.deferred_amount or 0.0, 'vest_date': vest}
            if existing:
                existing.write(vals)
            else:
                self.env['kprl.deferred.ledger'].create(vals)

    def action_calculate(self):
        """Manual calculate: refresh source inputs from performance, run the
        single engine over this line, and mark it computed. Blocked lines
        keep zeros plus the reason instead of a stale or invented payout."""
        self.ensure_one()
        if self.state not in ("draft", "computed"):
            from odoo.exceptions import UserError as _UE
            raise _UE("Calculate is allowed from Draft (or re-run from Computed).")
        if self.employee_id and self.period_id:
            perf = self.env["kprl.performance.input"].search([
                ("employee_id", "=", self.employee_id.id),
                ("period_id", "=", self.period_id.id)], limit=1)
            if perf:
                super(BonusPayout, self).write({"appraisal_score": perf.appraisal_score})
                if perf.team_pct not in (None, False) and float(perf.team_pct or 0.0) != 0.0:
                    v = float(perf.team_pct)
                    super(BonusPayout, self).write(
                        {"behaviour_05": v / 100.0 * 25.0 if v > 25.0 else v})
                else:
                    super(BonusPayout, self).write({"behaviour_05": 0.0})
        self._recalculate_from_engine()
        self.write({"state": "computed"})
        return True

    def action_approve(self):
        for rec in self:
            rec.ensure_deferred_entry()
        self.state = 'approved'

    def action_paid(self):
        self.state = 'paid'

    def action_print_slip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/kprl/payslip/%d/pdf' % self.id,
            'target': 'new',
        }

    def action_export_excel(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/kprl/payslip/%d/xlsx' % self.id,
            'target': 'new',
        }

    governance_event_ids = fields.Many2many(
    'kprl.governance.event',
    compute='_compute_governance_events',
    string='Governance Events'
)

    total_governance_deduction = fields.Float(
        string='Total Governance Deduction',
        compute='_compute_governance_events',
        store=False
    )

    clawback_event_ids = fields.Many2many(
    'kprl.governance.event',
    compute='_compute_clawback_events',
    string='Clawback Events (post-pay)'
)

    total_clawback_amount = fields.Float(
        string='Total Clawback Opened',
        compute='_compute_clawback_events',
        store=False
    )

    total_forfeited_via_clawback = fields.Float(
        string='Total Forfeited via Clawback',
        compute='_compute_clawback_events',
        store=False
    )

    @api.depends('employee_id', 'period_id')
    def _compute_governance_events(self):
        for rec in self:
            if rec.employee_id and rec.period_id:
                events = self.env['kprl.governance.event'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('period_id', '=', rec.period_id.id),
                    ('trigger_type', '=', 'malus'),
                    ('status', 'not in', ('waived', 'reversed')),
                ])
                prepay = events.filtered(lambda ev: (ev.deduction_stage or 'pre_pay') == 'pre_pay')
                rec.governance_event_ids = prepay
                rec.total_governance_deduction = sum(prepay.mapped('malus_amount'))
            else:
                rec.governance_event_ids = self.env['kprl.governance.event']
                rec.total_governance_deduction = 0.0

    @api.depends('employee_id', 'period_id')
    def _compute_clawback_events(self):
        for rec in self:
            if rec.employee_id and rec.period_id:
                events = self.env['kprl.governance.event'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('period_id', '=', rec.period_id.id),
                    ('trigger_type', '=', 'clawback'),
                    ('status', 'not in', ('waived', 'reversed')),
                ])
                rec.clawback_event_ids = events
                rec.total_clawback_amount = sum(events.mapped('clawback_amount'))
                forfeited = self.env['kprl.deferred.ledger'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('period_id', '=', rec.period_id.id),
                    ('status', '=', 'forfeited'),
                ])
                rec.total_forfeited_via_clawback = sum(forfeited.mapped('deferred_amount'))
            else:
                rec.clawback_event_ids = self.env['kprl.governance.event']
                rec.total_clawback_amount = 0.0
                rec.total_forfeited_via_clawback = 0.0
# ---------------------------------------------------------------------------
# ENGINE REWIRE: all derived fields below are populated exclusively by
# _recalculate_from_engine() from the single compensation engine
# (preview_payout + operations/sales legs). They are strictly readonly in
# the views. Corrections happen in source data (employee master, period
# performance, policy), never by hand-editing these fields.
# ---------------------------------------------------------------------------


    engine_status = fields.Selection(
        [("calculated", "Calculated"), ("waiting", "Waiting for data"),
         ("blocked", "Blocked")],
        string="Engine Status", default="waiting")
    blocking_errors_text = fields.Text(string="Blocking Reasons")
    has_ops_leg = fields.Boolean(string="Has Ops Leg", default=True)
    has_sales_leg = fields.Boolean(string="Has Sales Leg", default=False)
    sales_attainment = fields.Float(string="Sales Attainment", digits=(5, 4))
    sales_gate = fields.Float(string="Sales Gate", digits=(5, 4))
    retrieval_gate = fields.Float(string="Retrieval Gate", digits=(5, 4))
    retrieval_rate = fields.Float(string="Retrieval Rate", digits=(5, 4))
    sales_commission = fields.Float(string="Sales Commission", digits="Product Price")
    retrieval_commission = fields.Float(string="Retrieval Commission", digits="Product Price")
    sales_kpi_mult = fields.Float(string="Sales KPI Multiplier", digits=(5, 4))
    accelerator_factor = fields.Float(string="Accelerator Factor", digits=(5, 4))
    leadership_floor = fields.Float(string="Leadership Floor", digits="Product Price")
    sales_cap = fields.Float(string="Sales Cap Applied", digits="Product Price")
    sales_payout = fields.Float(string="Sales Payout", digits="Product Price")
    QA_QC_DEPT_CODES = ('QA',)

    def _is_qa_qc_dept(self):
        """Workbook STAFF PAYOUT AH6: the QA/QC department is insulated from
        the department + company GMP gates (still quality-KPI driven)."""
        self.ensure_one()
        dept = self.department_id
        if not dept:
            return False
        name = (dept.name or '').strip().upper()
        code = (dept.code or '').strip().upper()
        return code in self.QA_QC_DEPT_CODES or name == 'QA/QC'

    def _governance_overlay(self):
        """Dept GMP factor + aggregated pre-pay malus + QA/QC company-gate
        relief (workbook AJ6: net x 1/'BONUS ENGINE'!B26 for QA/QC)."""
        self.ensure_one()
        from .compensation import multipliers as _M
        d_factor, malus_pct, fixed = 1.0, 0.0, 0.0
        qa_relief = 1.0
        if self._is_qa_qc_dept():
            # AH6: dept GMP multiplier forced to 1 for QA/QC.
            d_factor = 1.0
            eng = self.env['kprl.bonus.engine'].search(
                [('period_id', '=', self.period_id.id)], limit=1,
                order='create_date desc') if self.period_id else None
            company_gate = float(getattr(eng, 'gmp_factor', None) or 1.0)
            qa_relief = (1.0 / company_gate) if company_gate > 0 else 1.0
        if self.department_id and self.period_id and not self._is_qa_qc_dept():
            dm = self.env['kprl.dept.kpi.multiplier'].search([
                ('period_id', '=', self.period_id.id),
                ('department_id', '=', self.department_id.id)], limit=1)
            if dm:
                st = dm.gmp_status or 'clean'
                if st == 'non_compliant':
                    st = 'major'
                params = self.period_id.parameter_ids[:1] if self.period_id else False
                relief = params.g_gmp_self_report_relief if params and params.g_gmp_self_report_relief else 0.5
                try:
                    d_factor = _M.dept_gmp_factor(st, dm.self_flag, relief)
                except ValueError as exc:
                    raise ValidationError(
                        'Invalid GMP Status on %s: %s. Use Clean / Minor / Major / Critical.'
                        % (self.department_id.name if self.department_id else 'department', exc))
        if self.employee_id and self.period_id:
            evs = self.env['kprl.governance.event'].search([
                ('employee_id', '=', self.employee_id.id),
                ('period_id', '=', self.period_id.id),
                ('trigger_type', '=', 'malus'),
                ('status', 'not in', ('waived', 'reversed'))])
            for ev in evs:
                if (ev.deduction_stage or 'pre_pay') != 'pre_pay':
                    continue
                malus_pct += ev.malus_pct or 0.0
                fixed += ev.malus_amount or 0.0
            malus_pct = min(malus_pct, 100.0)
        return d_factor, malus_pct, fixed, qa_relief

    def _engine_payload(self):
        """Single preview payload via the simulator (no duplicated mapping)."""
        self.ensure_one()
        sim = self.env['kprl.payout.simulator'].new({
            'period_id': self.period_id.id, 'employee_id': self.employee_id.id})
        sim._run_preview()
        return sim.to_preview_dict()

    def _recalculate_from_engine(self):
        """Write every derived field from the engine. Only entry point."""
        for rec in self:
            if not rec.employee_id or not rec.period_id:
                continue
            payload = rec._engine_payload()
            dept_gmp, malus_pct, fixed, qa_relief = rec._governance_overlay()
            vals = payout_vals_from_payload(payload, dept_gmp, malus_pct, fixed,
                                            qa_relief=qa_relief)
            vals.update(rec._sales_engine_display_vals())
            for fname, value in vals.items():
                rec[fname] = value
        return True

    def _sales_engine_display_vals(self):
        """DISPLAY ONLY: mirror the employee's Sales Engine result for the
        period so sales staff can see their sales bonus on Staff Payout.

        Source of truth is kprl.territory.engine.lines (workbook SALES
        ENGINE / SE_Pay) - the same number the Payout Report pays. These
        values are never added to net_payable / take_home_pay; doing so
        pays the commission twice. Non-sales staff keep the zeros set by
        payout_vals_from_payload.
        """
        self.ensure_one()
        lines = self.env['kprl.territory.engine.lines'].search([
            ('employee_id', '=', self.employee_id.id),
            ('territory_engine_id.period_id', '=', self.period_id.id)])
        if not lines:
            return {}
        first = lines[:1]
        return {
            'has_sales_leg': True,
            'sales_attainment': first.sales_attain or 0.0,
            'sales_gate': first.sales_gate or 0.0,
            'retrieval_gate': first.retrival_gate or 0.0,
            'retrieval_rate': first.retrival_rate or 0.0,
            'sales_commission': sum(lines.mapped('commission_sales')),
            'retrieval_commission': sum(lines.mapped('commission_retrival')),
            'sales_kpi_mult': first.kpi_mult or 0.0,
            'accelerator_factor': first.accel_factor or 0.0,
            'sales_payout': sum(lines.mapped('sales_payout')),
        }

    @api.onchange('employee_id', 'period_id')
    def _onchange_fetch_appraisal(self):
        for rec in self:
            if not rec.employee_id or not rec.period_id:
                continue
            perf = self.env['kprl.performance.input'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('period_id', '=', rec.period_id.id)], limit=1)
            if perf:
                rec.appraisal_score = perf.appraisal_score
                if perf.team_pct not in (None, False):
                    v = float(perf.team_pct)
                    rec.behaviour_05 = v / 100.0 * 25.0 if v > 25.0 else v
            rec._recalculate_from_engine()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (not vals.get('appraisal_score') or not vals.get('behaviour_05')) and vals.get('employee_id') and vals.get('period_id'):
                perf = self.env['kprl.performance.input'].search([
                    ('employee_id', '=', vals['employee_id']),
                    ('period_id', '=', vals['period_id'])], limit=1)
                if perf:
                    vals.setdefault('appraisal_score', perf.appraisal_score)
                    if perf.team_pct not in (None, False):
                        v = float(perf.team_pct)
                        vals.setdefault('behaviour_05', v / 100.0 * 25.0 if v > 25.0 else v)
        records = super(BonusPayout, self).create(vals_list)
        records._recalculate_from_engine()
        return records

    def write(self, vals):
        res = super(BonusPayout, self).write(vals)
        if any(k in vals for k in ('employee_id', 'period_id')):
            for rec in self:
                if rec.employee_id and rec.period_id:
                    perf = self.env['kprl.performance.input'].search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('period_id', '=', rec.period_id.id)], limit=1)
                    if perf:
                        super(BonusPayout, rec).write({'appraisal_score': perf.appraisal_score})
            self._recalculate_from_engine()
        return res

def payout_vals_from_payload(payload, dept_gmp=1.0, malus_pct=0.0, fixed_deduction=0.0,
                             qa_relief=1.0):
    """Pure mapping: engine preview payload -> kprl.bonus.payout vals.

    No env access. Workbook STAFF PAYOUT col AJ is applied here: governed =
    net_immediate x dept GMP x (1 - malus %) x QA/QC company-gate relief,
    capped by appraisal cap. Fixed-amount deductions are audit-only and
    never reduce the payout.

    Workbook parity: STAFF PAYOUT is the OPERATIONS leg only. Sales
    commission lives exclusively in the SALES ENGINE (SE_Pay) and is
    combined with ops only in the PAYOUT REPORT (G + H). The preview's
    sales leg is therefore ignored here; mapping it into net_payable paid
    every sales-track employee twice (staff payout + sales engine).
    """
    payload = payload or {}
    cls = payload.get("classification", {}) or {}
    ops = payload.get("operations_breakdown") or {}
    status = payload.get("status") or "waiting"
    # Reasons raised only by the SALES leg (sales role / KPI / attainment,
    # own_target / own_sales / own_retrieval) must not block this row.
    ops_errors = [e for e in (payload.get("blocking_errors", []) or [])
                  if not ((e or "").strip().startswith("Sales ")
                          or (e or "").strip().startswith("own_"))]
    zeros = {
        "total_points": 0.0, "value_point": 0.0, "base_eligible": 0.0,
        "dept_kpi_mult": 0.0, "appraisal_mult": 0.0, "behavioural_mult": 0.0,
        "adjusted_amount": 0.0, "exception_premium": 0.0, "gross_payable": 0.0,
        "payable": 0.0, "tenure_mult": 1.0, "tenure_enhance": 0.0,
        "final_floor": 0.0, "deferred_amount": 0.0, "net_immediate": 0.0,
        "quarterly_amount": 0.0, "net_payable": 0.0,
        "sales_attainment": 0.0, "sales_gate": 0.0, "retrieval_gate": 0.0,
        "retrieval_rate": 0.0, "sales_commission": 0.0,
        "retrieval_commission": 0.0, "sales_kpi_mult": 0.0,
        "accelerator_factor": 0.0, "leadership_floor": 0.0,
        "sales_cap": 0.0, "sales_payout": 0.0,
        "engine_status": status,
        "blocking_errors_text": "\n".join(ops_errors),
        "floor_check": False, "cap_check": True,
        "gmp_factor": dept_gmp or 1.0, "malus_pct_total": malus_pct or 0.0,
        "deferral_rate": (cls.get("deferral_rate") or 0.0) * 100.0,
        "proration_factor": 1.0,
    }
    engines = cls.get("engines", []) or []
    zeros["has_ops_leg"] = "operations" in engines
    zeros["has_sales_leg"] = "sales" in engines
    if ops_errors or not ops or ops.get("gross_bonus") is None:
        out = dict(zeros)
        if not ops_errors:
            ops_errors = ["engine returned no computable operations gross - pool or inputs incomplete"]
        out["engine_status"] = "blocked"
        out["blocking_errors_text"] = "\n".join(ops_errors)
        return out
    vals = dict(zeros)
    vals.update({
        "total_points": float(cls.get("total_points") or 0.0),
        "value_point": float(ops.get("value_per_point") or 0.0),
        "base_eligible": float(ops.get("base_eligible") or 0.0),
        "dept_kpi_mult": float(ops.get("department_kpi_multiplier") or 0.0),
        "appraisal_mult": float(ops.get("appraisal_multiplier") or 0.0),
        "behavioural_mult": float(ops.get("behaviour_multiplier") or 0.0),
        "adjusted_amount": float(ops.get("adjusted_bonus") or 0.0),
        "exception_premium": float(ops.get("exception_premium") or 0.0),
        "gross_payable": float(ops.get("gross_bonus") or 0.0),
        "tenure_mult": float(ops.get("tenure_multiplier") or 1.0),
        "proration_factor": float(ops.get("proration_factor") or 1.0),
    })
    vals["payable"] = vals["gross_payable"] * vals["proration_factor"]
    vals["tenure_enhance"] = float(ops.get("tenure_enhanced") or 0.0)
    vals["final_floor"] = float(ops.get("final_before_deferral") or 0.0)
    vals["deferred_amount"] = float(ops.get("deferred_amount") or 0.0)
    vals["net_immediate"] = float(ops.get("immediate_payment") or 0.0)
    vals["quarterly_amount"] = vals["net_immediate"]
    vals["floor_check"] = not bool(ops.get("floor_applied")) or vals["final_floor"] >= vals["tenure_enhance"]
    gov = max(vals["net_immediate"] * (dept_gmp or 1.0)
              * max(0.0, 1.0 - (malus_pct or 0.0) / 100.0) * (qa_relief or 1.0), 0.0)
    # AJ6 order: individual cap binds on the governed amount.
    _cap = (ops or {}).get("cap")
    if _cap:
        gov = min(gov, float(_cap))
    vals["net_payable"] = gov
    vals["engine_status"] = "calculated"
    return vals
