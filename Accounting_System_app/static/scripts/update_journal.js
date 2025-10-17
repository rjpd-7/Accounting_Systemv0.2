document.addEventListener("DOMContentLoaded", function () {
    const editJournalEntryBody = document.getElementById('edit-journal-entry-body');
    const editAllAccountsSelect = document.getElementById('edit-all-accounts-select');
    const editTotalDebit = document.getElementById('edit_total_debit');
    const editTotalCredit = document.getElementById('edit_total_credit');
    const editAddRowBtn = document.getElementById('edit-add-journal-row');
    const editClearBtn = document.getElementById('edit-clear-amounts-btn');

    // --- Utility: Update type + restrict debit/credit ---
    function updateEditAccountTypeAndRestrict(selectElem) {
        const row = selectElem.closest('tr');
        const typeInput = row.querySelector('input[name="edit_account_type"]');
        const debitInput = row.querySelector('input[name="edit_debit"]');
        const creditInput = row.querySelector('input[name="edit_credit"]');
        const selectedOption = selectElem.options[selectElem.selectedIndex];
        const type = selectedOption ? selectedOption.getAttribute('data-type') : "";

        typeInput.value = type;

        if (type === "Assets" || type === "Expenses") {
            debitInput.removeAttribute('readonly');
            creditInput.value = '';
            creditInput.setAttribute('readonly', true);
        } else if (type === "Liabilities" || type === "Equity" || type === "Revenue") {
            creditInput.removeAttribute('readonly');
            debitInput.value = '';
            debitInput.setAttribute('readonly', true);
        } else {
            debitInput.removeAttribute('readonly');
            creditInput.removeAttribute('readonly');
        }

        calculateEditTotals();
    }

    // --- Utility: Calculate totals ---
    function calculateEditTotals() {
        let totalDebit = 0, totalCredit = 0;

        editJournalEntryBody.querySelectorAll('input[name="edit_debit"]').forEach(input => {
            totalDebit += parseFloat(input.value) || 0;
        });
        editJournalEntryBody.querySelectorAll('input[name="edit_credit"]').forEach(input => {
            totalCredit += parseFloat(input.value) || 0;
        });

        editTotalDebit.value = totalDebit.toFixed(2);
        editTotalCredit.value = totalCredit.toFixed(2);

        if (totalDebit === totalCredit && totalDebit !== 0) {
            editTotalDebit.style.backgroundColor = "#d4edda";
            editTotalCredit.style.backgroundColor = "#d4edda";
            editTotalDebit.style.color = "#155724";
            editTotalCredit.style.color = "#155724";
        } else {
            editTotalDebit.style.backgroundColor = "#f8d7da";
            editTotalCredit.style.backgroundColor = "#f8d7da";
            editTotalDebit.style.color = "#721c24";
            editTotalCredit.style.color = "#721c24";
        }
    }

    // --- Clear all debit/credit ---
    function clearEditAmounts() {
        editJournalEntryBody.querySelectorAll('input[name="edit_debit"], input[name="edit_credit"]').forEach(input => {
            input.value = '';
        });
        calculateEditTotals();
    }

    // --- Attach input listeners ---
    function attachEditInputListeners(row) {
        row.querySelectorAll('input[name="edit_debit"], input[name="edit_credit"]').forEach(input => {
            input.addEventListener('input', calculateEditTotals);
        });
    }

    // --- Initialize first row (restricted) ---
    const firstRow = editJournalEntryBody.querySelector('tr');
    const firstSelect = firstRow.querySelector('select[name="edit_account_name"]');
    const firstActionCell = firstRow.querySelector('td:last-child');

    // Remove remove button (not allowed)
    firstActionCell.innerHTML = `<small class="text-muted">Main Debit</small>`;

    // Restrict to debit-only accounts (Assets, Expenses)
    firstSelect.querySelectorAll('option').forEach(opt => {
        const type = opt.getAttribute('data-type_edit') || opt.getAttribute('data-type');
        if (!(type === "Assets" || type === "Expenses")) {
            opt.remove();
        }
    });

    // Apply change listener
    firstSelect.addEventListener('change', function () {
        updateEditAccountTypeAndRestrict(this);
    });
    updateEditAccountTypeAndRestrict(firstSelect);
    attachEditInputListeners(firstRow);

    // --- Add row ---
    editAddRowBtn.addEventListener('click', function () {
        const newRow = document.createElement('tr');
        const selectHtml = `<select name="edit_account_name" required>${editAllAccountsSelect.innerHTML}</select>`;

        newRow.innerHTML = `
            <td>${selectHtml}</td>
            <td><input type="text" name="edit_account_type" readonly></td>
            <td><input type="number" name="edit_debit" step="0.01" min="0"></td>
            <td><input type="number" name="edit_credit" step="0.01" min="0"></td>
            <td><button type="button" class="btn btn-danger btn-sm remove-row">Remove</button></td>
        `;

        const newSelect = newRow.querySelector('select[name="edit_account_name"]');
        newSelect.addEventListener('change', function () {
            updateEditAccountTypeAndRestrict(this);
        });
        updateEditAccountTypeAndRestrict(newSelect);
        attachEditInputListeners(newRow);

        editJournalEntryBody.appendChild(newRow);
    });

    // --- Remove row (except first) ---
    editJournalEntryBody.addEventListener('click', function (e) {
        if (e.target.classList.contains('remove-row')) {
            const row = e.target.closest('tr');
            if (row !== firstRow) {
                row.remove();
                calculateEditTotals();
            }
        }
    });

    // --- Clear button ---
    editClearBtn.addEventListener('click', clearEditAmounts);
});
