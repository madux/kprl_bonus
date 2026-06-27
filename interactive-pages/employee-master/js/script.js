document.addEventListener("DOMContentLoaded", function() {
    var cards = document.querySelectorAll('.kprl-card');
    cards.forEach(function(card, index) {
        setTimeout(function() {
            card.classList.add('kprl-animate-in');
        }, index * 120);
    });

    var progressBars = document.querySelectorAll('.kprl-progress-bar-fill');
    setTimeout(function() {
        progressBars.forEach(function(bar) {
            var targetWidth = bar.getAttribute('data-progress');
            bar.style.width = targetWidth;
        });
    }, 400);

    var operationalInputs = document.querySelectorAll('.kprl-info-value-input:not([readonly])');
    operationalInputs.forEach(function(input) {
        input.addEventListener('focus', function(e) {
            e.target.parentElement.style.borderBottomColor = 'var(--kprl-primary-brand)';
        });
        input.addEventListener('blur', function(e) {
            e.target.parentElement.style.borderBottomColor = 'transparent';
        });
    });
});
