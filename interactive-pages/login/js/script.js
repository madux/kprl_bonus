(function() {
    var form = document.getElementById('kprl-login-form');
    var loginCard = document.getElementById('kprl-login-card');
    var successCard = document.getElementById('kprl-success-card');
    var submitBtn = document.getElementById('kprl-btn-submit');
    var resetBtn = document.getElementById('kprl-reset-btn');
    var emailInput = document.getElementById('kprl-email');
    var passwordInput = document.getElementById('kprl-password');

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        var email = emailInput.value.trim();
        var password = passwordInput.value.trim();

        if (!email) { emailInput.focus(); return; }
        if (!password) { passwordInput.focus(); return; }
        if (email.indexOf('@') === -1) { emailInput.focus(); return; }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Authenticating...';

        setTimeout(function() {
            loginCard.style.display = 'none';
            successCard.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.textContent = 'Sign In';
        }, 1200);
    });

    resetBtn.addEventListener('click', function() {
        successCard.style.display = 'none';
        loginCard.style.display = 'block';
        emailInput.value = 'finance@kprl.com.ng';
        passwordInput.value = '••••••••';
        emailInput.focus();
    });
})();
