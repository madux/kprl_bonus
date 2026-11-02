"""Workbook-realignment migration (dev): pool min 0.61 -> 0.606 (CONTROL B8)."""
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s", ("kprl_bonus_parameter", "min_pool_rate"))
    if not cr.fetchone():
        _logger.warning("kprl_bonus_parameter.min_pool_rate missing; skipping F6 fix")
        return
    cr.execute("UPDATE kprl_bonus_parameter SET min_pool_rate = 0.606 WHERE min_pool_rate = 0.61")
    if cr.rowcount:
        _logger.info("F6: migrated %d bonus.parameter rows to min_pool_rate 0.606", cr.rowcount)
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s", ("kprl_grade", "deferral_rate"))
    if not cr.fetchone():
        _logger.warning("kprl_grade.deferral_rate missing; skipping F7 seed")
        return
    cr.execute("UPDATE kprl_grade SET deferral_rate = 20 WHERE code IN (%s, %s, %s)", ("SENMGT", "TIER1", "TIER2"))
    _logger.info("F7: seeded senior-tier deferral on %d grade rows", cr.rowcount)
    cr.execute("UPDATE kprl_grade SET deferral_rate = 0 WHERE code NOT IN (%s, %s, %s) AND (deferral_rate IS NULL OR deferral_rate != 0)", ("SENMGT", "TIER1", "TIER2"))
    _logger.info("F7: zeroed deferral on %d non-senior grade rows", cr.rowcount)
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s", ("kprl_department", "gmp_status"))
    if cr.fetchone():
        cr.execute("UPDATE kprl_department SET gmp_status = %s WHERE gmp_status IS NULL", ("clean",))
        _logger.info("F8: defaulted standing GMP on %d department rows", cr.rowcount)
    cr.execute("UPDATE kprl_department SET name = %s WHERE code = %s AND name = %s", ("QA/QC", "QA", "Quality Assurance"))
    if cr.rowcount:
        _logger.info("F8: renamed QA department to QA/QC")
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s", ("kprl_aip_pool", "strategic_score"))
    if cr.fetchone():
        cr.execute("UPDATE kprl_aip_pool SET strategic_score = 0.8 WHERE strategic_score = 0")
        _logger.info("F5: workbook strategic 0.8 applied to %d AIP pools", cr.rowcount)
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s", ("kprl_aip_pool", "param_state"))
    if cr.fetchone():
        cr.execute("UPDATE kprl_aip_pool SET param_state = %s WHERE param_state IS NULL", ("approved",))
        _logger.info("F5: defaulted param approval on %d AIP pools", cr.rowcount)

