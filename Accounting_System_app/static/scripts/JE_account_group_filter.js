
document.addEventListener('DOMContentLoaded', function() {
    // Master copies of template options
    const masterAllOptions = Array.from(document.querySelectorAll('#all-accounts-select option')).map(opt => opt.cloneNode(true));
    const masterEditOptions = Array.from(document.querySelectorAll('#edit-all-accounts-select option')).map(opt => opt.cloneNode(true));

    const allAccountsSelect = document.getElementById('all-accounts-select');
    const editAllAccountsSelect = document.getElementById('edit-all-accounts-select');

    var account_select = document.getElementById('account_group_filter');

    // Group filter for accounts table
    const groupFilterSelect = document.getElementById('account_group_filter');
    const accountsTableBody = document.getElementById('accountsTableBody');
    var journalEntryBody = document.getElementById('journal-entry-body');

    function clearRowsExceptFirst(tableBodyElement) {
    var rows = tableBodyElement.querySelectorAll('tr');
    rows.forEach(function (row, index) {
        if (index !== 0) row.remove();
    });
}

    if (groupFilterSelect) {
        groupFilterSelect.addEventListener('change', function() {
            clearRowsExceptFirst(journalEntryBody);
        });
    }

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
            // ensure any change handlers (that update account type display) run
            try {
                sel.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (e) {
                // fallback for older browsers
                var evt = document.createEvent('HTMLEvents'); evt.initEvent('change', true, false); sel.dispatchEvent(evt);
            }
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
            try {
                sel.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (e) {
                var evt = document.createEvent('HTMLEvents'); evt.initEvent('change', true, false); sel.dispatchEvent(evt);
            }
        });
    }

    const groupFilter = document.getElementById('account_group_filter');
    if (groupFilter) {
        groupFilter.addEventListener('change', function() {
            applyFilterToInsert(this.value);
        });
        // apply initial filter (if default not all)
        applyFilterToInsert(groupFilter.value || '');
    }

    const editGroupFilter = document.getElementById('edit_account_group_filter');
    if (editGroupFilter) {
        editGroupFilter.addEventListener('change', function() {
            applyFilterToEdit(this.value);
        });
        applyFilterToEdit(editGroupFilter.value || '');
    }

});