/**
 * KPRL Bonus API Helper
 * Provides fetch-based access to the Odoo JSON endpoints.
 */
(function () {
    'use strict';

    const BASE = '/kprl/api';

    async function request(method, path, body) {
        const opts = {
            method: method,
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(BASE + path, opts);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: res.statusText }));
            throw new Error(err.error || res.statusText);
        }
        return res.json();
    }

    window.KPRL_API = {
        get: (path) => request('GET', path),
        put: (path, data) => request('PUT', path, data),
        post: (path, data) => request('POST', path, data),
    };

    // Helpers for formatting
    window.KPRL_FMT = {
        currency: (v) => {
            if (v == null) return '$0';
            const n = Number(v);
            return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        },
        pct: (v) => {
            if (v == null) return '0%';
            return (Number(v) * 100).toFixed(1).replace(/\.0$/, '') + '%';
        },
        pctRaw: (v) => {
            if (v == null) return '0%';
            return Number(v).toFixed(2).replace(/\.?0+$/, '') + '%';
        },
        score: (v) => {
            if (v == null) return '0.00';
            return Number(v).toFixed(2);
        },
        badge: (status) => {
            const map = {
                'exceed': 'kprl-tag-exceed',
                'target': 'kprl-tag-target',
                'watch': 'kprl-tag-watch',
                'pass': 'kprl-tag-target',
                'clean': 'kprl-tag-target',
            };
            return map[String(status).toLowerCase()] || 'kprl-tag-target';
        },
    };
})();
