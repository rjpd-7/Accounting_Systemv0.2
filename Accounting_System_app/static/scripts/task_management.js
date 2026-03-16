let taskStudents = [];
let taskCache = { sent: [], received: [] };
let taskSelectedRecipientIds = new Set();

function getCurrentDateTimeLocalString() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function getTaskCsrfToken() {
    const tokenInput = document.querySelector('[name="csrfmiddlewaretoken"]');
    return tokenInput ? tokenInput.value : '';
}

function initializeTaskManagement() {
    if (!window.taskApiUrls) {
        return;
    }

    const taskDeadlineInput = document.getElementById('task_deadline');
    if (taskDeadlineInput) {
        taskDeadlineInput.min = getCurrentDateTimeLocalString();
    }

    setupTaskEventListeners();
    loadTeacherStudentsForTasks();
    loadTasks();
    setInterval(loadTasks, 5000);
}

function setupTaskEventListeners() {
    const taskForm = document.getElementById('taskForm');
    if (taskForm) {
        taskForm.addEventListener('submit', handleTaskSubmit);
    }

    const attachmentsInput = document.getElementById('task_attachments');
    if (attachmentsInput) {
        attachmentsInput.addEventListener('change', handleTaskFileSelection);
    }

    const selectAllBtn = document.getElementById('task_select_all_recipients');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function(e) {
            e.preventDefault();
            setAllTaskRecipients(true);
        });
    }

    const clearAllBtn = document.getElementById('task_clear_all_recipients');
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', function(e) {
            e.preventDefault();
            setAllTaskRecipients(false);
        });
    }

    const sectionFilter = document.getElementById('task_section_filter');
    if (sectionFilter) {
        sectionFilter.addEventListener('change', applyTaskRecipientFilter);
    }

    const deleteTaskBtn = document.getElementById('deleteTaskBtn');
    if (deleteTaskBtn) {
        deleteTaskBtn.addEventListener('click', handleDeleteTask);
    }
}

function loadTeacherStudentsForTasks() {
    const container = document.getElementById('task_recipient_list');
    if (!container) {
        return;
    }

    fetch(window.taskApiUrls.getStudents, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to load students');
        }
        return response.json();
    })
    .then(data => {
        taskStudents = Array.isArray(data.students) ? data.students : [];
        populateTaskSectionFilterOptions();
        applyTaskRecipientFilter();
    })
    .catch(error => {
        container.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
    });
}

function populateTaskSectionFilterOptions() {
    const sectionFilter = document.getElementById('task_section_filter');
    if (!sectionFilter) {
        return;
    }

    const uniqueSections = new Set();
    taskStudents.forEach(student => {
        if (student.section) {
            uniqueSections.add(student.section);
        }
    });

    sectionFilter.innerHTML = '<option value="">All Sections</option>';
    Array.from(uniqueSections)
        .sort((a, b) => a.localeCompare(b))
        .forEach(section => {
            const option = document.createElement('option');
            option.value = section;
            option.textContent = section;
            sectionFilter.appendChild(option);
        });
}

function applyTaskRecipientFilter() {
    const sectionFilter = document.getElementById('task_section_filter');
    const selectedSection = sectionFilter ? sectionFilter.value : '';

    const filteredStudents = taskStudents.filter(student => {
        if (!selectedSection) {
            return true;
        }
        return (student.section || '') === selectedSection;
    });

    renderTaskRecipientCheckboxes(filteredStudents);
}

function renderTaskRecipientCheckboxes(studentsToRender) {
    const container = document.getElementById('task_recipient_list');
    if (!container) {
        return;
    }

    const students = Array.isArray(studentsToRender) ? studentsToRender : taskStudents;

    if (!students.length) {
        container.innerHTML = taskStudents.length
            ? '<div class="text-muted">No students found for the selected section.</div>'
            : '<div class="text-muted">No students available in your managed sections.</div>';
        return;
    }

    container.innerHTML = students.map((student, index) => `
        <div class="form-check mb-1">
            <input class="form-check-input task-recipient-checkbox" type="checkbox" value="${student.id}" id="task_recipient_${student.id}_${index}" ${taskSelectedRecipientIds.has(String(student.id)) ? 'checked' : ''}>
            <label class="form-check-label" for="task_recipient_${student.id}_${index}">
                ${student.full_name} (${student.section || 'No Section'})
            </label>
        </div>
    `).join('');

    container.querySelectorAll('.task-recipient-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const value = String(this.value);
            if (this.checked) {
                taskSelectedRecipientIds.add(value);
            } else {
                taskSelectedRecipientIds.delete(value);
            }
        });
    });
}

