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

    // Update account type display and (optionally) restrict — keeps existing behavior
    function updateEditAccountTypeAndRestrict(selectElem) {
        if (!selectElem) return;
        var row = selectElem.closest('tr');
        var typeInput = row.querySelector('input[name="edit_account_type"]');
        var debitInput = row.querySelector('input[name="edit_debit"]');
        var creditInput = row.querySelector('input[name="edit_credit"]');
        var selectedOption = selectElem.options[selectElem.selectedIndex];
        var type = optionType(selectedOption);

        if (typeInput) typeInput.value = type;
        var firstRow = journalEntryBody ? journalEntryBody.querySelector('tr') : null;
        var isFirstRow = firstRow && row === firstRow;
        if (isFirstRow) {
            // make last behavior consistent: first row must be debit-only
            if (creditInput) {
                creditInput.value = '';
                creditInput.setAttribute('readonly', 'true');
            }
            if (debitInput) {
                debitInput.removeAttribute('readonly');
            }
        }
        // ensure mutual-exclusivity behavior applied
        attachEditMutualExclusivity(row);

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

    // --- Numeric restrictions: block 'e', '+', '-' and sanitize paste ---
    function addNumericRestrictions(input) {
        if (!input) return;
        if (input._numericKeydown) input.removeEventListener('keydown', input._numericKeydown);
        input._numericKeydown = function (ev) {
            if (!ev || !ev.key) return;
            var k = ev.key;
            if (k === 'e' || k === 'E' || k === '+' || k === '-') ev.preventDefault();
        };
        input.addEventListener('keydown', input._numericKeydown);

        if (input._numericPaste) input.removeEventListener('paste', input._numericPaste);
        input._numericPaste = function (ev) {
            var data = (ev.clipboardData || window.clipboardData).getData('text') || '';
            if (/[eE+\-]/.test(data)) {
                ev.preventDefault();
                var sanitized = data.replace(/[eE+\-]/g, '');
                if (document.queryCommandSupported('insertText')) {
                    document.execCommand('insertText', false, sanitized);
                } else {
                    input.value = input.value + sanitized;
                }
                calculateEditTotals();
            }
        };
        input.addEventListener('paste', input._numericPaste);
    }

    
    // Enforce mutual exclusivity on a row: if debit > 0 clear credit and vice-versa
    function attachEditMutualExclusivity(row) {
        if (!row) return;
        var debit = row.querySelector('input[name="edit_debit"]');
        var credit = row.querySelector('input[name="edit_credit"]');

        // remove previous handlers
        if (debit && debit._handler) debit.removeEventListener('input', debit._handler);
        if (credit && credit._handler) credit.removeEventListener('input', credit._handler);

        addNumericRestrictions(debit);
        addNumericRestrictions(credit);

        if (debit) {
            debit._handler = function () {
                var d = parseFloat(debit.value) || 0;
                if (d > 0 && credit) {
                    if (credit.value && credit.value.trim() !== '') credit.value = '';
                }
                calculateEditTotals();
            };
            debit.addEventListener('input', debit._handler);
        }

        if (credit) {
            credit._handler = function () {
                var c = parseFloat(credit.value) || 0;
                if (c > 0 && debit) {
                    if (debit.value && debit.value.trim() !== '') debit.value = '';
                }
                calculateEditTotals();
            };
            credit.addEventListener('input', credit._handler);
        }

        // ensure totals recalc on manual edits
        [debit, credit].forEach(function (inp) {
            if (!inp) return;
            if (inp._totalsHandler) inp.removeEventListener('input', inp._totalsHandler);
            inp._totalsHandler = calculateEditTotals;
            inp.addEventListener('input', inp._totalsHandler);
        });

        // initial cleanup if both populated
        if (debit && credit) {
            var d0 = parseFloat(debit.value) || 0;
            var c0 = parseFloat(credit.value) || 0;
            if (d0 > 0 && c0 > 0) {
                // default: keep debit and clear credit (adjust if needed)
                credit.value = '';
            }
        }
    }

    // Public helper so prefill code can apply behaviors after inserting rows
    window.applyEditRowBehavior = function (row) {
        if (!row) return;
        var sel = row.querySelector('select[name="edit_account_name"], select.edit_account_name');
        if (sel) {
            // ensure change updates display and restrictions
            sel.addEventListener('change', function () {
                updateEditAccountTypeAndRestrict(this);
            });
            // set display now
            updateEditAccountTypeAndRestrict(sel);
        }
        attachEditMutualExclusivity(row);
    };

    // utility: apply behaviors to all rows (call after prefill)
    window.applyEditBehaviorToAllRows = function () {
        if (!journalEntryBody) return;
        journalEntryBody.querySelectorAll('tr').forEach(function (r) {
            window.applyEditRowBehavior(r);
        });
        calculateEditTotals();
    };

    // Delegated handlers to support first row and dynamically added rows
    if (journalEntryBody) {
        // input delegation for mutual exclusivity and totals (covers first row)
        journalEntryBody.addEventListener('input', function (e) {
            var t = e.target;
            if (!t) return;
            if (t.matches('input[name="edit_debit"]')) {
                var row = t.closest('tr');
                if (!row) return;
                var credit = row.querySelector('input[name="edit_credit"]');
                var d = parseFloat(t.value) || 0;
                if (d > 0 && credit && credit.value) credit.value = '';
                calculateEditTotals();
                return;
            }
            if (t.matches('input[name="edit_credit"]')) {
                var row2 = t.closest('tr');
                if (!row2) return;
                var debit = row2.querySelector('input[name="edit_debit"]');
                var c = parseFloat(t.value) || 0;
                if (c > 0 && debit && debit.value) debit.value = '';
                calculateEditTotals();
                return;
            }
        });

        // change delegation for selects
        journalEntryBody.addEventListener('change', function (e) {
            var t = e.target;
            if (!t) return;
            if (t.matches('select[name="edit_account_name"], select.edit_account_name')) {
                updateEditAccountTypeAndRestrict(t);
            }
        });
    }

    // Initialize existing rows (apply restrictions & totals)
    if (journalEntryBody) {
        journalEntryBody.querySelectorAll('select[name="edit_account_name"], select.edit_account_name').forEach(function(sel) {
            updateEditAccountTypeAndRestrict(sel);
        });
        // also ensure numeric restrictions & mutual exclusivity applied to existing inputs
        window.applyEditBehaviorToAllRows();
        calculateEditTotals();
    }

    // Add new row (uses all accounts)
    if (addRowBtn && journalEntryBody) {
        addRowBtn.addEventListener('click', function () {
            var newRow = document.createElement('tr');
            var optionsHtml = allAccountsSelect ? allAccountsSelect.innerHTML : '';
            var selectHtml = '<select class="form-select edit_account_name" name="edit_account_name" required>' + optionsHtml + '</select>';

            newRow.innerHTML = `
                <td>${selectHtml}</td>
                <td><input type="text" class="form-control" name="edit_account_type" readonly></td>
                <td><input type="number" class="form-control" name="edit_debit" step="0.01" min="0"></td>
                <td><input type="number" class="form-control" name="edit_credit" step="0.01" min="0"></td>
                <td><button type="button" class="btn btn-danger btn-sm remove-row">Remove</button></td>
            `;
            journalEntryBody.appendChild(newRow);

            // apply behaviors to the new row
            window.applyEditRowBehavior(newRow);

            // trigger change so display updates based on the selected option (if any)
            var sel = newRow.querySelector('select[name="edit_account_name"], select.edit_account_name');
            if (sel) sel.dispatchEvent(new Event('change', { bubbles: true }));
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
        const groupId = $(this).data('group');
        const groupName = $(this).data('group-name');
        const isDraft = $(this).data('is-draft');

        // set form action (use your URL pattern)
        var form = document.getElementById('edit_journal_form');
        if (form) {
            // use draft URL if this is a draft (isDraft will be "true" string or true), otherwise use approved URL
            if (isDraft === true || isDraft === 'true') {
                form.action = '/update_journal_draft/' + encodeURIComponent(headerId) + '/';
            } else {
                form.action = '/update_journal/' + encodeURIComponent(headerId) + '/';
            }
            // OR if you want a hidden field:
            var hid = form.querySelector('input[name="header_id"]');
            if (!hid) {
                hid = document.createElement('input');
                hid.type = 'hidden';
                hid.name = 'header_id';
                form.appendChild(hid);
            }
            hid.value = headerId;
        }

        // format date to yyyy-mm-dd
        let d = new Date(date);
        let datestring = d.getFullYear().toString().padStart(4, '0') + '-' + (d.getMonth()+1).toString().padStart(2, '0') + '-' + d.getDate().toString().padStart(2, '0');

        $('#edit-entry-date').val(datestring);
        $('#edit_journal_description').val(desc || '');
        
        // Set account group display (readonly) and hidden filter field
        if (groupId && groupName) {
            document.getElementById('edit_account_group_display').value = groupName;
            const groupFilterField = document.getElementById('edit_account_group_filter');
            if (groupFilterField) {
                groupFilterField.value = groupId;
                // Trigger change event to apply filtering
                groupFilterField.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

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

            // Ensure restrictions and behaviors run for vanilla listeners:
            var domSelect = $lastSelect[0];
            if (domSelect) {
                domSelect.dispatchEvent(new Event('change', { bubbles: true }));
                // call directly to guarantee behavior
                if (typeof updateEditAccountTypeAndRestrict === 'function') {
                    updateEditAccountTypeAndRestrict(domSelect);
                }
            }
        });

        // After prefill: attach behaviors to all rows (mutual exclusivity + numeric restrictions)
        if (typeof window.applyEditBehaviorToAllRows === 'function') {
            window.applyEditBehaviorToAllRows();
        } else {
            // fallback: calculate totals
            calculateEditTotals();
        }

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

            // optional: enforce last row credit as in insert if desired
            var rows = journalEntryBody ? journalEntryBody.querySelectorAll('tr') : [];
            if (rows.length) {
                var lastRow = rows[rows.length - 1];
                if (lastRow) {
                    var lastCreditInput = lastRow.querySelector('input[name="edit_credit"]');
                    var lastDebitInput = lastRow.querySelector('input[name="edit_debit"]');
                    var lastCredit = lastCreditInput ? parseFloat(lastCreditInput.value) || 0 : 0;
                    var lastDebit = lastDebitInput ? parseFloat(lastDebitInput.value) || 0 : 0;
                    if (lastCredit <= 0) {
                        e.preventDefault();
                        alert("The last journal line must be a credit amount.");
                        if (lastCreditInput) lastCreditInput.focus();
                        return;
                    }
                    if (lastDebit > 0) {
                        e.preventDefault();
                        alert("The last journal line must only contain a credit. Clear the debit on the last row.");
                        if (lastDebitInput) lastDebitInput.focus();
                        return;
                    }
                }
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