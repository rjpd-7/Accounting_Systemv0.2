/**
 * Admin Dashboard
 * Handles section filtering and student search functionality
 */

function getCsrfToken() {
    const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
    return tokenInput ? tokenInput.value : '';
}

/**
 * Apply Section and Student Search Filters
 */
function applySectionFilter() {
    const sectionFilter = document.getElementById('section_filter');
    const studentRows = document.querySelectorAll('tr[data-section-id]');
    const noFilterMatchRow = document.getElementById('noFilterMatchRow');
    
    if (!sectionFilter || studentRows.length === 0) return;

    const selectedValue = sectionFilter.value;
    const searchTerm = (document.getElementById('student_search')?.value || '').toLowerCase().trim();
    let visibleCount = 0;

    studentRows.forEach(row => {
        const rowSection = row.getAttribute('data-section-id');
        const studentName = row.getAttribute('data-student-name') || '';
        const username = row.getAttribute('data-username') || '';

        // Check section filter
        const sectionMatch = !selectedValue || rowSection === selectedValue;
        
        // Check search filter
        const searchMatch = !searchTerm || 
                           studentName.includes(searchTerm) || 
                           username.includes(searchTerm);

        // Show row only if both filters match
        const isMatch = sectionMatch && searchMatch;
        row.style.display = isMatch ? '' : 'none';
        if (isMatch) visibleCount += 1;
    });

    if (noFilterMatchRow) {
        noFilterMatchRow.style.display = visibleCount === 0 ? '' : 'none';
    }
}

/**
 * Initialize Section Filter
 */
function initSectionFilter() {
    const sectionFilter = document.getElementById('section_filter');
    if (sectionFilter) {
        sectionFilter.addEventListener('change', applySectionFilter);
        applySectionFilter(); // Apply on page load
    }
}

/**
 * Initialize Student Search
 */
function initStudentSearch() {
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
    const form = document.getElementById('adminStudentSectionAssignmentForm');
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
                        'adminStudentSectionAssignmentAlert',
                        data.error || 'Failed to save section assignments.',
                        'error'
                    );
                    return;
                }

                updateStudentSectionBadges(form);
                applySectionFilter();
                showStudentSectionAssignmentAlert(
                    'adminStudentSectionAssignmentAlert',
                    data.message || 'Section assignments saved successfully.',
                    'success'
                );
            })
            .catch(() => {
                showStudentSectionAssignmentAlert(
                    'adminStudentSectionAssignmentAlert',
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

function updateSectionNameAcrossDashboard(sectionId, newName) {
    const normalizedId = String(sectionId);

    document.querySelectorAll('select option').forEach(option => {
        if (String(option.value) === normalizedId) {
            option.textContent = newName;
        }
    });

    document.querySelectorAll('tr[data-section-id]').forEach(row => {
        if (String(row.getAttribute('data-section-id')) !== normalizedId) {
            return;
        }

        const badge = row.querySelector('td:nth-child(3) .badge');
        if (badge) {
            badge.textContent = newName;
        }
    });
}

function addSectionOptionToSelects(sectionId, sectionName) {
    const normalizedId = String(sectionId);
    const selects = [
        document.getElementById('rename_section_id'),
        document.getElementById('from_section_id'),
        document.getElementById('to_section_id'),
        document.getElementById('section_filter')
    ].filter(Boolean);

    selects.forEach(select => {
        const exists = Array.from(select.options).some(option => String(option.value) === normalizedId);
        if (exists) {
            return;
        }

        const option = document.createElement('option');
        option.value = normalizedId;
        option.textContent = sectionName;
        select.appendChild(option);
    });
}

function updateStudentRowsAfterTransfer(fromSectionId, toSectionId) {
    const fromId = String(fromSectionId);
    const toId = String(toSectionId);

    const targetOption = document.querySelector(`#adminStudentSectionAssignmentForm select[name^="section_for_"] option[value="${toId}"]`);
    const targetSectionName = targetOption ? targetOption.textContent.trim() : '';

    document.querySelectorAll('tr[data-section-id]').forEach(row => {
        if (String(row.getAttribute('data-section-id')) !== fromId) {
            return;
        }

        row.setAttribute('data-section-id', toId);

        const assignmentSelect = row.querySelector('select[name^="section_for_"]');
        if (assignmentSelect) {
            assignmentSelect.value = toId;
        }

        const badge = row.querySelector('td:nth-child(3) .badge');
        if (badge && targetSectionName) {
            badge.className = 'badge bg-primary';
            badge.textContent = targetSectionName;
        }
    });
}

function initRenameSectionForm() {
    const form = document.getElementById('adminRenameSectionForm');
    if (!form) {
        return;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton ? submitButton.innerHTML : '';

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = 'Renaming...';
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
                        'adminRenameSectionAlert',
                        data.error || 'Failed to rename section.',
                        'error'
                    );
                    return;
                }

                if (data.section_id && data.new_name) {
                    updateSectionNameAcrossDashboard(data.section_id, data.new_name);
                }

                const newSectionNameInput = document.getElementById('new_section_name');
                if (newSectionNameInput) {
                    newSectionNameInput.value = '';
                }

                showStudentSectionAssignmentAlert(
                    'adminRenameSectionAlert',
                    data.message || 'Section renamed successfully.',
                    'success'
                );
            })
            .catch(() => {
                showStudentSectionAssignmentAlert(
                    'adminRenameSectionAlert',
                    'An unexpected error occurred while renaming the section.',
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

function initCreateSectionForm() {
    const form = document.getElementById('adminCreateSectionForm');
    if (!form) {
        return;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton ? submitButton.innerHTML : '';

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = 'Adding...';
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
                        'adminCreateSectionAlert',
                        data.error || 'Failed to create section.',
                        'error'
                    );
                    return;
                }

                if (data.section_id && data.section_name) {
                    addSectionOptionToSelects(data.section_id, data.section_name);
                }

                form.reset();
                showStudentSectionAssignmentAlert(
                    'adminCreateSectionAlert',
                    data.message || 'Section created successfully.',
                    'success'
                );
            })
            .catch(() => {
                showStudentSectionAssignmentAlert(
                    'adminCreateSectionAlert',
                    'An unexpected error occurred while creating the section.',
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

function initSectionTransferForm() {
    const form = document.getElementById('adminSectionTransferForm');
    if (!form) {
        return;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton ? submitButton.innerHTML : '';

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = 'Changing...';
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
                        'adminSectionTransferAlert',
                        data.error || 'Failed to transfer students.',
                        'error'
                    );
                    return;
                }

                if (data.moved_count > 0 && data.from_section_id && data.to_section_id) {
                    updateStudentRowsAfterTransfer(data.from_section_id, data.to_section_id);
                    applySectionFilter();
                }

                showStudentSectionAssignmentAlert(
                    'adminSectionTransferAlert',
                    data.message || 'Section transfer completed successfully.',
                    'success'
                );
            })
            .catch(() => {
                showStudentSectionAssignmentAlert(
                    'adminSectionTransferAlert',
                    'An unexpected error occurred while transferring students.',
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

// Initialize all dashboard functionality when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initSectionFilter();
    initStudentSearch();
    initCreateSectionForm();
    initRenameSectionForm();
    initSectionTransferForm();
    initStudentSectionAssignmentForm();
});
