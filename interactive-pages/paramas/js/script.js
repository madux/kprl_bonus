document.addEventListener("DOMContentLoaded", function() {
    var saveBtn = document.getElementById("kprl-save-btn");
    if (saveBtn) {
        saveBtn.addEventListener("click", function() {
            saveBtn.innerText = "Saving...";
            setTimeout(function() {
                saveBtn.innerText = "Save";
                alert("Configuration snapshot saved locally. Remember to push to 'Request Approval' loop.");
            }, 600);
        });
    }

    var subTabs = document.querySelectorAll(".kprl-sub-tab");
    subTabs.forEach(function(tab) {
        tab.addEventListener("click", function() {
            subTabs.forEach(function(t) { t.classList.remove("kprl-sub-tab-active"); });
            this.classList.add("kprl-sub-tab-active");
        });
    });
});
