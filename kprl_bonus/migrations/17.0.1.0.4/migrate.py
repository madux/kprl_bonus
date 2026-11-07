import logging
_logger = logging.getLogger(__name__)

FK_QUERY = """
    SELECT tc.table_name, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage ccu
      ON ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND ccu.table_name = 'kprl_employee'
"""


def _normalize_table(cr, table):
    cr.execute(
        "UPDATE " + table + " h SET staff_id = UPPER(REPLACE(h.staff_id, '-', '/')) "
        "WHERE h.staff_id LIKE '%-%' AND NOT EXISTS ("
        "SELECT 1 FROM " + table + " o "
        "WHERE UPPER(REPLACE(o.staff_id, '-', '/')) = UPPER(REPLACE(h.staff_id, '-', '/')) "
        "AND o.id <> h.id)")
    _logger.info('KPRL: normalized %d %s staff IDs to slash form', cr.rowcount, table)


def _repoint_and_merge(cr):
    cr.execute(
        "SELECT id, staff_id FROM kprl_employee "
        "WHERE REPLACE(UPPER(staff_id), '-', '/') = 'KPRL/003' ORDER BY id")
    rows = cr.fetchall()
    if len(rows) < 2:
        _logger.info('KPRL: OLADIMEJI duplicate not found (rows=%d); merge skipped', len(rows))
        return
    keep = next((r[0] for r in rows if '/' in (r[1] or '')), rows[0][0])
    drop = [r[0] for r in rows if r[0] != keep]
    cr.execute(FK_QUERY)
    fks = cr.fetchall()
    for table, column in fks:
        if table == 'kprl_employee' and column == 'id':
            continue
        cr.execute(
            'UPDATE "%s" SET "%s" = %%s WHERE "%s" IN %%s' % (table, column, column),
            (keep, tuple(drop)))
        if cr.rowcount:
            _logger.info('KPRL: repointed %d %s.%s to employee %d', cr.rowcount, table, column, keep)
    cr.execute('SELECT employee_id FROM kprl_employee WHERE id IN %s', (tuple(drop),))
    hr_ids = [r[0] for r in cr.fetchall() if r[0]]
    cr.execute('DELETE FROM kprl_employee WHERE id IN %s', (tuple(drop),))
    _logger.info('KPRL: merged OLADIMEJI duplicate into KPRL/003 (kept id %d)', keep)
    for hr_id in hr_ids:
        cr.execute('SELECT count(*) FROM kprl_employee WHERE employee_id = %s', (hr_id,))
        if cr.fetchone()[0] == 0:
            try:
                cr.execute('DELETE FROM hr_employee WHERE id = %s', (hr_id,))
                _logger.info('KPRL: removed orphan hr_employee %d of merged duplicate', hr_id)
            except Exception as exc:
                _logger.warning('KPRL: kept hr_employee %d (%s)', hr_id, exc)


def _delete_test_records(cr):
    cr.execute(
        "SELECT id, name FROM kprl_employee "
        "WHERE (staff_id IS NULL OR staff_id = '') AND name IN ('Classy', 'John Doe')")
    rows = cr.fetchall()
    if not rows:
        _logger.info('KPRL: blank-ID test records not found; nothing to delete')
        return
    cr.execute(FK_QUERY)
    fks = cr.fetchall()
    for emp_id, name in rows:
        refs = 0
        for table, column in fks:
            if table == 'kprl_employee':
                continue
            cr.execute('SELECT count(*) FROM "%s" WHERE "%s" = %%s' % (table, column), (emp_id,))
            refs += cr.fetchone()[0]
        if refs:
            _logger.warning('KPRL: kept test record %s (id %d) with %d linked rows', name, emp_id, refs)
            continue
        cr.execute('SELECT employee_id FROM kprl_employee WHERE id = %s', (emp_id,))
        hr_row = cr.fetchone()
        cr.execute('DELETE FROM kprl_employee WHERE id = %s', (emp_id,))
        _logger.info('KPRL: deleted blank-ID test record %s', name)
        if hr_row and hr_row[0]:
            cr.execute('SELECT count(*) FROM kprl_employee WHERE employee_id = %s', (hr_row[0],))
            if cr.fetchone()[0] == 0:
                try:
                    cr.execute('DELETE FROM hr_employee WHERE id = %s', (hr_row[0],))
                except Exception as exc:
                    _logger.warning('KPRL: kept hr_employee %s (%s)', hr_row[0], exc)


def migrate(cr, version):
    _normalize_table(cr, 'hr_employee')
    _normalize_table(cr, 'kprl_employee')
    _repoint_and_merge(cr)
    _delete_test_records(cr)
