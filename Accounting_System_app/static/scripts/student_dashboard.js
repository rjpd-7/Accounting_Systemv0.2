/**
 * Student Dashboard
 * Handles student password update form submission.
 */

function getCsrfToken() {
    const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
    return tokenInput ? tokenInput.value : '';
}

function getStudentDashboardUrls() {
    const container = document.getElementById('studentDashboardData');
    if (!container) {
        return {};
    }

    return {
        changeOwnPassword: container.dataset.changeOwnPasswordUrl || ''
    };
}

function initOwnPasswordForm() {
    const form = document.getElementById('change_own_password_form');
    if (!form) {
        return;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const currentPassword = document.getElementById('current_password')?.value || '';
        const newPassword = document.getElementById('new_password_own')?.value || '';
        const confirmNewPassword = document.getElementById('confirm_new_password_own')?.value || '';
        const errorDiv = document.getElementById('changeOwnPasswordError');
        const urls = getStudentDashboardUrls();

        if (!errorDiv) {
            return;
        }

        errorDiv.style.display = 'none';

        if (newPassword !== confirmNewPassword) {
            errorDiv.textContent = 'New passwords do not match!';
            errorDiv.style.display = 'block';
            return;
        }

        if (newPassword.length < 8) {
            errorDiv.textContent = 'Password must be at least 8 characters long!';
            errorDiv.style.display = 'block';
            return;
        }

        if (!urls.changeOwnPassword) {
            errorDiv.textContent = 'Password endpoint is not configured.';
            errorDiv.style.display = 'block';
            return;
        }

        fetch(urls.changeOwnPassword, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('changeOwnPasswordModal'));
                    if (modal) {
                        modal.hide();
                    }
                    alert('Password changed successfully!');
                    form.reset();
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

document.addEventListener('DOMContentLoaded', function() {
    initOwnPasswordForm();
});
