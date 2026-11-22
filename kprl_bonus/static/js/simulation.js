/**
 * KPRL Bonus Simulation - v30 aligned (Ops Sec6 + Sales Sec7)
 * SINGLE SOURCE OF TRUTH: every cascade formula lives inside the backend
 * compensation engine (models/compensation/*). This page only renders the
 * API response of POST /kprl/api/simulate/<emp_id>/<period_id>; what-if
 * values go to the server as engine input overrides and are never
 * recomputed here.
 */
(function () {
    'use strict';
    // PARAMS may be object (from t-raw JSON) or string
    let PARAMS = window.KPRL_SIM_PARAMS || {};
    if (typeof PARAMS === 'string') {
        try { PARAMS = JSON.parse(PARAMS); } catch(e) { PARAMS = {}; }
    }
    let currentQuarter = 'Q2';
    let opsSeq = 0, salesSeq = 0, scenarioSeq = 0;

    function init() {
        // Show sales tab if sales employee
        const salesBtn = document.getElementById('kprl-tab-sales-btn');
        if (salesBtn && PARAMS.is_sales) {
            salesBtn.style.display = '';
        }
        setupTabs();
        setupQuarterFilters();
        setupSimInputs();
        setupSalesInputs();
        setupWhatIfSliders();
        prefillFromParams();
        refreshAll();
    }

    function debounce(fn, ms) {
        let t = null;
        return function () {
            const args = arguments, self = this;
            clearTimeout(t);
            t = setTimeout(() => fn.apply(self, args), ms);
        };
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
                if (target === 'sales') calculateSales();
                if (target === 'simulator') calculate();
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
                refreshAll();
            });
        });
    }

    function setupSimInputs() {
        document.querySelectorAll('.kprl-sim-input').forEach(inp => {
            inp.addEventListener('input', debounce(refreshAll, 250));
        });
        const calcBtn = document.getElementById('kprl-sim-calculate');
        if (calcBtn) calcBtn.addEventListener('click', refreshAll);
        const resetBtn = document.getElementById('kprl-sim-reset');
        if (resetBtn) resetBtn.addEventListener('click', () => {
            prefillFromParams();
            refreshAll();
        });
    }

    function setupSalesInputs() {
        ['kprl-sales-target','kprl-sales-own','kprl-sales-retr','kprl-sales-pk','kprl-sales-call','kprl-sales-cov','kprl-sales-new'].forEach(id=>{
            const el=document.getElementById(id);
            if(el) el.addEventListener('input', debounce(calculateSales, 250));
        });
    }

    function prefillFromParams() {
        const setVal=(id,v)=>{ const el=document.getElementById(id); if(el && v!==undefined && v!==null) el.value=v; };
        setVal('kprl-sim-base', PARAMS.base_eligible || 117800);
        setVal('kprl-sim-appraisal', PARAMS.appraisal_current || 82);
        setVal('kprl-sim-behavioural', PARAMS.behav_25_current || 20);
        setVal('kprl-sim-dept-kpi', PARAMS.dept_kpi_mult || 0.95);
        setVal('kprl-sim-exception', 0);
        setVal('kprl-sim-malus', 0);
        // Sales
        setVal('kprl-sales-target', PARAMS.own_target || 66000000);
        setVal('kprl-sales-own', PARAMS.own_sales || 45814086);
        setVal('kprl-sales-retr', PARAMS.own_retr || 33158079);
        setVal('kprl-sales-pk', PARAMS.pk_score || 0.90);
        setVal('kprl-sales-call', PARAMS.call_score || 0.88);
        setVal('kprl-sales-cov', PARAMS.cov_score || 0.97);
        setVal('kprl-sales-new', PARAMS.new_score || 0.80);
    }

    function getVal(id) {
        const el = document.getElementById(id);
        return el ? parseFloat(el.value) || 0 : 0;
    }

    function fmtCurrency(v) {
        if (v == null || isNaN(v)) return '\u20a60';
        return '\u20a6' + Math.round(v).toLocaleString('en-US');
    }

    function csrfToken() {
        if (typeof odoo !== 'undefined' && odoo.csrf_token) return odoo.csrf_token;
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        return window.KPRL_CSRF || '';
    }

    function simulateUrl() {
        const m = (window.location.pathname || '').match(/\/kprl\/simulate\/(\d+)/);
        return (m && PARAMS.period_id)
            ? '/kprl/api/simulate/' + m[1] + '/' + PARAMS.period_id : null;
    }

    async function fetchSim(overrides) {
        const url = simulateUrl();
        if (!url) throw new Error('simulation context missing (employee/period)');
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify({overrides: overrides || {}}),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || ('simulate API error ' + res.status));
        }
        return res.json();
    }

    function setSimStatus(kind, text) {
        const statusEl = document.getElementById('kprl-sim-status');
        const statusText = document.getElementById('kprl-sim-status-text');
        if (!statusEl || !statusText) return;
        statusEl.className = 'kprl-sim-status-box ' + (
            kind === 'error' ? 'kprl-status-warn' :
            kind === 'warn' ? 'kprl-status-warn' : 'kprl-status-pass');
        statusText.textContent = text;
    }

    const setIf = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

    // ---- OPS TAB ------------------------------------------------------
    async function calculate() {
        const seq = ++opsSeq;
        const overrides = {
            appraisal: getVal('kprl-sim-appraisal'),
            behaviour: getVal('kprl-sim-behavioural'),
            dept_kpi_mult: getVal('kprl-sim-dept-kpi'),
            malus_pct: getVal('kprl-sim-malus'),
            base_eligible: getVal('kprl-sim-base'),
        };
        let data;
        try {
            data = await fetchSim(overrides);
        } catch (e) {
            if (seq === opsSeq) setSimStatus('error', 'Simulation error: ' + e.message);
            return;
        }
        if (seq !== opsSeq || !data) return;

        const ops = data.ops || {};
        const gov = data.governed || {};
        const cls = data.classification || {};

        const effGmp = (gov.dept_gmp || 1.0) * (gov.qa_relief || 1.0);
        const proration = gov.proration_factor || 1.0;
        const tenure = ops.tenure_multiplier || 1.0;
        const deferralPct = (ops.deferral_rate || 0) * 100;
        const net = gov.net_payable || 0;
        const floorAmt = gov.final_floor || 0;
        const cap = gov.cap || PARAMS.g_individual_cap || 2000000;
        const deferred = gov.deferred_amount || 0;

        setIf('kprl-sim-proration', '\u00d7' + proration.toFixed(2));
        setIf('kprl-sim-tenure', '\u00d7' + tenure.toFixed(2));
        setIf('kprl-sim-gmp', '\u00d7' + effGmp.toFixed(2));
        setIf('kprl-sim-deferral', deferralPct + '%');
        setIf('kprl-out-base', fmtCurrency(ops.base_eligible));
        setIf('kprl-out-appraisal-mult', '\u00d7' + (ops.appraisal_multiplier || 0).toFixed(2));
        setIf('kprl-out-behavioural-mult', '\u00d7' + (ops.behaviour_multiplier || 0).toFixed(2));
        setIf('kprl-out-dept-mult', '\u00d7' + (ops.department_kpi_multiplier || 0).toFixed(2));
        setIf('kprl-out-proration', '\u00d7' + proration.toFixed(2));
        setIf('kprl-out-tenure', '\u00d7' + tenure.toFixed(2));
        setIf('kprl-out-gmp', '\u00d7' + effGmp.toFixed(2));
        setIf('kprl-out-exception', fmtCurrency(ops.exception_premium || 0));
        setIf('kprl-out-malus', (gov.malus_pct || 0) + '%');
        setIf('kprl-out-gross', fmtCurrency(gov.gross_payable));
        setIf('kprl-out-deferred', fmtCurrency(deferred));
        setIf('kprl-out-net', fmtCurrency(net));

        // Status box driven by engine booleans (floor tier + governed cap).
        const capPass = (gov.cap_check !== false) && net <= cap + 0.01;
        const floorPass = (PARAMS.min_floor || 0) <= floorAmt + 0.01;
        if (data.status === 'blocked') {
            setSimStatus('error', 'Blocked: ' + ((data.blocking_errors || []).join('; ') || 'missing inputs'));
        } else if (!floorPass) {
            setSimStatus('warn', 'Floor check: FAIL (final \u20a6' + Math.round(floorAmt ?? 0).toLocaleString() + ' < \u20a6' + (PARAMS.min_floor || 0).toLocaleString() + ')');
        } else if (!capPass) {
            setSimStatus('warn', 'Cap check: FAIL (net \u20a6' + Math.round(net).toLocaleString() + ' > \u20a6' + Math.round(cap).toLocaleString() + ')');
        } else {
            setSimStatus('pass', (PARAMS.min_floor > 0
                ? 'Floor check: PASS (final \u20a6' + Math.round(floorAmt).toLocaleString() + ' \u2265 \u20a6' + (PARAMS.min_floor || 0).toLocaleString() + ')'
                : 'Floor check: PASS (no floor for this grade)'));
        }
        window._lastOpsNet = net;
    }

    // ---- SALES TAB ----------------------------------------------------
    async function calculateSales() {
        if (!PARAMS.is_sales) return;
        const seq = ++salesSeq;
        const overrides = {
            own_target: getVal('kprl-sales-target'),
            own_sales: getVal('kprl-sales-own'),
            own_retrieval: getVal('kprl-sales-retr'),
            pk: getVal('kprl-sales-pk'),
            call: getVal('kprl-sales-call'),
            cov: getVal('kprl-sales-cov'),
            newc: getVal('kprl-sales-new'),
        };
        let data;
        try {
            data = await fetchSim(overrides);
        } catch (e) {
            if (seq === salesSeq) setSimStatus('error', 'Sales simulation error: ' + e.message);
            return;
        }
        if (seq !== salesSeq || !data) return;

        const sales = data.sales || {};
        const attain = sales.attainment || 0;
        const retr = sales.retrieval_rate || 0;
        const salesGate = sales.sales_gate || 0;
        const retrGate = sales.retrieval_gate || 0;
        const kpiMult = sales.kpi_multiplier || 0;
        const accel = sales.accelerator || 1.0;
        const gross = (sales.sales_commission || 0) + (sales.retrieval_commission || 0);
        const eligible = sales.eligible || 0;
        const final = sales.final_payout || 0;
        const cap = sales.cap || 0;
        const capPass = final <= cap;

        setIf('kprl-sales-attain', (attain * 100).toFixed(2) + '%');
        setIf('kprl-sales-retr-rate', (retr * 100).toFixed(2) + '%');
        setIf('kprl-sales-gate', salesGate.toFixed(4));
        setIf('kprl-sales-retr-gate', retrGate.toFixed(4));
        setIf('kprl-sales-kpi-mult', kpiMult.toFixed(4));
        setIf('kprl-sales-accel', accel.toFixed(4));
        setIf('kprl-sales-gross', fmtCurrency(gross));
        setIf('kprl-sales-eligible', fmtCurrency(eligible));
        setIf('kprl-sales-final', fmtCurrency(final));
        setIf('kprl-sales-cap-status', capPass
            ? 'PASS (\u2264 ' + fmtCurrency(cap) + ')'
            : 'CAPPED to ' + fmtCurrency(cap));
        if (data.status === 'blocked') {
            setSimStatus('error', 'Sales blocked: ' + ((data.blocking_errors || []).join('; ') || 'missing inputs'));
        }
        window._lastSalesFinal = final;
    }

    // ---- WHAT-IF SCENARIOS (engine-side too) --------------------------
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

    async function scenarioNet(overrides) {
        // Deviation-only overrides: keep the engine's actual base + context.
        const data = await fetchSim(overrides);
        return data;
    }

    async function calculateScenarios() {
        const seq = ++scenarioSeq;
        const common = {dept_kpi_mult: getVal('kprl-sim-dept-kpi')};
        const scenarios = [
            ['kprl-worst-appraisal', getVal('kprl-worst-appraisal'), 'kprl-worst-kpi', getVal('kprl-worst-kpi'), 'kprl-worst-behav', getVal('kprl-worst-behav')],
            ['kprl-current-appraisal', getVal('kprl-current-appraisal'), 'kprl-current-kpi', getVal('kprl-current-kpi'), 'kprl-current-behav', getVal('kprl-current-behav')],
            ['kprl-best-appraisal', getVal('kprl-best-appraisal'), 'kprl-best-kpi', getVal('kprl-best-kpi'), 'kprl-best-behav', getVal('kprl-best-behav')],
        ];
        try {
            for (const s of scenarios) {
                const overrides = Object.assign({}, common, {
                    appraisal: s[1], dept_kpi_mult: s[3], behaviour: s[5]});
                const data = await fetchSim(overrides);
                if (seq !== scenarioSeq) return;
                const gov = data.governed || {};
                // result element name: \u2026-worst-result / -current-result / -best-result
                const resultId = s[0].replace('appraisal', 'result');
                setIf(resultId, fmtCurrency(gov.net_payable || 0));
            }
        } catch (e) {
            if (seq === scenarioSeq) setSimStatus('error', 'Scenario error: ' + e.message);
        }
    }

    function refreshAll() {
        calculate();
        calculateSales();
        calculateScenarios();
    }

    // Init after DOM ready
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
