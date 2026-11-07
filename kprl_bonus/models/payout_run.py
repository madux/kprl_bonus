"""Compensation run header (Odoo persistence, NO formulas).

One run per period per revision: UNIQUE(period_id, revision_no) with
revision_no 0 for the original run. Corrections never edit an approved
run; they create revision_no+1 linked via revision_of, and the superseded
run stays readable. Only one non-superseded run per period is allowed
(enforced in Python).

Lifecycle: draft -> calculating -> review -> ready -> approved -> locked.
Finance: calculate + submit. CEO: approve. Lock after approval.
At APPROVED: snapshots frozen, policy locked, approved_by/at stamped,
no recalculation from live data afterwards. Deferred amounts are stored
but NOT posted (separate manual action).
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .compensation import run as run_engine

STATES = [
    ("draft", "Draft"),
    ("calculating", "Calculating"),
    ("review", "Review"),
    ("ready", "Ready for Approval"),
    ("approved", "Approved"),
    ("locked", "Locked"),
]
FROZEN_STATES = ("approved", "locked")


class PayoutRun(models.Model):
    _name = "kprl.payout.run"
    _description = "Compensation Payout Run"
    _order = "period_id desc, revision_no desc"
    _rec_name = "period_id"

    period_id = fields.Many2one("kprl.bonus.period", string="Period", required=True)
    revision_no = fields.Integer(string="Revision", default=0, required=True)
    revision_of = fields.Many2one("kprl.payout.run", string="Supersedes")
    superseded_by = fields.Many2one("kprl.payout.run", string="Superseded By", readonly=True)
    state = fields.Selection(STATES, string="Status", default="draft", required=True)

    policy_source_id = fields.Many2one("kprl.bonus.parameter", string="Policy Snapshot", readonly=True)
    policy_version = fields.Integer(string="Policy Version", readonly=True)

    calculated_at = fields.Datetime(string="Calculated At", readonly=True)
    approved_at = fields.Datetime(string="Approved At", readonly=True)
    approved_by = fields.Many2one("res.users", string="Approved By", readonly=True)

    line_ids = fields.One2many("kprl.payout.run.line", "run_id", string="Lines")

    employee_count = fields.Integer(string="Staff", readonly=True)
    calculated_count = fields.Integer(string="Calculated", readonly=True)
    blocked_count = fields.Integer(string="Blocked", readonly=True)
    combined_gross = fields.Float(string="Combined Gross", readonly=True)
    ebitda_cap_amount = fields.Float(string="Shared Cap (EBITDA)", readonly=True)
    cap_pressure = fields.Boolean(string="Cap Pressure", readonly=True)
    proration = fields.Float(string="Run Proration", readonly=True, digits=(5, 4))
    total_net_payable = fields.Float(string="Total Net Payable", readonly=True)
    total_deferred = fields.Float(string="Total Deferred", readonly=True)

    _sql_constraints = [
        ("period_revision_unique", "UNIQUE(period_id, revision_no)",
         "Only one run per period and revision! Use a revision run for corrections."),
    ]

    # -- guards --
    def _ensure_mutable(self):
        for rec in self:
            if rec.state in FROZEN_STATES:
                raise UserError("Run %s is %s: snapshots are immutable." % (rec.period_id.name, rec.state))

    def _ensure_finance(self):
        if not (self.env.user.has_group("kprl_bonus.group_kprl_finance")
                or self.env.user.has_group("kprl_bonus.group_kprl_ceo")
                or self.env.user.has_group("base.group_system")):
            raise AccessError("Finance role required.")

    def _ensure_ceo(self):
        if not (self.env.user.has_group("kprl_bonus.group_kprl_ceo")
                or self.env.user.has_group("base.group_system")):
            raise AccessError("CEO approval required.")

    @api.constrains("period_id", "revision_no", "superseded_by")
    def _check_single_active(self):
        for rec in self:
            if rec.revision_no == 0:
                continue
            if not rec.revision_of:
                raise ValidationError("A revision run must link the run it supersedes.")
            other = self.search([("period_id", "=", rec.period_id.id),
                                 ("id", "!=", rec.id),
                                 ("superseded_by", "=", False)], limit=1)
            if other and other.state in FROZEN_STATES + ("ready",):
                raise ValidationError(
                    "Period %s already has run rev %s in state %s; supersede it first."
                    % (rec.period_id.name, other.revision_no, other.state))

    def write(self, vals):
        if any(k not in ("state", "superseded_by", "approved_at", "approved_by") for k in vals):
            self._ensure_mutable()
        return super().write(vals)

    def unlink(self):
        self._ensure_mutable()
        return super().unlink()

    # -- lifecycle --
    def action_calculate(self):
        """Finance: (re)build lines from frozen previews, apply run rules."""
        self.ensure_one()
        self._ensure_finance()
        if self.state in FROZEN_STATES:
            raise UserError("Approved runs cannot be recalculated.")
        if self.state not in ("draft", "calculating", "review"):
            raise UserError("Calculate is allowed from draft/calculating/review.")
        self.state = "calculating"
        self.line_ids.filtered(lambda l: l.source == "auto").unlink()
        param = self.env["kprl.bonus.parameter"].search(
            [("period_id", "=", self.period_id.id)], limit=1)
        if param:
            self.policy_source_id = param.id
            self.policy_version = getattr(param, "version", 1) or 1
        perfs = self.env["kprl.performance.input"].search(
            [("period_id", "=", self.period_id.id)])
        if not perfs:
            raise UserError("No performance records for period %s." % self.period_id.name)
        Sim = self.env["kprl.payout.simulator"]
        legs = []
        previews = {}
        auto_ids = set()
        for perf in perfs:
            auto_ids.add(perf.employee_id.id)
        manual_ids = set(self.line_ids.filtered(
            lambda l: l.source == "manual").mapped("employee_id.id"))
        for emp_id in sorted(auto_ids | manual_ids):
            sim = Sim.new({"period_id": self.period_id.id, "employee_id": emp_id})
            sim._run_preview()
            payload = sim.to_preview_dict()
            previews[emp_id] = payload
            legs.append({
                "employee_id": emp_id,
                "status": "blocked" if payload.get("status") == "blocked" else "calculated",
                "ops_gross": (payload.get("operations_breakdown") or {}).get("gross"),
                "sales_gross": (payload.get("sales_breakdown") or {}).get("gross"),
                "ops_deferred": 0.0,
                "sales_deferred": 0.0,
            })
        cap_amount = self._shared_cap_amount(param)
        result = run_engine.apply_run_rules(legs, {"ebitda_cap_amount": cap_amount,
                                                   "period_id": self.period_id.id})
        Line = self.env["kprl.payout.run.line"]
        for line in result["lines"]:
            payload = previews.get(line["employee_id"], {})
            vals = {
                "status": line["status"],
                "engines": ",".join((payload.get("classification") or {}).get("engines", [])),
                "sub_pool": (payload.get("classification") or {}).get("sub_pool"),
                "preview_json": __import__("json").dumps(payload, default=str),
                "ops_gross": line["ops_gross"] or 0.0,
                "sales_gross": line["sales_gross"] or 0.0,
                "combined_gross": line["combined_gross"] or 0.0,
                "proration": line["proration"] or 0.0,
                "cap_adjustment": line["cap_adjustment"] or 0.0,
                "net_payable": line["net_payable"] or 0.0,
                "deferred": line["deferred"] or 0.0,
                "blocking_errors_text": "\n".join(payload.get("blocking_errors", [])),
                "warnings_text": "\n".join(payload.get("warnings", [])),
            }
            existing = self.line_ids.filtered(
                lambda l: l.employee_id.id == line["employee_id"])
            if existing:
                existing.write(vals)
            else:
                vals.update({"run_id": self.id,
                             "employee_id": line["employee_id"],
                             "source": "auto"})
                Line.create(vals)
        totals = result["totals"]
        self.write({
            "employee_count": totals["employee_count"],
            "calculated_count": totals["calculated_count"],
            "blocked_count": totals["blocked_count"],
            "combined_gross": totals["combined_gross"],
            "ebitda_cap_amount": cap_amount or 0.0,
            "cap_pressure": totals["cap_pressure"],
            "proration": totals["proration"],
            "total_net_payable": totals["total_net_payable"],
            "total_deferred": totals["total_deferred"],
            "calculated_at": fields.Datetime.now(),
            "state": "review",
        })
        return True

    def _shared_cap_amount(self, param):
        """Run-level shared cap base. Full EBITDA-based cap arrives with
        operations.py pool context; until then no cap (None = no proration)."""
        return None

    def action_submit(self):
        self.ensure_one()
        self._ensure_finance()
        if self.state != "review":
            raise UserError("Submit is allowed from Review.")
        self.state = "ready"
        return True

    def action_approve(self):
        """CEO: freeze snapshots, lock policy, stamp approval. No recalculation."""
        self.ensure_one()
        self._ensure_ceo()
        if self.state != "ready":
            raise UserError("Approve is allowed from Ready for Approval.")
        if self.policy_source_id:
            try:
                self.policy_source_id.write({"is_locked": True})
            except Exception:
                pass
        self.write({
            "approved_by": self.env.user.id,
            "approved_at": fields.Datetime.now(),
            "state": "approved",
        })
        return True

    def action_lock(self):
        self.ensure_one()
        self._ensure_ceo()
        if self.state != "approved":
            raise UserError("Lock is allowed from Approved.")
        self.state = "locked"
        return True

    def action_export(self):
        """Download the multi-sheet Excel workbook built from frozen snapshots."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/kprl/api/payout-run/%d/export" % self.id,
            "target": "self",
        }

    def action_create_revision(self):
        """Controlled correction: new revision run; original stays readable."""
        self.ensure_one()
        if self.state not in FROZEN_STATES:
            raise UserError("Only an approved/locked run can be superseded by a revision.")
        existing = self.search([("period_id", "=", self.period_id.id),
                                ("revision_no", ">", self.revision_no)], limit=1)
        if existing:
            raise UserError("A newer revision already exists.")
        rev = self.create({"period_id": self.period_id.id,
                           "revision_no": self.revision_no + 1,
                           "revision_of": self.id})
        self.superseded_by = rev.id
        return rev
