/**
 * KPRL Bonus Simulation — real-time bonus projection for employees
 */
(function () {
    'use strict';

    const API = window.KPRL_API;
    const FMT = window.KPRL_FMT;
    const EMP_ID = window.KPRL_EMPLOYEE_ID;
    const PARAMS = window.KPRL_SIM_PARAMS || {};

    let currentQuarter = 'Q2';

    function init() {
        setupTabs();
        setupQuarterFilters();
        setupSimInputs();
        setupWhatIfSliders();
        calculate();
        calculateScenarios();
    }

    function setupTabs() {
        const tabsEl = document.getElementById('kprl-sim-tabs');
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

    function setupQuarterFilters() {
        const filtersEl = document.getElementById('kprl-quarter-filters');
        if (!filtersEl) return;
        filtersEl.querySelectorAll('.kprl-filter-item').forEach(btn => {
            btn.addEventListener('click', () => {
                filtersEl.querySelectorAll('.kprl-filter-item').forEach(b => b.classList.remove('kprl-active-filter'));
                btn.classList.add('kprl-active-filter');
                currentQuarter = btn.dataset.quarter;
                const quarterLabel = document.getElementById('kprl-sim-quarter');
                if (quarterLabel) quarterLabel.textContent = currentQuarter + '-2026';
                calculate();
            });
        });
    }

    function setupSimInputs() {
        document.querySelectorAll('.kprl-sim-input').forEach(inp => {
            inp.addEventListener('input', calculate);
        });
        const calcBtn = document.getElementById('kprl-sim-calculate');
        if (calcBtn) calcBtn.addEventListener('click', calculate);
        const resetBtn = document.getElementById('kprl-sim-reset');
        if (resetBtn) resetBtn.addEventListener('click', () => {
            document.getElementById('kprl-sim-base').value = PARAMS.base_eligible || 117800;
            document.getElementById('kprl-sim-appraisal').value = 82;
            document.getElementById('kprl-sim-behavioural').value = 20;
            document.getElementById('kprl-sim-dept-kpi').value = 0.95;
            document.getElementById('kprl-sim-exception').value = 0;
            document.getElementById('kprl-sim-malus').value = 0;
            calculate();
        });
    }

    function getVal(id) {
        const el = document.getElementById(id);
        return el ? parseFloat(el.value) || 0 : 0;
    }

    function fmtCurrency(v) {
        if (v == null) return '₦0';
        return '₦' + Math.round(v).toLocaleString('en-US');
    }

    function appraisalToMult(score) {
        // Map 0-100 appraisal score to multiplier (0.60 to 1.20)
        if (score >= 90) return 1.20;
        if (score >= 80) return 1.05;
        if (score >= 70) return 0.95;
        if (score >= 60) return 0.85;
        if (score >= 50) return 0.75;
        return 0.60;
    }

    function behaviouralToMult(score) {
        // Map 0-25 behavioural score to multiplier (0.80 to 1.00)
        return 0.80 + (score / 25) * 0.20;
    }

    function calculate() {
        const base = getVal('kprl-sim-base');
        const appraisalScore = getVal('kprl-sim-appraisal');
        const behaviouralScore = getVal('kprl-sim-behavioural');
        const deptKpi = getVal('kprl-sim-dept-kpi');
        const exception = getVal('kprl-sim-exception');
        const malus = getVal('kprl-sim-malus');

        const appraisalMult = appraisalToMult(appraisalScore);
        const behaviouralMult = behaviouralToMult(behaviouralScore);
        const proration = PARAMS.proration_factor || 1.0;
        const tenure = PARAMS.tenure_mult || 1.0;
        const gmp = PARAMS.gmp_factor || 1.0;
        const deferralRate = PARAMS.deferral_rate || 20;

        const gross = Math.max(0,
            base * appraisalMult * behaviouralMult * deptKpi * proration * tenure * gmp
            + exception - malus
        );
        const deferred = gross * (deferralRate / 100);
        const net = gross - deferred;

        const minFloor = PARAMS.min_floor || 30000;
        const maxCap = PARAMS.max_cap || 500000;
        const floorPass = net >= minFloor;
        const capPass = gross <= maxCap;

        // Update multiplier displays
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
        set('kprl-sim-proration', '\u00D7' + proration.toFixed(2));
        set('kprl-sim-tenure', '\u00D7' + tenure.toFixed(2));
        set('kprl-sim-gmp', '\u00D7' + gmp.toFixed(2));
        set('kprl-sim-deferral', deferralRate + '%');

        // Update breakdown
        set('kprl-out-base', fmtCurrency(base));
        set('kprl-out-appraisal-mult', '\u00D7' + appraisalMult.toFixed(2));
        set('kprl-out-behavioural-mult', '\u00D7' + behaviouralMult.toFixed(2));
        set('kprl-out-dept-mult', '\u00D7' + deptKpi.toFixed(2));
        set('kprl-out-proration', '\u00D7' + proration.toFixed(2));
        set('kprl-out-tenure', '\u00D7' + tenure.toFixed(2));
        set('kprl-out-gmp', '\u00D7' + gmp.toFixed(2));
        set('kprl-out-exception', fmtCurrency(exception));
        set('kprl-out-malus', fmtCurrency(malus));
        set('kprl-out-gross', fmtCurrency(gross));
        set('kprl-out-deferred', fmtCurrency(deferred));
        set('kprl-out-net', fmtCurrency(net));

        // Status
        const statusEl = document.getElementById('kprl-sim-status');
        const statusText = document.getElementById('kprl-sim-status-text');
        if (statusEl && statusText) {
            if (!floorPass) {
                statusEl.className = 'kprl-sim-status-box kprl-status-warn';
                statusText.textContent = 'Floor check: FAIL (net ₦' + Math.round(net).toLocaleString() + ' < ₦' + minFloor.toLocaleString() + ')';
            } else if (!capPass) {
                statusEl.className = 'kprl-sim-status-box kprl-status-warn';
                statusText.textContent = 'Cap check: FAIL (gross ₦' + Math.round(gross).toLocaleString() + ' > ₦' + maxCap.toLocaleString() + ')';
            } else {
                statusEl.className = 'kprl-sim-status-box kprl-status-pass';
                statusText.textContent = 'Floor check: PASS (net ₦' + Math.round(net).toLocaleString() + ' > ₦' + minFloor.toLocaleString() + ')';
            }
        }
    }

    // ── What-If Scenarios ──
    function setupWhatIfSliders() {
        document.querySelectorAll('.kprl-range-input').forEach(slider => {
            slider.addEventListener('input', () => {
                updateSliderLabel(slider);
                calculateScenarios();
            });
        });
    }

    function updateSliderLabel(slider) {
        const id = slider.id;
        const val = parseFloat(slider.value);
        const labelEl = document.getElementById(id + '-val');
        if (!labelEl) return;
        if (id.includes('kpi')) {
            labelEl.textContent = (val / 100).toFixed(2);
        } else if (id.includes('behav')) {
            labelEl.textContent = val + '/25';
        } else {
            labelEl.textContent = val + '%';
        }
    }

    function scenarioNet(appraisal, kpi, behav) {
        const base = getVal('kprl-sim-base') || PARAMS.base_eligible || 117800;
        const appraisalMult = appraisalToMult(appraisal);
        const behaviouralMult = 0.80 + (behav / 25) * 0.20;
        const proration = PARAMS.proration_factor || 1.0;
        const tenure = PARAMS.tenure_mult || 1.0;
        const gmp = PARAMS.gmp_factor || 1.0;
        const deferralRate = PARAMS.deferral_rate || 20;
        const gross = Math.max(0,
            base * appraisalMult * behaviouralMult * (kpi / 100) * proration * tenure * gmp
        );
        return gross * (1 - deferralRate / 100);
    }

    function calculateScenarios() {
        const worst = scenarioNet(
            getVal('kprl-worst-appraisal'),
            getVal('kprl-worst-kpi'),
            getVal('kprl-worst-behav')
        );
        const current = scenarioNet(
            getVal('kprl-current-appraisal'),
            getVal('kprl-current-kpi'),
            getVal('kprl-current-behav')
        );
        const best = scenarioNet(
            getVal('kprl-best-appraisal'),
            getVal('kprl-best-kpi'),
            getVal('kprl-best-behav')
        );

        const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = fmtCurrency(val); };
        set('kprl-worst-result', worst);
        set('kprl-current-result', current);
        set('kprl-best-result', best);
    }

    init();
})();
