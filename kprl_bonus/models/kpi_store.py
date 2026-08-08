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
        default='https://kachelan.odoo.com/api/pms/appraisal',
    )
    token = fields.Char(
        string='API Token',
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
                emp = self.env['kprl.employee'].search(
                    [('staff_id', '=', rec.staff_id)], limit=1,
                )
                rec.employee_id = emp.id if emp else False
            else:
                rec.employee_id = False

    def action_fetch_kpi(self):
        URL = "https://kachelan.odoo.com/api/pms/appraisal"
        TOKEN = "MY_STATIC_SECRET_TOKEN_123456"
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "employee_number": "KPRL/0016",
            "date_from": False # "2026-01-01"      # Optional
        }
        response = requests.post(
            URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        _logger.info("Status Code:", response.status_code)
        _logger.info(response.json())

    def get_response_value(self, responseData):
        pass
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

    def get_response_value(self, responseData):
        message = responseData.get('message', '')
        if message and message.lower() not in ('successful', 'ok', 'success'):
            raise ValidationError(
                f'API returned an error: {message}\n'
                f'Return code: {responseData.get("returnCode", "N/A")}'
            )

        data = responseData.get('data', responseData)

        employee_number = (
            data.get('employee_number')
            or data.get('employeeNumber')
            or data.get('staff_id')
            or rec.staff_id if (rec := self) else False
        )
        score = (
            data.get('score')
            or data.get('appraisal_score')
            or data.get('appraisalScore')
            or 0.0
        )
        score_max = (
            data.get('score_max')
            or data.get('scoreMax')
            or data.get('max_score')
            or 100.0
        )
        appraisal_date = (
            data.get('date')
            or data.get('appraisal_date')
            or data.get('appraisalDate')
            or str(self.date_from) if self.date_from else False
        )

        employee = self.env['kprl.employee'].search(
            [('staff_id', '=', employee_number)], limit=1,
        )
        if not employee:
            raise ValidationError(
                f'No kprl.employee found with staff_id = {employee_number}'
            )

        vals = {
            'kpi_store_id': self.id,
            'staff_id': employee_number,
            'employee_id': employee.id,
            'appraisal_score': float(score),
            'score_max': float(score_max),
        }
        if appraisal_date:
            vals['appraisal_date'] = appraisal_date

        self.env['kprl.kpi.store.line'].create(vals)
        self.state = 'completed'
        self.result_message = f'Fetched score {score} for {employee_number}'

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

            if existing:
                existing.write({'appraisal_score': line.appraisal_score})
            else:
                perf_model.create({
                    'employee_id': line.employee_id.id,
                    'period_id': period.id,
                    'appraisal_score': line.appraisal_score,
                })

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
    period_id = fields.Many2one(
        'kprl.bonus.period', string='Period',
        related='kpi_store_id.period_id', store=True,
    )