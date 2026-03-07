/**
 * Teacher Dashboard
 * Handles teacher password updates and student section filtering.
 */

function getCsrfToken() {
    const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
    return tokenInput ? tokenInput.value : '';
}

function getTeacherDashboardUrls() {
    const container = document.getElementById('teacherDashboardData');
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
        const urls = getTeacherDashboardUrls();

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

function applySectionFilter() {
    const sectionFilter = document.getElementById('section_filter');
    const studentRows = document.querySelectorAll('tr[data-section-id]');
    const noFilterMatchRow = document.getElementById('noFilterMatchRow');

    if (!sectionFilter || studentRows.length === 0) {
        return;
    }

    const selectedValue = sectionFilter.value;
    const searchTerm = (document.getElementById('student_search')?.value || '').toLowerCase().trim();
    let visibleCount = 0;

    studentRows.forEach(row => {
        const rowSection = row.getAttribute('data-section-id');
        const studentName = row.getAttribute('data-student-name') || '';
        const username = row.getAttribute('data-username') || '';

        const sectionMatch = !selectedValue || rowSection === selectedValue;
        const searchMatch = !searchTerm || studentName.includes(searchTerm) || username.includes(searchTerm);
        const isMatch = sectionMatch && searchMatch;

        row.style.display = isMatch ? '' : 'none';
        if (isMatch) {
            visibleCount += 1;
        }
    });

    if (noFilterMatchRow) {
        noFilterMatchRow.style.display = visibleCount === 0 ? '' : 'none';
    }
}

function initStudentFiltering() {
    const sectionFilter = document.getElementById('section_filter');
    if (sectionFilter) {
        sectionFilter.addEventListener('change', applySectionFilter);
        applySectionFilter();
    }

    const studentSearchInput = document.getElementById('student_search');
    if (studentSearchInput) {
        studentSearchInput.addEventListener('input', applySectionFilter);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initOwnPasswordForm();
    initStudentFiltering();
});
