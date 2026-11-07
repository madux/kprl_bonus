from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    params = env['kprl.bonus.parameter'].search([])
    if not params:
        return
    fields = params._fields
    for name in ('base_bonus_pool', 'profitability_gate_factor',
                 'gmp_gate_factor', 'funded_pool_after_both_gate'):
        env.add_to_compute(fields[name], params)
    env.flush_all()
