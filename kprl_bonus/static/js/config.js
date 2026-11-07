/**
 * KPRL Control Panel — CEO/Superadmin config page
 */
(function () {
    'use strict';

    const API = window.KPRL_API;
    const FMT = window.KPRL_FMT;

    let paramData = {};
    let currentPeriodId = null;

    async function init() {
        const periods = await API.get('/periods');
        const active = periods.find(p => p.state === 'active') || periods[0];
        if (!active) return;
        currentPeriodId = active.id;
        const periodLabel = document.getElementById('kprl-param-period-name');
        if (periodLabel) periodLabel.textContent = active.name + ' Config';
        const periodLabel2 = document.getElementById('kprl-param-period-label');
        if (periodLabel2) periodLabel2.textContent = '\u2014 ' + active.name;

        // Load existing params
        try {
            paramData = await API.get('/config/' + currentPeriodId);
        } catch (e) {
            paramData = {};
        }
        renderPoolRatesForm();
        renderKpiWeightsForm();
        renderApprovalTimeline();
        setupTabs();
        setupSave();
        setupRequestApproval();
    }

    function renderPoolRatesForm() {
        const form = document.getElementById('kprl-pool-rates-form');
        if (!form) return;

        const fields = [
            { key: 'min_pool_rate', label: 'Pool Rate Min (floor) (EBITDA < 18%)', pct: true },
            { key: 'ebitda_scaling_start', label: 'EBITDA threshold Scaling Begins', pct: true },
            { key: 'ebitda_max_rate_threshold', label: 'EBITDA threshold Max Rate Reached', pct: true },
            { key: 'partial_gate_floor', label: 'Profitability Gate (Partial unlock) (EBITDA 18%)', pct: true },
            { key: 'full_gate_floor', label: 'Profitability Gate (full unlock) (EBITDA 22%)', pct: true },
            { key: 'max_pool_rate', label: 'Pool Rate Max (ceiling) (EBITDA >= 22%)', pct: true },
            { key: 'opm_subpool_share', label: 'OPM Sub-Pool Share', pct: true },
            { key: 'sen_mgt_share', label: 'Senior Mgmt Share of Sub-Pool', pct: true },
            { key: 'ops_sup_share', label: 'Ops/Sup Share of Sub-Pool', pct: true },
            { key: 'aip_annual_rate', label: 'AIP Annual Rate', pct: true },
            { key: 'aip_deferral_rate', label: 'AIP Deferral Rate', pct: true },
        ];

        form.innerHTML = fields.map(f => {
            const val = paramData[f.key] || 0;
            const displayVal = f.pct ? (val * 100).toFixed(2) + '%' : val;
            return `<div class="kprl-form-group">
                <label class="kprl-input-label">${f.label}</label>
                <div class="kprl-input-row">
                    <input type="text" class="kprl-interactive-input" data-key="${f.key}" value="${displayVal}">
                    <span class="kprl-approver-badge kprl-badge-blue-pill">${paramData[f.key + '_approver'] || 'Board'}</span>
                </div>
            </div>`;
        }).join('');
    }

    function renderKpiWeightsForm() {
        const form = document.getElementById('kprl-kpi-weights-form');
        if (!form) return;

        const fields = [
            { key: 'revenue_weight', label: 'Revenue Achievement Weight', max: 25 },
            { key: 'ebitda_weight', label: 'EBITDA Achievement Weight', max: 25 },
            { key: 'gmp_weight', label: 'GMP / Quality Score Weight', max: 25 },
            { key: 'extended_kpi_weight', label: 'Extended KPI Weight', max: 25 },
        ];

        const total = fields.reduce((s, f) => s + (paramData[f.key] || 0), 0);

        form.innerHTML = fields.map(f => {
            const val = paramData[f.key] || 0;
            return `<div class="kprl-form-group">
                <label class="kprl-input-label">${f.label}</label>
                <div class="kprl-input-row">
                    <input type="text" class="kprl-interactive-input kprl-kpi-input" data-key="${f.key}" value="${val.toFixed(1)}%">
                    <span class="kprl-approver-badge kprl-badge-green-pill">MAX ${f.max}%</span>
                </div>
            </div>`;
        }).join('') + `<div class="kprl-form-group">
            <label class="kprl-input-label" style="font-weight:700;">Total</label>
            <div class="kprl-input-row">
                <span id="kprl-kpi-total" style="font-weight:700;font-size:16px;color:${Math.abs(total - 100) < 0.01 ? '#28a745' : '#dc3545'}">${total.toFixed(1)}%</span>
                <span class="kprl-approver-badge ${Math.abs(total - 100) < 0.01 ? 'kprl-badge-green-pill' : 'kprl-badge-orange-pill'}">${Math.abs(total - 100) < 0.01 ? 'VALID' : 'MUST SUM TO 100%'}</span>
            </div>
        </div>`;

        // live total update
        form.querySelectorAll('.kprl-kpi-input').forEach(inp => {
            inp.addEventListener('input', updateKpiTotal);
        });
    }

    function updateKpiTotal() {
        const inputs = document.querySelectorAll('.kprl-kpi-input');
        let total = 0;
        inputs.forEach(inp => {
            total += parseFloat(inp.value) || 0;
        });
        const el = document.getElementById('kprl-kpi-total');
        if (el) {
            el.textContent = total.toFixed(1) + '%';
            el.style.color = Math.abs(total - 100) < 0.01 ? '#28a745' : '#dc3545';
        }
    }

    function renderApprovalTimeline() {
        const el = document.getElementById('kprl-approval-timeline');
        if (!el) return;

        const state = paramData.state || 'draft';
        const createdDate = paramData.create_date || '';
        const approverName = paramData.approver_id ? paramData.approver_id[1] : null;
        const approvalDate = paramData.approval_date || '';
        const periodName = paramData.period_id ? paramData.period_id[1] : '';
        const version = paramData.version || 1;

        function fmtDate(dtStr) {
            if (!dtStr) return '';
            const d = new Date(dtStr);
            if (isNaN(d)) return dtStr;
            const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            return d.getDate() + '-' + months[d.getMonth()] + '-' + d.getFullYear()
                + ' ' + String(d.getHours()).padStart(2,'0') + ':'
                + String(d.getMinutes()).padStart(2,'0');
        }

        const items = [];

        items.push({
            title: 'Parameter Set Created (v' + version + ')',
            meta: 'System' + (createdDate ? ' \u2022 ' + fmtDate(createdDate) : ''),
            badge: 'DONE',
            cls: 'kprl-badge-gray',
        });

        if (state === 'draft') {
            items.push({
                title: 'CEO / Superadmin Review',
                meta: 'Awaiting submission',
                badge: 'DRAFT',
                cls: 'kprl-badge-gray',
            });
        } else if (state === 'pending_approval') {
            items.push({
                title: 'CEO / Superadmin Review',
                meta: 'Awaiting approval',
                badge: 'PENDING',
                cls: 'kprl-badge-orange',
            });
        } else if (state === 'approved') {
            items.push({
                title: 'CEO / Superadmin Review',
                meta: (approverName || 'CEO') + (approvalDate ? ' \u2022 ' + fmtDate(approvalDate) : ''),
                badge: 'APPROVED',
                cls: 'kprl-badge-green',
            });
            items.push({
                title: 'Effective From',
                meta: periodName,
                badge: 'ACTIVE',
                cls: 'kprl-badge-green-filled',
                noLine: true,
            });
        } else if (state === 'rejected') {
            items.push({
                title: 'CEO / Superadmin Review',
                meta: (approverName || 'CEO') + (approvalDate ? ' \u2022 ' + fmtDate(approvalDate) : ''),
                badge: 'REJECTED',
                cls: 'kprl-badge-red',
            });
        }

        el.innerHTML = '<div class="kprl-timeline">' + items.map((item, i) => {
            const noLine = item.noLine || i === items.length - 1;
            return '<div class="kprl-timeline-item' + (noLine ? ' kprl-no-line' : '') + '">'
                + '<div class="kprl-timeline-content">'
                + '<div class="kprl-node-title">' + item.title + '</div>'
                + '<div class="kprl-node-meta">' + item.meta + '</div>'
                + '</div>'
                + '<span class="kprl-badge ' + item.cls + '">' + item.badge + '</span>'
                + '</div>';
        }).join('') + '</div>';
    }

    function setupRequestApproval() {
        const btn = document.getElementById('kprl-request-approval-btn');
        if (!btn) return;
        btn.addEventListener('click', async () => {
            if (!currentPeriodId) return;
            const state = paramData.state || 'draft';
            if (state !== 'draft' && state !== 'rejected') {
                alert('Parameters can only be submitted from Draft or Rejected status.');
                return;
            }
            if (!confirm('Submit these parameters for CEO approval?')) return;
            btn.textContent = 'Submitting...';
            btn.disabled = true;
            try {
                await API.put('/config/' + currentPeriodId + '/submit', {});
                btn.textContent = 'Submitted!';
                setTimeout(() => { btn.textContent = 'Request Approval'; btn.disabled = false; }, 2000);
                paramData.state = 'pending_approval';
                renderApprovalTimeline();
            } catch (e) {
                btn.textContent = 'Error';
                setTimeout(() => { btn.textContent = 'Request Approval'; btn.disabled = false; }, 2000);
                alert('Submit failed: ' + (e.message || 'Unknown error'));
            }
        });
    }

    function setupTabs() {
        document.querySelectorAll('.kprl-sub-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.kprl-sub-tab').forEach(t => t.classList.remove('kprl-sub-tab-active'));
                tab.classList.add('kprl-sub-tab-active');
                // Tab content switching would go here
            });
        });
    }

    function getMinMaxBounds(key) {
        const bounds = {
            min_pool_rate: { min: 0.0, max: 0.01, label: 'Pool Rate Min (floor)' },
            ebitda_scaling_start: { min: 0.10, max: 0.15, label: 'EBITDA threshold Scaling Start' },
            ebitda_max_rate_threshold: { min: 0.25, max: 0.70, label: 'EBITDA threshold Max Rate' },
            partial_gate_floor: { min: 0.001, max: 0.015, label: 'Profitability Gate (Partial unlock)' },
            full_gate_floor: { min: 0.015, max: 0.03, label: 'Profitability Gate (full unlock)' },
            max_pool_rate: { min: 0.015, max: 0.03, label: 'Pool Rate Max (ceiling)' },
            opm_subpool_share: { min: 0.50, max: 0.80, label: 'OPM Sub-Pool Share' },
            sen_mgt_share: { min: 0.60, max: 0.80, label: 'Senior Mgmt Share' },
            ops_sup_share: { min: 0.20, max: 0.40, label: 'Ops/Sup Share' },
            aip_annual_rate: { min: 0.001, max: 0.01, label: 'AIP Annual Rate' },
            aip_deferral_rate: { min: 0.20, max: 0.40, label: 'AIP Deferral Rate' },
            revenue_weight: { min: 0.0, max: 25.0, label: 'Revenue Weight' },
            ebitda_weight: { min: 0.0, max: 25.0, label: 'EBITDA Weight' },
            gmp_weight: { min: 0.0, max: 25.0, label: 'GMP Weight' },
            extended_kpi_weight: { min: 0.0, max: 25.0, label: 'Extended KPI Weight' },
        };
        return bounds[key] || null;
    }

    function setupSave() {
        const btn = document.getElementById('kprl-save-btn');
        const msg = document.getElementById('kprl-validation-msg');
        const msgText = document.getElementById('kprl-validation-text');
        if (!btn) return;
        btn.addEventListener('click', async () => {
            const data = {};
            const errors = [];

            // Collect pool rate fields
            document.querySelectorAll('#kprl-pool-rates-form .kprl-interactive-input').forEach(inp => {
                const key = inp.dataset.key;
                let val = parseFloat(inp.value) || 0;
                const rawPct = parseFloat(inp.value) || 0;
                if (key.includes('rate') || key.includes('share')) {
                    val = val / 100;
                }
                data[key] = val;

                // Validate min/max
                const bound = getMinMaxBounds(key);
                if (bound) {
                    const rawVal = key.includes('rate') || key.includes('share') ? val : rawPct;
                    if (rawVal < bound.min || rawVal > bound.max) {
                        errors.push(bound.label + ' must be between ' + bound.min + ' and ' + bound.max + '. Got: ' + rawVal);
                    }
                }
            });

            // Collect KPI weight fields
            document.querySelectorAll('#kprl-kpi-weights-form .kprl-interactive-input').forEach(inp => {
                const key = inp.dataset.key;
                let val = parseFloat(inp.value) || 0;
                data[key] = val;

                const bound = getMinMaxBounds(key);
                if (bound) {
                    if (val < bound.min || val > bound.max) {
                        errors.push(bound.label + ' must be between ' + bound.min + ' and ' + bound.max + '. Got: ' + val);
                    }
                }
            });

            // Validate KPI sum = 100%
            const kpiTotal = ['revenue_weight', 'ebitda_weight', 'gmp_weight', 'extended_kpi_weight']
                .reduce((s, k) => s + (data[k] || 0), 0);
            if (Math.abs(kpiTotal - 100) >= 0.01) {
                errors.push('KPI weights must sum to 100%. Current total: ' + kpiTotal.toFixed(1) + '%');
            }

            // Cross-field consistency: A < B (min pool rate < max pool rate)
            if (data.min_pool_rate != null && data.max_pool_rate != null) {
                if (data.min_pool_rate >= data.max_pool_rate) {
                    errors.push('Pool Rate Min (floor) (' + (data.min_pool_rate * 100).toFixed(2) + '%) must be below Pool Rate Max (ceiling) (' + (data.max_pool_rate * 100).toFixed(2) + '%)');
                }
            }

            // Cross-field consistency: C <= E (EBITDA scaling start <= full gate floor)
            if (data.ebitda_scaling_start != null && data.full_gate_floor != null) {
                if (data.ebitda_scaling_start > data.full_gate_floor) {
                    errors.push('EBITDA threshold Scaling Start (' + (data.ebitda_scaling_start * 100).toFixed(2) + '%) must not exceed Profitability Gate (full unlock) (' + (data.full_gate_floor * 100).toFixed(2) + '%)');
                }
            }

            // Cross-field consistency: D > E (EBITDA max rate threshold > full gate floor)
            if (data.ebitda_max_rate_threshold != null && data.full_gate_floor != null) {
                if (data.ebitda_max_rate_threshold <= data.full_gate_floor) {
                    errors.push('EBITDA threshold Max Rate (' + (data.ebitda_max_rate_threshold * 100).toFixed(2) + '%) must exceed Profitability Gate (full unlock) (' + (data.full_gate_floor * 100).toFixed(2) + '%)');
                }
            }

            // Cross-field consistency: F < E (partial gate floor < full gate floor)
            if (data.partial_gate_floor != null && data.full_gate_floor != null) {
                if (data.partial_gate_floor >= data.full_gate_floor) {
                    errors.push('Profitability Gate (Partial unlock) (' + (data.partial_gate_floor * 100).toFixed(2) + '%) must be below Profitability Gate (full unlock) (' + (data.full_gate_floor * 100).toFixed(2) + '%)');
                }
            }

            // Cross-field consistency: Pool shares sum = 100%
            const poolTotal = (data.opm_subpool_share || 0) + (data.sen_mgt_share || 0) + (data.ops_sup_share || 0);
            if (Math.abs(poolTotal - 1.0) >= 0.01) {
                errors.push('Pool shares must sum to 100%. Current total: ' + (poolTotal * 100).toFixed(1) + '%');
            }

            if (errors.length > 0) {
                if (msg) {
                    msg.style.display = 'flex';
                    msg.className = msg.className.replace(/kprl-msg-\w+/g, '') + ' kprl-msg-error';
                    msgText.textContent = errors.join('; ');
                }
                return;
            }

            btn.textContent = 'Saving...';
            btn.disabled = true;

            try {
                await API.put('/config/' + currentPeriodId, data);
                btn.textContent = 'Saved!';
                setTimeout(() => { btn.textContent = 'Save'; btn.disabled = false; }, 1500);
                if (msg) {
                    msg.style.display = 'flex';
                    msg.className = msg.className.replace(/kprl-msg-\w+/g, '') + ' kprl-msg-success';
                    msgText.textContent = 'Configuration saved successfully';
                }
            } catch (e) {
                btn.textContent = 'Error';
                setTimeout(() => { btn.textContent = 'Save'; btn.disabled = false; }, 2000);
                if (msg) {
                    msg.style.display = 'flex';
                    msg.className = msg.className.replace(/kprl-msg-\w+/g, '') + ' kprl-msg-error';
                    msgText.textContent = 'Save failed: ' + (e.message || 'Unknown error');
                } else {
                    alert('Save failed: ' + e.message);
                }
            }
        });
    }

    init();
})();
