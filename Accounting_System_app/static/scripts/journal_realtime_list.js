/**
 * Live journal list refresh without full page reload.
 * Listens for realtime events emitted by journal_code_hybrid.js.
 */

(function () {
    let refreshTimer = null;
    let isRefreshing = false;
    let pollingInterval = null;
    const pollingDelay = 5000;

    function hasJournalTables() {
        return Boolean(document.querySelector('#draft .display_table') || document.querySelector('#approved .display_table'));
    }

    function refreshJournalTables() {
        if (isRefreshing) return;
        if (!hasJournalTables()) return;
        isRefreshing = true;

        const draftSearchValue = document.getElementById('searchDraftJournals')?.value || '';
        const approvedSearchValue = document.getElementById('searchApprovedJournals')?.value || '';
        const bulkApprovalSearchValue = document.getElementById('bulkApprovalUserSearch')?.value || '';

        const url = `${window.location.pathname}?_rt=${Date.now()}`;
        fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            cache: 'no-store'
        })
            .then(response => response.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const newBulkApprovalSection = doc.querySelector('#draft #bulk-approval-section');
                const newDraftTable = doc.querySelector('#draft .display_table');
                const newApprovedTable = doc.querySelector('#approved .display_table');
                const currentBulkApprovalSection = document.querySelector('#draft #bulk-approval-section');
                const currentDraftTable = document.querySelector('#draft .display_table');
                const currentApprovedTable = document.querySelector('#approved .display_table');

                if (newBulkApprovalSection && currentBulkApprovalSection) {
                    currentBulkApprovalSection.outerHTML = newBulkApprovalSection.outerHTML;
                }

                if (newDraftTable && currentDraftTable) {
                    currentDraftTable.innerHTML = newDraftTable.innerHTML;
                }
                if (newApprovedTable && currentApprovedTable) {
                    currentApprovedTable.innerHTML = newApprovedTable.innerHTML;
                }

                const draftSearchInput = document.getElementById('searchDraftJournals');
                const approvedSearchInput = document.getElementById('searchApprovedJournals');
                const bulkApprovalSearchInput = document.getElementById('bulkApprovalUserSearch');

                if (draftSearchInput) {
                    draftSearchInput.value = draftSearchValue;
                }
                if (approvedSearchInput) {
                    approvedSearchInput.value = approvedSearchValue;
                }
                if (bulkApprovalSearchInput) {
                    bulkApprovalSearchInput.value = bulkApprovalSearchValue;
                }

                if (typeof window.initJournalSearch === 'function') {
                    window.initJournalSearch();
                } else if (typeof window.applyJournalSearchFilters === 'function') {
                    window.applyJournalSearchFilters();
                }
            })
            .catch(error => {
                console.error('Failed to refresh journal tables:', error);
            })
            .finally(() => {
                isRefreshing = false;
            });
    }

    function queueRefresh() {
        if (refreshTimer) {
            clearTimeout(refreshTimer);
        }
        refreshTimer = setTimeout(refreshJournalTables, 350);
    }

    function startPolling() {
        if (pollingInterval || !hasJournalTables()) {
            return;
        }

        pollingInterval = setInterval(() => {
            if (document.hidden) {
                return;
            }

            queueRefresh();
        }, pollingDelay);
    }

    function stopPolling() {
        if (!pollingInterval) {
            return;
        }

        clearInterval(pollingInterval);
        pollingInterval = null;
    }

    window.addEventListener('journal:realtime-update', function () {
        queueRefresh();
    });

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            return;
        }

        queueRefresh();
    });

    window.addEventListener('focus', function () {
        queueRefresh();
    });

    window.addEventListener('beforeunload', function () {
        stopPolling();
    });

    startPolling();
})();
