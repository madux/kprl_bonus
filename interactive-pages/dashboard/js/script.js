(function() {
    var deptData = {
        'Q1-2026': [
            { dept: 'Operations', score: '0.92', mult: '1.02', hc: '11', payout: '721,300', status: 'Target' },
            { dept: 'Finance & Admin', score: '0.89', mult: '1.00', hc: '8', payout: '589,400', status: 'Target' },
            { dept: 'Sales & Marketing', score: '0.85', mult: '0.98', hc: '10', payout: '512,600', status: 'Watch' },
            { dept: 'Human Resources', score: '0.94', mult: '1.06', hc: '5', payout: '388,200', status: 'Exceed' },
            { dept: 'Engineering', score: '0.88', mult: '1.00', hc: '7', payout: '467,800', status: 'Target' },
            { dept: 'Legal & Compliance', score: '0.82', mult: '0.96', hc: '4', payout: '271,500', status: 'Watch' },
            { dept: 'Corporate Services', score: '0.87', mult: '0.99', hc: '11', payout: '584,200', status: 'Target' }
        ],
        'Q2-2026': [
            { dept: 'Operations', score: '0.95', mult: '1.05', hc: '12', payout: '892,450', status: 'Target' },
            { dept: 'Finance & Admin', score: '0.92', mult: '1.02', hc: '8', payout: '654,200', status: 'Target' },
            { dept: 'Sales & Marketing', score: '0.88', mult: '1.00', hc: '10', payout: '589,100', status: 'Watch' },
            { dept: 'Human Resources', score: '0.96', mult: '1.08', hc: '5', payout: '423,800', status: 'Exceed' },
            { dept: 'Engineering', score: '0.91', mult: '1.03', hc: '7', payout: '512,600', status: 'Target' },
            { dept: 'Legal & Compliance', score: '0.85', mult: '0.98', hc: '4', payout: '298,150', status: 'Watch' },
            { dept: 'Corporate Services', score: '0.90', mult: '1.01', hc: '11', payout: '649,800', status: 'Target' }
        ],
        'Q3-2026': [
            { dept: 'Operations', score: '0.93', mult: '1.03', hc: '12', payout: '845,200', status: 'Target' },
            { dept: 'Finance & Admin', score: '0.91', mult: '1.01', hc: '8', payout: '621,500', status: 'Target' },
            { dept: 'Sales & Marketing', score: '0.87', mult: '0.99', hc: '11', payout: '574,300', status: 'Watch' },
            { dept: 'Human Resources', score: '0.95', mult: '1.07', hc: '5', payout: '409,600', status: 'Exceed' },
            { dept: 'Engineering', score: '0.90', mult: '1.02', hc: '7', payout: '498,700', status: 'Target' },
            { dept: 'Legal & Compliance', score: '0.84', mult: '0.97', hc: '4', payout: '285,900', status: 'Watch' },
            { dept: 'Corporate Services', score: '0.89', mult: '1.00', hc: '11', payout: '632,100', status: 'Target' }
        ],
        'Q4-2026': [
            { dept: 'Operations', score: '0.94', mult: '1.04', hc: '12', payout: '868,900', status: 'Target' },
            { dept: 'Finance & Admin', score: '0.93', mult: '1.03', hc: '9', payout: '678,300', status: 'Exceed' },
            { dept: 'Sales & Marketing', score: '0.89', mult: '1.01', hc: '11', payout: '612,800', status: 'Target' },
            { dept: 'Human Resources', score: '0.97', mult: '1.09', hc: '5', payout: '438,200', status: 'Exceed' },
            { dept: 'Engineering', score: '0.92', mult: '1.04', hc: '8', payout: '534,100', status: 'Target' },
            { dept: 'Legal & Compliance', score: '0.86', mult: '0.99', hc: '4', payout: '312,400', status: 'Watch' },
            { dept: 'Corporate Services', score: '0.91', mult: '1.02', hc: '11', payout: '664,500', status: 'Target' }
        ]
    };

    var kpiData = {
        'Q1-2026': { pool: '$3,112,400', payout: '$3,535,200', prev: '2.1%', hc: '56 / 56', rev: '102%', ebitda: '28.5%', prorate: '0.95x', aip: '$420,000', kpiScore: '0.88', poolFunded: '$3,112,400' },
        'Q2-2026': { pool: '$3,792,820', payout: '$4,300,300', prev: '1.8%', hc: '57 / 57', rev: '108%', ebitda: '30.0%', prorate: '1.00x', aip: '$480,000', kpiScore: '0.92', poolFunded: '$3,792,820' },
        'Q3-2026': { pool: '$3,521,600', payout: '$3,867,400', prev: '1.9%', hc: '58 / 58', rev: '105%', ebitda: '29.2%', prorate: '0.98x', aip: '$450,000', kpiScore: '0.90', poolFunded: '$3,521,600' },
        'Q4-2026': { pool: '$3,987,100', payout: '$4,512,800', prev: '1.7%', hc: '60 / 60', rev: '112%', ebitda: '31.5%', prorate: '1.00x', aip: '$510,000', kpiScore: '0.94', poolFunded: '$3,987,100' }
    };

    var currentPeriod = 'Q2-2026';
    var tabBtns = document.querySelectorAll('.kprl-tab-btn');
    var tbody = document.getElementById('kprl-table-body');
    var currentView = document.getElementById('kprl-current-view');
    var kpiScoreEl = document.getElementById('kprl-kpi-score');
    var poolFundedEl = document.getElementById('kprl-pool-funded');

    function getStatusClass(status) {
        if (status === 'Target') return 'kprl-tag-target';
        if (status === 'Exceed') return 'kprl-tag-exceed';
        return 'kprl-tag-watch';
    }

    function renderTable(period) {
        var rows = deptData[period];
        var html = '';
        if (!rows || rows.length === 0) {
            html = '<tr><td colspan="6" style="text-align:center;color:#adb5bd;padding:30px 20px;font-style:italic;">No data available for this period</td></tr>';
        } else {
            for (var i = 0; i < rows.length; i++) {
                var r = rows[i];
                html += '<tr>' +
                    '<td>' + r.dept + '</td>' +
                    '<td>' + r.score + '</td>' +
                    '<td>' + r.mult + '</td>' +
                    '<td>' + r.hc + '</td>' +
                    '<td>$' + r.payout + '</td>' +
                    '<td><span class="kprl-status-tag ' + getStatusClass(r.status) + '">' + r.status + '</span></td>' +
                    '</tr>';
            }
        }
        tbody.innerHTML = html;
    }

    function updateKpiCards(period) {
        var k = kpiData[period];
        if (!k) return;
        document.getElementById('kprl-kpi-pool').textContent = k.pool;
        document.getElementById('kprl-kpi-payout').textContent = k.payout;
        document.getElementById('kprl-kpi-prev').textContent = k.prev;
        document.getElementById('kprl-kpi-hc').textContent = k.hc;
        document.getElementById('kprl-kpi-rev').textContent = k.rev;
        document.getElementById('kprl-kpi-ebitda').textContent = k.ebitda;
        document.getElementById('kprl-kpi-prorate').textContent = k.prorate;
        document.getElementById('kprl-kpi-aip').textContent = k.aip;
        kpiScoreEl.textContent = k.kpiScore;
        poolFundedEl.textContent = k.poolFunded;
    }

    function switchPeriod(period) {
        if (period === currentPeriod) return;
        currentPeriod = period;

        for (var i = 0; i < tabBtns.length; i++) {
            tabBtns[i].classList.remove('kprl-tab-active');
        }
        var activeBtn = document.querySelector('.kprl-tab-btn[data-period="' + period + '"]');
        if (activeBtn) activeBtn.classList.add('kprl-tab-active');

        currentView.textContent = period + ' Dashboard';
        renderTable(period);
        updateKpiCards(period);
    }

    for (var i = 0; i < tabBtns.length; i++) {
        tabBtns[i].addEventListener('click', function() {
            switchPeriod(this.getAttribute('data-period'));
        });
    }

    renderTable('Q2-2026');

    var runBtn = document.getElementById('btn-run-computation');
    var overlay = document.getElementById('kprl-computation-overlay');
    var progressFill = document.getElementById('kprl-progress-fill');
    var compText = document.getElementById('kprl-comp-text');

    runBtn.addEventListener('click', function() {
        runBtn.disabled = true;
        runBtn.textContent = 'Computing...';
        overlay.style.display = 'flex';
        progressFill.style.width = '0%';
        compText.textContent = 'Calculating bonus pool allocation...';

        var steps = [
            { pct: 20, text: 'Validating gate conditions...' },
            { pct: 40, text: 'Computing KPI scores...' },
            { pct: 60, text: 'Applying multipliers...' },
            { pct: 85, text: 'Calculating departmental payouts...' },
            { pct: 100, text: 'Finalizing results...' }
        ];
        var stepIndex = 0;

        function advanceStep() {
            if (stepIndex >= steps.length) {
                setTimeout(function() {
                    overlay.style.display = 'none';
                    runBtn.disabled = false;
                    runBtn.textContent = 'Run Computation';
                }, 400);
                return;
            }
            var step = steps[stepIndex];
            progressFill.style.width = step.pct + '%';
            compText.textContent = step.text;
            stepIndex++;
            setTimeout(advanceStep, 700);
        }

        setTimeout(advanceStep, 500);
    });

    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            overlay.style.display = 'none';
            runBtn.disabled = false;
            runBtn.textContent = 'Run Computation';
        }
    });
})();
