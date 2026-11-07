/** @odoo-module **/

import {
  Component,
  onMounted,
  onWillStart,
  onWillUnmount,
  useRef,
  useState,
} from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

const CURRENCY = new Intl.NumberFormat('en-NG', {
  style: 'currency',
  currency: 'NGN',
  maximumFractionDigits: 0,
});

export class KprlDashboard extends Component {
  setup() {
    this.rpc = useService('rpc');
    this.chartCanvasRef = useRef('trendChart');
    this.trendChart = null;

    this.state = useState({
      periods: [],
      currentPeriodId: null,
      currentPeriodName: '',
      engine: {},
      departments: [],
      territories: [],
      employees: [],
      trends: [],
      loading: true,
      computing: false,
      compStep: '',
      compPct: 0,
      trendMetric: 'effective_pool',
      trendType: 'bar',
      slaResultsDate: '',
      slaPayoutDate: '',
      slaStatus: 'ON TRACK',
      // Territory Performance
      // Self-Service
      selectedEmployeeId: null,
      employeePayout: null,
      selfServiceLoading: false,
    });

    onWillStart(async () => {
      await this._loadPeriods();
      await this._loadEmployees();
    });

    onMounted(() => {
      this._renderTrendChart();
    });
    onWillUnmount(() => {
      if (this.trendChart) {
        this.trendChart.destroy();
        this.trendChart = null;
      }
    });
  }

  async _loadPeriods() {
    try {
      // const periods = await this.rpc('/kprl/api/periods');
      const resp = await fetch('/kprl/api/periods');
      const data = await resp.json();
      this.state.periods = data;
      if (data.length > 0) {
        this.state.currentPeriodId = data[0].id;
        this.state.currentPeriodName = data[0].name;
        await this._loadDashboard();
        await this._loadTrends();
      }
    } catch (e) {
      console.error('Periods load error:', e);
    } finally {
      this.state.loading = false;
    }
  }

  // async _loadDashboard() {
  //   if (!this.state.currentPeriodId) return;
  //   try {
  //     const resp = await fetch(
  //       `/kprl/api/dashboard/${this.state.currentPeriodId}`,
  //     );
  //     const data = await resp.json();
  //     this.state.engine = data.engine || {};
  //     this.state.departments = data.departments || [];
  //   } catch (e) {
  //     console.error('Dashboard load error:', e);
  //   }
  // }
  async _loadDashboard() {
    if (!this.state.currentPeriodId) return;
    try {
      const resp = await fetch(
        `/kprl/api/dashboard/${this.state.currentPeriodId}`,
      );
      const data = await resp.json();
      this.state.engine = data.engine || {};

      if (data.period) {
        this.state.slaResultsDate = data.period.sla_results_date || '';
        this.state.slaPayoutDate = data.period.sla_payout_date || '';
        this.state.slaStatus = data.period.sla_status || 'ON TRACK';
      }

      const deptScores = data.departments || [];
      const payouts = data.payouts || [];

      const deptAgg = {};
      for (const p of payouts) {
        const deptId = p.department_id ? p.department_id[0] : null;
        if (!deptId) continue;
        if (!deptAgg[deptId]) {
          deptAgg[deptId] = { headcount: 0, netPayout: 0 };
        }
        deptAgg[deptId].headcount += 1;
        deptAgg[deptId].netPayout += p.net_immediate || 0;
      }

      this.state.departments = deptScores.map((d) => {
        const deptId = d.department_id ? d.department_id[0] : null;
        const agg = deptAgg[deptId] || { headcount: 0, netPayout: 0 };
        return {
          ...d,
          headcount: agg.headcount,
          net_payout: agg.netPayout,
        };
      });

      // Territory performance data
      const terrResp = await fetch(
        `/kprl/api/territories/${this.state.currentPeriodId}`,
      );
      const terrData = await terrResp.json();
      const payoutMap = {};
      for (const p of terrData.payouts || []) {
        const tid = p.territory_id[0];
        if (
          !payoutMap[tid] ||
          p.achievement_pct > payoutMap[tid].achievement_pct
        ) {
          payoutMap[tid] = p;
        }
      }
      this.state.territories = (terrData.territories || []).map((t) => ({
        ...t,
        latest_payout: payoutMap[t.id] || null,
        achievement_pct: payoutMap[t.id]
          ? payoutMap[t.id].achievement_pct
          : t.achieve_pct || 0,
        commission_payable: payoutMap[t.id]
          ? payoutMap[t.id].commission_payable
          : 0,
      }));
    } catch (e) {
      console.error('Dashboard load error:', e);
    }
  }
  async _loadEmployees() {
    try {
      const resp = await fetch('/kprl/api/employees');
      const data = await resp.json();
      this.state.employees = data || [];
    } catch (e) {
      console.error('Employees load error:', e);
    }
  }

