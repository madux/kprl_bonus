import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute('SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s', ('kprl_employee', 'date_hired'))
    if cr.fetchone():
        cr.execute('ALTER TABLE kprl_employee RENAME COLUMN date_hired TO employment_date')
        _logger.info('KPRL: renamed kprl_employee.date_hired to employment_date')
