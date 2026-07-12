/**
 * KPRL OWL Login Component
 * Two-step authentication: Email/Password -> TOTP (if enabled)
 * Integrates with Odoo's /web/session/authenticate and /web/login/totp
 */
(function () {
  'use strict';

  /* ─── Helpers ─── */
  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    if (typeof odoo !== 'undefined' && odoo.csrf_token) return odoo.csrf_token;
    return '';
  }

  function getDbName() {
    var meta = document.querySelector('meta[name="kprl-db"]');
    if (meta) return meta.getAttribute('content');
    return '';
  }

  function getRedirectUrl() {
    var meta = document.querySelector('meta[name="kprl-redirect"]');
    if (meta) return meta.getAttribute('content');
    return '/kprl/dashboard';
  }

  /* ─── OWL ─── */
  var { Component, mount, useState, xml } = owl;

  /* ─── Template (inline, no QWeb server processing) ─── */
  var LOGIN_TEMPLATE = xml`
        <div class="kprl-login-root">
            <t t-if="state.loading">
                <div class="kprl-login-loading">
                    <div class="kprl-login-spinner"/>
                    <span class="kprl-login-loading-text" t-esc="state.loadingMsg"/>
                </div>
            </t>
            <div class="kprl-login-container">
                <div class="kprl-login-banner">
                    <div class="kprl-login-banner-content">
                        <h1 class="kprl-login-brand-title">KPRL</h1>
                        <p class="kprl-login-brand-subtitle">Bonus Management System</p>
                        <span class="kprl-login-version-tag">v1.0 — Odoo Integrated</span>
                    </div>
                    <div class="kprl-login-art">
                        <div class="kprl-login-circle-1"/>
                        <div class="kprl-login-circle-2"/>
                        <div class="kprl-login-circle-3"/>
                        <div class="kprl-login-boxes">
                            <div class="kprl-login-entity-box">
                                <span class="kprl-login-entity-text">Employees</span>
                            </div>
                            <div class="kprl-login-entity-box">
                                <span class="kprl-login-entity-text">Departments</span>
                            </div>
                            <div class="kprl-login-entity-box">
                                <span class="kprl-login-entity-text">Territories</span>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="kprl-login-form-section">
                    <div class="kprl-login-card">
                        <div class="kprl-login-logo"/>
                        <div class="kprl-login-steps">
                            <div class="kprl-login-step-dot" t-att-class="state.step === 'login' ? 'active' : ''"/>
                            <span class="kprl-login-step-label">Credentials</span>
                            <span class="kprl-login-step-label">·</span>
                            <div class="kprl-login-step-dot" t-att-class="state.step === 'totp' ? 'active' : ''"/>
                            <span class="kprl-login-step-label">Verification</span>
                        </div>
                        <t t-if="state.step === 'login'">
                            <div class="kprl-login-fade-enter">
                                <h2 class="kprl-login-card-title">KPRL BMS</h2>
                                <p class="kprl-login-card-subtitle">Sign in to your account</p>
                                <t t-if="state.error">
                                    <div class="kprl-login-error" t-esc="state.error"/>
                                </t>
                                <form t-on-submit="submitLogin" autocomplete="off">
                                    <div class="kprl-login-field">
                                        <label class="kprl-login-label">Email Address</label>
                                        <input type="email" class="kprl-login-input" placeholder="email@kprl.com" t-att-value="state.email" t-on-input="onEmailInput" autofocus="autofocus" required="required"/>
                                    </div>
                                    <div class="kprl-login-field">
                                        <label class="kprl-login-label">Password</label>
                                        <input type="password" class="kprl-login-input" placeholder="Enter your password" t-att-value="state.password" t-on-input="onPasswordInput" required="required"/>
                                    </div>
                                    <div class="kprl-login-mfa-alert">
                                        <i class="fa fa-shield kprl-login-mfa-icon"/>
                                        <span class="kprl-login-mfa-text">Multi-factor authentication (TOTP) available. <a href="/web/totp/enable" style="color:#1a73e8;font-weight:600;text-decoration:underline;">Enroll</a> in your profile after signing in.</span>
                                    </div>
                                    <button type="submit" class="kprl-login-btn" t-att-disabled="state.loading">Sign In</button>
                                </form>
                                <a href="/web/reset_password" class="kprl-login-forgot">Forgot password?</a>
                                <div>
                                    <p class="kprl-login-footer-text">Access restricted to authorised KPRL personnel</p>
                                    <p class="kprl-login-copyright">Powered by Odoo 17 ERP · KPRL Nigeria Ltd</p>
                                </div>
                            </div>
                        </t>
                        <t t-if="state.step === 'totp'">
                            <div class="kprl-login-fade-enter">
                                <h2 class="kprl-login-card-title">Verify Your Identity</h2>
                                <p class="kprl-login-card-subtitle">Enter the 6-digit code from your authenticator app</p>
                                <button class="kprl-login-back" t-on-click="backToLogin">
                                    <i class="fa fa-arrow-left"/> Back to sign in
                                </button>
                                <t t-if="state.error">
                                    <div class="kprl-login-error" t-esc="state.error"/>
                                </t>
                                <form t-on-submit="submitTotp" autocomplete="off">
                                    <div class="kprl-login-field">
                                        <label class="kprl-login-label">Authentication Code</label>
                                        <input type="text" class="kprl-login-input kprl-login-totp-input" placeholder="000000" maxlength="6" inputmode="numeric" pattern="[0-9]{6}" autocomplete="one-time-code" t-att-value="state.totpCode" t-on-input="onTotpInput" autofocus="autofocus" required="required"/>
                                    </div>
                                    <div class="kprl-login-remember">
                                        <input type="checkbox" id="kprl-remember-device" t-att-checked="state.remember" t-on-change="onRememberToggle"/>
                                        <label for="kprl-remember-device">Don't ask again on this device</label>
                                    </div>
                                    <button type="submit" class="kprl-login-btn" t-att-disabled="state.loading">
                                        <i class="fa fa-shield"/> Verify
                                    </button>
                                </form>
                                <div>
                                    <p class="kprl-login-footer-text"><i class="fa fa-info-circle"/> Lost your device? Contact IT support to reset your TOTP.</p>
                                </div>
                            </div>
                        </t>
                    </div>
                </div>
            </div>
        </div>`;

  /* ─── Component ─── */
  class KprlLogin extends Component {
    setup() {
      this.state = useState({
        step: 'login',
        loading: false,
        loadingMsg: '',
        error: null,
        email: '',
        password: '',
        totpCode: '',
        remember: false,
      });
      this.csrfToken = getCsrfToken();
      this.dbName = getDbName();
      this.redirectUrl = getRedirectUrl();
    }

    onEmailInput(ev) {
      this.state.email = ev.target.value;
    }

    onPasswordInput(ev) {
      this.state.password = ev.target.value;
    }

    async submitLogin(ev) {
      ev.preventDefault();
      if (this.state.loading) return;
      this.state.error = null;
      this.state.loading = true;
      this.state.loadingMsg = 'Authenticating...';

      try {
        var resp = await fetch('/web/session/authenticate', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': this.csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({
            db: this.dbName,
            login: this.state.email,
            password: this.state.password,
          }),
        });

        var data = await resp.json();
        var result = data.result || data;

        if (result.uid) {
          this.state.loadingMsg = 'Redirecting...';
          window.location.href = this.redirectUrl;
          return;
        }

        if (result.uid === 0 || result.uid === null) {
          this.state.step = 'totp';
          this.state.loading = false;
          this.state.error = null;
          this.state.totpCode = '';
          return;
        }

        this.state.error = this._extractError(data, result);
        this.state.loading = false;
      } catch (err) {
        console.error('Login error:', err);
        this.state.loadingMsg = 'Redirecting...';
        var form = document.createElement('form');
        form.method = 'POST';
        form.action =
          '/web/login?redirect=' + encodeURIComponent(this.redirectUrl);
        var fields = {
          login: this.state.email,
          password: this.state.password,
          csrf_token: this.csrfToken,
          redirect: this.redirectUrl,
        };
        for (var key in fields) {
          var input = document.createElement('input');
          input.type = 'hidden';
          input.name = key;
          input.value = fields[key];
          form.appendChild(input);
        }
        document.body.appendChild(form);
        form.submit();
      }
    }

    onTotpInput(ev) {
      this.state.totpCode = ev.target.value.replace(/\s/g, '');
    }

    onRememberToggle() {
      this.state.remember = !this.state.remember;
    }

    async submitTotp(ev) {
      ev.preventDefault();
      if (this.state.loading) return;
      this.state.error = null;
      this.state.loading = true;
      this.state.loadingMsg = 'Verifying code...';

      try {
        var formData = new URLSearchParams();
        formData.append('totp_token', this.state.totpCode);
        formData.append('csrf_token', this.csrfToken);
        formData.append('redirect', this.redirectUrl);
        if (this.state.remember) {
          formData.append('remember', '1');
        }

        var resp = await fetch('/web/login/totp', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: formData.toString(),
          redirect: 'follow',
        });

        var finalUrl = resp.url || '';

        if (finalUrl.includes('login') || finalUrl.includes('totp')) {
          this.state.error = 'Invalid authentication code. Please try again.';
          this.state.loading = false;
          this.state.totpCode = '';
          return;
        }

        this.state.loadingMsg = 'Verified! Redirecting...';
        window.location.href = finalUrl || this.redirectUrl;
      } catch (err) {
        console.error('TOTP error:', err);
        this.state.error = 'Verification failed. Please try again.';
        this.state.loading = false;
        this.state.totpCode = '';
      }
    }

    backToLogin() {
      this.state.step = 'login';
      this.state.error = null;
      this.state.totpCode = '';
      this.state.password = '';
    }

    _extractError(data, result) {
      var err = data.error || result.error;
      if (err && typeof err === 'object') {
        return (
          (err.data && err.data.message) ||
          err.message ||
          'Invalid email or password.'
        );
      }
      if (typeof err === 'string' && err) {
        return err;
      }
      return 'Invalid email or password. Please try again.';
    }
  }

  KprlLogin.template = LOGIN_TEMPLATE;

  function initLogin() {
    var root = document.getElementById('kprl-login-root');
    if (!root) return;
    mount(KprlLogin, root);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLogin);
  } else {
    initLogin();
  }
})();
