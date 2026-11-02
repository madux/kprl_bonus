# -*- coding: utf-8 -*-
import logging
import json
import requests
from datetime import datetime

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from requests.exceptions import RequestException

_logger = logging.getLogger(__name__)


class KpiStore(models.Model):
    _name = 'kprl.kpi.store'
    _description = 'KPI Store - Appraisal API Fetcher'
    _rec_name = 'display_name'

    api_url = fields.Char(
        string='Appraisal API URL',
        required=True,
        default='https://kachelan.odoo.com/api/pms/appraisal',
    )
    token = fields.Char(
        string='API Token',
        required=True,
        default='MY_STATIC_SECRET_TOKEN_123456',
    )
    staff_id = fields.Char(
        string='Staff ID',
        help='The employee_number to pass to the API (maps to kprl.employee.staff_id)',
    )
    date_from = fields.Date(string='Date From (Optional)')
    period_id = fields.Many2one(
        'kprl.bonus.period', string='Target Period',
        help='Period to push appraisal scores into kprl.performance.input',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('completed', 'Completed')],
        string='Status', default='draft',
    )
    kpi_store_line_ids = fields.One2many(
        'kprl.kpi.store.line', 'kpi_store_id', string='KPI Store Lines',
    )
    raw_result = fields.Text(string='Raw API Result')
    result_message = fields.Char(string='Result Message')
    employee_id = fields.Many2one(
        'kprl.employee', string='Matched Employee',
        compute='_compute_employee_id', store=True,
    )

    @api.depends('staff_id')
    def _compute_employee_id(self):
        for rec in self:
            if rec.staff_id:
                emp = self._find_kprl_employee(rec.staff_id)
                rec.employee_id = emp.id if emp else False
            else:
                rec.employee_id = False

    @api.model
    def _call_appraisal_api(self, api_url, token, employee_number=False, date_from=False):
        """POST to the appraisal API.

        Envelope: result.result.success + result.result.data[] with keys
        employee_number / employee_name / work_email / department_name /
        phone / average_aggregate / overall_score / potential_assessment_score /
        current_assessment_score / employment_date (YYYY-MM-DD or null).
        Returns (result_dict, raw_text). Console-logs status, top-level
        keys, record count and a first-record sample for inspection."""
        URL = api_url or "https://kachelan.odoo.com/api/pms/appraisal"
        TOKEN = token or "MY_STATIC_SECRET_TOKEN_123456"
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "employee_number": employee_number or False,
            "date_from": date_from or None,
        }
        _logger.info("KPRL KPI Store: POST %s payload=%s", URL, payload)
        try:
            response = requests.post(
                URL,
                headers=headers,
                json=payload,
                timeout=30,
                verify=False,
            )
        except RequestException as e:
            _logger.exception("KPRL KPI Store: connection failed for %s", URL)
            raise ValidationError(f"Unable to reach Appraisal API.\n{str(e)}")
        if response.status_code >= 400:
            _logger.warning(
                "KPRL KPI Store: HTTP %s body=%s",
                response.status_code, (response.text or "")[:2000],
            )
            raise ValidationError(
                f"Appraisal API returned HTTP {response.status_code}.\n{(response.text or '')[:500]}"
            )
        try:
            result = response.json()
        except ValueError:
            _logger.warning("KPRL KPI Store: non-JSON body=%s", (response.text or "")[:2000])
            raise ValidationError("Appraisal API did not return JSON.")
        keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
        _logger.info("KPRL KPI Store: HTTP %s top-level keys=%s", response.status_code, keys)
        inner = (result.get("result", {}) or {}) if isinstance(result, dict) else {}
        data = inner.get("data", [])
        sample = data[0] if isinstance(data, list) and data else None
        _logger.info(
            "KPRL KPI Store: %s record(s); sample=%s",
            len(data) if isinstance(data, list) else "?",
            json.dumps(sample, default=str)[:2000],
        )
        return result, (response.text or "")

    def action_fetch_kpi(self):
        self.ensure_one()
        date_from = self.date_from.strftime("%Y-%m-%d") if self.date_from else None
        result, _raw = self._call_appraisal_api(
            self.api_url, self.token, self.staff_id or False, date_from,
        )
        return result

    @api.model
    def _numbers_equal(self, a, b):
        """Separator-tolerant staff-ID match: Odoo uses dashes (KPRL-043),
        PMS uses slashes (KPRL/043). Case/whitespace-insensitive."""
        if not a or not b:
            return False
        norm = lambda n: str(n).strip().upper().replace("-", "/")
        return norm(a) == norm(b)

    @api.model
    def _numbering_sample(self, data, limit=20):
        """Employee_numbers seen in a PMS data list (for logs + messages)."""
        return [r.get("employee_number") for r in (data or [])
                if isinstance(r, dict) and r.get("employee_number")][:limit]

    @api.model
    def _numbering_hint(self, sample, total=None, limit=10):
        """Human-readable PMS numbering sample for error messages shown
        to users (who cannot open odoo.log)."""
        nums = [str(n) for n in (sample or []) if n]
        if not nums:
            return "PMS returned no employee records at all."
        shown = ", ".join(nums[:limit])
        n_total = total if total is not None else len(nums)
        extra = "" if n_total <= limit else " (+%d more)" % (n_total - limit)
        return "PMS uses IDs like: %s%s." % (shown, extra)

    @api.model
    def _fetch_with_fallback(self, api_url, token, employee_number=False, date_from=False):
        """Targeted fetch, falling back to an unfiltered pull matched locally.

        The PMS sometimes answers a targeted lookup with 'Employee not
        found' even though the employee exists (numbering/format drift).
        In that case we pull unfiltered, log the numbering the PMS
        actually uses, and match locally. Returns (result, raw_text,
        data_list, numbering_sample) of the effective call, where
        numbering_sample is the list of PMS employee_numbers seen (used
        to show the user the real PMS numbering in error messages)."""
        result, raw_text = self._call_appraisal_api(
            api_url, token, employee_number or False, date_from,
        )
        inner = (result.get("result", {}) or {}) if isinstance(result, dict) else {}
        if isinstance(inner, dict) and inner.get("error"):
            raise ValidationError(
                f"Appraisal API error.\n{str(inner.get('error'))[:500]}"
            )
        data = (inner.get("data", []) or []) if isinstance(inner, dict) else []
        if data or not employee_number:
            return result, raw_text, data, self._numbering_sample(data)
        _logger.info(
            "KPRL KPI Store: no hit for '%s' (%s); retrying unfiltered pull",
            employee_number, inner.get("message") or "no message",
        )
        result2, raw2 = self._call_appraisal_api(api_url, token, False, date_from)
        inner2 = (result2.get("result", {}) or {}) if isinstance(result2, dict) else {}
        data2 = (inner2.get("data", []) or []) if isinstance(inner2, dict) else []
        nums = [r.get("employee_number") for r in data2 if isinstance(r, dict)][:20]
        _logger.info(
            "KPRL KPI Store: unfiltered pull returned %d record(s); "
            "PMS numbering sample=%s",
            len(data2), nums,
        )
        matched = [
            r for r in data2
            if isinstance(r, dict) and self._numbers_equal(r.get("employee_number"), employee_number)
        ]
        if matched:
            _logger.info(
                "KPRL KPI Store: '%s' matched in unfiltered pull as '%s'",
                employee_number,
                matched[0].get("employee_number") if isinstance(matched[0], dict) else "?",
            )
            return result2, raw2, matched, self._numbering_sample(data2)
        return result2, raw2, [], self._numbering_sample(data2)

    @api.model
    def _behaviour_scores_from_pms(self, rec):
        """Per-employee behavioural scores from one PMS record dict.

        Reads potential_assessment_score + current_assessment_score
        (missing/null -> 0.0), averages them, and normalises the total
        into the Behaviour /25 scale (percent-style values > 25 are
        converted via /100*25, values already 0-25 pass through).
        Returns (potential, current, behaviour_25). Unique per employee:
        call inside the per-record loop, never aggregated across staff.
        """
        rec = rec or {}
        try:
            potential = float(rec.get('potential_assessment_score') or 0.0)
        except (TypeError, ValueError):
            potential = 0.0
        try:
            current = float(rec.get('current_assessment_score') or 0.0)
        except (TypeError, ValueError):
            current = 0.0
        total = (potential + current) / 2.0
        behaviour_25 = total / 100.0 * 25.0 if total > 25.0 else total
        return potential, current, behaviour_25

    def get_department(self, name):
        department = self.env['hr.department'].sudo().search([('name', '=ilike', name)], limit =1)
        if not department:
            department = self.env['hr.department'].sudo().create({
                'name': name
            })
        kprl_department = self.env['kprl.department'].sudo().search([('name', '=ilike', name)], limit =1)
        if not kprl_department:
            kprl_department = self.env['kprl.department'].sudo().create({
                'name': name
            })
        return department.id, kprl_department.id

    @api.model
    @api.model
    def _staff_domain(self, number):
        """OR-domain covering dash/slash drift (KPRL-043 / KPRL/043)."""
        from .kprl_math import staff_id_variants
        variants = staff_id_variants(number)
        if not variants:
            return [('id', '=', 0)]
        dom = [('staff_id', '=', variants[0])]
        for variant in variants[1:]:
            dom = ['|'] + dom + [('staff_id', '=', variant)]
        return dom

    @api.model
    def _find_kprl_employee(self, number):
        if not number:
            return self.env['kprl.employee'].browse()
        return self.env['kprl.employee'].search(self._staff_domain(number), limit=1)

    @api.model
    def _resolve_grade(self, code, name):
        """Match PMS grade to kprl.grade: code first (exact, upper), then
        name (case-insensitive). Returns record or False (caller raises)."""
        Grade = self.env['kprl.grade']
        if code and str(code).strip():
            grade = Grade.search([('code', '=', str(code).strip().upper())], limit=1)
            if grade:
                return grade
        if name and str(name).strip():
            grade = Grade.search([('name', '=ilike', str(name).strip())], limit=1)
            if grade:
                return grade
        return False

    @api.model
    def _resolve_manager(self, mgr_number, employee_id=False):
        """Resolve manager_staff_number to a kprl.employee (tolerant match).
        Returns record or False (missing, blank, or self-reference)."""
        if not mgr_number:
            return False
        mgr = self._find_kprl_employee(mgr_number)
        if not mgr:
            return False
        if employee_id and mgr.id == employee_id:
            return False
        return mgr

    @api.model
    def _validate_batch_records(self, data):
        """Pre-pass: every PMS record's grade + manager must resolve before
        any write happens. Returns a list of human-readable problems."""
        from .kprl_math import normalize_staff_id
        problems = []
        recs = [r for r in (data or []) if isinstance(r, dict) and r.get('employee_number')]
        incoming = {normalize_staff_id(r.get('employee_number')) for r in recs}
        existing = {normalize_staff_id(s) for s in
                    self.env['kprl.employee'].search([]).mapped('staff_id')}
        known = {s for s in (incoming | existing) if s}
        for rec in recs:
            sid = rec.get('employee_number')
            if rec.get('grade_code') or rec.get('grade_name'):
                if not self._resolve_grade(rec.get('grade_code'), rec.get('grade_name')):
                    problems.append(
                        "%s: grade code=%r name=%r not found in Odoo grades. "
                        "Update PMS grade_name/grade_code." % (
                            sid, rec.get('grade_code'), rec.get('grade_name')))
            mgr = rec.get('manager_staff_number')
            if mgr:
                if normalize_staff_id(mgr) == normalize_staff_id(sid):
                    problems.append(
                        "%s: manager_staff_number is self. Fix PMS reporting line." % sid)
                elif normalize_staff_id(mgr) not in known:
                    problems.append(
                        "%s: manager %r not found. Sync the manager first or fix "
                        "PMS manager_staff_number." % (sid, mgr))
        return problems

    def _sync_employee_record(self, rec, period=False, link_manager=True):
        """Find-or-create hr + kprl employee from one API record dict.

        Matches kprl.employee by staff_id only (names may differ in
        spelling between systems). Updates master fields on match.
        Optionally upserts the period performance input. One bad record
        raises ValidationError so the caller can isolate it."""
        from .kprl_math import normalize_staff_id, check_staff_id
        staff_id = normalize_staff_id((rec or {}).get('employee_number'))
        if not staff_id:
            raise ValidationError('API record without employee_number; skipped.')
        try:
            check_staff_id(staff_id)
        except ValueError as exc:
            raise ValidationError(
                'PMS sent an invalid staff ID %r: %s' % (
                    (rec or {}).get('employee_number'), exc))
        employee_name = rec.get('employee_name') or staff_id
        work_email = rec.get('work_email')
        department_name = rec.get('department_name')
        phone = rec.get('phone')
        # --------------------------------------------------
        # HR EMPLOYEE
        # --------------------------------------------------
        hr_employee = self.env['hr.employee'].search(
            self._staff_domain(staff_id), limit=1)
        if not hr_employee:
            hr_employee = self.env['hr.employee'].create({
                'name': employee_name,
                'staff_id': staff_id,
            })
        # --------------------------------------------------
        # KPRL EMPLOYEE (match by Staff ID only)
        # --------------------------------------------------
        kprl_employee = self._find_kprl_employee(staff_id)
        kprl_vals = {
            'name': employee_name,
            'employee_id': hr_employee.id,
        }
        if work_email:
            kprl_vals['work_email'] = work_email
        if phone:
            kprl_vals['phone'] = phone
        if rec.get('job_title'):
            kprl_vals['job_title'] = rec['job_title']
        if rec.get('grade_code') or rec.get('grade_name'):
            grade = self._resolve_grade(rec.get('grade_code'), rec.get('grade_name'))
            if not grade:
                raise ValidationError(
                    "Staff %s: PMS grade code=%r name=%r not found in Odoo grades. "
                    "Update PMS grade_name/grade_code, then re-sync." % (
                        staff_id, rec.get('grade_code'), rec.get('grade_name')))
            kprl_vals['grade_id'] = grade.id
        from .kprl_math import parse_pms_employment_date
        hired = parse_pms_employment_date(rec.get('employment_date'))
        if hired:
            kprl_vals['employment_date'] = hired
        elif rec.get('employment_date') not in (None, '', False):
            _logger.warning(
                "KPRL KPI Store: staff %s sent unparseable employment_date=%r; kept existing.",
                staff_id, rec.get('employment_date'))
        if department_name:
            _hr_dep, kprl_dep = self.get_department(department_name)
            kprl_vals['department_id'] = kprl_dep
        if not kprl_employee:
            kprl_employee = self.env['kprl.employee'].create(dict(
                kprl_vals, staff_id=staff_id,
            ))
        else:
            kprl_employee.write(kprl_vals)
        if link_manager and rec.get('manager_staff_number'):
            mgr = self._resolve_manager(rec.get('manager_staff_number'), kprl_employee.id)
            if not mgr:
                raise ValidationError(
                    "Staff %s: manager %r not found. Sync the manager first or fix "
                    "PMS manager_staff_number, then re-sync." % (
                        staff_id, rec.get('manager_staff_number')))
            if (kprl_employee.manager_id.id or False) != mgr.id:
                kprl_employee.write({'manager_id': mgr.id})
        # --------------------------------------------------
        # PERFORMANCE INPUT
        # --------------------------------------------------
        if period:
            performance_input = self.env['kprl.performance.input'].search([
                ('employee_id', '=', kprl_employee.id),
                ('period_id', '=', period.id),
            ], limit=1)
            _pot, _cur, _behav25 = self._behaviour_scores_from_pms(rec)
            vals = {
                'period_id': period.id,
                'employee_id': kprl_employee.id,
                # API average_aggregate mapped to appraisal score
                'appraisal_score': rec.get('average_aggregate', 0.0),
                'retain_score': rec.get('overall_score', 0.0),
                # PMS behavioural duo averaged into Behaviour (/25)
                'potential_assessment_score': _pot,
                'current_assessment_score': _cur,
                'team_pct': _behav25,
            }
            if performance_input:
                performance_input.write(vals)
            else:
                self.env['kprl.performance.input'].create(vals)
        return kprl_employee

    def get_api_response_value(self):
        self.ensure_one()
        date_from = self.date_from.strftime("%Y-%m-%d") if self.date_from else None
        _result, raw_text, data, numbering = self._fetch_with_fallback(
            self.api_url, self.token, self.staff_id or False, date_from,
        )
        self.raw_result = (raw_text or "")[:5000]
        if not data:
            raise ValidationError(
                "No appraisal records found"
                + (f" for '{self.staff_id}'" if self.staff_id else "")
                + ". Fix the Staff ID to match PMS numbering. "
                + self._numbering_hint(numbering)
            )
        period = self.period_id or self.env['kprl.bonus.period'].search([
            ('date_start', '<=', self.date_from),
            ('date_end', '>=', self.date_from),
        ], limit=1)

        if not period:
            raise ValidationError(
                'No bonus period found. Please set a Target Period on the KPI Store record '
                'or ensure a period exists that covers the Date From value.'
            )

        problems = self._validate_batch_records(data)
        if problems:
            raise ValidationError(
                "PMS sync blocked: fix these in PMS (or sync the listed managers first), "
                "then re-run. No records were written.\n- " + "\n- ".join(problems))
        self.kpi_store_line_ids.unlink()
        ok, skipped, errors = 0, 0, []
        synced = []
        for rec in data:
            if not isinstance(rec, dict):
                skipped += 1
                continue
            try:
                kprl_employee = self._sync_employee_record(rec, period, link_manager=False)
                synced.append((kprl_employee, rec))
                _pot, _cur, _behav25 = self._behaviour_scores_from_pms(rec)
                self.env['kprl.kpi.store.line'].create({
                    'kpi_store_id': self.id,
                    'staff_id': rec.get('employee_number'),
                    'employee_id': kprl_employee.id,
                    'appraisal_score': rec.get('average_aggregate', 0.0),
                    'score_max': 100.0,
                    'appraisal_date': self.date_from or False,
                    'potential_assessment_score': _pot,
                    'current_assessment_score': _cur,
                    'behaviour_25': _behav25,
                })
                ok += 1
            except ValidationError as e:
                skipped += 1
                errors.append(str(e))
                _logger.warning(
                    "KPRL KPI Store: skipped record %s: %s",
                    (rec.get('employee_number') if isinstance(rec, dict) else '?'), e,
                )
                continue
        for kprl_employee, rec in synced:
            if rec.get('manager_staff_number'):
                mgr = self._resolve_manager(rec.get('manager_staff_number'), kprl_employee.id)
                if not mgr:
                    raise ValidationError(
                        "Staff %s: manager %r not found. Sync the manager first or fix "
                        "PMS manager_staff_number, then re-sync." % (
                            rec.get('employee_number'), rec.get('manager_staff_number')))
                if (kprl_employee.manager_id.id or False) != mgr.id:
                    kprl_employee.write({'manager_id': mgr.id})
        self.state = 'completed'
        self.result_message = f'Fetched {ok} employee(s)' + (f', skipped {skipped}' if skipped else '')
        if errors:
            _logger.info("KPRL KPI Store: skipped details=%s", errors[:5])
                    
    # def action_fetch_kpixxxx(self):
    #     for rec in self:
    #         icp = self.env['ir.config_parameter'].sudo()

    #         api_url = rec.api_url or icp.get_param(
    #             'kprl_kpi_store.api_url',
    #             'https://kachelan.odoo.com/api/pms/appraisal',
    #         )
    #         token = rec.token or icp.get_param('kprl_kpi_store.token', '')

    #         if not token:
    #             raise ValidationError(
    #                 'API token is required. Set it on the record or in '
    #                 'ir.config_parameter (kprl_kpi_store.token).'
    #             )
    #         if not rec.staff_id:
    #             raise ValidationError(
    #                 'Staff ID is required. Enter the employee_number '
    #                 '(e.g. KPRL/0016) to fetch.'
    #             )

    #         payload = {
    #             'employee_number': rec.staff_id,
    #             'date_from': str(rec.date_from) if rec.date_from else False,
    #         }

    #         headers = {
    #             'Authorization': f'Bearer {token}',
    #             'Content-Type': 'application/json',
    #         }

    #         try:
    #             _logger.info(
    #                 'KPI Store: Calling %s with payload %s', api_url, payload,
    #             )
    #             response = requests.post(
    #                 api_url,
    #                 json=payload,
    #                 headers=headers,
    #                 timeout=120,
    #             )
    #             response.raise_for_status()
    #             result = response.json()

    #             _logger.info('KPI Store: Response %s', result)

    #             rec.raw_result = json.dumps(result, indent=4)
    #             rec.get_response_value(result)

    #         except RequestException as e:
    #             _logger.exception('KPI Store API Error')
    #             raise ValidationError(
    #                 f'Unable to connect to Appraisal API.\n{str(e)}'
    #             )


    def action_push_to_performance(self):
        perf_model = self.env['kprl.performance.input']
        for line in self.kpi_store_line_ids:
            if not line.period_id and not self.period_id:
                raise ValidationError(
                    'Set a Target Period on the KPI Store record before '
                    'pushing to performance inputs.'
                )
            period = line.period_id or self.period_id

            existing = perf_model.search([
                ('employee_id', '=', line.employee_id.id),
                ('period_id', '=', period.id),
            ], limit=1)

            push_vals = {
                'appraisal_score': line.appraisal_score,
                'potential_assessment_score': line.potential_assessment_score,
                'current_assessment_score': line.current_assessment_score,
                'team_pct': line.behaviour_25,
            }
            if existing:
                existing.write(push_vals)
            else:
                push_vals.update({
                    'employee_id': line.employee_id.id,
                    'period_id': period.id,
                })
                perf_model.create(push_vals)

    def action_reset(self):
        self.state = 'draft'


class KpiStoreLine(models.Model):
    _name = 'kprl.kpi.store.line'
    _description = 'KPI Store Line'
    _rec_name = 'employee_id'

    kpi_store_id = fields.Many2one(
        'kprl.kpi.store', string='KPI Store', required=True,
        ondelete='cascade',
    )
    staff_id = fields.Char(string='Staff ID')
    employee_id = fields.Many2one(
        'kprl.employee', string='Employee',
    )
    appraisal_score = fields.Float(
        string='Appraisal Score', digits=(5, 2),
    )
    score_max = fields.Float(
        string='Score Max', default=100.0,
    )
    appraisal_date = fields.Date(string='Appraisal Date')
    potential_assessment_score = fields.Float(
        string='Potential Assessment', digits=(5, 2),
    )
    current_assessment_score = fields.Float(
        string='Current Assessment', digits=(5, 2),
    )
    behaviour_25 = fields.Float(
        string='Behaviour (/25)', digits=(5, 2),
        help='Per-employee total: (potential + current) / 2, normalised to /25.',
    )
    period_id = fields.Many2one(
        'kprl.bonus.period', string='Period',
        related='kpi_store_id.period_id', store=True,
    )