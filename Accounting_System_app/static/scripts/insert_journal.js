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

    function updateAccountTypeAndRestrict(selectElem) {
        var row = selectElem.closest('tr');
        var typeInput = row.querySelector('input[name="account_type"]');
        var debitInput = row.querySelector('input[name="debit"]');
        var creditInput = row.querySelector('input[name="credit"]');
        var selectedOption = selectElem.options[selectElem.selectedIndex];
        var type = selectedOption.getAttribute('data-type') || "";

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
    }

    // Initial setup for all rows
    document.querySelectorAll('#journal-entry-body select[name="account_name"]').forEach(function(selectElem) {
        selectElem.addEventListener('change', function() {
            updateAccountTypeAndRestrict(this);
        });
        updateAccountTypeAndRestrict(selectElem);
    });

    addRowBtn.addEventListener('click', function () {
        var firstRow = journalEntryBody.querySelector('tr');
        var newRow = firstRow.cloneNode(true);

        // Clear input values in the new row
        newRow.querySelectorAll('input').forEach(function(input) {
            input.value = '';
        });

        // Add remove button
        var actionCell = newRow.querySelector('td:last-child');
        actionCell.innerHTML = '<button type="button" class="btn btn-danger btn-sm remove-row">Remove</button>';

        // Add event listener for new row's select
        var newSelect = newRow.querySelector('select[name="account_name"]');
        newSelect.addEventListener('change', function() {
            updateAccountTypeAndRestrict(this);
        });
        updateAccountTypeAndRestrict(newSelect);

        journalEntryBody.appendChild(newRow);
    });

    // Delegate remove row button click
    journalEntryBody.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-row')) {
            var row = e.target.closest('tr');
            if (journalEntryBody.rows.length > 1) {
                row.remove();
            }
        }
    });

    // Handle form submit
    document.getElementById("journal_form").addEventListener("submit", (e) => {
        // e.preventDefault(); // Uncomment for AJAX, keep commented for normal submit

        let journal_code = document.getElementById("journal_code").value;
        alert(`Journal Entry Created!\nJournal Code: ${journal_code}`);

        // Increment code_counter
        localStorage.setItem('journal_code_counter', parseInt(localStorage.getItem('journal_code_counter'), 10) + 1);
    });
});