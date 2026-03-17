/**
 * AJAX Journal Approval Handler
 * Approves journals without page refresh, with confirmation dialog
 */

(function() {
    // Handle approve button clicks
    document.addEventListener('click', function(event) {
        if (event.target.closest('.approve-journal-btn')) {
            event.preventDefault();
            const button = event.target.closest('.approve-journal-btn');
            const journalId = button.dataset.journalId;
            const journalCode = button.dataset.journalCode;
            const entriesTableId = button.dataset.entriesTableId || `entries_draft_${journalId}`;
            
            // Show confirmation modal
            const modal = document.getElementById('approveJournalModal');
            if (!modal) {
                console.error('Approval modal not found');
                return;
            }
            
            // Set modal title and button text
            document.getElementById('approveJournalTitle').textContent = `Approve Journal ${journalCode}`;
            document.getElementById('approveJournalCode').textContent = journalCode;
            document.getElementById('approveJournalConfirmBtn').dataset.journalId = journalId;
            document.getElementById('approveJournalConfirmBtn').dataset.entriesTableId = entriesTableId;
            
            const bootstrapModal = new bootstrap.Modal(modal);
            bootstrapModal.show();
        }
    });

    // Handle confirmation
    document.addEventListener('click', function(event) {
        if (event.target.id === 'approveJournalConfirmBtn') {
            const journalId = event.target.dataset.journalId;
            const entriesTableId = event.target.dataset.entriesTableId || `entries_draft_${journalId}`;
            const balanceValidation = validateDraftBalance(journalId, entriesTableId);
            if (!balanceValidation.valid) {
                const shouldContinue = confirm(`${balanceValidation.message}\n\nDo you want to continue and let the server perform the final validation?`);
                if (!shouldContinue) {
                    showAlert('danger', balanceValidation.message);
                    return;
                }
            }
            approveJournalAjax(journalId);
        }
    });

    function collectDraftRows(journalId, entriesTableId) {
        const rows = [];
        const sourceRows = document.querySelectorAll(`#${entriesTableId} tr`);
        sourceRows.forEach((row) => {
            const accountId = row.dataset.accountId;
            if (!accountId) {
                return;
            }
            rows.push({
                accountId: String(accountId),
                accountName: row.dataset.accountName || '',
                accountType: row.dataset.accountType || '',
                debit: window.journalBalanceValidation.toNumber(row.dataset.debit),
                credit: window.journalBalanceValidation.toNumber(row.dataset.credit),
            });
        });
        return rows;
    }

    function validateDraftBalance(journalId, entriesTableId) {
        if (!window.journalBalanceValidation || typeof window.journalBalanceValidation.validateRows !== 'function') {
            return { valid: true, message: '' };
        }
        const rows = collectDraftRows(journalId, entriesTableId);
        return window.journalBalanceValidation.validateRows(rows);
    }

    function approveJournalAjax(journalId) {
        const confirmBtn = document.getElementById('approveJournalConfirmBtn');
        const originalText = confirmBtn.innerHTML;
        
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Approving...';

        fetch(`/approve_journal_draft/${journalId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value || getCookie('csrftoken'),
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => {
                if (response.redirected) {
                    // If redirected, the server returned a redirect - this shouldn't happen with our AJAX
                    window.location.href = response.url;
                    return;
                }
                return response.json();
            })
            .then(data => {
                if (data && data.success) {
                    // Close modal
                    bootstrap.Modal.getInstance(document.getElementById('approveJournalModal')).hide();
                    
                    // Show success message
                    showAlert('success', `Journal approved successfully!`);
                    
                    // Refresh journal lists (trigger the realtime update event)
                    window.dispatchEvent(new CustomEvent('journal:realtime-update', {
                        detail: { 
                            action: 'approved',
                            journal_id: journalId
                        }
                    }));
                    
                    // Reset button
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = originalText;
                } else {
                    showAlert('danger', data?.error || 'Error approving journal');
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = originalText;
                }
            })
            .catch(error => {
                console.error('Error approving journal:', error);
                showAlert('danger', 'Error approving journal. Please try again.');
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = originalText;
            });
    }

    function showAlert(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        const mainContent = document.querySelector('main.main-content');
        if (mainContent) {
            mainContent.insertBefore(alertDiv, mainContent.firstChild);
            
            // Auto dismiss after 5 seconds
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
})();
