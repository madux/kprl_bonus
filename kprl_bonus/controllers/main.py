import json
import base64
from odoo import http
from odoo.http import request, Response
from odoo.exceptions import AccessError
from odoo.addons.web.controllers.main import Home


class KprlApi(http.Controller):
    """JSON API endpoints for the KPRL Bonus frontend."""

    # ─── Periods ────────────────────────────────────────────────────────────

    @http.route('/kprl/api/periods', type='http', auth='user', methods=['GET'],
                csrf=False)
    def api_periods(self):
        periods = request.env['kprl.bonus.period'].search_read(
            [], ['id', 'name', 'date_start', 'date_end', 'state'],
            order='date_start desc'
        )
        return self._json_response(periods)

    # ─── Dashboard ──────────────────────────────────────────────────────────

    @http.route('/kprl/api/dashboard/<int:period_id>', type='http',
                auth='user', methods=['GET'], csrf=False)
    def api_dashboard(self, period_id):
        period = request.env['kprl.bonus.period'].browse(period_id)
        if not period.exists():
            return self._json_error('Period not found', 404)

        engine = request.env['kprl.bonus.engine'].search([
            ('period_id', '=', period_id),
        ], limit=1, order='create_date desc')

        dept_payouts = request.env['kprl.bonus.payout'].search_read([
            ('period_id', '=', period_id),
        ], ['employee_id', 'department_id', 'gross_payable', 'net_immediate',
            'dept_kpi_mult'])

        dept_scores = request.env['kprl.dept.kpi.multiplier'].search_read([
            ('period_id', '=', period_id),
        ], ['department_id', 'kpi_score', 'multiplier', 'gmp_status'])

        data = {
            'period': {'id': period.id, 'name': period.name,
                       'state': period.state},
            'engine': engine.read(['quarterly_revenue', 'net_revenue',
                'pool_contribution', 'gate_status', 'ebitda_margin',
                'gate_factor', 'gmp_status', 'gmp_factor', 'company_kpi_score',
                'effective_pool', 'proration_factor', 'total_payout',
                'ops_payout', 'sales_commission', 'payout_as_pct_revenue',
                'pool_util_vs_ebitda_cap', 'headcount', 'aip_pool',
                'state'])[0] if engine else {},
            'departments': dept_scores,
            'payouts': dept_payouts,
        }
        return self._json_response(data)

    # ─── Departments ────────────────────────────────────────────────────────

    @http.route('/kprl/api/departments/<int:period_id>', type='http',
                auth='user', methods=['GET'], csrf=False)
    def api_departments(self, period_id):
        depts = request.env['kprl.dept.kpi.multiplier'].search_read([
            ('period_id', '=', period_id),
        ], ['department_id', 'kpi_score', 'multiplier', 'weight', 'gmp_status'])
        return self._json_response(depts)

    # ─── Employees ──────────────────────────────────────────────────────────

    @http.route('/kprl/api/employees', type='http', auth='user',
                methods=['GET'], csrf=False)
    def api_employees(self):
        employees = request.env['kprl.employee'].search_read(
            [], ['id', 'name', 'employee_id', 'department_id', 'grade_id',
                 'job_title', 'status', 'is_sales', 'sales_role',
                 'tenure_years', 'date_hired'],
            order='employee_id'
        )
        return self._json_response(employees)

    @http.route('/kprl/api/employee/<int:emp_id>', type='http', auth='user',
                methods=['GET'], csrf=False)
    def api_employee_detail(self, emp_id):
        emp = request.env['kprl.employee'].browse(emp_id)
        if not emp.exists():
            return self._json_error('Employee not found', 404)
        data = emp.read(['id', 'name', 'employee_id', 'department_id',
                         'grade_id', 'job_title', 'subpool_id', 'date_hired',
                         'tenure_years', 'manager_id', 'status', 'is_sales',
                         'sales_role', 'territory_id', 'email', 'phone'])[0]
        if data.get('department_id'):
            dept = request.env['kprl.department'].browse(
                data['department_id'][0])
            data['department_name'] = dept.name
        if data.get('grade_id'):
            grade = request.env['kprl.grade'].browse(data['grade_id'][0])
            data['grade_code'] = grade.code
            data['grade_name'] = grade.name
            data['token_rate'] = grade.token_rate
            data['total_points'] = grade.total_points
        return self._json_response(data)

    @http.route('/kprl/api/employee/<int:emp_id>/payout/<int:period_id>',
                type='http', auth='user', methods=['GET'], csrf=False)
    def api_employee_payout(self, emp_id, period_id):
        payout = request.env['kprl.bonus.payout'].search([
            ('employee_id', '=', emp_id),
            ('period_id', '=', period_id),
        ], limit=1)
        if not payout:
            return self._json_response({})
        data = payout.read(['id', 'period_id', 'employee_id', 'base_eligible',
            'dept_kpi_mult', 'appraisal_mult', 'behavioural_mult',
            'exception_premium', 'proration_factor', 'tenure_mult', 'gmp_factor',
            'malus_amount', 'gross_payable', 'deferral_rate', 'deferred_amount',
            'net_immediate', 'state'])[0]
        return self._json_response(data)

    # ─── Performance Inputs ─────────────────────────────────────────────────

    @http.route('/kprl/api/performance/<int:period_id>', type='http',
                auth='user', methods=['GET'], csrf=False)
    def api_performance(self, period_id):
        records = request.env['kprl.performance.input'].search_read([
            ('period_id', '=', period_id),
        ], ['employee_id', 'appraisal_score', 'retain_score', 'own_target',
            'own_sales', 'own_revenue', 'prod_pct', 'call_pct', 'present_pct',
            'team_pct'])
        return self._json_response(records)

    @http.route('/kprl/api/performance', type='http', auth='user',
                methods=['PUT'], csrf=False)
    def api_performance_save(self):
        data = json.loads(request.httprequest.data)
        perf = request.env['kprl.performance.input']
        for rec in data:
            existing = perf.search([
                ('employee_id', '=', rec.get('employee_id')),
                ('period_id', '=', rec.get('period_id')),
            ], limit=1)
            if existing:
                existing.write(rec)
            else:
                perf.create(rec)
        return self._json_response({'status': 'saved'})

    # ─── Bonus Config / Parameters ──────────────────────────────────────────

    @http.route('/kprl/api/config/<int:period_id>', type='http', auth='user',
                methods=['GET'], csrf=False)
    def api_config(self, period_id):
        param = request.env['kprl.bonus.parameter'].search([
            ('period_id', '=', period_id),
        ], limit=1)
        if not param:
            return self._json_response({})
        data = param.read([])[0]
        return self._json_response(data)

    @http.route('/kprl/api/config/<int:period_id>', type='http', auth='user',
                methods=['PUT'], csrf=False)
    def api_config_save(self, period_id):
        data = json.loads(request.httprequest.data)
        param = request.env['kprl.bonus.parameter'].search([
            ('period_id', '=', period_id),
        ], limit=1)
        if param and param.is_locked:
            return self._json_error('Parameters are locked (approved)', 403)
        try:
            if param:
                param.write(data)
            else:
                data['period_id'] = period_id
                request.env['kprl.bonus.parameter'].create(data)
        except AccessError as e:
            return self._json_error(str(e), 403)
        return self._json_response({'status': 'saved'})

    @http.route('/kprl/api/config/<int:period_id>/submit', type='http',
                auth='user', methods=['PUT'], csrf=False)
    def api_config_submit(self, period_id):
        param = request.env['kprl.bonus.parameter'].search([
            ('period_id', '=', period_id),
        ], limit=1)
        if not param:
            return self._json_error('No parameters found for this period', 404)
        if param.state not in ('draft', 'rejected'):
            return self._json_error(
                'Parameters can only be submitted from Draft or Rejected status', 403)
        param.action_submit()
        return self._json_response({'status': 'submitted', 'state': 'pending_approval'})

    # ─── Compute Bonus ──────────────────────────────────────────────────────

    @http.route('/kprl/api/compute/<int:period_id>', type='http', auth='user',
                methods=['POST'], csrf=False)
    def api_compute(self, period_id):
        period = request.env['kprl.bonus.period'].browse(period_id)
        if not period.exists():
            return self._json_error('Period not found', 404)

        engine = request.env['kprl.bonus.engine'].search([
            ('period_id', '=', period_id),
        ], limit=1, order='create_date desc')

        if not engine:
            engine = request.env['kprl.bonus.engine'].create({
                'period_id': period_id,
            })

        try:
            engine.action_compute()
            return self._json_response({
                'status': 'computed',
                'engine_id': engine.id,
                'effective_pool': engine.effective_pool,
                'total_payout': engine.total_payout,
                'gate_status': engine.gate_status,
            })
        except Exception as e:
            return self._json_error(str(e), 500)

    # ─── Payouts ────────────────────────────────────────────────────────────

    @http.route('/kprl/api/payouts/<int:period_id>', type='http', auth='user',
                methods=['GET'], csrf=False)
    def api_payouts(self, period_id):
        payouts = request.env['kprl.bonus.payout'].search_read([
            ('period_id', '=', period_id),
        ], ['employee_id', 'department_id', 'grade_id', 'gross_payable',
            'deferred_amount', 'net_immediate', 'state'])
        return self._json_response(payouts)

    # ─── Territories ────────────────────────────────────────────────────────

    @http.route('/kprl/api/territories/<int:period_id>', type='http',
                auth='user', methods=['GET'], csrf=False)
    def api_territories(self, period_id):
        territories = request.env['kprl.territory'].search_read(
            [], ['id', 'name', 'code', 'rsm_id', 'rsm_target', 'team_target',
                 'effective_target', 'source']
        )
        payouts = request.env['kprl.territory.payout'].search_read([
            ('period_id', '=', period_id),
        ], ['territory_id', 'achievement_pct', 'commission_payable'])
        return self._json_response({
            'territories': territories,
            'payouts': payouts,
        })

    # ─── Deferred Ledger ────────────────────────────────────────────────────

    @http.route('/kprl/api/deferred/<int:emp_id>', type='http', auth='user',
                methods=['GET'], csrf=False)
    def api_deferred(self, emp_id):
        entries = request.env['kprl.deferred.ledger'].search_read([
            ('employee_id', '=', emp_id),
        ], ['period_id', 'calculated_bonus', 'deferral_rate', 'deferred_amount',
            'vest_date', 'status'])
        return self._json_response(entries)

    # ─── Governance ─────────────────────────────────────────────────────────

    @http.route('/kprl/api/governance', type='http', auth='user',
                methods=['GET'], csrf=False)
    def api_governance(self):
        events = request.env['kprl.governance.event'].search_read(
            [], ['name', 'employee_id', 'period_id', 'trigger_type', 'severity',
                 'stage', 'malus_pct', 'clawback_amount', 'status',
                 'description'],
            order='create_date desc'
        )
        return self._json_response(events)

    @http.route('/kprl/api/governance', type='http', auth='user',
                methods=['POST'], csrf=False)
    def api_governance_create(self):
        data = json.loads(request.httprequest.data)
        event = request.env['kprl.governance.event'].create(data)
        return self._json_response({'id': event.id, 'status': 'created'})

    # ─── Product Pool ───────────────────────────────────────────────────────

    @http.route('/kprl/api/product-pool/<int:period_id>', type='http',
                auth='user', methods=['GET'], csrf=False)
    def api_product_pool(self, period_id):
        pool = request.env['kprl.product.pool'].search_read([
            ('period_id', '=', period_id),
        ], ['product_id', 'quantity_units', 'unit_price', 'sku_rate',
            'quantity_revenue', 'pool_contribution', 'margin_pct'])
        return self._json_response(pool)

    # ─── Trends (Dashboard Chart) ──────────────────────────────────────────

    @http.route('/kprl/api/trends', type='http', auth='user', methods=['GET'],
                csrf=False)
    def api_trends(self):
        periods = request.env['kprl.bonus.period'].search_read(
            [], ['id', 'name'], order='date_start asc'
        )
        trend_data = []
        for p in periods:
            engine = request.env['kprl.bonus.engine'].search([
                ('period_id', '=', p['id']),
            ], limit=1, order='create_date desc')
            trend_data.append({
                'period_id': p['id'],
                'period_name': p['name'],
                'effective_pool': engine.effective_pool if engine else 0,
                'total_payout': engine.total_payout if engine else 0,
                'company_kpi_score': engine.company_kpi_score if engine else 0,
                'ebitda_margin': engine.ebitda_margin if engine else 0,
                'quarterly_revenue': engine.quarterly_revenue if engine else 0,
                'headcount': engine.headcount if engine else 0,
            })
        return self._json_response(trend_data)

    # ─── Territory Payouts ──────────────────────────────────────────────────

    @http.route('/kprl/api/territory-payout/<int:period_id>', type='http',
                auth='user', methods=['GET'], csrf=False)
    def api_territory_payout(self, period_id):
        payouts = request.env['kprl.territory.payout'].search_read([
            ('period_id', '=', period_id),
        ], ['territory_id', 'effective_target', 'achievement_pct',
            'commission_payable', 'state'])
        return self._json_response(payouts)

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _json_response(self, data, status=200):
        return Response(
            json.dumps(data, default=str),
            status=status,
            mimetype='application/json',
            headers=[('Content-Type', 'application/json; charset=utf-8')]
        )

    def _json_error(self, message, status=400):
        return self._json_response({'error': message}, status)


