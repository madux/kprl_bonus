"""Compensation run line (frozen per-employee snapshot, NO formulas).

preview_json holds the full frozen preview payload (inputs, policy
values, leg breakdowns, warnings, blocking errors). Money columns are
flattened copies for list views and Excel export. Lines of an approved
or locked run are immutable.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class PayoutRunLine(models.Model):
    _name = "kprl.payout.run.line"
    _description = "Compensation Payout Run Line"
    _order = "employee_id"
    _rec_name = "employee_id"

    run_id = fields.Many2one("kprl.payout.run", string="Run", required=True, ondelete="cascade")
    period_id = fields.Many2one("kprl.bonus.period", related="run_id.period_id", store=True, readonly=True)
    employee_id = fields.Many2one("kprl.employee", string="Employee", required=True)
    source = fields.Selection([("auto", "Auto"), ("manual", "Manual")],
                              string="Source", readonly=True, default="auto")
    status = fields.Selection([("pending", "Pending"), ("calculated", "Calculated"), ("blocked", "Blocked")],
                              string="Status", readonly=True, default="pending")

    @api.onchange("employee_id")
    def _onchange_employee_classify(self):
        from .compensation import grade_policy
        for rec in self:
            emp = rec.employee_id
            if not emp or not emp.exists():
                continue
            grade = emp.grade_id
            senior = bool(grade.is_senior_mgmt_tier) if grade else False
            contract = {"senior": senior} if grade else None
            pool = (emp.pool_type or "OPM").strip().upper()
            if pool == "SALES":
                sub = "SALES"
            elif pool == "SUP":
                sub = "SEN-MGT" if senior else "OPS-SUP"
            else:
                sub = "OPM"
            rec.sub_pool = sub
            rec.engines = ",".join(grade_policy.required_engines(
                emp.pool_type, emp.track, emp.sales_role))
    engines = fields.Char(string="Engines", readonly=True)
    sub_pool = fields.Char(string="Sub-Pool", readonly=True)
    preview_json = fields.Text(string="Frozen Preview Snapshot", readonly=True)

    ops_gross = fields.Float(string="Ops Gross", readonly=True)
    sales_gross = fields.Float(string="Sales Gross", readonly=True)
    combined_gross = fields.Float(string="Combined Gross", readonly=True)
    proration = fields.Float(string="Run Proration", readonly=True, digits=(5, 4))
    cap_adjustment = fields.Float(string="Cap Adjustment", readonly=True)
    net_payable = fields.Float(string="Net Payable", readonly=True)
    deferred = fields.Float(string="Deferred", readonly=True)
    blocking_errors_text = fields.Text(string="Blocking Reasons", readonly=True)
    warnings_text = fields.Text(string="Warnings", readonly=True)

    snapshot_html = fields.Html(string="Calculation Breakdown", compute="_compute_snapshot_html")

    @api.depends("preview_json", "status")
    def _compute_snapshot_html(self):
        import json as _json
        from markupsafe import escape as _esc
        for rec in self:
            try:
                snap = _json.loads(rec.preview_json or "{}")
            except ValueError:
                snap = {}
            if not snap:
                rec.snapshot_html = "<p><em>No snapshot yet. Run Calculate on the payout run.</em></p>"
                continue
            emp = snap.get("employee", {}) or {}
            cls = snap.get("classification", {}) or {}
            src = snap.get("source_inputs", {}) or {}
            polv = snap.get("policy_values", {}) or {}
            ops = snap.get("operations_breakdown") or {}
            sales = snap.get("sales_breakdown") or {}
            totals = snap.get("totals", {}) or {}

            def fmt(v, money=False, pct=False):
                if v is None:
                    return "<em>NOT PROVIDED</em>"
                if isinstance(v, bool):
                    return "Yes" if v else "No"
                if pct and isinstance(v, (int, float)):
                    return "%.2f%%" % (v * 100.0)
                if money and isinstance(v, (int, float)):
                    return "&#8358;%s" % format(v, ",.2f")
                if isinstance(v, float):
                    return "%.4f" % v
                return _esc(str(v))

            def rows(pairs):
                return "".join(
                    "<tr><td>%s</td><td style='text-align:right'>%s</td></tr>" % (_esc(k), v)
                    for k, v in pairs)

            def section(title, pairs):
                return ("<h4>%s</h4><table style='width:100%%'>%s</table>" % (_esc(title), rows(pairs)))

            status = snap.get("status", "")
            badge = {"calculated": "green", "blocked": "red"}.get(status, "gray")
            html = ["<div class='o_snapshot'>",
                    "<p><strong>Status:</strong> "
                    "<span style='color:%s'><strong>%s</strong></span></p>" % (badge, _esc(status.upper()))]
            html.append(section("Employee", [
                ("Name", _esc(emp.get("name") or "-")),
                ("Staff ID", _esc(emp.get("staff_id") or "-")),
                ("Grade", _esc(emp.get("grade") or "-")),
                ("Department", _esc(emp.get("department") or "-")),
                ("Pool / Track", "%s / %s" % (_esc(emp.get("pool_type") or "-"), _esc(emp.get("track") or "-"))),
                ("Sales role", _esc(emp.get("sales_role") or "-")),
                ("Years of service", fmt(src.get("years_of_service")))]))
            html.append(section("Classification (auto)", [
                ("Engines", _esc(", ".join(cls.get("engines", [])) or "-")),
                ("Sub-pool", _esc(cls.get("sub_pool") or "-")),
                ("Base points", fmt(cls.get("base_points"))),
                ("Skill premium", fmt(cls.get("skill_premium"))),
                ("Total points", fmt(cls.get("total_points"))),
                ("Deferral rate", fmt(cls.get("deferral_rate"), pct=True))]))
            html.append(section("Source inputs", [
                ("Appraisal", fmt(src.get("appraisal"), pct=True)),
                ("Behaviour (/25)", fmt(src.get("behaviour"))),
                ("Department KPI", fmt(polv.get("department_kpi"), pct=True)),
                ("Own target", fmt(src.get("own_target"), money=True)),
                ("Own sales", fmt(src.get("own_sales"), money=True)),
                ("Own retrieval", fmt(src.get("own_retrieval"), money=True))]))
            if ops:
                html.append(section("Operations leg", [
                    ("Value / point", fmt(ops.get("value_per_point"), money=True)),
                    ("Base eligible", fmt(ops.get("base_eligible"), money=True)),
                    ("Dept KPI mult", fmt(ops.get("department_kpi_multiplier"))),
                    ("Appraisal mult", fmt(ops.get("appraisal_multiplier"))),
                    ("Behaviour mult", fmt(ops.get("behaviour_multiplier"))),
                    ("Gross bonus", fmt(ops.get("gross_bonus"), money=True)),
                    ("Proration", fmt(ops.get("proration_factor"))),
                    ("Tenure mult", fmt(ops.get("tenure_multiplier"))),
                    ("Floor", fmt(ops.get("floor"), money=True)),
                    ("Deferred", fmt(ops.get("deferred_amount"), money=True)),
                    ("Net payable", fmt(ops.get("net_payable"), money=True))]))
                if ops.get("blocked_reason"):
                    html.append("<p style='color:red'><strong>Blocked:</strong> %s</p>"
                                % _esc(ops["blocked_reason"]))
            if sales:
                html.append(section("Sales leg", [
                    ("Attainment", fmt(sales.get("sales_attainment"), pct=True)),
                    ("Sales gate", fmt(sales.get("sales_gate"))),
                    ("Retrieval rate", fmt(sales.get("retrieval_rate"), pct=True)),
                    ("Retrieval gate", fmt(sales.get("retrieval_gate"))),
                    ("Sales commission", fmt(sales.get("sales_commission"), money=True)),
                    ("Retrieval commission", fmt(sales.get("retrieval_commission"), money=True)),
                    ("KPI mult", fmt(sales.get("kpi_multiplier"))),
                    ("Accelerator", fmt(sales.get("accelerator"))),
                    ("Cap", fmt(sales.get("cap"), money=True)),
                    ("Final payout", fmt(sales.get("final_payout"), money=True))]))
                if sales.get("blocked_reason"):
                    html.append("<p style='color:red'><strong>Blocked:</strong> %s</p>"
                                % _esc(sales["blocked_reason"]))
            for err in snap.get("blocking_errors", []) or []:
                html.append("<p style='color:red'>BLOCKED: %s</p>" % _esc(err))
            for w in snap.get("warnings", []) or []:
                html.append("<p style='color:orange'>Warning: %s</p>" % _esc(w))
            html.append("</div>")
            rec.snapshot_html = "".join(html)

    _sql_constraints = [
        ("run_employee_unique", "UNIQUE(run_id, employee_id)",
         "An employee can only appear once per run!"),
    ]

    def write(self, vals):
        for rec in self:
            if rec.run_id.state in ("approved", "locked"):
                raise UserError("Run %s is %s: line snapshots are immutable."
                                % (rec.run_id.period_id.name, rec.run_id.state))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.run_id.state in ("approved", "locked"):
                raise UserError("Run %s is %s: line snapshots are immutable."
                                % (rec.run_id.period_id.name, rec.run_id.state))
        return super().unlink()
