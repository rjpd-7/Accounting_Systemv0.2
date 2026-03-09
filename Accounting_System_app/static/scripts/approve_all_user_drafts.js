/**
 * AJAX Bulk Journal Approval Handler
 * Approves all draft journals for a specific user without page refresh
 */

(function() {
    // Handle "Approve All" button clicks
    document.addEventListener('click', function(event) {
        if (event.target.closest('.approve-all-user-drafts-btn')) {
            event.preventDefault();
            const button = event.target.closest('.approve-all-user-drafts-btn');
            const userId = button.dataset.userId;
            const userName = button.dataset.userName;
            const draftCount = button.dataset.draftCount;
            
            // Show confirmation modal
            const modal = document.getElementById('approveAllUserDraftsModal');
            if (!modal) {
                console.error('Bulk approval modal not found');
                return;
            }
            
            // Set modal content
            document.getElementById('approveAllUserName').textContent = userName;
            document.getElementById('approveAllDraftCount').textContent = draftCount;
            document.getElementById('approveAllConfirmBtn').dataset.userId = userId;
            document.getElementById('approveAllConfirmBtn').dataset.userName = userName;
            
            const bootstrapModal = new bootstrap.Modal(modal);
            bootstrapModal.show();
        }
    });

    // Handle confirmation
    document.addEventListener('click', function(event) {
        if (event.target.id === 'approveAllConfirmBtn') {
            const userId = event.target.dataset.userId;
            const userName = event.target.dataset.userName;
            approveAllUserDraftsAjax(userId, userName);
        }
    });

    function approveAllUserDraftsAjax(userId, userName) {
        const confirmBtn = document.getElementById('approveAllConfirmBtn');
        const originalText = confirmBtn.innerHTML;
        
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Approving...';

        fetch(`/approve_all_user_drafts/${userId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value || getCookie('csrftoken'),
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                    return;
                }
                return response.json();
            })
            .then(data => {
                if (data && data.success) {
                    // Close modal
                    bootstrap.Modal.getInstance(document.getElementById('approveAllUserDraftsModal')).hide();
                    
                    // Show success message with count
                    showAlert('success', `${data.approved_count} journal(s) approved successfully for ${userName}!`);
                    
                    // Refresh journal lists (trigger the realtime update event)
                    window.dispatchEvent(new CustomEvent('journal:realtime-update', {
                        detail: { 
                            action: 'approved',
                            user_id: userId,
                            count: data.approved_count
                        }
                    }));
                    
                    // Reset button
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = originalText;
                } else {
                    showAlert('danger', data?.error || 'Error approving journals');
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = originalText;
                }
            })
            .catch(error => {
                console.error('Error approving journals:', error);
                showAlert('danger', 'Error approving journals. Please try again.');
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
