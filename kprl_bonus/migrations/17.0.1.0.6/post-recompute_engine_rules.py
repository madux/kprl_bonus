import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.kprl_bonus.models.bonus_payout import payout_vals_from_payload

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recompute live engine runs after the company KPI/GMP source change.

    Finalized runs are historical snapshots and are intentionally left
    untouched. Draft/computed runs are refreshed, including their payout
    lines where the period has enough data.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Engine = env['kprl.bonus.engine']
    engines = Engine.search([('state', '!=', 'finalized')])
    if not engines:
        return

    fields = Engine._fields
    for name in ('company_kpi_avg', 'company_gmp_avg',
                 'company_gmp_band_factor', 'company_kpi_score',
                 'company_performance_multiplier'):
        env.add_to_compute(fields[name], engines)
    env.flush_all()

    for engine in engines.filtered('period_id'):
        try:
            engine.action_compute()
            env.flush_all()
        except Exception as exc:
            # A blocked run must not keep a stale pool or stale payout rows
            # from the old rule. Operations payouts are zeroed; any sales
            # leg already on the line is preserved.
            engine.effective_pool = 0.0
            engine.ops_payout = 0.0
            engine.total_payout = engine.sales_commission or 0.0
            payouts = env['kprl.bonus.payout'].search(
                [('period_id', '=', engine.period_id.id)])
            for payout in payouts:
                sales = payout.sales_payout or 0.0
                vals = payout_vals_from_payload({
                    'status': 'blocked',
                    'blocking_errors': [str(exc)],
                    'sales_breakdown': {'final_payout': sales},
                })
                payout.write(vals)
            env.flush_all()
            _logger.warning(
                'Could not recompute bonus engine %s for period %s: %s',
                engine.id, engine.period_id.name, exc)
