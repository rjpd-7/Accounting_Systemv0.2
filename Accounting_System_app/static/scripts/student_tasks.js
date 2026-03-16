let studentTaskCache = [];
let currentStudentTaskId = null;

function getStudentTaskCsrfToken() {
    const tokenInput = document.querySelector('[name="csrfmiddlewaretoken"]');
    return tokenInput ? tokenInput.value : '';
}

function initializeStudentTasks() {
    if (!window.studentTaskApiUrls) {
        return;
    }

    setupStudentTaskFilters();
    loadStudentTasks();
    setInterval(loadStudentTasks, 5000);
}

function setupStudentTaskFilters() {
    const searchInput = document.getElementById('student_task_search');
    if (searchInput) {
        searchInput.addEventListener('input', applyStudentTaskFilters);
    }

    const deadlineInput = document.getElementById('student_task_deadline_filter');
    if (deadlineInput) {
        deadlineInput.addEventListener('change', applyStudentTaskFilters);
    }

    const overdueOnlyInput = document.getElementById('student_task_overdue_only');
    if (overdueOnlyInput) {
        overdueOnlyInput.addEventListener('change', applyStudentTaskFilters);
    }

    const clearBtn = document.getElementById('student_task_filter_clear');
    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            if (searchInput) {
                searchInput.value = '';
            }
            if (deadlineInput) {
                deadlineInput.value = '';
            }
            if (overdueOnlyInput) {
                overdueOnlyInput.checked = false;
            }
            applyStudentTaskFilters();
        });
    }

    const submissionFilesInput = document.getElementById('student_task_submission_files');
    if (submissionFilesInput) {
        submissionFilesInput.addEventListener('change', renderStudentSubmissionFileList);
    }

    const submissionForm = document.getElementById('studentTaskSubmissionForm');
    if (submissionForm) {
        submissionForm.addEventListener('submit', handleStudentTaskSubmission);
    }
}

function loadStudentTasks() {
    return fetch(window.studentTaskApiUrls.getTasks, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to load assigned tasks');
        }
        return response.json();
    })
    .then(data => {
        studentTaskCache = data.received || [];
        applyStudentTaskFilters();
    })
    .catch(error => {
        console.error('Error loading student tasks:', error);
        const container = document.getElementById('student-task-received-list');
        if (container) {
            container.innerHTML = '<div class="text-center text-danger p-4"><p>Failed to load assigned tasks.</p></div>';
        }
    });
}

function applyStudentTaskFilters() {
    const searchTerm = (document.getElementById('student_task_search')?.value || '').toLowerCase().trim();
    const deadlineFilter = (document.getElementById('student_task_deadline_filter')?.value || '').trim();
    const overdueOnly = document.getElementById('student_task_overdue_only')?.checked || false;

    const filteredTasks = studentTaskCache.filter(task => {
        const teacher = (task.sender || '').toLowerCase();
        const title = (task.title || '').toLowerCase();
        const description = (task.description || '').toLowerCase();

        const matchesSearch = !searchTerm ||
            teacher.includes(searchTerm) ||
            title.includes(searchTerm) ||
            description.includes(searchTerm);

        const matchesDeadline = !deadlineFilter || (task.deadline === deadlineFilter);
        const matchesOverdue = !overdueOnly || Boolean(task.is_overdue);

        return matchesSearch && matchesDeadline && matchesOverdue;
    });

    displayStudentTasks(filteredTasks);
}