function getSelectedTaskRecipientIds() {
    return Array.from(taskSelectedRecipientIds);
}

function setAllTaskRecipients(checked) {
    const checkboxes = document.querySelectorAll('input.task-recipient-checkbox');
    if (!checked) {
        taskSelectedRecipientIds.clear();
    }

    checkboxes.forEach(el => {
        el.checked = checked;
        const value = String(el.value);
        if (checked) {
            taskSelectedRecipientIds.add(value);
        }
    });
}

function handleTaskFileSelection(event) {
    const files = event.target.files;
    const fileList = document.getElementById('task-file-list');

    if (!fileList) {
        return;
    }

    if (!files.length) {
        fileList.innerHTML = '';
        return;
    }

    fileList.innerHTML = '<ul class="list-unstyled mb-0">' +
        Array.from(files).map(file => `<li><i class="bi bi-file"></i> ${file.name}</li>`).join('') +
        '</ul>';
}

function handleTaskSubmit(event) {
    event.preventDefault();

    const selectedRecipients = getSelectedTaskRecipientIds();
    if (!selectedRecipients.length) {
        showTaskAlert('Please select at least one student.', 'warning');
        return;
    }

    const title = document.getElementById('task_title')?.value.trim() || '';
    const description = document.getElementById('task_description')?.value.trim() || '';
    const deadline = document.getElementById('task_deadline')?.value || '';

    if (!title || !description || !deadline) {
        showTaskAlert('Title, instructions, and deadline are required.', 'warning');
        return;
    }

    const formData = new FormData();
    selectedRecipients.forEach(id => formData.append('recipients', id));
    formData.append('title', title);
    formData.append('description', description);
    formData.append('deadline', deadline);

    const attachmentsInput = document.getElementById('task_attachments');
    if (attachmentsInput && attachmentsInput.files.length > 0) {
        for (let file of attachmentsInput.files) {
            formData.append('attachments', file);
        }
    }

    const submitBtn = document.getElementById('sendTaskBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';
    }

    fetch(window.taskApiUrls.sendTask, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getTaskCsrfToken()
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
    .then(data => {
        const form = document.getElementById('taskForm');
        if (form) {
            form.reset();
        }

        taskSelectedRecipientIds.clear();
        applyTaskRecipientFilter();

        document.getElementById('task-file-list').innerHTML = '';

        const modal = bootstrap.Modal.getInstance(document.getElementById('sendTaskModal'));
        if (modal) {
            modal.hide();
        }

        showTaskAlert(data.message || 'Task sent successfully.', 'success');
        loadTasks();
    })
    .catch(error => {
        showTaskAlert('Error sending task: ' + error.message, 'danger');
    })
    .finally(() => {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Send Task';
        }
    });
}

function loadTasks() {
    fetch(window.taskApiUrls.getTasks, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to load tasks');
        }
        return response.json();
    })
    .then(data => {
        taskCache.sent = data.sent || [];
        taskCache.received = data.received || [];
        displaySentTasks(taskCache.sent);
        displayReceivedTasks(taskCache.received);
    })
    .catch(error => {
        console.error('Error loading tasks:', error);
    });
}

function displaySentTasks(tasks) {
    const container = document.getElementById('task-sent-list');
    if (!container) {
        return;
    }

    if (!tasks.length) {
        container.innerHTML = '<div class="text-center text-muted p-4"><p>No sent tasks</p></div>';
        return;
    }

    container.innerHTML = tasks.map(task => `
        <div class="message-item" onclick="viewTask('sent', ${task.id})">
            <div class="message-header">
                <strong>To: ${task.recipient}</strong>
                <small class="text-muted">${task.created_at}</small>
            </div>
            <div class="message-subject">${task.title}</div>
            <div class="message-preview">Deadline: ${task.deadline}${task.all_submitted ? ' • ALL SUBMITTED' : ` • ${task.submitted_count}/${task.recipient_count} SUBMITTED`}</div>
            ${task.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${task.attachments.length} file(s)</div>` : ''}
        </div>
    `).join('');
}

function displayReceivedTasks(tasks) {
    const container = document.getElementById('task-received-list');
    if (!container) {
        return;
    }

    if (!tasks.length) {
        container.innerHTML = '<div class="text-center text-muted p-4"><p>No received tasks</p></div>';
        return;
    }

    container.innerHTML = tasks.map(task => `
        <div class="message-item ${task.is_overdue ? 'unread' : ''}" onclick="viewTask('received', ${task.id})">
            <div class="message-header">
                <strong>From: ${task.sender}</strong>
                <small class="text-muted">${task.created_at}</small>
            </div>
            <div class="message-subject">${task.title}</div>
            <div class="message-preview">Deadline: ${task.deadline}${task.is_overdue ? ' • OVERDUE' : ''}</div>
            ${task.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${task.attachments.length} file(s)</div>` : ''}
        </div>
    `).join('');
}

