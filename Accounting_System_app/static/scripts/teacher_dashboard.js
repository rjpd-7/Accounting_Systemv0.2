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

function showStudentSectionAssignmentAlert(containerId, message, level) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }

    const alertClass = level === 'success' ? 'alert-success' : 'alert-danger';
    container.className = `alert ${alertClass} py-2 mb-3`;
    container.textContent = message;
    container.style.display = 'block';
}

function updateStudentSectionBadges(form) {
    const rows = form.querySelectorAll('tr[data-section-id]');
    rows.forEach(row => {
        const assignmentSelect = row.querySelector('select[name^="section_for_"]');
        const currentSectionCell = row.querySelector('td:nth-child(3)');
        if (!assignmentSelect || !currentSectionCell) {
            return;
        }

        const selectedValue = assignmentSelect.value;
        const selectedOption = assignmentSelect.options[assignmentSelect.selectedIndex];
        const sectionName = selectedOption ? selectedOption.textContent.trim() : 'Unassigned';

        if (selectedValue) {
            currentSectionCell.innerHTML = `<span class="badge bg-primary">${sectionName}</span>`;
            row.setAttribute('data-section-id', selectedValue);
        } else {
            currentSectionCell.innerHTML = '<span class="badge bg-secondary">Unassigned</span>';
            row.setAttribute('data-section-id', 'unassigned');
        }
    });
}

function initStudentSectionAssignmentForm() {
    const form = document.getElementById('teacherStudentSectionAssignmentForm');
    if (!form) {
        return;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton ? submitButton.innerHTML : '';

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = 'Saving...';
        }

        fetch(form.action, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            },
            body: new FormData(form)
        })
            .then(async response => {
                const data = await response.json().catch(() => ({}));
                return { ok: response.ok, data };
            })
            .then(({ ok, data }) => {
                if (!ok || !data.success) {
                    showStudentSectionAssignmentAlert(
                        'teacherStudentSectionAssignmentAlert',
                        data.error || 'Failed to save section assignments.',
                        'error'
                    );
                    return;
                }

                updateStudentSectionBadges(form);
                applySectionFilter();
                showStudentSectionAssignmentAlert(
                    'teacherStudentSectionAssignmentAlert',
                    data.message || 'Section assignments saved successfully.',
                    'success'
                );
            })
            .catch(() => {
                showStudentSectionAssignmentAlert(
                    'teacherStudentSectionAssignmentAlert',
                    'An unexpected error occurred while saving section assignments.',
                    'error'
                );
            })
            .finally(() => {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalButtonText;
                }
            });
    });
}

function initAccountGroupsForm() {
    const form = document.getElementById('teacherAccountGroupsForm');
    if (!form) {
        return;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton ? submitButton.innerHTML : '';

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = 'Saving...';
        }

        fetch(form.action, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            },
            body: new FormData(form)
        })
            .then(async response => {
                const data = await response.json().catch(() => ({}));
                return { ok: response.ok, data };
            })
            .then(({ ok, data }) => {
                if (!ok || !data.success) {
                    showStudentSectionAssignmentAlert(
                        'teacherAccountGroupsAlert',
                        data.error || 'Failed to save account groups.',
                        'error'
                    );
                    return;
                }

                showStudentSectionAssignmentAlert(
                    'teacherAccountGroupsAlert',
                    data.message || 'Account groups saved successfully.',
                    'success'
                );
            })
            .catch(() => {
                showStudentSectionAssignmentAlert(
                    'teacherAccountGroupsAlert',
                    'An unexpected error occurred while saving account groups.',
                    'error'
                );
            })
            .finally(() => {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalButtonText;
                }
            });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initOwnPasswordForm();
    initStudentFiltering();
    initStudentSectionAssignmentForm();
    initAccountGroupsForm();
});
