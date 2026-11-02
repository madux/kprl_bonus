"""Payout simulator (parallel screen, Slice 1).

Thin Odoo wrapper around the pure preview service
(models/compensation/preview.py). Contains NO payout formulas: it only
loads records, maps them to plain dicts, calls preview_payout(), and
stores the display values. The backend recalculates on every change, so
calculation is a consequence of selection, not a user action.

The existing kprl.bonus.payout UI and its computed fields are untouched.
"""
import json

from odoo import api, fields, models

from .compensation import preview as preview_engine
from .compensation import sales as sales_engine
from .compensation.policy import PolicySnapshot


def _norm_frac(value):
    if value is None or value is False:
        return None
    v = float(value)
    return v / 100.0 if v > 2.0 else v


class PayoutSimulator(models.TransientModel):
    _name = "kprl.payout.simulator"
    _description = "Payout Simulator (preview only, parallel screen)"

    # -- the only editable inputs (no restrictive domains: every employee
    # must be selectable, exactly like the old screen; eligibility is a
    # calculated outcome, not a selection filter) --
    period_id = fields.Many2one("kprl.bonus.period", string="Period",
                                default=lambda self: self._default_period())
    employee_id = fields.Many2one("kprl.employee", string="Employee")

    @api.model
    def _default_period(self):
        period = self.env["kprl.bonus.period"].search(
            [("state", "=", "active")], limit=1)
        if not period:
            period = self.env["kprl.bonus.period"].search(
                [], order="date_start desc", limit=1)
        return period.id if period else False

    # -- status --
    status = fields.Selection(
        [("calculated", "Calculated"), ("waiting", "Waiting for data"),
         ("blocked", "Blocked")],
        string="Calculation Status", readonly=True, default="waiting",
    )
    blocking_errors_text = fields.Text(string="Blocking Reasons", readonly=True)
    warnings_text = fields.Text(string="Warnings", readonly=True)
    preview_json = fields.Text(string="Preview Payload", readonly=True)

    # -- employee card (all readonly, derived from employeeId) --
    emp_name = fields.Char(string="Name", readonly=True)
    staff_id = fields.Char(string="Staff ID", readonly=True)
    grade_name = fields.Char(string="Grade", readonly=True)
    dept_name = fields.Char(string="Department", readonly=True)
    pool_type = fields.Char(string="Pool", readonly=True)
    track = fields.Char(string="Track", readonly=True)
    sales_role = fields.Char(string="Sales Role", readonly=True)
    territory_name = fields.Char(string="Territory", readonly=True)
    years_of_service = fields.Float(string="Years of Service", readonly=True)
    emp_status = fields.Char(string="Employee Status", readonly=True)

    # -- classification (readonly) --
    engines_display = fields.Char(string="Engines", readonly=True)
    sub_pool = fields.Char(string="Sub-Pool", readonly=True)
    base_points = fields.Float(string="Base Points", readonly=True, digits=(5, 2))
    skill_premium = fields.Float(string="Skill Premium", readonly=True, digits=(5, 2))
    total_points = fields.Float(string="Total Points", readonly=True, digits=(5, 2))
    deferral_rate = fields.Float(string="Deferral Rate", readonly=True, digits=(5, 4))

    # -- source inputs (readonly mirror of period performance) --
    appraisal = fields.Float(string="Appraisal (0-1)", readonly=True, digits=(5, 4))
    behaviour = fields.Float(string="Behaviour (/25)", readonly=True, digits=(5, 2))
    dept_kpi = fields.Float(string="Department KPI (0-1)", readonly=True, digits=(5, 4))

    # -- stub breakdown values available in slice 1 (readonly) --
    appraisal_multiplier = fields.Float(string="Appraisal Multiplier", readonly=True, digits=(5, 4))
    behaviour_multiplier = fields.Float(string="Behaviour Multiplier", readonly=True, digits=(5, 4))
    tenure_multiplier = fields.Float(string="Tenure Multiplier", readonly=True, digits=(5, 4))
    sales_attainment = fields.Float(string="Sales Attainment", readonly=True, digits=(5, 4))
    sales_gate = fields.Float(string="Sales Gate", readonly=True, digits=(5, 4))
    retrieval_gate = fields.Float(string="Retrieval Gate", readonly=True, digits=(5, 4))
    combined_gross = fields.Float(string="Combined Gross (stub)", readonly=True)

    @api.onchange("period_id", "employee_id")
    def _onchange_auto_preview(self):
        self._run_preview()

    def action_refresh(self):
        self.ensure_one()
        self._run_preview()
        return True

    # -- record -> plain dict mapping (no formulas here) --
    def _employee_dict(self):
        self.ensure_one()
        emp = self.employee_id
        if not emp or not emp.exists():
            return {}
        grade = emp.grade_id
        dept = emp.department_id
        terr = emp.territory_id
        return {
            "id": emp.id,
            "name": emp.name,
            "staff_id": emp.staff_id,
            "grade": {
                "code": grade.code if grade else None,
                "name": grade.name if grade else None,
                "yp_points": grade.yp_points if grade else None,
                "skill_max": grade.skill_max if grade else None,
                "aip_eligible": grade.aip_eligible if grade else False,
                "is_senior_mgmt_tier": grade.is_senior_mgmt_tier if grade else False,
            },
            "department": {"name": dept.name if dept else None},
            "pool_type": emp.pool_type,
            "track": emp.track,
            "sales_role": emp.sales_role,
            "territory": {"name": terr.name if terr else None},
            "years_of_service": float(emp._tenure_bracket_years()),
            "skill_premium": float(emp.skill_premium_pts or 0.0),
            "status": emp.status,
        }

    def _behaviour_25(self, perf):
        if not perf:
            return None
        for fname in ("team_pct",):
            v = getattr(perf, fname, None)
            if v not in (None, False):
                v = float(v)
                return v / 100.0 * 25.0 if v > 25.0 else v
        return None

    def _kpi_01(self, value):
        if value in (None, False):
            return None
        v = float(value)
        return v / 100.0 if v > 2.0 else v

    def _performance_dict(self):
        self.ensure_one()
        if not self.employee_id or not self.period_id:
            return None
        Performance = self.env["kprl.performance.input"]
        perf = Performance.search(
            [("employee_id", "=", self.employee_id.id),
             ("period_id", "=", self.period_id.id)], limit=1)
        if not perf:
            return None
        pk = perf.product_knowledge_score if perf.product_knowledge_score not in (None, False) and perf.product_knowledge_score else (self._kpi_01(perf.prod_know) if perf.prod_know else None)
        call = perf.call_report_compliance if perf.call_report_compliance not in (None, False) and perf.call_report_compliance else (self._kpi_01(perf.call_rep) if perf.call_rep else None)
        cov = perf.customer_coverage_rate if perf.customer_coverage_rate not in (None, False) and perf.customer_coverage_rate else (self._kpi_01(perf.coverage) if perf.coverage else None)
        new = perf.new_customer_acquisition if perf.new_customer_acquisition not in (None, False) and perf.new_customer_acquisition else (self._kpi_01(perf.new_cust) if perf.new_cust else None)
        dept_kpi = self._dept_kpi_fraction()
        territory_sales = float(perf.territory_sales) if perf.territory_sales not in (None, False) else None
        territory_retrieval = float(perf.territory_retrievals) if perf.territory_retrievals not in (None, False) else None
        territory_target = float(perf.territory_target) if perf.territory_target not in (None, False) else None

        role = sales_engine.normalize_role(self.employee_id.sales_role)
        territory = self.employee_id.territory_id
        if territory and role in sales_engine.RSM_ROLES + sales_engine.DUAL_ROLES:
            sales_staff = self.env["kprl.employee"].with_context(
                active_test=False
            ).search([
                ("territory_id", "=", territory.id),
                ("sales_role", "in", tuple(
                    sales_engine.TOP_ROLES + sales_engine.RSM_ROLES
                    + sales_engine.ASM_ROLES + sales_engine.DUAL_ROLES
                )),
            ])
            if territory.rsm_id:
                sales_staff |= territory.rsm_id
            sales_staff |= self.employee_id
            team_perfs = Performance.search([
                ("period_id", "=", self.period_id.id),
                ("employee_id", "in", sales_staff.ids),
            ])
            perfs_by_employee = {
                team_perf.employee_id.id: team_perf
                for team_perf in team_perfs
            }
            totals = sales_engine.aggregate_territory_performance([
                {
                    "own_target": team_perf.own_target,
                    "own_sales": team_perf.own_sales,
                    "own_retrieval": team_perf.own_retrievals,
                }
                for team_perf in team_perfs
            ])
            territory_sales = totals["territory_sales"]
            territory_retrieval = totals["territory_retrieval"]
            if territory.target_source == "team":
                territory_target = totals["team_target"]
            else:
                rsm = territory.rsm_id or sales_staff.filtered(
                    lambda staff: sales_engine.normalize_role(staff.sales_role)
                    in sales_engine.RSM_ROLES + sales_engine.DUAL_ROLES
                )[:1]
                rsm_perf = perfs_by_employee.get(rsm.id) if rsm else None
                territory_target = (
                    float(rsm_perf.own_target)
                    if rsm_perf and rsm_perf.own_target is not None
                    else float(territory.rsm_target or 0.0)
                )
        return {
            "appraisal": _norm_frac(perf.appraisal_score) if perf.appraisal_score not in (None, False) else None,
            "behaviour": self._behaviour_25(perf),
            "own_target": float(perf.own_target) if perf.own_target not in (None, False) else None,
            "own_sales": float(perf.own_sales) if perf.own_sales not in (None, False) else None,
            "own_retrieval": float(perf.own_retrievals) if perf.own_retrievals not in (None, False) else None,
            "territory_sales": territory_sales,
            "territory_retrieval": territory_retrieval,
            "territory_target": territory_target,
            "product_knowledge": self._kpi_01(pk),
            "call_report": self._kpi_01(call),
            "customer_coverage": self._kpi_01(cov),
            "new_customer": self._kpi_01(new),
            "dept_kpi_score": dept_kpi,
        }

    def _dept_kpi_fraction(self):
        if not self.employee_id or not self.period_id:
            return None
        dept = self.employee_id.department_id
        if not dept:
            return None
        rec = self.env["kprl.dept.kpi.multiplier"].search(
            [("department_id", "=", dept.id),
             ("period_id", "=", self.period_id.id)], limit=1)
        if rec and rec.kpi_score not in (None, False) and float(rec.kpi_score or 0.0) != 0.0:
            s = float(rec.kpi_score)
            mx = float(rec.kpi_score_max or 100.0)
            if s <= 1.0:
                return s
            return s / (mx if mx > 1.0 else 100.0)
        if dept.kpi_multiplier not in (None, False):
            return _norm_frac(dept.kpi_multiplier)
        return None

    def _policy_snapshot(self):
        if not self.period_id:
            return PolicySnapshot()
        param = self.env["kprl.bonus.parameter"].search(
            [("period_id", "=", self.period_id.id)], limit=1)
        if not param:
            return PolicySnapshot(period_id=self.period_id.id)
        return PolicySnapshot.from_mapping(
            param, source_id=param.id, period_id=self.period_id.id,
            version=getattr(param, "version", 1) or 1)

    def _pool_ctx(self):
        ctx = {}
        if self.period_id:
            ctx["ebitda_margin"] = _norm_frac(self.period_id.ebitda_margin) \
                if self.period_id.ebitda_margin not in (None, False) else None
            snap = self._policy_snapshot()
            partial = getattr(snap, "partial_gate", 0.20) or 0.20
            period = self.period_id
            ctx["national_sales"] = float(period.national_actual_sales or 0.0) or None
            ctx["national_retrieval"] = float(period.national_actual_retrievals or 0.0) or None
            ctx["national_target"] = float(period.national_sales_target or 0.0) or None
            ctx["floor_eligible"] = bool(
                ctx["ebitda_margin"] is not None and ctx["ebitda_margin"] >= partial)
        if self.employee_id and self.employee_id.exists():
            eng = self.env["kprl.bonus.engine"].search(
                [("period_id", "=", self.period_id.id)], limit=1, order="create_date desc")
            if eng and eng.computed_on:
                code = (self.employee_id.subpool_id.code or "OPM") if self.employee_id.subpool_id else "OPM"
                # Workbook STAFF PAYOUT I6/W6: any non-OPM, non-senior
                # employee (incl. SALES pool) is valued on the OPS-SUP pool.
                field = {"SENMGT": "senior_mgt_value_point",
                         "OPM": "opm_value_point",
                         "OPSSUP": "ops_sup_value_point",
                         "SALES": "ops_sup_value_point"}.get(code)
                value_per_point = getattr(eng, field, None) if field else None
                if value_per_point is not None:
                    ctx["value_per_point"] = float(value_per_point)
                    ctx["pool_proration_factor"] = float(eng.proration_factor or 1.0)
        return ctx

    def _run_preview(self):
        for rec in self:
            if not rec.employee_id or not rec.period_id:
                rec._write_empty("waiting", ["select a period and an employee"])
                continue
            result = preview_engine.preview_payout(
                rec._employee_dict(), rec._performance_dict(),
                rec._policy_snapshot(), rec._pool_ctx())
            rec._write_result(result)

    def _write_empty(self, status, errors):
        self.status = status
        self.blocking_errors_text = "\n".join(errors)
        self.warnings_text = ""
        self.preview_json = ""
        for fname in ("emp_name", "staff_id", "grade_name", "dept_name",
                      "pool_type", "track", "sales_role", "territory_name",
                      "emp_status", "engines_display", "sub_pool"):
            setattr(self, fname, False)
        for fname in ("years_of_service", "base_points", "skill_premium",
                      "total_points", "deferral_rate", "appraisal",
                      "behaviour", "dept_kpi", "appraisal_multiplier",
                      "behaviour_multiplier", "tenure_multiplier",
                      "sales_attainment", "sales_gate", "retrieval_gate",
                      "combined_gross"):
            setattr(self, fname, 0.0)

    def _write_result(self, result):
        emp = result.get("employee", {})
        cls = result.get("classification", {})
        src = result.get("source_inputs", {})
        ops = result.get("operations_breakdown") or {}
        sales = result.get("sales_breakdown") or {}
        totals = result.get("totals", {})
        self.status = result.get("status", "waiting")
        self.blocking_errors_text = "\n".join(result.get("blocking_errors", []))
        self.warnings_text = "\n".join(result.get("warnings", []))
        self.preview_json = json.dumps(result, default=str)
        self.emp_name = emp.get("name")
        self.staff_id = emp.get("staff_id")
        self.grade_name = emp.get("grade")
        self.dept_name = emp.get("department")
        self.pool_type = emp.get("pool_type")
        self.track = emp.get("track")
        self.sales_role = emp.get("sales_role")
        self.territory_name = emp.get("territory")
        self.emp_status = emp.get("status")
        self.years_of_service = float(src.get("years_of_service") or 0.0)
        self.engines_display = ", ".join(cls.get("engines", []))
        self.sub_pool = cls.get("sub_pool")
        self.base_points = float(cls.get("base_points") or 0.0)
        self.skill_premium = float(cls.get("skill_premium") or 0.0)
        self.total_points = float(cls.get("total_points") or 0.0)
        self.deferral_rate = float(cls.get("deferral_rate") or 0.0)
        self.appraisal = float(src.get("appraisal")) if src.get("appraisal") is not None else 0.0
        self.behaviour = float(src.get("behaviour")) if src.get("behaviour") is not None else 0.0
        dept_kpi = (result.get("policy_values") or {}).get("department_kpi")
        self.dept_kpi = float(dept_kpi) if dept_kpi is not None else 0.0
        self.appraisal_multiplier = float(ops.get("appraisal_multiplier")) \
            if ops.get("appraisal_multiplier") is not None else 0.0
        self.behaviour_multiplier = float(ops.get("behaviour_multiplier")) \
            if ops.get("behaviour_multiplier") is not None else 0.0
        self.tenure_multiplier = float(ops.get("tenure_multiplier")) \
            if ops.get("tenure_multiplier") is not None else 0.0
        self.sales_attainment = float(sales.get("attainment")) \
            if sales.get("attainment") is not None else 0.0
        self.sales_gate = float(sales.get("sales_gate")) \
            if sales.get("sales_gate") is not None else 0.0
        self.retrieval_gate = float(sales.get("retrieval_gate")) \
            if sales.get("retrieval_gate") is not None else 0.0
        self.combined_gross = float(totals.get("gross") or 0.0)

    def to_preview_dict(self):
        self.ensure_one()
        if not self.preview_json:
            self._run_preview()
        try:
            return json.loads(self.preview_json or "{}")
        except ValueError:
            return {"status": "blocked", "blocking_errors": ["preview payload is corrupt; refresh"],
                    "warnings": []}
