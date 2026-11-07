'2026-Q2 end-to-end asserts. Run: odoo-bin shell -d DB < tools/validate_v30_odoo.py'
period = env['kprl.bonus.period'].search([('name', '=', '2026-Q2')], limit=1)
assert period, '2026-Q2 period missing'
eng = env['kprl.bonus.engine'].search([('period_id', '=', period.id)], limit=1, order='create_date desc')
assert eng, 'bonus engine run missing for 2026-Q2'
exp = {'pool_contribution': 3808260.0, 'effective_pool': 3792819.67, 'opm_value_point': 39924.42, 'ops_payout': 2994737.81, 'sales_commission': 1305562.10, 'total_payout': 4300299.91}
for f, want in exp.items():
    got = getattr(eng, f)
    assert abs(got - want) < 1.0, f + ' got=' + str(got) + ' want=' + str(want)
    print('PASS ' + f + '=' + str(round(got, 2)))
p1 = env['kprl.bonus.payout'].search([('period_id', '=', period.id), ('employee_id.staff_id', '=', 'KPRL-001')], limit=1)
assert p1, 'KPRL-001 payout missing'
assert abs((p1.net_immediate or 0.0) - 146318.84) < 1.0, 'KPRL-001 net got=' + str(p1.net_immediate)
print('PASS KPRL-001 net=' + str(round(p1.net_immediate, 2)))
led = env['kprl.deferred.ledger'].search([('period_id', '=', period.id)])
tot_def = sum(led.mapped('deferred_amount'))
assert abs(tot_def - 212450.41) < 1.0, 'deferred got=' + str(tot_def)
print('PASS deferred total=' + str(round(tot_def, 2)))
print('ODOO HARNESS OK')
