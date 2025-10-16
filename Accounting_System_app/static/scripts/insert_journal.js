document.addEventListener("DOMContentLoaded", function () {
    if(!localStorage.getItem('journal_code_counter')){
        localStorage.setItem('journal_code_counter', 0);
    }

    // Journal Code Generation
    function generateJournalCode(){
        let last_number = parseInt(localStorage.getItem('journal_code_counter'), 10);
        // Incremental part, padded to 10 digits
        let incremental = last_number.toString().padStart(10, '0');
        // Prefix 'JE' + 10 digit incremental = 12 digits total
        return 'JE-' + incremental;
    }

    // Generate journal code once insert journal modal opens
    document.getElementById('staticBackdrop').addEventListener('shown.bs.modal', function () {
         console.log("Modal opened"); // Debug log
        document.getElementById("journal_code").value = generateJournalCode();
    });

    //Journal Table functions.
    var addRowBtn = document.getElementById('add-journal-row');
    var journalEntryBody = document.getElementById('journal-entry-body');

    addRowBtn.addEventListener('click', function () {
        // Clone the first row
        var firstRow = journalEntryBody.querySelector('tr');
        var newRow = firstRow.cloneNode(true);

        // Clear input values in the new row
        newRow.querySelectorAll('input').forEach(function(input) {
            input.value = '';
            input.removeAttribute('readonly');
        });

        // Enable credit input for new rows
        var creditInput = newRow.querySelector('input[name="credit"]');
        if (creditInput) {
            creditInput.removeAttribute('readonly');
        }

        // Add remove button if not present
        var actionCell = newRow.querySelector('td:last-child');
        actionCell.innerHTML = '<button type="button" class="btn btn-danger btn-sm remove-row">Remove</button>';

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
        //e.preventDefault();

        let journal_code = document.getElementById("journal_code").value;

        //if (!account_name || !account_type) {
        //    alert("Please complete all fields.");
        //    return;
        //}

        alert(`Journal Entry Created!\nAccount Code  : ${account_code}\nAccount Name : ${account_name}\nAccount Type   : ${account_type}`);

        // Increment code_counter
        localStorage.setItem('journal_code_counter', parseInt(localStorage.getItem('journal_code_counter'), 10) + 1);

    });
});