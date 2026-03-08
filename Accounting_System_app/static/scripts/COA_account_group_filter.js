
document.addEventListener('DOMContentLoaded', function() {
    // Master copies of template options
    const masterAllOptions = Array.from(document.querySelectorAll('#all-accounts-select option')).map(opt => opt.cloneNode(true));
    const masterEditOptions = Array.from(document.querySelectorAll('#edit-all-accounts-select option')).map(opt => opt.cloneNode(true));

    const allAccountsSelect = document.getElementById('all-accounts-select');
    const editAllAccountsSelect = document.getElementById('edit-all-accounts-select');

    var account_select = document.getElementById('account_group_filter');

    // Group filter for accounts table
    const groupFilterSelect = document.getElementById('accountGroupFilter');
    const accountSearchInput = document.getElementById('accountSearch');
    const accountsTableBody = document.getElementById('accountsTableBody');
    var journalEntryBody = document.getElementById('journal-entry-body');

    function clearRowsExceptFirst(tableBodyElement) {
        var rows = tableBodyElement.querySelectorAll('tr');
        rows.forEach(function (row, index) {
            if (index !== 0) row.remove();
        });
    }

    // Filter accounts table based on selected group and search term
    function filterAccountsTable() {
        const groupId = groupFilterSelect ? groupFilterSelect.value : '';
        const searchTerm = accountSearchInput ? accountSearchInput.value.toLowerCase().trim() : '';
        
        // Filter table rows
        if (accountsTableBody) {
            const rows = accountsTableBody.querySelectorAll('tr.account-row');
            let visibleCount = 0;
            
            rows.forEach(row => {
                const rowGroupId = row.dataset.groupId;
                const code = row.dataset.code || '';
                const name = row.dataset.name || '';
                const type = row.dataset.type || '';
                const description = row.dataset.description || '';
                const groupName = row.dataset.groupName || '';
                
                // Check group filter
                const groupMatch = !groupId || rowGroupId === groupId || rowGroupId === 'null';
                
                // Check search filter
                const searchMatch = !searchTerm || 
                                   code.includes(searchTerm) || 
                                   name.includes(searchTerm) || 
                                   type.includes(searchTerm) ||
                                   description.includes(searchTerm) ||
                                   groupName.includes(searchTerm);
                
                // Show row only if both filters match
                if (groupMatch && searchMatch) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });
        }
        
        // Filter mobile cards
        const accountCardsContainer = document.getElementById('accountCardsContainer');
        if (accountCardsContainer) {
            const cards = accountCardsContainer.querySelectorAll('.account-card');
            let visibleCardCount = 0;
            
            cards.forEach(card => {
                const cardGroupId = card.dataset.groupId;
                const code = card.dataset.code || '';
                const name = card.dataset.name || '';
                const type = card.dataset.type || '';
                const description = card.dataset.description || '';
                const groupName = card.dataset.groupName || '';
                
                // Check group filter
                const groupMatch = !groupId || cardGroupId === groupId || cardGroupId === 'null';
                
                // Check search filter
                const searchMatch = !searchTerm || 
                                   code.includes(searchTerm) || 
                                   name.includes(searchTerm) || 
                                   type.includes(searchTerm) ||
                                   description.includes(searchTerm) ||
                                   groupName.includes(searchTerm);
                
                // Show card only if both filters match
                if (groupMatch && searchMatch) {
                    card.style.display = '';
                    visibleCardCount++;
                } else {
                    card.style.display = 'none';
                }
            });
        }
    }

    if (groupFilterSelect) {
        groupFilterSelect.addEventListener('change', filterAccountsTable);
    }
    
    if (accountSearchInput) {
        accountSearchInput.addEventListener('input', filterAccountsTable);
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