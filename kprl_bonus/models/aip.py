from odoo import models, fields, api
from odoo.exceptions import AccessError, ValidationError
import datetime
from .kprl_math import score_to_multiplier, normalize_score, appraisal_to_multiplier


class AipPool(models.Model):
    _name = 'kprl.aip.pool'
    _description = 'AIP Annual Pool (Sec J)'
    _order = 'year desc'

    name = fields.Char(string='Year', required=True)
    year = fields.Char(string='Year Label', required=True)
    annual_revenue_target = fields.Float(string='Annual Revenue Target', digits='Product Price')
    pool_rate = fields.Float(string='AIP Pool Rate', digits=(5, 4), default=0.002)
    full_year_ebitda = fields.Float(string='Full-Year EBITDA Margin (%)', digits=(5, 2))
    gate_threshold = fields.Float(string='Gate EBITDA Threshold (%)', digits=(5, 2), default=30.0)
    q1_kpi = fields.Float(string='Q1 Company KPI', digits=(5, 4))
    q2_kpi = fields.Float(string='Q2 Company KPI', digits=(5, 4))
    q3_kpi = fields.Float(string='Q3 Company KPI', digits=(5, 4))
    q4_kpi = fields.Float(string='Q4 Company KPI', digits=(5, 4))
    strategic_score = fields.Float(string='Strategic Objectives Score', digits=(5, 4), default=0.80,
        help='Workbook BONUS ENGINE B107 standing assumption; changes need CEO approval.')
    gross_pool = fields.Float(string='AIP Gross Pool', digits='Product Price', compute='_compute_pool', store=True)
    gate_factor = fields.Float(string='AIP Gate Factor', digits=(5, 2), compute='_compute_pool', store=True)
    funded_pool = fields.Float(string='AIP Funded Pool', digits='Product Price', compute='_compute_pool', store=True)
    avg_kpi = fields.Float(string='Annual Avg KPI', digits=(5, 4), compute='_compute_pool', store=True)
    composite = fields.Float(string='Composite Score', digits=(5, 4), compute='_compute_pool', store=True)
    aip_mult = fields.Float(string='AIP Performance Multiplier', digits=(5, 4), compute='_compute_pool', store=True)
    effective_pool = fields.Float(string='AIP Effective Pool', digits='Product Price', compute='_compute_pool', store=True)
    deferral_rate = fields.Float(string='AIP Deferred Rate', digits=(5, 4), default=0.30)
    state = fields.Selection([('draft', 'Draft'), ('computed', 'Computed'), ('paid', 'Paid')], string='Status', default='draft')
    param_state = fields.Selection([('approved', 'Approved'), ('pending_approval', 'Pending CEO Approval')], string='Parameter Approval', default='approved')
    param_submitted_by = fields.Many2one('res.users', string='Parameters Submitted By', readonly=True)
    param_approver_id = fields.Many2one('res.users', string='Parameters Approved By', readonly=True)
    param_approval_date = fields.Datetime(string='Parameter Approval Date', readonly=True)
    param_request_event_id = fields.Many2one('kprl.governance.event', string='Parameter Change Request', readonly=True)
    line_ids = fields.One2many('kprl.aip.line', 'pool_id', string='Allocations')
    accrual_ids = fields.One2many('kprl.aip.accrual', 'pool_id', string='Accrual Tracker')
    @api.depends('annual_revenue_target', 'pool_rate', 'full_year_ebitda', 'gate_threshold', 'q1_kpi', 'q2_kpi', 'q3_kpi', 'q4_kpi', 'strategic_score')
    def _compute_pool(self):
        for rec in self:
            rec.gross_pool = (rec.annual_revenue_target or 0.0) * (rec.pool_rate or 0.0)
            rec.gate_factor = 1.0 if (rec.full_year_ebitda or 0.0) >= (rec.gate_threshold or 22.0) else 0.0
            rec.funded_pool = rec.gross_pool * rec.gate_factor
            kpis = [k for k in [rec.q1_kpi, rec.q2_kpi, rec.q3_kpi, rec.q4_kpi] if k]
            rec.avg_kpi = sum(kpis) / len(kpis) if kpis else 0.0
            rec.composite = 0.60 * normalize_score(rec.avg_kpi) + 0.40 * normalize_score(rec.strategic_score or 0.0)
            rec.aip_mult = score_to_multiplier(rec.composite)
            rec.effective_pool = rec.funded_pool * rec.aip_mult
    AIP_GUARDED_PARAMS = ('gate_threshold', 'strategic_score', 'pool_rate', 'deferral_rate')

    def write(self, vals):
        guarded = set(vals) & set(self.AIP_GUARDED_PARAMS)
        if guarded and not self.env.user.has_group('kprl_bonus.group_kprl_admin'):
            raise AccessError('Only Admin, Finance or CEO may change AIP parameters (gate, strategic score, pool/deferral rates).')
        res = super().write(vals)
        if guarded:
            is_ceo = self.env.user.has_group('kprl_bonus.group_kprl_ceo')
            for rec in self:
                if is_ceo:
                    super(AipPool, rec).write({'param_state': 'approved', 'param_approver_id': self.env.user.id, 'param_approval_date': fields.Datetime.now()})
                else:
                    ev = self.env['kprl.governance.event'].create({
                        'trigger_type': 'aip_param_change',
                        'description': 'AIP parameter change on %s: %s' % (rec.name or rec.year or rec.id, ', '.join(sorted(guarded))),
                        'status': 'pending',
                    })
                    super(AipPool, rec).write({'param_state': 'pending_approval', 'param_submitted_by': self.env.user.id, 'param_request_event_id': ev.id})
        return res

    def action_approve_aip_params(self):
        self.ensure_one()
        if not self.env.user.has_group('kprl_bonus.group_kprl_ceo'):
            raise AccessError('Only the CEO may approve AIP parameter changes.')
        if self.param_submitted_by and self.param_submitted_by.id == self.env.user.id:
            raise ValidationError('The submitter cannot approve their own parameter change.')
        self.write({'param_state': 'approved', 'param_approver_id': self.env.user.id, 'param_approval_date': fields.Datetime.now()})
        if self.param_request_event_id:
            self.param_request_event_id.write({'status': 'applied', 'approver_id': self.env.user.id})
        return True

    def action_compute(self):
        self.ensure_one()
        elig = self.env['kprl.employee'].search([('aip_eligible', '=', True), ('status', '=', 'active')])
        if not elig:
            raise ValidationError('No AIP-eligible active employees found.')
        weights = {}
        appr = {}
        for emp in elig:
            pts = emp.grade_id.total_points if emp.grade_id else 0.0
            factor = self._annual_appraisal_multiplier(emp)
            appr[emp.id] = factor
            weights[emp.id] = (pts or 0.0) * (factor or 0.0)
        total_w = sum(weights.values()) or 1.0
        self.line_ids.unlink()
        for emp in elig:
            amt = self.effective_pool * weights[emp.id] / total_w
            self.env['kprl.aip.line'].create({
                'pool_id': self.id,
                'employee_id': emp.id,
                'aip_points': emp.grade_id.total_points if emp.grade_id else 0.0,
                'annual_appraisal': appr[emp.id],
                'weighted_score': weights[emp.id],
                'amount': amt,
                'deferred_amount': amt * (self.deferral_rate or 0.0),
                'immediate_amount': amt * (1.0 - (self.deferral_rate or 0.0)),
            })
        self.state = 'computed'

    def _annual_appraisal_multiplier(self, emp):
        """Section J col E = AIP points × appraisal MULTIPLIER (M curve)."""
        perf = self.env['kprl.performance.input'].search([('employee_id', '=', emp.id)], order='id desc', limit=1)
        val = perf.appraisal_score if perf and perf.appraisal_score else 0.0
        return appraisal_to_multiplier(normalize_score(val))

    def action_build_accruals_from_periods(self):
        """Section K accrual tracker: build quarterly accrual rows straight
        from the kprl.bonus.period records of this AIP year."""
        self.ensure_one()
        year = (self.year or '')[:4]
        domain = []
        periods = self.env['kprl.bonus.period'].search(
            [('name', 'ilike', year)] if year else [], order='date_start asc')
        quarters = []
        for i, p in enumerate(periods[:4], start=1):
            quarters.append({
                'n': i,
                'label': p.name,
                'ebitda': p.ebitda_margin or 0.0,
                'kpi': p.company_kpi or 0.0,
                # YTD approximations: average of quarters seen so far
                'ytd_ebitda': sum(q['ebitda'] for q in quarters) / i,
                'ytd_kpi': sum(q['kpi'] for q in quarters) / i,
            })
        if not quarters:
            raise ValidationError('No periods found for year %s.' % year)
        self.action_accrue(quarters)

    def action_accrue(self, quarters):
        self.ensure_one()
        self.accrual_ids.unlink()
        cumul = 0.0
        for q in quarters:
            ytd_ebitda = q.get('ytd_ebitda') or 0.0
            ytd_kpi = q.get('ytd_kpi') or 0.0
            gate = 1.0 if ytd_ebitda >= (self.gate_threshold or 22.0) else 0.0
            comp = 0.60 * normalize_score(ytd_kpi) + 0.40 * normalize_score(self.strategic_score or 0.0)
            mult = score_to_multiplier(comp)
            projected = self.gross_pool * gate * mult
            nq = q.get('n') or 1
            target_cumul = projected * nq / 4.0
            this_q = max(target_cumul - cumul, 0.0)
            cumul = target_cumul
            self.env['kprl.aip.accrual'].create({
                'pool_id': self.id,
                'quarter': nq,
                'period_label': q.get('label') or '',
                'qtr_ebitda': q.get('ebitda') or 0.0,
                'qtr_kpi': q.get('kpi') or 0.0,
                'ytd_ebitda': ytd_ebitda,
                'ytd_kpi': ytd_kpi,
                'gate': gate,
                'mult': mult,
                'projected_annual': projected,
                'cumulative_accrued': cumul,
                'this_qtr_accrual': this_q,
                'status': 'accrued' if q.get('actual') else 'pending',
            })
    def action_post_deferred(self):
        self.ensure_one()
        for line in self.line_ids:
            if not line.deferred_amount:
                continue
            exists = self.env['kprl.deferred.ledger'].search([('employee_id', '=', line.employee_id.id), ('aip_pool_id', '=', self.id)], limit=1)
            vals = {'employee_id': line.employee_id.id, 'calculated_bonus': line.amount, 'deferral_rate': (self.deferral_rate or 0.0) * 100.0, 'deferred_amount': line.deferred_amount, 'vest_date': datetime.date(int(self.year[:4]) + 2, 3, 31) if self.year and self.year[:4].isdigit() else datetime.date(2028, 3, 31), 'note': 'AIP ' + (self.year or ''), 'aip_pool_id': self.id}
            if exists:
                exists.write(vals)
            else:
                self.env['kprl.deferred.ledger'].create(vals)
        self.state = 'paid'