function viewTask(type, taskId) {
    const source = type === 'sent' ? taskCache.sent : taskCache.received;
    const task = source.find(item => item.id === taskId);
    if (!task) {
        return;
    }

    const detailsContainer = document.getElementById('task-detail-content');
    if (!detailsContainer) {
        return;
    }

    const directionLine = task.type === 'received'
        ? `From: <strong>${task.sender}</strong>`
        : `To: <strong>${task.recipient}</strong>`;

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

    let recipientsStatusHtml = '';
    if (type === 'sent' && Array.isArray(task.recipients) && task.recipients.length > 0) {
        recipientsStatusHtml = `
            <div class="mt-4">
                <h6>Student Submission Status</h6>
                <div class="table-responsive">
                    <table class="table table-sm align-middle mb-0">
                        <thead>
                            <tr>
                                <th>Student</th>
                                <th>Status</th>
                                <th>Submitted At</th>
                                <th>Files</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${task.recipients.map(recipient => `
                                <tr>
                                    <td>${recipient.student_name}</td>
                                    <td>${recipient.is_submitted ? '<span class="badge bg-success">Submitted</span>' : '<span class="badge bg-secondary">Pending</span>'}</td>
                                    <td>${recipient.submitted_at || '<span class="text-muted">Not yet submitted</span>'}</td>
                                    <td>
                                        ${recipient.is_submitted
                                            ? ((recipient.submission_attachments && recipient.submission_attachments.length > 0)
                                                ? recipient.submission_attachments.map(att => `<div><a href="${att.download_url}" target="_blank" rel="noopener">${att.filename}</a></div>`).join('')
                                                : '<span class="text-muted">No files</span>')
                                            : '<span class="text-muted">-</span>'}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    detailsContainer.innerHTML = `
        <div>
            <div class="mb-3 pb-3 border-bottom">
                <p class="mb-1">${directionLine}</p>
                <small class="text-muted">Created: ${task.created_at}</small><br>
                <small class="text-muted">Deadline: ${task.deadline}${task.is_overdue ? ' (Overdue)' : ''}</small>
                ${type === 'sent' ? `<br><small class="text-muted">Submission Summary: ${task.submitted_count}/${task.recipient_count} submitted</small>` : ''}
            </div>
            <div class="mb-3">
                <h6>${task.title}</h6>
            </div>
            <div class="mb-3">
                <p style="white-space: pre-wrap; word-wrap: break-word;">${task.description}</p>
            </div>
            ${attachmentsHtml}
            ${recipientsStatusHtml}
        </div>
    `;

    const deleteBtn = document.getElementById('deleteTaskBtn');
    if (deleteBtn) {
        deleteBtn.setAttribute('data-task-id', String(task.id));
    }

    const modal = new bootstrap.Modal(document.getElementById('taskDetailModal'));
    modal.show();
}

window.viewTask = viewTask;

function handleDeleteTask() {
    const taskId = this.getAttribute('data-task-id');
    if (!taskId) {
        return;
    }

    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }

    const deleteUrl = window.taskApiUrls.deleteTask.replace('0', taskId);
    fetch(deleteUrl, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getTaskCsrfToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const modal = bootstrap.Modal.getInstance(document.getElementById('taskDetailModal'));
            if (modal) {
                modal.hide();
            }
            showTaskAlert('Task deleted.', 'success');
            loadTasks();
            return;
        }
        showTaskAlert(data.error || 'Failed to delete task.', 'danger');
    })
    .catch(error => {
        showTaskAlert('Error deleting task: ' + error.message, 'danger');
    });
}

function showTaskAlert(message, type) {
    const container = document.querySelector('#task-sent-list')?.closest('.messaging-container');
    if (!container) {
        return;
    }

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`;

    container.insertBefore(alertDiv, container.firstChild);
    setTimeout(() => alertDiv.remove(), 4000);
}

document.addEventListener('DOMContentLoaded', initializeTaskManagement);