class KprlPages(http.Controller):
    """Serve the KPRL frontend pages through Odoo."""

    @http.route('/kprl/dashboard', type='http', auth='user', website=True)
    def page_dashboard(self):
        periods = request.env['kprl.bonus.period'].search_read(
            [], ['id', 'name'], order='date_start desc'
        )
        return request.render('kprl_bonus.dashboard_page', {
            'periods': periods,
        })

    @http.route('/kprl/employee/<int:emp_id>', type='http', auth='user',
                website=True)
    def page_employee(self, emp_id):
        emp = request.env['kprl.employee'].browse(emp_id)
        if not emp.exists():
            return request.not_found()
        return request.render('kprl_bonus.employee_page', {
            'employee': emp,
        })

    @http.route('/kprl/employees', type='http', auth='user', website=True)
    def page_employees(self):
        employees = request.env['kprl.employee'].search([])
        return request.render('kprl_bonus.employee_list_page', {
            'employees': employees,
        })

    @http.route('/kprl/config', type='http', auth='user', website=True)
    def page_config(self):
        params = request.env['kprl.bonus.parameter'].search([], limit=1,
                    order='period_id desc')
        return request.render('kprl_bonus.config_page', {
            'params': params,
        })

    @http.route('/kprl/payouts', type='http', auth='user', website=True)
    def page_payouts(self):
        periods = request.env['kprl.bonus.period'].search_read(
            [], ['id', 'name'], order='date_start desc'
        )
        return request.render('kprl_bonus.payouts_page', {
            'periods': periods,
        })

    @http.route('/kprl/deferred', type='http', auth='user', website=True)
    def page_deferred(self):
        entries = request.env['kprl.deferred.ledger'].search([])
        return request.render('kprl_bonus.deferred_page', {
            'entries': entries,
        })

    @http.route('/kprl/performance', type='http', auth='user', website=True)
    def page_performance(self):
        periods = request.env['kprl.bonus.period'].search_read(
            [], ['id', 'name'], order='date_start desc'
        )
        employees = request.env['kprl.employee'].search_read(
            [], ['id', 'name', 'employee_id']
        )
        return request.render('kprl_bonus.performance_page', {
            'periods': periods,
            'employees': employees,
        })

    @http.route('/kprl/governance', type='http', auth='user', website=True)
    def page_governance(self):
        events = request.env['kprl.governance.event'].search([],
                    order='create_date desc')
        return request.render('kprl_bonus.governance_page', {
            'events': events,
        })

    @http.route('/kprl/territories', type='http', auth='user', website=True)
    def page_territories(self):
        territories = request.env['kprl.territory'].search([])
        return request.render('kprl_bonus.territories_page', {
            'territories': territories,
        })

    # ─── Login (branded) ──────────────────────────────────────────────────

    @http.route('/kprl/login', type='http', auth='public', website=True,
                sitemap=False)
    def page_login(self, redirect=None, **kwargs):
        if request.session.uid:
            return request.redirect('/kprl/dashboard')
        values = {'redirect': redirect or '/kprl/dashboard'}
        return request.render('kprl_bonus.login_page', values)

    @http.route('/kprl/simulate/<int:emp_id>', type='http', auth='user',
                website=True)
    def page_simulation(self, emp_id):
        emp = request.env['kprl.employee'].browse(emp_id)
        if not emp.exists():
            return request.not_found()

        # Get current period and params
        periods = request.env['kprl.bonus.period'].search(
            [], order='date_start desc')
        active = periods.filtered(lambda p: p.state == 'active')
        period = active[0] if active else periods[0] if periods else None

        sim_params = {}
        if period:
            param = request.env['kprl.bonus.parameter'].search([
                ('period_id', '=', period.id),
            ], limit=1)
            if param:
                sim_params = {
                    'period_name': period.name,
                    'base_eligible': emp.grade_id.token_rate * emp.grade_id.total_points if emp.grade_id else 0,
                    'deferral_rate': emp.grade_id.deferral_rate if emp.grade_id else 0,
                    'tenure_mult': 1.0,
                    'gmp_factor': 1.0,
                    'proration_factor': 1.0,
                    'min_floor': param.minimum_floor or 30000,
                    'max_cap': param.maximum_cap or 500000,
                }

        return request.render('kprl_bonus.simulation_page', {
            'employee': emp,
            'sim_params': sim_params,
        })
