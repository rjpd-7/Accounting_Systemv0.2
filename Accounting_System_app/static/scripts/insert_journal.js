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
    var insertModal = document.getElementById('staticBackdrop');
    if (insertModal) {
        insertModal.addEventListener('shown.bs.modal', function () {
            var jc = document.getElementById("journal_code");
            if (jc) jc.value = generateJournalCode();
        });
    }

    // Journal Table elements
    var addRowBtn = document.getElementById('add-journal-row');
    var journalEntryBody = document.getElementById('journal-entry-body');
    var allAccountsSelect = document.getElementById('all-accounts-select');
    var totalDebitField = document.getElementById('total_debit');
    var totalCreditField = document.getElementById('total_credit');
    var clearAmountsBtn = document.getElementById('clear-amounts-btn');

    function updateAccountTypeDisplay(selectElem) {
        if (!selectElem) return;
        var row = selectElem.closest('tr');
        if (!row) return;
        var typeInput = row.querySelector('input[name="account_type"]');
        var selectedOption = selectElem.options[selectElem.selectedIndex];
        var type = selectedOption ? (selectedOption.getAttribute('data-type') || '') : '';
        if (typeInput) typeInput.value = type;
    }

    function calculateTotals() {
        var totalDebit = 0;
        var totalCredit = 0;

        if (journalEntryBody) {
            journalEntryBody.querySelectorAll('input[name="debit"]').forEach(function(input) {
                totalDebit += parseFloat(input.value) || 0;
            });
            journalEntryBody.querySelectorAll('input[name="credit"]').forEach(function(input) {
                totalCredit += parseFloat(input.value) || 0;
            });
        }

        if (totalDebitField) totalDebitField.value = totalDebit.toFixed(2);
        if (totalCreditField) totalCreditField.value = totalCredit.toFixed(2);

        if (totalDebit === totalCredit && totalDebit !== 0) {
            if (totalDebitField) {
                totalDebitField.style.backgroundColor = "#d4edda";
                totalDebitField.style.color = "#155724";
            }
            if (totalCreditField) {
                totalCreditField.style.backgroundColor = "#d4edda";
                totalCreditField.style.color = "#155724";
            }
        } else {
            if (totalDebitField) {
                totalDebitField.style.backgroundColor = "#f8d7da";
                totalDebitField.style.color = "#721c24";
            }
            if (totalCreditField) {
                totalCreditField.style.backgroundColor = "#f8d7da";
                totalCreditField.style.color = "#721c24";
            }
        }
    }

    function clearAmounts() {
        if (!journalEntryBody) return;
        journalEntryBody.querySelectorAll('input[name="debit"], input[name="credit"]').forEach(function(input) {
            input.value = '';
        });
        calculateTotals();
    }
    if (clearAmountsBtn) clearAmountsBtn.addEventListener('click', clearAmounts);

    // Enforce mutual exclusivity: when one input has >0 value, clear the other input in the same row.
    function attachMutualExclusivity(row) {
        if (!row) return;
        var debit = row.querySelector('input[name="debit"]');
        var credit = row.querySelector('input[name="credit"]');

        function addNumericRestrictions(input) {
            if (!input) return;
            // keydown: block e/E, +, -
            if (input._numericKeydown) input.removeEventListener('keydown', input._numericKeydown);
            input._numericKeydown = function (ev) {
                if (!ev || !ev.key) return;
                var k = ev.key;
                if (k === 'e' || k === 'E' || k === '+' || k === '-') {
                    ev.preventDefault();
                }
            };
            input.addEventListener('keydown', input._numericKeydown);

            // paste: sanitize clipboard content
            if (input._numericPaste) input.removeEventListener('paste', input._numericPaste);
            input._numericPaste = function (ev) {
                var data = (ev.clipboardData || window.clipboardData).getData('text') || '';
                if (/[eE+\-]/.test(data)) {
                     ev.preventDefault();
                    var sanitized = data.replace(/[eE+\-]/g, '');
                    // insert sanitized text at cursor
                    if (document.queryCommandSupported('insertText')) {
                        document.execCommand('insertText', false, sanitized);
                    } else {
                        // fallback: append
                        input.value = input.value + sanitized;
                    }
                    // trigger totals recalc
                    calculateTotals();
                }
            };
            input.addEventListener('paste', input._numericPaste);
        }

        // remove existing handlers if attached
        if (debit && debit._mutualHandler) debit.removeEventListener('input', debit._mutualHandler);
        if (credit && credit._mutualHandler) credit.removeEventListener('input', credit._mutualHandler);

        addNumericRestrictions(debit);
        addNumericRestrictions(credit);
        
        if (debit) {
            debit._mutualHandler = function () {
                var d = parseFloat(debit.value) || 0;
                if (d > 0 && credit) {
                    // clear credit when user types a debit
                    if (credit.value && credit.value.trim() !== '') credit.value = '';
                }
                calculateTotals();
            };
            debit.addEventListener('input', debit._mutualHandler);
        }

        if (credit) {
            credit._mutualHandler = function () {
                var c = parseFloat(credit.value) || 0;
                if (c > 0 && debit) {
                    // clear debit when user types a credit
                    if (debit.value && debit.value.trim() !== '') debit.value = '';
                }
                calculateTotals();
            };
            credit.addEventListener('input', credit._mutualHandler);
        }

        // also attach change listeners to recalc totals on manual edits (fallback)
        [debit, credit].forEach(function(inp) {
            if (!inp) return;
            if (inp._totalsHandler) inp.removeEventListener('input', inp._totalsHandler);
            inp._totalsHandler = calculateTotals;
            inp.addEventListener('input', inp._totalsHandler);
        });

        // initialize: if both have values, keep the last non-zero and clear the other
        if (debit && credit) {
            var d0 = parseFloat(debit.value) || 0;
            var c0 = parseFloat(credit.value) || 0;
            if (d0 > 0 && c0 > 0) {
                // prefer the one that was entered last — we cannot detect order here; clear credit by default
                credit.value = '';
            }
        }
    }

    // initialize existing rows
    if (journalEntryBody) {
        journalEntryBody.querySelectorAll('tr').forEach(function(row) {
            // attach handlers for select -> update type display
            var sel = row.querySelector('select[name="account_name"]');
            if (sel) {
                sel.addEventListener('change', function () {
                    updateAccountTypeDisplay(this);
                });
                updateAccountTypeDisplay(sel);
            }
            attachMutualExclusivity(row);
        });
    }

    // add new row
    if (addRowBtn) {
        addRowBtn.addEventListener('click', function () {
            if (!journalEntryBody) return;
            var newRow = document.createElement('tr');
            var optionsHtml = allAccountsSelect ? allAccountsSelect.innerHTML : '';
            var selectHtml = '<select name="account_name" class="form-select" required>' + optionsHtml + '</select>';

            newRow.innerHTML = `
                <td>${selectHtml}</td>
                <td><input type="text" name="account_type" class="form-control" readonly></td>
                <td><input type="number" name="debit" step="0.01" min="0" class="form-control"></td>
                <td><input type="number" name="credit" step="0.01" min="0" class="form-control"></td>
                <td><button type="button" class="btn btn-danger btn-sm remove-row">Remove</button></td>
            `;
            journalEntryBody.appendChild(newRow);

            // wire select and inputs for the new row
            var sel = newRow.querySelector('select[name="account_name"]');
            if (sel) {
                sel.addEventListener('change', function() {
                    updateAccountTypeDisplay(this);
                });
                updateAccountTypeDisplay(sel);
            }
            attachMutualExclusivity(newRow);
        });
    }

    // remove row delegate
    if (journalEntryBody) {
        journalEntryBody.addEventListener('click', function (e) {
            if (e.target.classList.contains('remove-row')) {
                var row = e.target.closest('tr');
                if (!row) return;
                // keep at least one row
                var rows = journalEntryBody.querySelectorAll('tr');
                if (rows.length > 1) {
                    row.remove();
                    calculateTotals();
                }
            }
        });
    }

    // form submit validation
    var journalForm = document.getElementById("journal_form");
