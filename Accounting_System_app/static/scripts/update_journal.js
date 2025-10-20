document.addEventListener("DOMContentLoaded", function () {

    // Journal Table functions.
    var addRowBtn = document.getElementById('edit-add-journal-row');
    var journalEntryBody = document.getElementById('edit-journal-entry-body');
    var allAccountsSelect = document.getElementById('edit-all-accounts-select');
    var totalDebitField = document.getElementById('edit_total_debit');
    var totalCreditField = document.getElementById('edit_total_credit');

    function updateEditAccountTypeAndRestrict(selectElem) {
        var row = selectElem.closest('tr');
        var typeInput = row.querySelector('input[name="edit_account_type"]');
        var debitInput = row.querySelector('input[name="edit_debit"]');
        var creditInput = row.querySelector('input[name="edit_credit"]');
        var selectedOption = selectElem.options[selectElem.selectedIndex];
        var type = selectedOption ? selectedOption.getAttribute('data-type_edit') : "";

        // Show Account Type
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

        calculateEditTotals();
    }

    // Calculate Totals
    function calculateEditTotals() {
        let totalDebit = 0;
        let totalCredit = 0;

        journalEntryBody.querySelectorAll('input[name="edit_debit"]').forEach(input => {
            totalDebit += parseFloat(input.value) || 0;
        });
        journalEntryBody.querySelectorAll('input[name="edit_credit"]').forEach(input => {
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

    function clearEditDebitAndCreditInputs() {
        journalEntryBody.querySelectorAll('input[name="edit_debit"], input[name="edit_credit"]').forEach(input => {
            input.value = '';
        });
        calculateEditTotals();
    }

    document.getElementById('edit-clear-amounts-btn').addEventListener('click', clearEditDebitAndCreditInputs);

    // Real Time Totals calculation
    function attachEditInputListeners(row) {
        row.querySelectorAll('input[name="edit_debit"], input[name="edit_credit"]').forEach(input => {
            input.addEventListener('input', calculateEditTotals);
        });
    }

    // Initial setup for all rows
    document.querySelectorAll('#edit-journal-entry-body select[name="edit_account_name"]').forEach(function(selectElem) {
        selectElem.addEventListener('change', function() {
            updateEditAccountTypeAndRestrict(this);
        });
        updateEditAccountTypeAndRestrict(selectElem);
    });

    // Real time row input for both debit and credit
    journalEntryBody.querySelectorAll('tr').forEach(row => {
        attachEditInputListeners(row);
    });

    addRowBtn.addEventListener('click', function () {
        var newRow = document.createElement('tr');
        var selectHtml = '<select name="edit_account_name" required>' + allAccountsSelect.innerHTML + '</select>';

        newRow.innerHTML = `
            <td>${selectHtml}</td>
            <td><input type="text" name="edit_account_type" readonly></td>
            <td><input type="number" name="edit_debit" step="0.01" min="0"></td>
            <td><input type="number" name="edit_credit" step="0.01" min="0"></td>
            <td><button type="button" class="btn btn-danger btn-sm remove-row">Remove</button></td>
        `;
        // Add remove button
        var actionCell = newRow.querySelector('td:last-child');
        actionCell.innerHTML = '<button type="button" class="btn btn-danger btn-sm remove-row">Remove</button>';

        // Add event listener for new row's select
        var newSelect = newRow.querySelector('select[name="edit_account_name"]');
        newSelect.addEventListener('change', function() {
            updateEditAccountTypeAndRestrict(this);
        });
        updateEditAccountTypeAndRestrict(newSelect);

        attachEditInputListeners(newRow);
        journalEntryBody.appendChild(newRow);
    });

    // Delegate remove row button click
    journalEntryBody.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-row')) {
            var row = e.target.closest('tr');
            if (journalEntryBody.rows.length > 1) {
                row.remove();
                calculateEditTotals();
            }
        }
    });

   $(document).on('click', '#edit_button', function() {
        const headerId = $(this).data('id');
        const date = $(this).data('date');
        const desc = $(this).data('description');

        // Fill header fields
        $('#edit-entry-date').val(date);
        $('#edit_journal_description').val(desc);

        const tbody = $('#edit-journal-entry-body');
        tbody.empty();

        // Loop through hidden rows
        $(`#entries_${headerId} tr`).each(function(index) {
            const accountId = $(this).data('account-id');
            const accountName = $(this).data('account-name');
            const accountType = $(this).data('account-type');
            const debit = $(this).data('debit');
            const credit = $(this).data('credit');

            // Create table row
            const row = `
                <tr>
                    <td>
                        <select class="form-select edit_account_name" name="edit_account_name" required>
                            ${$('#edit-all-accounts-select').html()}
                        </select>
                    </td>
                    <td><input type="text" class="form-control" name="edit_account_type" value="${accountType}" readonly></td>
                    <td><input type="number" class="form-control" name="edit_debit" value="${debit}" step="0.01" min="0"></td>
                    <td><input type="number" class="form-control" name="edit_credit" value="${credit}" step="0.01" min="0"></td>
                    <td>
                        ${index > 0 ? '<button type="button" class="btn btn-danger btn-sm remove-row">Remove</button>' : ''}
                    </td>
                </tr>
            `;
            tbody.append(row);

            // Set selected account
            tbody.find('tr:last select').val(accountId);
        });

        $('#EDITstaticBackdrop').modal('show');

        calculateEditTotals();

    });

    document.getElementById("edit_journal_form").addEventListener("submit", (e) => {
        // e.preventDefault();
        // Get numeric values — these come in as strings
        const total_debit = parseFloat(document.getElementById("edit_total_debit").value) || 0;
        const total_credit = parseFloat(document.getElementById("edit_total_credit").value) || 0;

        // Checks if there are 0 values
        if (total_debit === 0) {
            e.preventDefault(); // stop form submission
            alert("Please enter amount!");
            return;
        }

        // Checks if totals match
        if (total_debit !== total_credit) {
            e.preventDefault(); // stop form submission
            alert("Total Debit and Credit must be equal before saving!");
            return;
        }
        
        // Optional success message
        alert(`Journal Entry Updated`);
    });

    // Reset the form when closed
    document.getElementById('EDITstaticBackdrop').addEventListener('hidden.bs.modal', function () {
        const form = document.getElementById('edit_journal_form');

        // Reset the entire form
        form.reset();

        // Remove all rows except the first one
        const rows = journalEntryBody.querySelectorAll('tr');
        rows.forEach((row, index) => {
            if (index !== 0) row.remove();
        });

        // Clear debit/credit and totals
        clearEditDebitAndCreditInputs();

        // Reset account type restrictions for the first row
        const firstSelect = journalEntryBody.querySelector('select[name="edit_account_name"]');
        if (firstSelect) updateEditAccountTypeAndRestrict(firstSelect);

    });
});