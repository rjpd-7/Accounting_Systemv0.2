/**
 * Admin User Management
 * Handles user CRUD operations (Create, Read, Update, Delete)
 */

// Get CSRF token
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// Get URLs from data attributes
function getApiUrls() {
    const container = document.getElementById('userManagementData');
    if (!container) {
        console.error('userManagementData element not found');
        return {};
    }
    
    return {
        changePassword: container.dataset.changePasswordUrl,
        toggleActive: container.dataset.toggleActiveUrl,
        updateUser: container.dataset.updateUserUrl,
        deleteUser: container.dataset.deleteUserUrl
    };
}

/**
 * Open Change Password Modal
 */
function openChangePasswordModal(userId, username) {
    document.getElementById('change_password_user_id').value = userId;
    document.getElementById('changePasswordUsername').textContent = username;
    document.getElementById('new_password').value = '';
    document.getElementById('confirm_new_password').value = '';
    document.getElementById('changePasswordError').style.display = 'none';
    
    const modal = new bootstrap.Modal(document.getElementById('changePasswordModal'));
    modal.show();
}

/**
 * Handle Change Password Form Submission
 */
function initChangePasswordForm() {
    const form = document.getElementById('change_password_form');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const newPassword = document.getElementById('new_password').value;
        const confirmNewPassword = document.getElementById('confirm_new_password').value;
        const userId = document.getElementById('change_password_user_id').value;
        const errorDiv = document.getElementById('changePasswordError');
        
        // Validation
        if (newPassword !== confirmNewPassword) {
            errorDiv.textContent = 'Passwords do not match!';
            errorDiv.style.display = 'block';
            return;
        }
        
        if (newPassword.length < 8) {
            errorDiv.textContent = 'Password must be at least 8 characters long!';
            errorDiv.style.display = 'block';
            return;
        }
        
        // Submit password change via AJAX
        const urls = getApiUrls();
        fetch(urls.changePassword, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                user_id: userId,
                new_password: newPassword
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                bootstrap.Modal.getInstance(document.getElementById('changePasswordModal')).hide();
                alert('Password changed successfully!');
            } else {
                errorDiv.textContent = data.error || 'Failed to change password';
                errorDiv.style.display = 'block';
            }
        })
        .catch(error => {
            errorDiv.textContent = 'An error occurred while changing the password';
            errorDiv.style.display = 'block';
            console.error('Error:', error);
        });
    });
}

/**
 * Toggle User Active Status
 */
function toggleUserStatus(userId, isActive) {
    const action = isActive ? 'deactivate' : 'activate';
    if (!confirm(`Are you sure you want to ${action} this user?`)) {
        return;
    }
    
    const urls = getApiUrls();
    fetch(urls.toggleActive, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            user_id: userId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload(); // Reload to reflect changes
        } else {
            alert('Failed to update user status: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('An error occurred while updating user status');
        console.error('Error:', error);
    });
}

/**
 * Open Edit User Modal
 */
function openEditUserModal(userId, username, firstName, lastName, email, role) {
    document.getElementById('edit_user_id').value = userId;
    document.getElementById('edit_first_name').value = firstName;
    document.getElementById('edit_last_name').value = lastName;
    document.getElementById('edit_email').value = email;
    document.getElementById('edit_role').value = role;
    document.getElementById('editUserError').style.display = 'none';
    
    const modal = new bootstrap.Modal(document.getElementById('editUserModal'));
    modal.show();
}

/**
 * Handle Edit User Form Submission
 */
function initEditUserForm() {
    const form = document.getElementById('edit_user_form');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const userId = document.getElementById('edit_user_id').value;
        const firstName = document.getElementById('edit_first_name').value.trim();
        const lastName = document.getElementById('edit_last_name').value.trim();
        const email = document.getElementById('edit_email').value.trim();
        const role = document.getElementById('edit_role').value.trim();
        
        if (!firstName && !lastName && !email && !role) {
            alert('Please update at least one field');
            return;
        }
        
        const urls = getApiUrls();
        fetch(urls.updateUser, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                user_id: userId,
                first_name: firstName,
                last_name: lastName,
                email: email,
                role: role
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                location.reload();
            } else {
                document.getElementById('editUserError').textContent = data.error || 'Unknown error';
                document.getElementById('editUserError').style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('editUserError').textContent = 'An error occurred while updating the user';
            document.getElementById('editUserError').style.display = 'block';
        });
    });
}

/**
 * Delete User
 */
function deleteUser(userId, username) {
    if (!confirm(`Are you sure you want to delete user "${username}"? This action cannot be undone.`)) {
        return;
    }
    
    const urls = getApiUrls();
    fetch(urls.deleteUser, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            user_id: userId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            location.reload();
        } else {
            alert('Failed to delete user: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('An error occurred while deleting the user');
        console.error('Error:', error);
    });
}

/**
 * User Search Functionality
 */
function initUserSearch() {
    const searchUsersInput = document.getElementById('searchUsers');
    if (!searchUsersInput) return;
    
    searchUsersInput.addEventListener('input', function() {
        const searchTerm = searchUsersInput.value.toLowerCase().trim();
        const userRows = document.querySelectorAll('.user-row');
        let visibleCount = 0;

        userRows.forEach(row => {
            const username = row.getAttribute('data-username') || '';
            const fullname = row.getAttribute('data-fullname') || '';
            const email = row.getAttribute('data-email') || '';
            const role = row.getAttribute('data-role') || '';

            const isMatch = username.includes(searchTerm) ||
                           fullname.includes(searchTerm) ||
                           email.includes(searchTerm) ||
                           role.includes(searchTerm);

            if (isMatch) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        // Show "No results" message for desktop table view
        const tableBody = document.getElementById('userTableBody');
        let noResultsMsg = document.querySelector('.no-user-search-results');
        if (visibleCount === 0 && searchTerm !== '' && tableBody) {
            if (!noResultsMsg) {
                const tr = document.createElement('tr');
                tr.className = 'no-user-search-results';
                tr.innerHTML = '<td colspan="6" class="text-center"><div class="alert alert-info mb-0">No users match your search.</div></td>';
                tableBody.appendChild(tr);
            }
        } else if (noResultsMsg) {
            noResultsMsg.remove();
        }
        
        // Show "No results" message for mobile card view
        const cardsContainer = document.getElementById('userCardsContainer');
        let noResultsMsgMobile = document.querySelector('.no-user-search-results-mobile');
        if (visibleCount === 0 && searchTerm !== '' && cardsContainer) {
            if (!noResultsMsgMobile) {
                const div = document.createElement('div');
                div.className = 'no-user-search-results-mobile alert alert-info';
                div.textContent = 'No users match your search.';
                cardsContainer.appendChild(div);
            }
        } else if (noResultsMsgMobile) {
            noResultsMsgMobile.remove();
        }
    });
}

// Initialize all user management functionality when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initChangePasswordForm();
    initEditUserForm();
    initUserSearch();
});
