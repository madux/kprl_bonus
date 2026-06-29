/**
 * KPRL Bonus API Helper
 * Uses Odoo's built-in rpc via inject CSRF token from server.
 * Load this script AFTER the CSRF token window var is set.
 */
(function () {
    'use strict';

    var BASE = '/kprl/api';

    function getCsrf() {
        // 1) Odoo global rpc
        if (typeof odoo !== 'undefined' && odoo.csrf_token) {
            return odoo.csrf_token;
        }
        // 2) Meta tag injected by template
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) {
            return meta.getAttribute('content');
        }
        // 3) Fallback window var
        return window.KPRL_CSRF || '';
    }

    async function request(method, path, body) {
        var opts = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrf(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
        };
        if (body) {
            opts.body = JSON.stringify(body);
        }
        var res = await fetch(BASE + path, opts);
        if (!res.ok) {
            var err = await res.json().catch(function () { return { error: res.statusText }; });
            throw new Error(err.error || err.message || res.statusText);
        }
        return res.json();
    }

    window.KPRL_API = {
        get: function (path) { return request('GET', path); },
        put: function (path, data) { return request('PUT', path, data); },
        post: function (path, data) { return request('POST', path, data); },
    };

    window.KPRL_FMT = {
        currency: function (v) {
            if (v == null) return '$0';
            var n = Number(v);
            return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        },
        pct: function (v) {
            if (v == null) return '0%';
            return (Number(v) * 100).toFixed(1).replace(/\.0$/, '') + '%';
        },
        pctRaw: function (v) {
            if (v == null) return '0%';
            return Number(v).toFixed(2).replace(/\.?0+$/, '') + '%';
        },
        score: function (v) {
            if (v == null) return '0.00';
            return Number(v).toFixed(2);
        },
        badge: function (status) {
            var map = {
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
