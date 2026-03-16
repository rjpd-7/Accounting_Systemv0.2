let studentTaskCache = [];

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

    const clearBtn = document.getElementById('student_task_filter_clear');
    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            if (searchInput) {
                searchInput.value = '';
            }
            if (deadlineInput) {
                deadlineInput.value = '';
            }
            applyStudentTaskFilters();
        });
    }
}

function loadStudentTasks() {
    fetch(window.studentTaskApiUrls.getTasks, {
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

    const filteredTasks = studentTaskCache.filter(task => {
        const teacher = (task.sender || '').toLowerCase();
        const title = (task.title || '').toLowerCase();
        const description = (task.description || '').toLowerCase();

        const matchesSearch = !searchTerm ||
            teacher.includes(searchTerm) ||
            title.includes(searchTerm) ||
            description.includes(searchTerm);

        const matchesDeadline = !deadlineFilter || (task.deadline === deadlineFilter);

        return matchesSearch && matchesDeadline;
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
            (document.getElementById('student_task_deadline_filter')?.value || '').trim()
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
            <div class="message-preview">Deadline: ${task.deadline}${task.is_overdue ? ' • OVERDUE' : ''}</div>
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
                <small class="text-muted">Deadline: ${task.deadline}${task.is_overdue ? ' (Overdue)' : ''}</small>
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

    const modal = new bootstrap.Modal(document.getElementById('studentTaskDetailModal'));
    modal.show();
}

window.viewStudentTask = viewStudentTask;

document.addEventListener('DOMContentLoaded', initializeStudentTasks);
