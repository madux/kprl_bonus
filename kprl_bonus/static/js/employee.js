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
        const active = periods.find(p => p.state === 'active') || periods[0];
        if (!active) return;
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
        tabsEl.querySelectorAll('.kprl-tab-item').forEach(tab => {
            tab.addEventListener('click', () => {
                tabsEl.querySelectorAll('.kprl-tab-item').forEach(t => t.classList.remove('kprl-active-tab'));
                tab.classList.add('kprl-active-tab');
                const target = tab.dataset.tab;
                document.querySelectorAll('.kprl-tab-content').forEach(c => {
                    c.style.display = c.id === 'kprl-tab-' + target ? '' : 'none';
                });
            });
        });
    }

    async function loadPayout(empId, periodId) {
        try {
            const payout = await API.get('/employee/' + empId + '/payout/' + periodId);
            if (!payout || !payout.id) return;
            const el = document.getElementById('kprl-payout-content');
            if (!el) return;
            el.innerHTML = '<div class="kprl-table-row"><span class="kprl-table-label">Base Eligible</span><span class="kprl-table-value">' + FMT.currency(payout.base_eligible) + '</span></div>'
                + '<div class="kprl-table-row"><span class="kprl-table-label">Dept KPI Mult</span><span class="kprl-table-value">\u00D7' + (payout.dept_kpi_mult || 1).toFixed(2) + '</span></div>'
                + '<div class="kprl-table-row"><span class="kprl-table-label">Appraisal Mult</span><span class="kprl-table-value">\u00D7' + (payout.appraisal_mult || 1).toFixed(2) + '</span></div>'
                + '<div class="kprl-table-row"><span class="kprl-table-label">Behavioural Mult</span><span class="kprl-table-value">\u00D7' + (payout.behavioural_mult || 1).toFixed(2) + '</span></div>'
                + '<div class="kprl-table-row"><span class="kprl-table-label">Exception Premium</span><span class="kprl-table-value">' + FMT.currency(payout.exception_premium) + '</span></div>'
                + '<div class="kprl-table-row"><span class="kprl-table-label">Proration</span><span class="kprl-table-value">\u00D7' + (payout.proration_factor || 1).toFixed(2) + '</span></div>'
                + '<div class="kprl-table-row"><span class="kprl-table-label">Tenure Mult</span><span class="kprl-table-value">\u00D7' + (payout.tenure_mult || 1).toFixed(2) + '</span></div>'
                + '<div class="kprl-table-row"><span class="kprl-table-label">GMP Dept Factor</span><span class="kprl-table-value">\u00D7' + (payout.gmp_factor || 1).toFixed(2) + '</span></div>'
                + '<div class="kprl-table-row"><span class="kprl-table-label">Malus</span><span class="kprl-table-value">' + FMT.currency(payout.malus_amount) + '</span></div>'
                + '<div class="kprl-table-row kprl-summary-row-break"><span class="kprl-table-label">Gross Payable</span><span class="kprl-table-value kprl-text-bold">' + FMT.currency(payout.gross_payable) + '</span></div>'
                + '<div class="kprl-table-row"><span class="kprl-table-label">Deferred (' + (payout.deferral_rate || 0).toFixed(0) + '%)</span><span class="kprl-table-value">' + FMT.currency(payout.deferred_amount) + '</span></div>'
                + '<div class="kprl-table-row kprl-net-immediate-row"><span class="kprl-table-label">NET IMMEDIATE</span><span class="kprl-table-value">' + FMT.currency(payout.net_immediate) + '</span></div>';
        } catch (e) {
            console.error('Payout load error:', e);
        }
    }

    async function loadPerformance(empId, periodId) {
        try {
            const records = await API.get('/performance/' + periodId);
            const me = records.find(r => r.employee_id[0] === empId);
            if (!me) return;

            const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
            const setBar = (id, pct) => { const el = document.getElementById(id); if (el) el.style.width = pct; };

            setVal('kprl-appraisal-score', (me.appraisal_score || 0) + ' / 100');
            setBar('kprl-appraisal-bar', (me.appraisal_score || 0) + '%');
            setVal('kprl-behavioural-score', (me.call_pct || 0).toFixed(0) + ' / 25');
            setBar('kprl-behavioural-bar', ((me.call_pct || 0) / 25 * 100) + '%');
            setVal('kprl-dept-kpi', (me.retain_score || 0).toFixed(2) + ' / 1.00');
            setBar('kprl-dept-kpi-bar', (me.retain_score || 0) * 100 + '%');
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
                el.innerHTML = '<div class="kprl-table-row"><span class="kprl-table-label">No deferred entries found</span></div>';
                return;
            }
            el.innerHTML = entries.map(e => '<div class="kprl-table-row">'
                + '<span class="kprl-table-label">' + (e.period_id ? e.period_id[1] : 'N/A') + ' — Deferred ' + (e.deferred_amount ? FMT.currency(e.deferred_amount) : '₦0') + '</span>'
                + '<span class="kprl-table-value">' + (e.status || 'pending').toUpperCase() + '</span>'
                + '</div>').join('');
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
                    const payout = await API.get('/employee/' + empId + '/payout/' + p.id);
                    if (payout && payout.id) {
                        rows.push('<div class="kprl-table-row">'
                            + '<span class="kprl-table-label">' + p.name + '</span>'
                            + '<span class="kprl-table-value">' + FMT.currency(payout.gross_payable) + ' gross / ' + FMT.currency(payout.net_immediate) + ' net</span>'
                            + '</div>');
                    }
                } catch (err) { /* skip */ }
            }
            el.innerHTML = rows.length > 0 ? rows.join('') : '<div class="kprl-table-row"><span class="kprl-table-label">No payout history found</span></div>';
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