  async selectEmployee(ev) {
    const empId = parseInt(ev.target.value, 10);
    this.state.selectedEmployeeId = empId;
    this.state.employeePayout = null;
    if (!empId || !this.state.currentPeriodId) return;
    this.state.selfServiceLoading = true;
    try {
      const resp = await fetch(
        `/kprl/api/employee/self-service/${empId}/${this.state.currentPeriodId}`,
      );
      const data = await resp.json();
      this.state.employeePayout = data;
    } catch (e) {
      console.error('Self-service load error:', e);
    } finally {
      this.state.selfServiceLoading = false;
    }
  }

  async _loadTrends() {
    try {
      const resp = await fetch('/kprl/api/trends');
      const data = await resp.json();
      this.state.trends = data;
      this._renderTrendChart();
      setTimeout(() => this._renderTrendChart(), 500);
    } catch (e) {
      console.error('Trends load error:', e);
    }
  }

  async selectPeriod(periodId, periodName) {
    if (this.state.currentPeriodId === periodId) return;
    this.state.currentPeriodId = periodId;
    this.state.currentPeriodName = periodName;
    await this._loadDashboard();
  }

  async runComputation() {
    if (this.state.computing || !this.state.currentPeriodId) return;
    this.state.computing = true;
    this.state.compPct = 0;
    const steps = [
      { pct: 15, msg: 'Validating gate conditions...' },
      { pct: 35, msg: 'Computing KPI scores...' },
      { pct: 55, msg: 'Calculating pool allocation...' },
      { pct: 75, msg: 'Applying proration & multipliers...' },
      { pct: 90, msg: 'Finalizing results...' },
      { pct: 100, msg: 'Done!' },
    ];
    let i = 0;
    const advance = () => {
      if (i >= steps.length) {
        this.state.computing = false;
        this._loadDashboard();
        this._loadTrends();
        return;
      }
      this.state.compPct = steps[i].pct;
      this.state.compStep = steps[i].msg;
      i++;
      setTimeout(advance, 500);
    };
    try {
      await fetch(`/kprl/api/compute/${this.state.currentPeriodId}`, {
        method: 'POST',
      });
    } catch (e) {
      console.error('Computation error:', e);
    }
    setTimeout(advance, 300);
  }

  _renderTrendChart() {
    const canvas = this.chartCanvasRef.el;
    if (!canvas || typeof Chart === 'undefined') return;
    if (this.trendChart) {
      this.trendChart.destroy();
      this.trendChart = null;
    }
    const metric = this.state.trendMetric;
    const type = this.state.trendType;
    const labels = this.state.trends.map((t) => t.period_name);
    const values = this.state.trends.map((t) => t[metric] || 0);
    const color = '#71496f';
    this.trendChart = new Chart(canvas.getContext('2d'), {
      type,
      data: {
        labels,
        datasets: [
          {
            label: this._metricLabel(metric),
            data: values,
            backgroundColor: type === 'bar' ? color + 'cc' : color + '22',
            borderColor: color,
            borderWidth: type === 'line' ? 3 : 1,
            fill: type === 'line',
            tension: 0.3,
            pointBackgroundColor: color,
            pointRadius: type === 'line' ? 5 : 0,
            pointHoverRadius: 7,
            borderRadius: type === 'bar' ? 4 : 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#212529',
            padding: 10,
            cornerRadius: 6,
            callbacks: { label: (ctx) => this._fmtTooltip(metric, ctx.raw) },
          },
        },
        scales: {
          y: {
            beginAtZero: false,
            ticks: {
              callback: (v) => this._fmtAxis(metric, v),
              font: { size: 11 },
              color: '#6c757d',
            },
            grid: { color: '#f1f3f5' },
          },
          x: {
            grid: { display: false },
            ticks: { font: { size: 11 }, color: '#495057' },
          },
        },
      },
    });
  }

