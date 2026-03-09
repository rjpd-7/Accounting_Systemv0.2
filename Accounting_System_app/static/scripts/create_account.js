document.addEventListener("DOMContentLoaded", function () {
    const modal = document.getElementById("staticBackdrop");
    const form = document.getElementById("account_form");
    const accountCodeInput = document.getElementById("account_code");
    const accountTypeSelect = document.getElementById("account_type");

    if (!modal || !form || !accountCodeInput || !accountTypeSelect) {
        return;
    }

    async function fetchNextAccountCode(accountType) {
        if (!accountType) {
            accountCodeInput.value = "";
            return;
        }

        accountCodeInput.value = "Generating...";
        accountCodeInput.readOnly = true;

        try {
            const response = await fetch(`/api/next_account_code/?type=${encodeURIComponent(accountType)}`);
            const data = await response.json();

            if (data.success) {
                accountCodeInput.value = data.code;
            } else {
                accountCodeInput.value = "";
                console.error("Failed to fetch next account code:", data.error || "Unknown error");
            }
        } catch (error) {
            accountCodeInput.value = "";
            console.error("Error fetching account code:", error);
        }
    }

    modal.addEventListener("shown.bs.modal", function () {
        fetchNextAccountCode(accountTypeSelect.value);
    });

    accountTypeSelect.addEventListener("change", function () {
        fetchNextAccountCode(this.value);
    });

    form.addEventListener("submit", async function (event) {
        const accountNameInput = document.getElementById("account_name");
        const submitBtn = form.querySelector('input[type="submit"], button[type="submit"]');

        if (!accountNameInput.value.trim() || !accountTypeSelect.value) {
            event.preventDefault();
            alert("Please complete all required fields.");
            return;
        }

        // Refresh preview code right before submit for better UX.
        // Backend still finalizes the true code atomically.
        event.preventDefault();
        if (submitBtn) {
            submitBtn.disabled = true;
        }

        try {
            await fetchNextAccountCode(accountTypeSelect.value);
            form.submit();
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
            }
        }
    });

    modal.addEventListener("hidden.bs.modal", function () {
        form.reset();
        accountCodeInput.value = "";
    });
});