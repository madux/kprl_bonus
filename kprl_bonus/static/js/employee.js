/**
 * KPRL Employee Detail — loads payout, performance, deferred, history via API
 */
(function () {
  'use strict';

  const API = window.KPRL_API;
  const FMT = window.KPRL_FMT;
  const EMP_ID = window.KPRL_EMPLOYEE_ID;

  async function init() {
    if (!EMP_ID) return;
    setupTabs();
    const periods = await API.get('/periods');
    const active = periods.find((p) => p.state === 'active') || periods[0];
    if (!active) {
      document
        .querySelectorAll('.kprl-tab-content .kprl-table-label')
        .forEach(function (el) {
          if (el.textContent.indexOf('Loading') !== -1)
            el.textContent = 'No bonus periods found';
        });
      return;
    }
    await Promise.all([
      loadPayout(EMP_ID, active.id),
      loadPerformance(EMP_ID, active.id),
      loadDeferred(EMP_ID),
      loadHistory(EMP_ID),
    ]);
  }

  function setupTabs() {
    const tabsEl = document.getElementById('kprl-emp-tabs');
    if (!tabsEl) return;
    tabsEl.querySelectorAll('.kprl-tab-item').forEach((tab) => {
      tab.addEventListener('click', () => {
        tabsEl
          .querySelectorAll('.kprl-tab-item')
          .forEach((t) => t.classList.remove('kprl-active-tab'));
        tab.classList.add('kprl-active-tab');
        const target = tab.dataset.tab;
        document.querySelectorAll('.kprl-tab-content').forEach((c) => {
          c.style.display = c.id === 'kprl-tab-' + target ? '' : 'none';
        });
      });
    });
  }

  async function loadPayout(empId, periodId) {
    try {
      const payout = await API.get(
        '/employee/' + empId + '/payout/' + periodId,
      );
      const el = document.getElementById('kprl-payout-content');
      if (!el) return;
      if (!payout || !payout.id) {
        el.innerHTML =
          '<div class="kprl-table-summary"><p class="kprl-table-label">You\'re all caught up!</p><span class="kprl-table-label">New payout data will show up here as they arrive.</span></div>';
        return;
      }
      el.innerHTML =
        '<div class="kprl-table-row"><span class="kprl-table-label">Base Eligible</span><span class="kprl-table-value">' +
        FMT.currency(payout.base_eligible) +
        '</span></div>' +
        '<div class="kprl-table-row"><span class="kprl-table-label">Dept KPI Mult</span><span class="kprl-table-value">\u00D7' +
        (payout.dept_kpi_mult || 1).toFixed(2) +
        '</span></div>' +
        '<div class="kprl-table-row"><span class="kprl-table-label">Appraisal Mult</span><span class="kprl-table-value">\u00D7' +
        (payout.appraisal_mult || 1).toFixed(2) +
        '</span></div>' +
        '<div class="kprl-table-row"><span class="kprl-table-label">Behavioural Mult</span><span class="kprl-table-value">\u00D7' +
        (payout.behavioural_mult || 1).toFixed(2) +
        '</span></div>' +
        '<div class="kprl-table-row"><span class="kprl-table-label">Exception Premium</span><span class="kprl-table-value">' +
        FMT.currency(payout.exception_premium) +
        '</span></div>' +
        '<div class="kprl-table-row"><span class="kprl-table-label">Proration</span><span class="kprl-table-value">\u00D7' +
        (payout.proration_factor || 1).toFixed(2) +
        '</span></div>' +
        '<div class="kprl-table-row"><span class="kprl-table-label">Tenure Mult</span><span class="kprl-table-value">\u00D7' +
        (payout.tenure_mult || 1).toFixed(2) +
        '</span></div>' +
        '<div class="kprl-table-row"><span class="kprl-table-label">GMP Dept Factor</span><span class="kprl-table-value">\u00D7' +
        (payout.gmp_factor || 1).toFixed(2) +
        '</span></div>' +
        '<div class="kprl-table-row"><span class="kprl-table-label">Malus</span><span class="kprl-table-value">' +
        FMT.currency(payout.malus_amount) +
        '</span></div>' +
        '<div class="kprl-table-row kprl-summary-row-break"><span class="kprl-table-label">Gross Payable</span><span class="kprl-table-value kprl-text-bold">' +
        FMT.currency(payout.gross_payable) +
        '</span></div>' +
        '<div class="kprl-table-row"><span class="kprl-table-label">Deferred (' +
        (payout.deferral_rate || 0).toFixed(0) +
        '%)</span><span class="kprl-table-value">' +
        FMT.currency(payout.deferred_amount) +
        '</span></div>' +
        '<div class="kprl-table-row kprl-net-immediate-row"><span class="kprl-table-label">NET IMMEDIATE</span><span class="kprl-table-value">' +
        FMT.currency(payout.net_immediate) +
        '</span></div>' +
        '<td style="padding:10px 16px;color:#c62828;font-weight:600;">' +
        (payout.total_governance_deduction > 0 ? '-' + FMT.currency(payout.total_governance_deduction) : '-') +
        '</td>' +
    } catch (e) {
      console.error('Payout load error:', e);
    }
  }

  async function loadPerformance(empId, periodId) {
    try {
      const records = await API.get('/performance/' + periodId);
      const me = records.find((r) => {
        const rid = Array.isArray(r.employee_id)
          ? r.employee_id[0]
          : r.employee_id;
        return rid === empId;
      });

      const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };
      const setBar = (id, pct) => {
        const el = document.getElementById(id);
        if (el) el.style.width = pct;
      };

      if (!me) {
        setVal('kprl-appraisal-score', 'No data');
        setVal('kprl-behavioural-score', 'No data');
        setVal('kprl-dept-kpi', 'No data');
        setBar('kprl-appraisal-bar', '0%');
        setBar('kprl-behavioural-bar', '0%');
        setBar('kprl-dept-kpi-bar', '0%');
        return;
      }

      setVal('kprl-appraisal-score', (me.appraisal_score || 0) + ' / 100');
      setBar(
        'kprl-appraisal-bar',
        Math.min(me.appraisal_score || 0, 100) + '%',
      );
      setVal('kprl-behavioural-score', (me.team_pct || 0).toFixed(1) + ' / 25');
      setBar('kprl-behavioural-bar', ((me.team_pct || 0) / 25) * 100 + '%');
      setVal('kprl-dept-kpi', (me.prod_pct || 0).toFixed(1));
      setBar('kprl-dept-kpi-bar', Math.min(me.prod_pct || 0, 100) + '%');
    } catch (e) {
      console.error('Performance load error:', e);
    }
  }

  async function loadDeferred(empId) {
    try {
      const entries = await API.get('/deferred/' + empId);
      const el = document.getElementById('kprl-deferred-content');
      if (!el) return;
      if (!entries || entries.length === 0) {
        el.innerHTML =
          '<div class="kprl-table-row"><span class="kprl-table-label">No deferred entries found</span></div>';
        return;
      }
      el.innerHTML = entries
        .map(
          (e) =>
            '<div class="kprl-table-row">' +
            '<span class="kprl-table-label">' +
            (e.period_id ? e.period_id[1] : 'N/A') +
            ' — Deferred ' +
            (e.deferred_amount ? FMT.currency(e.deferred_amount) : '₦0') +
            '</span>' +
            '<span class="kprl-table-value">' +
            (e.status || 'pending').toUpperCase() +
            '</span>' +
            '</div>',
        )
        .join('');
    } catch (e) {
      console.error('Deferred load error:', e);
    }
  }

  async function loadHistory(empId) {
    try {
      const periods = await API.get('/periods');
      const el = document.getElementById('kprl-history-content');
      if (!el) return;
      const rows = [];
      for (const p of periods) {
        try {
          const payout = await API.get(
            '/employee/' + empId + '/payout/' + p.id,
          );
          if (payout && payout.id) {
            rows.push(
              '<tr>' +
                '<td style="padding:10px 16px;font-weight:500;color:#2D3142;">' +
                p.name +
                '</td>' +
                '<td style="padding:10px 16px;color:#5a5a5a;">' +
                FMT.currency(payout.base_eligible) +
                '</td>' +
                '<td style="padding:10px 16px;color:#5a5a5a;">\u00D7' +
                (payout.dept_kpi_mult || 1).toFixed(2) +
                '</td>' +
                '<td style="padding:10px 16px;color:#5a5a5a;">\u00D7' +
                (payout.appraisal_mult || 0).toFixed(2) +
                '</td>' +
                '<td style="padding:10px 16px;color:#5a5a5a;">\u00D7' +
                (payout.behavioural_mult || 1).toFixed(2) +
                '</td>' +
                '<td style="padding:10px 16px;font-weight:600;color:#6a3d6a;">' +
                FMT.currency(payout.gross_payable) +
                '</td>' +
                '<td style="padding:10px 16px;color:#856404;">' +
                FMT.currency(payout.deferred_amount) +
                '</td>' +
                '<td style="padding:10px 16px;font-weight:700;color:#1b5e20;">' +
                FMT.currency(payout.net_immediate) +
                '</td>' +
                '<td style="padding:10px 16px;color:#c62828;font-weight:600;">' +
                (payout.total_governance_deduction > 0 ? '-' + FMT.currency(payout.total_governance_deduction) : '-') +
                '</td>' +
                '<td style="padding:10px 16px;"><span style="padding:4px 10px;border-radius:12px;font-size:11px;font-weight:700;' +
                (payout.state === 'paid'
                  ? 'background:#def2e6;color:#1b5e20;'
                  : payout.state === 'approved'
                    ? 'background:#e8f0fe;color:#1a73e8;'
                    : 'background:#f0f2f5;color:#7A8296;') +
                '">' +
                (payout.state || 'draft').toUpperCase() +
                '</span></td>' +
                '</tr>',
            );
          }
        } catch (err) {
          /* skip */
        }
      }
      if (rows.length > 0) {
        el.innerHTML =
          '<table style="width:100%;border-collapse:collapse;font-size:14px;">' +
          '<thead><tr style="background:#f4f6f9;">' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Period</th>' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Base Eligible</th>' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Dept KPI</th>' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Appraisal</th>' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Behavioural</th>' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Gross Payable</th>' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Deferred</th>' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Net Immediate</th>' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Malus / Clawback</th>' +
          '<th style="padding:12px 16px;text-align:left;font-weight:600;color:#6a3d6a;">Status</th>' +
          '</tr></thead>' +
          '<tbody>' +
          rows.join('') +
          '</tbody>' +
          '</table>';
      } else {
        el.innerHTML =
          '<p style="color:#7A8296;font-size:13px;padding:16px;">No payout history found.</p>';
      }
    } catch (e) {
      console.error('History load error:', e);
    }
  }

  // Card entrance animations
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.kprl-card').forEach((card, i) => {
      setTimeout(() => card.classList.add('kprl-animate-in'), i * 120);
    });
  });

  if (EMP_ID) init();
})();
