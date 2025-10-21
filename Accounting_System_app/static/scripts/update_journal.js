document.addEventListener("DOMContentLoaded", function () {

    // Safe element getters
    var addRowBtn = document.getElementById('edit-add-journal-row');
    var journalEntryBody = document.getElementById('edit-journal-entry-body');
    var allAccountsSelect = document.getElementById('edit-all-accounts-select');
    var totalDebitField = document.getElementById('edit_total_debit');
    var totalCreditField = document.getElementById('edit_total_credit');
    var clearAmountsBtn = document.getElementById('edit-clear-amounts-btn');
    var editForm = document.getElementById("edit_journal_form");
    var editModal = document.getElementById('EDITstaticBackdrop');

    // helper: get data-type from an option safely
    function optionType(opt) {
        return opt ? (opt.getAttribute('data-type') || opt.getAttribute('data-type_edit') || "") : "";
    }

    // Update account type display and apply debit/credit restrictions
    function updateEditAccountTypeAndRestrict(selectElem) {
        if (!selectElem) return;
        var row = selectElem.closest('tr');
        var typeInput = row.querySelector('input[name="edit_account_type"]');
        var debitInput = row.querySelector('input[name="edit_debit"]');
        var creditInput = row.querySelector('input[name="edit_credit"]');
        var selectedOption = selectElem.options[selectElem.selectedIndex];
        var type = optionType(selectedOption);

        if (typeInput) typeInput.value = type;

        if (debitInput && creditInput) {
            if (type === "Assets" || type === "Expenses") {
                debitInput.removeAttribute('readonly');
                creditInput.value = '';
                creditInput.setAttribute('readonly', 'true');
            } else if (type === "Liabilities" || type === "Equity" || type === "Revenue") {
                creditInput.removeAttribute('readonly');
                debitInput.value = '';
                debitInput.setAttribute('readonly', 'true');
            } else {
                debitInput.removeAttribute('readonly');
                creditInput.removeAttribute('readonly');
            }
        }
        calculateEditTotals();
    }

    // Calculate totals and update UI safely
    function calculateEditTotals() {
        if (!journalEntryBody) return;
        var totalDebit = 0;
        var totalCredit = 0;

        journalEntryBody.querySelectorAll('input[name="edit_debit"]').forEach(function(input) {
            totalDebit += parseFloat(input.value) || 0;
        });
        journalEntryBody.querySelectorAll('input[name="edit_credit"]').forEach(function(input) {
            totalCredit += parseFloat(input.value) || 0;
        });

        if (totalDebitField) totalDebitField.value = totalDebit.toFixed(2);
        if (totalCreditField) totalCreditField.value = totalCredit.toFixed(2);

        if (totalDebitField && totalCreditField) {
            if (totalDebit === totalCredit && totalDebit !== 0) {
                totalDebitField.style.backgroundColor = "#d4edda";
                totalCreditField.style.backgroundColor = "#d4edda";
                totalDebitField.style.color = "#155724";
                totalCreditField.style.color = "#155724";
            } else {
                totalDebitField.style.backgroundColor = "#f8d7da";
                totalCreditField.style.backgroundColor = "#f8d7da";
                totalDebitField.style.color = "#721c24";
                totalCreditField.style.color = "#721c24";
            }
        }
    }

    function clearEditDebitAndCreditInputs() {
        if (!journalEntryBody) return;
        journalEntryBody.querySelectorAll('input[name="edit_debit"], input[name="edit_credit"]').forEach(function(input) {
            input.value = '';
        });
        calculateEditTotals();
    }

    if (clearAmountsBtn) clearAmountsBtn.addEventListener('click', clearEditDebitAndCreditInputs);

    // Delegate change on selects to support dynamically added rows
    if (journalEntryBody) {
        journalEntryBody.addEventListener('change', function(e) {
            if (e.target && e.target.matches('select[name="edit_account_name"], select.edit_account_name')) {
                updateEditAccountTypeAndRestrict(e.target);
            }
        });

        // Delegate input events for totals
        journalEntryBody.addEventListener('input', function(e) {
            if (e.target && (e.target.matches('input[name="edit_debit"]') || e.target.matches('input[name="edit_credit"]'))) {
                calculateEditTotals();
            }
        });
    }

    // Initialize existing rows (apply restrictions & totals)
    if (journalEntryBody) {
        journalEntryBody.querySelectorAll('select[name="edit_account_name"], select.edit_account_name').forEach(function(sel) {
            updateEditAccountTypeAndRestrict(sel);
        });
        calculateEditTotals();
    }

    // Add new row (uses all accounts)
    if (addRowBtn && journalEntryBody) {
        addRowBtn.addEventListener('click', function () {
            var newRow = document.createElement('tr');
            var optionsHtml = allAccountsSelect ? allAccountsSelect.innerHTML : '';
            var selectHtml = '<select class="form-select" name="edit_account_name" required>' + optionsHtml + '</select>';

            newRow.innerHTML = `
                <td>${selectHtml}</td>
                <td><input type="text" class="form-control" name="edit_account_type" readonly></td>
                <td><input type="number" class="form-control" name="edit_debit" step="0.01" min="0"></td>
                <td><input type="number" class="form-control" name="edit_credit" step="0.01" min="0"></td>
                <td><button type="button" class="btn btn-danger btn-sm remove-row">Remove</button></td>
            `;
            journalEntryBody.appendChild(newRow);

            // set initial restrictions for the default selected option
            var sel = newRow.querySelector('select[name="edit_account_name"]');
            if (sel) updateEditAccountTypeAndRestrict(sel);
        });
    }

    // Remove row handler (delegated)
    if (journalEntryBody) {
        journalEntryBody.addEventListener('click', function(e) {
            if (e.target && e.target.matches('.remove-row')) {
                var row = e.target.closest('tr');
                if (row && !row.classList.contains('fixed-row')) {
                    row.remove();
                    calculateEditTotals();
                }
            }
        });
    }

    // Prefill modal rows from hidden table and keep behavior consistent
    // uses jQuery in your project — make sure jQuery is loaded
    $(document).on('click', '#edit_button', function() {
        const headerId = $(this).data('id');
        const date = $(this).data('date');
        const desc = $(this).data('description');

        // format date to yyyy-mm-dd
        let d = new Date(date);
        let datestring = d.getFullYear().toString().padStart(4, '0') + '-' + (d.getMonth()+1).toString().padStart(2, '0') + '-' + d.getDate().toString().padStart(2, '0');

        $('#edit-entry-date').val(datestring);
        $('#edit_journal_description').val(desc || '');

        const tbody = $('#edit-journal-entry-body');
        tbody.empty();

        // Iterate hidden rows and create modal rows
        $(`#entries_${headerId} tr`).each(function(index) {
            const accountId = $(this).data('account-id');
            const accountName = $(this).data('account-name');
            const accountType = $(this).data('account-type') || '';
            const debit = $(this).data('debit') || '';
            const credit = $(this).data('credit') || '';

            const accountOptions = index === 0 ? $('#edit-debit-accounts').html() : $('#edit-all-accounts-select').html();

            const rowHtml = `
                <tr ${index === 0 ? 'class="fixed-row"' : ''}>
                    <td>
                        <select class="form-select edit_account_name" name="edit_account_name" required>
                            ${accountOptions}
                        </select>
                    </td>
                    <td><input type="text" class="form-control" name="edit_account_type" value="${accountType}" readonly></td>
                    <td><input type="number" class="form-control" name="edit_debit" value="${debit}" step="0.01" min="0"></td>
                    <td><input type="number" class="form-control" name="edit_credit" value="${credit}" step="0.01" min="0"></td>
                    <td>${index > 0 ? '<button type="button" class="btn btn-danger btn-sm remove-row">Remove</button>' : ''}</td>
                </tr>
            `;
            tbody.append(rowHtml);

            // set select value by accountId or accountName, then trigger change to apply restrictions
            // set select value by accountId or accountName, then trigger change to apply restrictions
            var $lastSelect = tbody.find('tr:last select');
            if (accountId) {
                $lastSelect.val(accountId);
            }
            if (!$lastSelect.val()) {
                // fallback match by option text
                $lastSelect.find('option').each(function() {
                    if ($(this).text().trim() === accountName) {
                        $lastSelect.val($(this).val());
                    }
                });
            }

            // Ensure restrictions run for vanilla listeners:
            // 1) dispatch a native change event (bubbles)
            // 2) call the restriction function directly as a fallback
            var domSelect = $lastSelect[0];
            if (domSelect) {
                domSelect.dispatchEvent(new Event('change', { bubbles: true }));
                // call directly to guarantee behavior
                if (typeof updateEditAccountTypeAndRestrict === 'function') {
                    updateEditAccountTypeAndRestrict(domSelect);
                }
            }
        });

        calculateEditTotals();
        $('#EDITstaticBackdrop').modal('show');
    });

    // Form submit validation
    if (editForm) {
        editForm.addEventListener("submit", function(e) {
            const total_debit = parseFloat(totalDebitField ? totalDebitField.value : 0) || 0;
            const total_credit = parseFloat(totalCreditField ? totalCreditField.value : 0) || 0;

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
            alert("Journal Entry Updated");
        });
    }

    // Reset when modal closes
    if (editModal) {
        editModal.addEventListener('hidden.bs.modal', function () {
            if (!journalEntryBody) return;
            if (editForm) editForm.reset();

            // remove extra rows
            const rows = journalEntryBody.querySelectorAll('tr');
            rows.forEach((row, idx) => {
                if (idx !== 0) row.remove();
            });

            clearEditDebitAndCreditInputs();

            // reapply restrictions on first row
            const firstSelect = journalEntryBody.querySelector('select[name="edit_account_name"], select.edit_account_name');
            if (firstSelect) updateEditAccountTypeAndRestrict(firstSelect);
        });
    }

});