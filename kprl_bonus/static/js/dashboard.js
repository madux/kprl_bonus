/**
 * KPRL Dashboard — interactive frontend backed by JSON API
 */
(function () {
    'use strict';

    const API = window.KPRL_API;
    const FMT = window.KPRL_FMT;

    let periods = [];
    let currentPeriodId = null;
    let currentPeriodName = '';
    let trendChart = null;

    // DOM refs
    const $ = (id) => document.getElementById(id);
    const tabsEl = document.getElementById('kprl-period-tabs');
    const tbody = document.getElementById('kprl-table-body');
    const overlay = document.getElementById('kprl-computation-overlay');
    const progressFill = document.getElementById('kprl-progress-fill');
    const compText = document.getElementById('kprl-comp-text');
    const btnRun = document.getElementById('btn-run-computation');

    async function init() {
        const data = await API.get('/periods');
        periods = data;
        if (periods.length === 0) return;
        currentPeriodId = periods[0].id;
        currentPeriodName = periods[0].name;
        renderTabs();
        await loadDashboard();
        await initTrendChart();
        setupTrendFilters();
    }

    function renderTabs() {
        if (!tabsEl) return;
        periods.forEach((p, i) => {
            const btn = tabsEl.querySelector(`[data-period="${p.name}"]`);
            if (btn) {
                btn.addEventListener('click', () => switchPeriod(p.id, p.name));
                if (i === 0) btn.classList.add('kprl-tab-active');
            }
        });
    }

    async function switchPeriod(id, name) {
        currentPeriodId = id;
        currentPeriodName = name;
        tabsEl.querySelectorAll('.kprl-tab-btn').forEach((b) => {
            b.classList.toggle('kprl-tab-active', b.dataset.period === name);
        });
        const view = document.getElementById('kprl-current-view');
        if (view) view.textContent = name + ' Dashboard';
        await loadDashboard();
    }

    async function loadDashboard() {
        if (!currentPeriodId) return;
        try {
            const data = await API.get('/dashboard/' + currentPeriodId);
            updateKpiCards(data);
            updateDeptTable(data);
        } catch (e) {
            console.error('Dashboard load error:', e);
        }
    }

    function updateKpiCards(data) {
        const e = data.engine || {};
        const setText = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        setText('kprl-kpi-score', FMT.score(e.company_kpi_score));
        setText('kprl-pool-funded', FMT.currency(e.effective_pool));
        setText('kprl-kpi-pool', FMT.currency(e.effective_pool));
        setText('kprl-kpi-payout', FMT.currency(e.total_payout));
        setText('kprl-kpi-prev', e.payout_as_pct_revenue != null ? FMT.pctRaw(e.payout_as_pct_revenue * 100) : '--');
        setText('kprl-kpi-hc', (e.headcount || 0) + ' eligible');
        setText('kprl-kpi-rev', FMT.currency(e.quarterly_revenue));
        setText('kprl-kpi-ebitda', e.ebitda_margin != null ? e.ebitda_margin + '%' : '--');
        setText('kprl-kpi-prorate', (e.proration_factor || 1) + '\u00D7');
        setText('kprl-kpi-aip', FMT.currency(e.aip_pool));
        setText('kprl-gate-text', 'Profitability Gate: ' + ((e.gate_status || '').toUpperCase()));
        setText('kprl-gmp-text', 'GMP Gate: ' + ((e.gmp_status || 'N/A').toUpperCase()));
    }

    function updateDeptTable(data) {
        if (!tbody) return;
        const depts = data.departments || [];
        if (depts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:#999;">No department data available</td></tr>';
            return;
        }
        const rows = depts.map((d) => {
            const status = (d.gmp_status === 'clean') ? 'Target' : 'Watch';
            return `<tr>
                <td>${d.department_id[1] || 'N/A'}</td>
                <td>${FMT.score(d.kpi_score)}</td>
                <td>${d.multiplier ? d.multiplier.toFixed(2) : '1.00'}</td>
                <td>--</td>
                <td>--</td>
                <td><span class="kprl-tag ${FMT.badge(status)}">${status}</span></td>
            </tr>`;
        }).join('');
        tbody.innerHTML = rows;
    }

    // ── Trend Analysis ──
    let trendData = [];

    async function initTrendChart() {
        try {
            trendData = await API.get('/trends');
        } catch (e) {
            console.error('Trend data load error:', e);
        }
        renderTrendChart();
    }

    function setupTrendFilters() {
        const metric = document.getElementById('kprl-trend-metric');
        const chartType = document.getElementById('kprl-trend-chart-type');
        if (metric) metric.addEventListener('change', renderTrendChart);
        if (chartType) chartType.addEventListener('change', renderTrendChart);
        document.querySelectorAll('.kprl-trend-period-cb').forEach(cb => {
            cb.addEventListener('change', renderTrendChart);
        });
    }

    function getSelectedPeriodIds() {
        const ids = [];
        document.querySelectorAll('.kprl-trend-period-cb:checked').forEach(cb => {
            ids.push(parseInt(cb.value));
        });
        return ids;
    }

    function renderTrendChart() {
        const canvas = document.getElementById('kprl-trend-chart');
        if (!canvas) return;

        const metric = document.getElementById('kprl-trend-metric');
        const chartType = document.getElementById('kprl-trend-chart-type');
        if (!metric || !chartType) return;

        const metricKey = metric.value;
        const type = chartType.value;
        const selectedIds = getSelectedPeriodIds();

        const labels = [];
        const values = [];

        trendData.forEach(d => {
            if (selectedIds.length === 0 || selectedIds.includes(d.period_id)) {
                labels.push(d.period_name);
                values.push(d[metricKey] || 0);
            }
        });

        if (trendChart) trendChart.destroy();

        const ctx = canvas.getContext('2d');
        const color = '#6a3d6a';

        trendChart = new Chart(ctx, {
            type: type,
            data: {
                labels: labels,
                datasets: [{
                    label: metric.options[metric.selectedIndex].text,
                    data: values,
                    backgroundColor: type === 'bar' ? color + '99' : color + '33',
                    borderColor: color,
                    borderWidth: type === 'line' ? 3 : 1,
                    fill: type === 'line',
                    tension: 0.3,
                    pointBackgroundColor: color,
                    pointRadius: type === 'line' ? 4 : 0,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                const raw = ctx.raw;
                                if (metricKey === 'ebitda_margin' || metricKey === 'company_kpi_score') {
                                    return raw.toFixed(1) + '%';
                                }
                                if (metricKey === 'headcount') {
                                    return Math.round(raw) + ' employees';
                                }
                                return '$' + (raw / 1e6).toFixed(1) + 'M';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: function (val) {
                                if (metricKey === 'ebitda_margin' || metricKey === 'company_kpi_score') {
                                    return val.toFixed(1) + '%';
                                }
                                if (metricKey === 'headcount') {
                                    return Math.round(val);
                                }
                                return '$' + (val / 1e6).toFixed(1) + 'M';
                            }
                        }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // ── Computation overlay ──
    if (btnRun) {
        btnRun.addEventListener('click', async () => {
            if (!currentPeriodId) return;
            overlay.style.display = 'flex';
            btnRun.disabled = true;
            progressFill.style.width = '0%';

            const steps = [
                { pct: 20, msg: 'Validating gate conditions...' },
                { pct: 40, msg: 'Computing KPI scores...' },
                { pct: 60, msg: 'Calculating pool allocation...' },
                { pct: 80, msg: 'Applying proration & multipliers...' },
                { pct: 100, msg: 'Finalizing results...' },
            ];

            let i = 0;
            const advance = () => {
                if (i >= steps.length) {
                    overlay.style.display = 'none';
                    btnRun.disabled = false;
                    loadDashboard();
                    initTrendChart();
                    return;
                }
                const s = steps[i];
                progressFill.style.width = s.pct + '%';
                compText.textContent = s.msg;
                i++;
                setTimeout(advance, 600);
            };

            API.post('/compute/' + currentPeriodId).catch(console.error);
            setTimeout(advance, 400);
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.style.display = 'none';
                btnRun.disabled = false;
            }
        });
    }

    init();
})();
