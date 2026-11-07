/**
 * KPRL Login — client-side UX enhancements.
 * Auth is handled by Odoo's /web/login endpoint.
 */
(function () {
    'use strict';

    var form = document.getElementById('kprl-login-form');
    var submitBtn = document.getElementById('kprl-btn-submit');

    if (form && submitBtn) {
        form.addEventListener('submit', function () {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Authenticating...';
        });
    }
})();