if (journalForm) {
    journalForm.addEventListener("submit", function (e) {
        // increment code counter
        localStorage.setItem('journal_code_counter', parseInt(localStorage.getItem('journal_code_counter'), 10) + 1);

        var total_debit = parseFloat((totalDebitField && totalDebitField.value) || 0) || 0;
        var total_credit = parseFloat((totalCreditField && totalCreditField.value) || 0) || 0;

        if (total_debit === 0) {
            e.preventDefault();
            alert("Please enter amount!");
            return;
        }
        if (total_debit !== total_credit) {
            e.preventDefault();
            alert("Total Debit and Credit must be equal before saving!");
            return;
        }

        // Ensure last row has a credit > 0
        if (!journalEntryBody) {
            // defensive: if body missing, block submit
            e.preventDefault();
            alert("Invalid journal lines.");
            return;
        }
        var rows = journalEntryBody.querySelectorAll('tr');
        if (!rows || rows.length === 0) {
            e.preventDefault();
            alert("Please add at least one journal line.");
            return;
        }
        var lastRow = rows[rows.length - 1];
        var lastCreditInput = lastRow ? lastRow.querySelector('input[name=\"credit\"]') : null;
        var lastDebitInput = lastRow ? lastRow.querySelector('input[name=\"debit\"]') : null;
        var lastCredit = lastCreditInput ? parseFloat(lastCreditInput.value) || 0 : 0;
        var lastDebit = lastDebitInput ? parseFloat(lastDebitInput.value) || 0 : 0;

        if (lastCredit <= 0) {
            e.preventDefault();
            alert("The last journal line must be a credit amount.");
            // optionally focus the credit input
            if (lastCreditInput) lastCreditInput.focus();
            return;
        }
        // also ensure last row does not have a debit value simultaneously
        if (lastDebit > 0) {
            e.preventDefault();
            alert("The last journal line must only contain a credit. Clear the debit on the last row.");
            if (lastDebitInput) lastDebitInput.focus();
            return;
        }

        // allow submit
    });
}

    // reset modal on close
    if (insertModal) {
        insertModal.addEventListener('hidden.bs.modal', function () {
            var form = document.getElementById('journal_form');
            if (form) form.reset();

            // remove extra rows, keep first
            if (journalEntryBody) {
                var rows = journalEntryBody.querySelectorAll('tr');
                rows.forEach(function (row, index) {
                    if (index !== 0) row.remove();
                });
                // reattach handlers to the remaining first row
                var firstRow = journalEntryBody.querySelector('tr');
                if (firstRow) attachMutualExclusivity(firstRow);
                var firstSel = firstRow ? firstRow.querySelector('select[name="account_name"]') : null;
                if (firstSel) updateAccountTypeDisplay(firstSel);
            }

            clearAmounts();
            var jc = document.getElementById("journal_code");
            if (jc) jc.value = generateJournalCode();
        });
    }

});