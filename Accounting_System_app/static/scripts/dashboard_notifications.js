document.addEventListener('DOMContentLoaded', function () {
    const button = document.getElementById('dashboardNotificationBtn');
    const badge = document.getElementById('dashboardNotificationBadge');
    const listContainer = document.getElementById('dashboardNotificationList');
    const emptyState = document.getElementById('dashboardNotificationEmpty');
    const endpoint = window.dashboardNotificationApiUrl;

    if (!button || !badge || !endpoint) {
        return;
    }

    function getTargetElement(target) {
        if (target === 'messages') {
            return document.getElementById('dashboard-messaging-section');
        }
        if (target === 'tasks') {
            return document.getElementById('task-management-section') || document.getElementById('student-tasks-section');
        }
        return null;
    }

    function renderNotificationList(payload) {
        if (!listContainer || !emptyState) return;

        const notifications = Array.isArray(payload.latest_notifications) ? payload.latest_notifications : [];
        if (notifications.length === 0) {
            listContainer.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }

        emptyState.style.display = 'none';
        listContainer.innerHTML = notifications.map(item => {
            const iconClass = item.type === 'task' ? 'bi-list-check' : 'bi-chat-dots';
            const title = String(item.title || 'Notification');
            const subtitle = String(item.subtitle || '');
            const createdAt = String(item.created_at || '');
            const target = String(item.target || 'messages');
            const label = String(item.label || 'Notification');

            return `
                <button type="button" class="dropdown-item dashboard-notification-item py-2" data-target="${target}">
                    <div class="d-flex gap-2 align-items-start">
                        <i class="bi ${iconClass} mt-1"></i>
                        <div class="flex-grow-1 text-start">
                            <div class="fw-semibold">${label}: ${title}</div>
                            <small>${subtitle}</small>
                            <small>${createdAt}</small>
                        </div>
                    </div>
                </button>
            `;
        }).join('');
    }

    function renderNotificationState(payload) {
        const unreadMessages = Number(payload.unread_messages || 0);
        const pendingTasks = Number(payload.pending_tasks || 0);
        const totalUnread = Number(payload.total_unread || 0);

        if (totalUnread > 0) {
            badge.textContent = totalUnread > 99 ? '99+' : String(totalUnread);
            badge.style.display = 'inline-flex';
            button.classList.add('has-notifications');
        } else {
            badge.style.display = 'none';
            button.classList.remove('has-notifications');
        }

        const summary = `${unreadMessages} unread message(s), ${pendingTasks} pending task(s)`;
        button.setAttribute('title', summary);
        button.setAttribute('aria-label', `Notifications: ${summary}`);

        renderNotificationList(payload);
    }

    async function refreshNotifications() {
        try {
            const response = await fetch(endpoint, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) return;
            const payload = await response.json();
            renderNotificationState(payload);
        } catch (error) {
            console.error('Failed to refresh dashboard notifications:', error);
        }
    }

    if (listContainer) {
        listContainer.addEventListener('click', function (event) {
            const item = event.target.closest('.dashboard-notification-item');
            if (!item) return;

            const target = item.getAttribute('data-target') || 'messages';
            const targetElement = getTargetElement(target);
            if (targetElement) {
                targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

            if (window.bootstrap && window.bootstrap.Dropdown) {
                const dropdownInstance = window.bootstrap.Dropdown.getOrCreateInstance(button);
                dropdownInstance.hide();
            }
        });
    }

    refreshNotifications();
    setInterval(refreshNotifications, 15000);
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
            refreshNotifications();
        }
    });
});
