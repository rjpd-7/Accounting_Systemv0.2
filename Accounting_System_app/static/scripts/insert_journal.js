document.addEventListener("DOMContentLoaded", function () {
    if(!localStorage.getItem('journal_code_counter')){
        localStorage.setItem('journal_code_counter', 0);
    }

    // Journal Code Generation
    function generateJournalCode(){
        let last_number = parseInt(localStorage.getItem('journal_code_counter'), 10);
        let incremental = last_number.toString().padStart(10, '0');
        return 'JE-' + incremental;
    }

    // Generate journal code once insert journal modal opens
    // If you use a modal, adjust the selector accordingly
    // document.getElementById('staticBackdrop').addEventListener('shown.bs.modal', function () {
    //     document.getElementById("journal_code").value = generateJournalCode();
    // });
    // Or just set on page load:
    document.getElementById("journal_code").value = generateJournalCode();

    // Journal Table functions.
    var addRowBtn = document.getElementById('add-journal-row');
    var journalEntryBody = document.getElementById('journal-entry-body');
    var allAccountsSelect = document.getElementById('all-accounts-select');
    var totalDebitField = document.getElementById('total_debit');
    var totalCreditField = document.getElementById('total_credit');

    function updateAccountTypeAndRestrict(selectElem) {
        var row = selectElem.closest('tr');
        var typeInput = row.querySelector('input[name="account_type"]');
        var debitInput = row.querySelector('input[name="debit"]');
        var creditInput = row.querySelector('input[name="credit"]');
        var selectedOption = selectElem.options[selectElem.selectedIndex];
        var type = selectedOption ? selectedOption.getAttribute('data-type') : "";

        // Show type
        typeInput.value = type;

        // Restrict debit/credit based on type
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

        calculateTotals();
    }

    // Calculate Totals
    function calculateTotals() {
        let totalDebit = 0;
        let totalCredit = 0;

        journalEntryBody.querySelectorAll('input[name="debit"]').forEach(input => {
            totalDebit += parseFloat(input.value) || 0;
        });
        journalEntryBody.querySelectorAll('input[name="credit"]').forEach(input => {
            totalCredit += parseFloat(input.value) || 0;
        });

        totalDebitField.value = totalDebit
        totalCreditField.value = totalCredit;

        if (totalDebit === totalCredit && totalDebit !== 0) {
            totalDebitField.style.backgroundColor = "#d4edda"; // light green
            totalCreditField.style.backgroundColor = "#d4edda";
            totalDebitField.style.color = "#155724"; // dark green text
            totalCreditField.style.color = "#155724";
        } else {
            totalDebitField.style.backgroundColor = "#f8d7da"; // light red
            totalCreditField.style.backgroundColor = "#f8d7da";
            totalDebitField.style.color = "#721c24"; // dark red text
            totalCreditField.style.color = "#721c24";
        }
    }

    function clearDebitAndCreditInputs() {
        journalEntryBody.querySelectorAll('input[name="debit"], input[name="credit"]').forEach(input => {
            input.value = '';
        });
        calculateTotals();
    }

    document.getElementById('clear-amounts-btn').addEventListener('click', clearDebitAndCreditInputs);

    // Real Time Totals calculation
    function attachInputListeners(row) {
        row.querySelectorAll('input[name="debit"], input[name="credit"]').forEach(input => {
            input.addEventListener('input', calculateTotals);
        });
    }

    // Initial setup for all rows
    document.querySelectorAll('#journal-entry-body select[name="account_name"]').forEach(function(selectElem) {
        selectElem.addEventListener('change', function() {
            updateAccountTypeAndRestrict(this);
        });
        updateAccountTypeAndRestrict(selectElem);
    });

    // Real time row input for both debit and credit
    journalEntryBody.querySelectorAll('tr').forEach(row => {
        attachInputListeners(row);
    });

    addRowBtn.addEventListener('click', function () {
        var newRow = document.createElement('tr');
        var selectHtml = '<select name="account_name" required>' + allAccountsSelect.innerHTML + '</select>';

        newRow.innerHTML = `
            <td>${selectHtml}</td>
            <td><input type="text" name="account_type" readonly></td>
            <td><input type="number" name="debit" step="0.01" min="0"></td>
            <td><input type="number" name="credit" step="0.01" min="0"></td>
            <td><button type="button" class="btn btn-danger btn-sm remove-row">Remove</button></td>
        `;
        // Add remove button
        var actionCell = newRow.querySelector('td:last-child');
        actionCell.innerHTML = '<button type="button" class="btn btn-danger btn-sm remove-row">Remove</button>';

        // Add event listener for new row's select
        var newSelect = newRow.querySelector('select[name="account_name"]');
        newSelect.addEventListener('change', function() {
            updateAccountTypeAndRestrict(this);
        });
        updateAccountTypeAndRestrict(newSelect);

        attachInputListeners(newRow);
        journalEntryBody.appendChild(newRow);
    });

    // Delegate remove row button click
    journalEntryBody.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-row')) {
            var row = e.target.closest('tr');
            if (journalEntryBody.rows.length > 1) {
                row.remove();
                calculateTotals();
            }
        }
    });

    // Handle form submit
    document.getElementById("journal_form").addEventListener("submit", (e) => {
        // e.preventDefault(); // Uncomment for AJAX, keep commented for normal submit

        let journal_code = document.getElementById("journal_code").value;

        if (totalDebit !== totalCredit) {
            alert("Total Debit and Credit must be equal before saving!");
            return false;
        }

        alert(`Journal Entry Created!\nJournal Code: ${journal_code}`);

        // Increment code_counter
        localStorage.setItem('journal_code_counter', parseInt(localStorage.getItem('journal_code_counter'), 10) + 1);
    });

    // Reset the form when closed
    document.getElementById('staticBackdrop').addEventListener('hidden.bs.modal', function () {
    const form = document.getElementById('journal_form');

    // Reset the entire form
    form.reset();

    // Remove all rows except the first one
    const rows = journalEntryBody.querySelectorAll('tr');
    rows.forEach((row, index) => {
        if (index !== 0) row.remove();
    });

    // Clear debit/credit and totals
    clearDebitAndCreditInputs();

    // Reset journal code
    document.getElementById("journal_code").value = generateJournalCode();

    // Reset account type restrictions for the first row
    const firstSelect = journalEntryBody.querySelector('select[name="account_name"]');
    if (firstSelect) updateAccountTypeAndRestrict(firstSelect);
});
});