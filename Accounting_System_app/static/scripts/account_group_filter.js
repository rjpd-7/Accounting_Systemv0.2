
document.addEventListener('DOMContentLoaded', function() {
    // Master copies of template options
    const masterAllOptions = Array.from(document.querySelectorAll('#all-accounts-select option')).map(opt => opt.cloneNode(true));
    const masterEditOptions = Array.from(document.querySelectorAll('#edit-all-accounts-select option')).map(opt => opt.cloneNode(true));

    const allAccountsSelect = document.getElementById('all-accounts-select');
    const editAllAccountsSelect = document.getElementById('edit-all-accounts-select');

    var account_select = document.getElementById('account_group_filter');

    function buildOptionsFromMaster(masterOptions, groupId) {
        const frag = document.createDocumentFragment();
        masterOptions.forEach(opt => {
            const optGroup = opt.dataset.group || '';
            if (!groupId || optGroup === groupId) {
                frag.appendChild(opt.cloneNode(true));
            }
        });
        return frag;
    }

    function applyFilterToInsert(groupId) {
        // Replace template options for new rows
        if (allAccountsSelect) {
            allAccountsSelect.innerHTML = '';
            allAccountsSelect.appendChild(buildOptionsFromMaster(masterAllOptions, groupId));
        }
        // Update visible selects in current journal rows
        document.querySelectorAll('#journal-entry-body select[name="account_name"]').forEach(sel => {
            const current = sel.value;
            sel.innerHTML = '';
            sel.appendChild(buildOptionsFromMaster(masterAllOptions, groupId));
            if (current && Array.from(sel.options).some(o => o.value === current)) sel.value = current;
        });
    }

    function clearJournalRowsInsert(groupId) {
        const tbody = document.getElementById('journal-entry-body');
        if (!tbody) return;
        const firstRow = tbody.querySelector('tr');
        let newRow;
        if (firstRow) {
            newRow = firstRow.cloneNode(true);
        } else {
            newRow = document.createElement('tr');
            newRow.innerHTML = `
                <td><select class="form-select" name="account_name" required></select></td>
                <td><input type="text" name="account_type" class="form-control" readonly></td>
                <td><input type="number" name="debit" step="0.01" min="0" class="form-control"></td>
                <td><input type="number" name="credit" step="0.01" min="0" class="form-control" readonly></td>
                <td></td>
            `;
        }
        newRow.querySelectorAll('input').forEach(inp => inp.value = '');
        const sel = newRow.querySelector('select[name="account_name"]');
        if (sel) {
            sel.innerHTML = '';
            sel.appendChild(buildOptionsFromMaster(masterAllOptions, groupId));
        }
        tbody.innerHTML = '';
        tbody.appendChild(newRow);
    }

    function clearValuesInRows(tbodySelector, selectName) {
        const tbody = document.querySelector(tbodySelector);
        if (!tbody) return;
        tbody.querySelectorAll('tr').forEach(row => {
            const sel = row.querySelector(`select[name="${selectName}"]`);
            if (sel) {
                // select first option if available
                if (sel.options && sel.options.length > 0) {
                    sel.selectedIndex = 0;
                    // trigger change event so any attached handlers run
                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
            // clear numeric/text inputs
            row.querySelectorAll('input[type="number"]').forEach(inp => inp.value = '');
            row.querySelectorAll('input[type="text"]').forEach(inp => {
                // clear account_type display fields only
                if (inp.name && inp.name.toLowerCase().includes('account_type')) inp.value = '';
            });
        });
    }

    function applyFilterToEdit(groupId) {
        if (editAllAccountsSelect) {
            editAllAccountsSelect.innerHTML = '';
            editAllAccountsSelect.appendChild(buildOptionsFromMaster(masterEditOptions, groupId));
        }
        document.querySelectorAll('#edit-journal-entry-body select[name="edit_account_name"]').forEach(sel => {
            const current = sel.value;
            sel.innerHTML = '';
            sel.appendChild(buildOptionsFromMaster(masterEditOptions, groupId));
            if (current && Array.from(sel.options).some(o => o.value === current)) sel.value = current;
        });
    }

    function clearJournalRowsEdit(groupId) {
        const tbody = document.getElementById('edit-journal-entry-body');
        if (!tbody) return;
        const firstRow = tbody.querySelector('tr');
        let newRow;
        if (firstRow) {
            newRow = firstRow.cloneNode(true);
        } else {
            newRow = document.createElement('tr');
            newRow.innerHTML = `
                <td><select class="form-select" name="edit_account_name" required></select></td>
                <td><input type="text" name="edit_account_type" class="form-control" readonly></td>
                <td><input type="number" name="edit_debit" step="0.01" min="0" class="form-control"></td>
                <td><input type="number" name="edit_credit" step="0.01" min="0" class="form-control" readonly></td>
                <td></td>
            `;
        }
        newRow.querySelectorAll('input').forEach(inp => inp.value = '');
        const sel = newRow.querySelector('select[name="edit_account_name"]');
        if (sel) {
            sel.innerHTML = '';
            sel.appendChild(buildOptionsFromMaster(masterEditOptions, groupId));
        }
        tbody.innerHTML = '';
        tbody.appendChild(newRow);
    }

    const groupFilter = document.getElementById('account_group_filter');
    if (groupFilter) {
        groupFilter.addEventListener('change', function() {
            applyFilterToInsert(this.value);
            clearJournalRowsInsert(this.value);
            // ensure all rows' values are cleared/reset
            clearValuesInRows('#journal-entry-body', 'account_name');
        });
        // apply initial filter (if default not all)
        applyFilterToInsert(groupFilter.value || '');
        clearJournalRowsInsert(groupFilter.value || '');
        clearValuesInRows('#journal-entry-body', 'account_name');
    }

    const editGroupFilter = document.getElementById('edit_account_group_filter');
    if (editGroupFilter) {
        editGroupFilter.addEventListener('change', function() {
            applyFilterToEdit(this.value);
            clearJournalRowsEdit(this.value);
            clearValuesInRows('#edit-journal-entry-body', 'edit_account_name');
        });
        applyFilterToEdit(editGroupFilter.value || '');
        clearJournalRowsEdit(editGroupFilter.value || '');
        clearValuesInRows('#edit-journal-entry-body', 'edit_account_name');
    }

    if (account_select) {
        account_select.addEventListener('hidden.bs.modal', function () {
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