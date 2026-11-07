/** @odoo-module **/

import { Component, onWillStart, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

const CURRENCY = new Intl.NumberFormat('en-NG', {
  style: 'currency',
  currency: 'NGN',
  maximumFractionDigits: 0,
});

export class KprlGovernance extends Component {
  setup() {
    this.notification = useService('notification');

    this.state = useState({
      loading: true,
      activeTab: 'governance_log',
      events: [],
      selectedEvent: null,
      auditTrail: [],
      employees: [],
      periods: [],
      summary: {
        open_events: 0,
        pending_fd_approval: 0,
        malus_applied_ytd: 0,
        clawback_active: 0,
        audit_entries: 0,
      },
      filterSeverity: 'all',
      filterStatus: 'all',
      showModal: false,
      newEvent: {
        employee_id: '',
        period_id: '',
        trigger_type: 'policy_breach',
        trigger_description: '',
        severity: 'minor',
        malus_pct: 0,
        malus_amount: 0,
        investigation_lead: '',
        evidence_ref: '',
        description: '',
      },
    });

    onWillStart(async () => {
      await this._loadData();
    });
  }

  async _loadData() {
    try {
      const [summaryResp, eventsResp, auditResp, empResp, periodResp] =
        await Promise.all([
          fetch('/kprl/api/governance/summary'),
          fetch('/kprl/api/governance/events'),
          fetch('/kprl/api/audit-trail?limit=15'),
          fetch('/kprl/api/employees'),
          fetch('/kprl/api/periods'),
        ]);
      this.state.summary = await summaryResp.json();
      this.state.events = await eventsResp.json();
      this.state.auditTrail = await auditResp.json();
      this.state.employees = await empResp.json();
      this.state.periods = await periodResp.json();
      if (this.state.events.length > 0) {
        this.state.selectedEvent = this.state.events[0];
      }
    } catch (e) {
      console.error('Governance load error:', e);
    } finally {
      this.state.loading = false;
    }
  }

  switchTab(tab) {
    this.state.activeTab = tab;
  }

  selectEvent(ev) {
    this.state.selectedEvent = ev;
  }

  openNewEvent() {
    this.state.newEvent = {
      employee_id: '',
      period_id: '',
      trigger_type: 'policy_breach',
      trigger_description: '',
      severity: 'minor',
      malus_pct: 0,
      malus_amount: 0,
      investigation_lead: '',
      evidence_ref: '',
      description: '',
    };
    this.state.showModal = true;
  }

  closeModal() {
    this.state.showModal = false;
  }

  async saveNewEvent() {
    const ev = this.state.newEvent;
    if (!ev.description) {
      this.notification.add('Description is required', {
        type: 'danger',
      });
      return;
    }
    const payload = {
      trigger_type: ev.trigger_type,
      trigger_description: ev.trigger_description,
      severity: ev.severity,
      malus_pct: parseFloat(ev.malus_pct) || 0,
      malus_amount: parseFloat(ev.malus_amount) || 0,
      investigation_lead: ev.investigation_lead,
      evidence_ref: ev.evidence_ref,
      description: ev.description,
      status: 'open',
      stage: 'open',
    };
    if (ev.employee_id) {
      payload.employee_id = parseInt(ev.employee_id);
    }
    if (ev.period_id) {
      payload.period_id = parseInt(ev.period_id);
    }
    try {
      const resp = await fetch('/kprl/api/governance', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': this._getCsrf(),
        },
        body: JSON.stringify(payload),
      });
      const result = await resp.json();
      if (result.error) {
        this.notification.add(result.error, { type: 'danger' });
        return;
      }
      this.state.showModal = false;
      this.notification.add('Governance event created successfully', {
        type: 'success',
      });
      await this._loadData();
    } catch (e) {
      console.error('Save error:', e);
      this.notification.add('Failed to save event', { type: 'danger' });
    }
  }

  _getCsrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  get filteredEvents() {
    let events = this.state.events;
    if (this.state.activeTab === 'malus_events') {
      events = events.filter((e) =>
        [
          'policy_breach',
          'gmp_deviation',
          'late_reporting',
          'kpi_data_dispute',
          'malus',
        ].includes(e.trigger_type),
      );
    } else if (this.state.activeTab === 'clawback_register') {
      events = events.filter((e) => e.trigger_type === 'clawback');
    }
    if (this.state.filterSeverity !== 'all') {
      events = events.filter((e) => e.severity === this.state.filterSeverity);
    }
    if (this.state.filterStatus !== 'all') {
      events = events.filter((e) => e.status === this.state.filterStatus);
    }
    return events;
  }

  onFilterSeverity(ev) {
    this.state.filterSeverity = ev.target.value;
  }

  onFilterStatus(ev) {
    this.state.filterStatus = ev.target.value;
  }

  fmtCurrency(val) {
    return val != null ? CURRENCY.format(val) : '₦0:00';
  }

  fmtDate(val) {
    if (!val) return '--';
    const d = new Date(val);
    return d.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  }

  fmtDateTime(val) {
    if (!val) return '--';
    const d = new Date(val);
    return (
      d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      }) +
      ' ' +
      d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
    );
  }

  severityClass(sev) {
    const map = {
      low: 'kprl-sev-low',
      minor: 'kprl-sev-minor',
      medium: 'kprl-sev-medium',
      major: 'kprl-sev-major',
      high: 'kprl-sev-high',
      critical: 'kprl-sev-critical',
    };
    return map[sev] || 'kprl-sev-minor';
  }

  statusClass(st) {
    const map = {
      open: 'kprl-st-open',
      pending: 'kprl-st-pending',
      applied: 'kprl-st-applied',
      waived: 'kprl-st-waived',
      closed: 'kprl-st-closed',
    };
    return map[st] || 'kprl-st-open';
  }

  stageLabel(st) {
    const map = {
      open: 'Open',
      under_review: 'Under Review',
      investigation: 'Under Investigation',
      closed: 'Closed',
    };
    return map[st] || st;
  }

  triggerLabel(t) {
    const map = {
      policy_breach: 'Policy Breach',
      gmp_deviation: 'GMP Deviation',
      late_reporting: 'Late Reporting',
      kpi_data_dispute: 'KPI Data Dispute',
      malus: 'Malus',
      clawback: 'Clawback',
    };
    return map[t] || t;
  }

  auditTimeAgo(ts) {
    if (!ts) return '';
    const now = new Date();
    const d = new Date(ts);
    const diff = Math.floor((now - d) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + ' min ago';
    if (diff < 86400) return Math.floor(diff / 3600) + ' hours ago';
    return Math.floor(diff / 86400) + ' days ago';
  }

  get hasPendingWarning() {
    return this.state.summary.pending_fd_approval > 0;
  }
}

KprlGovernance.template = 'kprl_bonus.KprlGovernance';
registry.category('actions').add('kprl_governance', KprlGovernance);
