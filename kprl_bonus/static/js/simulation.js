/**
 * KPRL Bonus Simulation - v30 aligned (Ops Sec6 + Sales Sec7)
 * Uses Control Panel params via window.KPRL_SIM_PARAMS (from page_simulation)
 */
(function () {
    'use strict';
    // PARAMS may be object (from t-raw JSON) or string
    let PARAMS = window.KPRL_SIM_PARAMS || {};
    if (typeof PARAMS === 'string') {
        try { PARAMS = JSON.parse(PARAMS); } catch(e) { PARAMS = {}; }
    }
    let currentQuarter = 'Q2';

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
        calculate();
        calculateSales();
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
                calculate();
                calculateSales();
            });
        });
    }

    function setupSimInputs() {
        document.querySelectorAll('.kprl-sim-input').forEach(inp => {
            inp.addEventListener('input', () => { calculate(); calculateSales(); calculateScenarios(); });
        });
        const calcBtn = document.getElementById('kprl-sim-calculate');
        if (calcBtn) calcBtn.addEventListener('click', () => { calculate(); calculateSales(); });
        const resetBtn = document.getElementById('kprl-sim-reset');
        if (resetBtn) resetBtn.addEventListener('click', () => {
            prefillFromParams();
            calculate(); calculateSales();
        });
    }

    function setupSalesInputs() {
        ['kprl-sales-target','kprl-sales-own','kprl-sales-retr','kprl-sales-pk','kprl-sales-call','kprl-sales-cov','kprl-sales-new'].forEach(id=>{
            const el=document.getElementById(id);
            if(el) el.addEventListener('input', calculateSales);
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
        if (v == null || isNaN(v)) return '₦0';
        return '₦' + Math.round(v).toLocaleString('en-US');
    }

    function appraisalToMult(scorePercent) {
        const score = scorePercent / 100.0;
        if (score < 0.65) return 0.0;
        if (score < 0.75) return 0.60 + (score - 0.65) * 1.5; // corrected slope to reach 0.75 at 0.75
        if (score < 0.90) return 0.75 + (score - 0.75) * 1.0;
        if (score < 1.10) return 0.90 + (score - 0.90) * 1.0; // 0.90->0.90, 1.00->1.00, 1.10->1.10
        return 1.10;
    }

    function behaviouralToMult(score25) {
        return 0.80 + (score25 / 25.0) * 0.20;
    }

    function calculate() {
        const base = getVal('kprl-sim-base');
        const appraisalScore = getVal('kprl-sim-appraisal');
        const behaviouralScore = getVal('kprl-sim-behavioural');
        const deptKpi = getVal('kprl-sim-dept-kpi');
        const exceptionManual = getVal('kprl-sim-exception');
        const malus = getVal('kprl-sim-malus');

        const appraisalMult = appraisalToMult(appraisalScore);
        const behaviouralMult = behaviouralToMult(behaviouralScore);
        const proration = PARAMS.proration_factor || 1.0;
        const tenure = PARAMS.tenure_mult || 1.0;
        const gmp = PARAMS.gmp_factor || 1.0;
        const deferralRate = PARAMS.deferral_rate || 0;

        // Sec6 cascade: Adjusted -> Gross -> Payable -> Final -> Net
        const adjusted = base * deptKpi * appraisalMult * behaviouralMult;
        let exc = 0;
        if (appraisalMult >= 1.10) exc = adjusted * 0.10;
        if (exceptionManual > exc) exc = exceptionManual;
        const gross = Math.max(0, adjusted + exc - malus);
        const payable = gross * proration;
        const payableTenured = payable * tenure;
        const minFloor = PARAMS.min_floor || 0;
        let final = Math.max(payableTenured, minFloor);
        const gCap = PARAMS.g_individual_cap || 2000000;
        const stretchCap = PARAMS.i4_stretch_cap || 5000000;
        // Use stretch cap if over target? For ops, use gCap only. For sales, sales calc handles stretch.
        if (final > gCap) final = gCap;
        const deferred = final * (deferralRate / 100.0);
        const net = final - deferred;

        const floorPass = final >= minFloor - 0.01;
        const capPass = final <= gCap + 0.01;

        const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
        set('kprl-sim-proration', '×' + proration.toFixed(2));
        set('kprl-sim-tenure', '×' + tenure.toFixed(2));
        set('kprl-sim-gmp', '×' + gmp.toFixed(2));
        set('kprl-sim-deferral', deferralRate + '%');
        set('kprl-out-base', fmtCurrency(base));
        set('kprl-out-appraisal-mult', '×' + appraisalMult.toFixed(2));
        set('kprl-out-behavioural-mult', '×' + behaviouralMult.toFixed(2));
        set('kprl-out-dept-mult', '×' + deptKpi.toFixed(2));
        set('kprl-out-proration', '×' + proration.toFixed(2));
        set('kprl-out-tenure', '×' + tenure.toFixed(2));
        set('kprl-out-gmp', '×' + gmp.toFixed(2));
        set('kprl-out-exception', fmtCurrency(exc));
        set('kprl-out-malus', fmtCurrency(malus));
        set('kprl-out-gross', fmtCurrency(gross));
        set('kprl-out-deferred', fmtCurrency(deferred));
        set('kprl-out-net', fmtCurrency(net));
        // Also show payable/final for debugging if elements exist
        const statusEl = document.getElementById('kprl-sim-status');
        const statusText = document.getElementById('kprl-sim-status-text');
        if (statusEl && statusText) {
            if (!floorPass) {
                statusEl.className = 'kprl-sim-status-box kprl-status-warn';
                statusText.textContent = 'Floor check: FAIL (final ₦' + Math.round(final).toLocaleString() + ' < ₦' + minFloor.toLocaleString() + ')';
            } else if (!capPass) {
                statusEl.className = 'kprl-sim-status-box kprl-status-warn';
                statusText.textContent = 'Cap check: FAIL (final ₦' + Math.round(final).toLocaleString() + ' > ₦' + gCap.toLocaleString() + ')';
            } else {
                statusEl.className = 'kprl-sim-status-box kprl-status-pass';
                if (minFloor>0) statusText.textContent = 'Floor check: PASS (final ₦' + Math.round(final).toLocaleString() + ' ≥ ₦' + minFloor.toLocaleString() + ')';
                else statusText.textContent = 'Floor check: PASS (no floor for this grade)';
            }
        }
        // Update net display for what-if to use
        window._lastOpsNet = net;
    }

    function calculateSales() {
        if (!PARAMS.is_sales) return;
        const ownTarget = getVal('kprl-sales-target');
        const ownSales = getVal('kprl-sales-own');
        const ownRetr = getVal('kprl-sales-retr');
        const pk = getVal('kprl-sales-pk');
        const call = getVal('kprl-sales-call');
        const cov = getVal('kprl-sales-cov');
        const nw = getVal('kprl-sales-new');

        const natSales = PARAMS.nat_sales || 0;
        const natRetr = PARAMS.nat_retr || 0;
        const salesRate = PARAMS.sales_comm_rate || 0.003;
        const retrRate = PARAMS.retr_comm_rate || 0.007;

        // Determine role floors/mins from Control Panel H/B/K
        const role = (PARAMS.sales_role || 'asm').toLowerCase();
        let salesFloor, salesMin, retrFloor, retrMin, poolShare;
        const ps = PARAMS.pool_shares || {gm:0.10,nsm:0.08,headtech:0.05,rsm:0.22,asm:0.55,rsm_asm:0.4235};
        if (role === 'gm') { salesFloor = PARAMS.h1_top_sales_floor || 0.50; salesMin = PARAMS.b34_min || 0.65; retrFloor = PARAMS.h4_top_retr_floor || 0.65; retrMin = 0.75; poolShare = ps.gm; }
        else if (role === 'nsm') { salesFloor = PARAMS.h1_top_sales_floor || 0.50; salesMin = PARAMS.b34_min || 0.65; retrFloor = PARAMS.h4_top_retr_floor || 0.65; retrMin = 0.75; poolShare = ps.nsm; }
        else if (role === 'headtech') { salesFloor = 0.50; salesMin = 0.65; retrFloor = 0.65; retrMin = 0.75; poolShare = ps.headtech; }
        else if (role === 'rsm') { salesFloor = PARAMS.h2_rsm_sales_floor || 0.65; salesMin = PARAMS.b36_min || 0.75; retrFloor = PARAMS.h5_rsm_retr_floor || 0.70; retrMin = 0.75; poolShare = ps.rsm; }
        else if (role === 'rsm_asm') { salesFloor = PARAMS.k3_floor || 0.65; salesMin = PARAMS.k1_min || 0.75; retrFloor = PARAMS.k4_floor || 0.70; retrMin = PARAMS.k2_min || 0.75; poolShare = ps.rsm_asm; }
        else { salesFloor = PARAMS.h3_asm_sales_floor || 0.65; salesMin = PARAMS.b38_min || 0.70; retrFloor = PARAMS.h6_asm_retr_floor || 0.70; retrMin = PARAMS.b39_min || 0.70; poolShare = ps.asm; }

        const attain = ownTarget>0 ? ownSales/ownTarget : 0;
        const retr = ownSales>0 ? ownRetr/ownSales : 0;

        function ramp(val,floor,min){ if(val<floor) return 0; if(val>=min) return 1; if(min===floor) return val>=min?1:0; return (val-floor)/(min-floor); }
        const salesGate = ramp(attain, salesFloor, salesMin);
        let retrGate = ramp(retr, retrFloor, retrMin);
        if (salesGate===0) retrGate = 0; // master kills

        const commSales = natSales * poolShare * salesRate;
        const commRetr = natRetr * poolShare * retrRate;
        const gross = commSales + commRetr;
        const eligible = (commSales * salesGate) + (commRetr * salesGate * retrGate);

        const w = PARAMS.kpi_weights || {pk:0.40,call:0.10,cov:0.30,new:0.20};
        const weighted = pk*w.pk + call*w.call + cov*w.cov + nw*w.new;
        const kpiFloor = PARAMS.kpi_floor || 0.80;
        const kpiRange = PARAMS.kpi_range || 0.40;
        let kpiMult = kpiFloor + weighted * kpiRange;
        kpiMult = Math.max(kpiFloor, Math.min(kpiFloor+kpiRange, kpiMult));

        const tenure = PARAMS.tenure_mult || 1.0;
        const kick = PARAMS.accel_kick || 1.00;
        const ceiling = PARAMS.accel_ceiling || 1.50;
        const boost = PARAMS.accel_boost || 0.50;
        let accel = 1.0;
        if (attain >= ceiling) accel = 1.0 + boost;
        else if (attain >= kick) accel = 1.0 + ((attain - kick)/(ceiling - kick))*boost;

        let final = eligible * kpiMult * tenure * accel;
        const gCap = PARAMS.g_individual_cap || 2000000;
        const stretch = PARAMS.i4_stretch_cap || 5000000;
        const cap = attain > kick ? stretch : gCap;
        const capPass = final <= cap;
        if (final > cap) final = cap;

        const set=(id,val)=>{ const el=document.getElementById(id); if(el) el.textContent=val; };
        set('kprl-sales-attain', (attain*100).toFixed(2)+'%');
        set('kprl-sales-retr-rate', (retr*100).toFixed(2)+'%');
        set('kprl-sales-gate', salesGate.toFixed(4));
        set('kprl-sales-retr-gate', retrGate.toFixed(4));
        set('kprl-sales-kpi-mult', kpiMult.toFixed(4));
        set('kprl-sales-accel', accel.toFixed(4));
        set('kprl-sales-gross', fmtCurrency(gross));
        set('kprl-sales-eligible', fmtCurrency(eligible));
        set('kprl-sales-final', fmtCurrency(final));
        set('kprl-sales-cap-status', capPass ? 'PASS (≤ '+fmtCurrency(cap)+')' : 'CAPPED to '+fmtCurrency(cap));
        window._lastSalesFinal = final;
    }

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
        const appraisalMult = (function(s){ const sc=s/100; if(sc<0.65) return 0; if(sc<0.75) return 0.60+(sc-0.65)*1.5; if(sc<0.90) return 0.75+(sc-0.75); if(sc<1.10) return 0.90+(sc-0.90); return 1.10; })(appraisal);
        const behaviouralMult = 0.80 + (behav / 25) * 0.20;
        const proration = PARAMS.proration_factor || 1.0;
        const tenure = PARAMS.tenure_mult || 1.0;
        const gmp = PARAMS.gmp_factor || 1.0;
        const deferralRate = PARAMS.deferral_rate || 0;
        const deptKpi = kpi/100.0;
        const adjusted = base * deptKpi * appraisalMult * behaviouralMult;
        const exc = appraisalMult>=1.10 ? adjusted*0.10 : 0;
        const gross = Math.max(0, adjusted + exc);
        const payable = gross * proration;
        const final = Math.max(payable * tenure, PARAMS.min_floor || 0);
        const capped = Math.min(final, PARAMS.g_individual_cap || 2000000);
        return capped * (1 - deferralRate / 100);
    }

    function calculateScenarios() {
        const worst = scenarioNet(getVal('kprl-worst-appraisal'), getVal('kprl-worst-kpi'), getVal('kprl-worst-behav'));
        const current = scenarioNet(getVal('kprl-current-appraisal'), getVal('kprl-current-kpi'), getVal('kprl-current-behav'));
        const best = scenarioNet(getVal('kprl-best-appraisal'), getVal('kprl-best-kpi'), getVal('kprl-best-behav'));
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = fmtCurrency(val); };
        set('kprl-worst-result', worst);
        set('kprl-current-result', current);
        set('kprl-best-result', best);
    }

    // Init after DOM ready
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
