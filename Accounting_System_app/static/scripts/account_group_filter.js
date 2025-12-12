
document.addEventListener('DOMContentLoaded', function() {
    // Master copies of template options
    const masterAllOptions = Array.from(document.querySelectorAll('#all-accounts-select option')).map(opt => opt.cloneNode(true));
    const masterEditOptions = Array.from(document.querySelectorAll('#edit-all-accounts-select option')).map(opt => opt.cloneNode(true));

    const allAccountsSelect = document.getElementById('all-accounts-select');
    const editAllAccountsSelect = document.getElementById('edit-all-accounts-select');

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