function displayStudentTasks(tasks) {
    const container = document.getElementById('student-task-received-list');
    if (!container) {
        return;
    }

    if (!tasks.length) {
        const hasFilters = Boolean(
            (document.getElementById('student_task_search')?.value || '').trim() ||
            (document.getElementById('student_task_deadline_filter')?.value || '').trim() ||
            (document.getElementById('student_task_overdue_only')?.checked || false)
        );

        container.innerHTML = hasFilters
            ? '<div class="text-center text-muted p-4"><p>No tasks match your filters.</p></div>'
            : '<div class="text-center text-muted p-4"><p>No assigned tasks yet.</p></div>';
        return;
    }

    container.innerHTML = tasks.map(task => `
        <div class="message-item ${task.is_overdue ? 'unread' : ''}" onclick="viewStudentTask(${task.id})">
            <div class="message-header">
                <strong>From: ${task.sender}</strong>
                <small class="text-muted">${task.created_at}</small>
            </div>
            <div class="message-subject">${task.title}</div>
            <div class="message-preview">Deadline: ${task.deadline}${task.has_submission ? ' • SUBMITTED' : (task.is_overdue ? ' • OVERDUE' : '')}</div>
            ${task.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${task.attachments.length} file(s)</div>` : ''}
        </div>
    `).join('');
}

function viewStudentTask(taskId) {
    const task = studentTaskCache.find(item => item.id === taskId);
    if (!task) {
        return;
    }

    const detailsContainer = document.getElementById('student-task-detail-content');
    if (!detailsContainer) {
        return;
    }

    currentStudentTaskId = task.id;

    const attachmentsHtml = task.attachments.length
        ? `
            <div class="mt-3">
                <strong>Attachments:</strong>
                <ul class="list-unstyled mt-2">
                    ${task.attachments.map(att => `<li><i class="bi bi-file"></i> <a href="${att.download_url || att.url}" class="ms-2">${att.filename}</a></li>`).join('')}
                </ul>
            </div>
        `
        : '';

    detailsContainer.innerHTML = `
        <div>
            <div class="mb-3 pb-3 border-bottom">
                <p class="mb-1">From: <strong>${task.sender}</strong></p>
                <small class="text-muted">Created: ${task.created_at}</small><br>
                <small class="text-muted">Deadline: ${task.deadline}${task.has_submission ? ' (Submitted)' : (task.is_overdue ? ' (Overdue)' : '')}</small>
            </div>
            <div class="mb-3">
                <h6>${task.title}</h6>
            </div>
            <div class="mb-3">
                <p style="white-space: pre-wrap; word-wrap: break-word;">${task.description}</p>
            </div>
            ${attachmentsHtml}
        </div>
    `;

    renderStudentSubmissionSection(task);

    const modal = new bootstrap.Modal(document.getElementById('studentTaskDetailModal'));
    modal.show();
}

function renderStudentSubmissionSection(task) {
    const statusContainer = document.getElementById('student-task-submission-status');
    const submissionForm = document.getElementById('studentTaskSubmissionForm');
    const commentInput = document.getElementById('student_task_submission_comment');
    const filesInput = document.getElementById('student_task_submission_files');
    const fileList = document.getElementById('student-task-submission-file-list');

    if (!statusContainer || !submissionForm || !commentInput || !filesInput || !fileList) {
        return;
    }

    commentInput.value = '';
    filesInput.value = '';
    fileList.innerHTML = '';

    if (task.has_submission && task.submission) {
        const submissionAttachments = task.submission.attachments || [];
        const submissionAttachmentsHtml = submissionAttachments.length
            ? `
                <div class="mt-2">
                    <strong>Submitted Files:</strong>
                    <ul class="list-unstyled mt-2 mb-0">
                        ${submissionAttachments.map(att => `<li><i class="bi bi-file-earmark-check"></i> <a href="${att.download_url || att.url}" class="ms-2">${att.filename}</a></li>`).join('')}
                    </ul>
                </div>
            `
            : '';

        statusContainer.innerHTML = `
            <div class="alert alert-success mb-0">
                <strong>Submitted:</strong> ${task.submission.submitted_at}
                ${task.submission.comment ? `<br><strong>Your Note:</strong> ${task.submission.comment}` : ''}
                ${submissionAttachmentsHtml}
            </div>
        `;
        submissionForm.style.display = 'none';
        return;
    }

    statusContainer.innerHTML = '<div class="alert alert-info mb-0">Upload your completed files, then click <strong>Turn In Work</strong>.</div>';
    submissionForm.style.display = '';
}

function renderStudentSubmissionFileList() {
    const filesInput = document.getElementById('student_task_submission_files');
    const fileList = document.getElementById('student-task-submission-file-list');
    if (!filesInput || !fileList) {
        return;
    }

    if (!filesInput.files.length) {
        fileList.innerHTML = '';
        return;
    }

    fileList.innerHTML = '<ul class="list-unstyled mb-0">' +
        Array.from(filesInput.files).map(file => `<li><i class="bi bi-file"></i> ${file.name}</li>`).join('') +
        '</ul>';
}

function handleStudentTaskSubmission(event) {
    event.preventDefault();

    if (!currentStudentTaskId) {
        return;
    }

    const filesInput = document.getElementById('student_task_submission_files');
    const commentInput = document.getElementById('student_task_submission_comment');
    const submitBtn = document.getElementById('student_task_turn_in_btn');
    const statusContainer = document.getElementById('student-task-submission-status');

    if (!filesInput || !submitBtn || !statusContainer) {
        return;
    }

    if (!filesInput.files.length) {
        statusContainer.innerHTML = '<div class="alert alert-warning mb-0">Please attach at least one file before turning in.</div>';
        return;
    }

    const formData = new FormData();
    if (commentInput && commentInput.value.trim()) {
        formData.append('comment', commentInput.value.trim());
    }
    for (let file of filesInput.files) {
        formData.append('submission_files', file);
    }

    const submitUrl = window.studentTaskApiUrls.submitTask.replace('0', currentStudentTaskId);
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...';

    fetch(submitUrl, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getStudentTaskCsrfToken()
        }
    })
    .then(async response => {
        let data = {};
        try {
            data = await response.json();
        } catch (err) {
            data = { error: 'Unexpected server response.' };
        }
        if (!response.ok) {
            throw new Error(data.error || `Request failed (${response.status})`);
        }
        return data;
    })
    .then(() => {
        return loadStudentTasks().then(() => {
            const refreshedTask = studentTaskCache.find(item => item.id === currentStudentTaskId);
            if (refreshedTask) {
                viewStudentTask(refreshedTask.id);
            }
        });
    })
    .catch(error => {
        statusContainer.innerHTML = `<div class="alert alert-danger mb-0">${error.message}</div>`;
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Turn In Work';
    });
}

window.viewStudentTask = viewStudentTask;

document.addEventListener('DOMContentLoaded', initializeStudentTasks);
