import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute('SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s', ('kprl_bonus_engine', 'aip_pool'))
    if cr.fetchone():
        cr.execute('ALTER TABLE kprl_bonus_engine RENAME COLUMN aip_pool TO qipm_pool')
        _logger.info('QIPM: renamed kprl_bonus_engine.aip_pool to qipm_pool')