class AipLine(models.Model):
    _name = 'kprl.aip.line'
    _description = 'AIP Allocation Line'

    pool_id = fields.Many2one('kprl.aip.pool', string='AIP Pool', required=True, ondelete='cascade')
    employee_id = fields.Many2one('kprl.employee', string='Employee', required=True)
    aip_points = fields.Float(string='AIP Points', digits=(5, 2))
    annual_appraisal = fields.Float(string='Annual Appraisal Factor', digits=(5, 4))
    weighted_score = fields.Float(string='Weighted Score', digits=(5, 4))
    amount = fields.Float(string='AIP Amount', digits='Product Price')
    deferred_amount = fields.Float(string='Deferred (30%)', digits='Product Price')
    immediate_amount = fields.Float(string='Immediate Cash (70%)', digits='Product Price')


class AipAccrual(models.Model):
    _name = 'kprl.aip.accrual'
    _description = 'AIP Quarterly Accrual'
    _order = 'quarter'

    pool_id = fields.Many2one('kprl.aip.pool', string='AIP Pool', required=True, ondelete='cascade')
    quarter = fields.Integer(string='Quarter')
    period_label = fields.Char(string='Period')
    qtr_ebitda = fields.Float(string='Qtr EBITDA (%)', digits=(5, 2))
    qtr_kpi = fields.Float(string='Qtr KPI', digits=(5, 4))
    ytd_ebitda = fields.Float(string='YTD EBITDA (%)', digits=(5, 2))
    ytd_kpi = fields.Float(string='YTD KPI', digits=(5, 4))
    gate = fields.Float(string='Gate', digits=(5, 2))
    mult = fields.Float(string='Multiplier', digits=(5, 4))
    projected_annual = fields.Float(string='Projected Annual AIP', digits='Product Price')
    cumulative_accrued = fields.Float(string='Cumulative Accrued', digits='Product Price')
    this_qtr_accrual = fields.Float(string='This-Qtr Accrual', digits='Product Price')
    status = fields.Selection([('accrued', 'Accrued YTD'), ('pending', 'Pending')], string='Status', default='pending')