  onTrendMetricChange(ev) {
    this.state.trendMetric = ev.target.value;
    this._renderTrendChart();
  }
  onTrendTypeChange(ev) {
    this.state.trendType = ev.target.value;
    this._renderTrendChart();
  }

  _metricLabel(key) {
    return (
      {
        effective_pool: 'Effective Pool',
        total_payout: 'Total Payout',
        company_kpi_score: 'Company KPI Score',
        ebitda_margin: 'EBITDA Margin',
        quarterly_revenue: 'Quarterly Revenue',
        headcount: 'Headcount',
      }[key] || key
    );
  }
  _fmtTooltip(key, val) {
    if (key === 'ebitda_margin' || key === 'company_kpi_score')
      return val.toFixed(1) + '%';
    if (key === 'headcount') return Math.round(val) + ' employees';
    return CURRENCY.format(val);
  }
  _fmtAxis(key, val) {
    if (key === 'ebitda_margin' || key === 'company_kpi_score')
      return val.toFixed(0) + '%';
    if (key === 'headcount') return Math.round(val);
    if (Math.abs(val) >= 1e6) return (val / 1e6).toFixed(1) + 'M';
    if (Math.abs(val) >= 1e3) return (val / 1e3).toFixed(0) + 'K';
    return val;
  }
  fmtCurrency(val) {
    return val != null ? CURRENCY.format(val) : '--';
  }
  fmtPct(val) {
    return val != null ? (val * 100).toFixed(1) + '%' : '--';
  }
  fmtScore(val) {
    return val != null ? val.toFixed(2) : '--';
  }
  fmtMult(val) {
    return val ? val.toFixed(2) + 'x' : '1.00x';
  }
  gateLabel(s) {
    return (
      { full: 'PASS', partial: 'PARTIAL', closed: 'CLOSED' }[s] || '--'
    ).toUpperCase();
  }

  fmtSLADate(val) {
    if (!val) return '--';
    const d = new Date(val + 'T00:00:00');
    return d.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  }
  gmpLabel(s) {
    return (s || 'N/A').toUpperCase();
  }
  // deptStatus(d) {
  //   return d.gmp_status === 'clean' ? 'ON TARGET' : 'WATCH';
  // }

  deptStatus(d) {
    const score = d.kpi_score || 0;
    if (score >= 1.0) return 'EXCEED';
    if (score >= 0.9) return 'ON TARGET';
    return 'WATCH';
  }

  // deptStatusCls(d) {
  //   return d.gmp_status === 'clean' ? 'kprl-tag-target' : 'kprl-tag-watch';
  // }

  deptStatusCls(d) {
    const score = d.kpi_score || 0;
    if (score >= 1.0) return 'kprl-tag-exceed';
    if (score >= 0.9) return 'kprl-tag-target';
    return 'kprl-tag-watch';
  }

  achievementBarClass(pct) {
    if (pct >= 100) return 'kprl-achieve-green';
    if (pct >= 75) return 'kprl-achieve-yellow';
    if (pct >= 50) return 'kprl-achieve-orange';
    return 'kprl-achieve-red';
  }

  achievementBarStyle(pct) {
    return 'width:' + Math.min(pct, 100) + '%';
  }

  sourceBadgeClass(source) {
    return source === 'RSM' ? 'kprl-badge-rsm' : 'kprl-badge-team';
  }
}

KprlDashboard.template = 'kprl_bonus.KprlDashboard';
registry.category('actions').add('kprl_dashboard', KprlDashboard);

