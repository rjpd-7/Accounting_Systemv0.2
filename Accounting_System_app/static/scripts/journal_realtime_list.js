/**
 * Live journal list refresh without full page reload.
 * Listens for realtime events emitted by journal_code_hybrid.js.
 */

(function () {
    let refreshTimer = null;
    let isRefreshing = false;

    function refreshJournalTables() {
        if (isRefreshing) return;
        isRefreshing = true;

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

    window.addEventListener('journal:realtime-update', function () {
        queueRefresh();
    });
})();
