document.addEventListener('DOMContentLoaded', function () {
    const endpoint = window.dashboardNotificationApiUrl;
    if (!endpoint) return;

    const homeLink = Array.from(document.querySelectorAll('.sidebar a.nav-link')).find(link => {
        const hasHomeIcon = Boolean(link.querySelector('.bi-house'));
        const description = (link.querySelector('.description')?.textContent || '').trim().toLowerCase();
        return hasHomeIcon && description === 'home';
    });

    if (!homeLink) return;

    if (!document.getElementById('sidebarHomeNotificationStyles')) {
        const style = document.createElement('style');
        style.id = 'sidebarHomeNotificationStyles';
        style.textContent = `
            .sidebar .nav-link .icon {
                position: relative;
            }
            .sidebar-home-notification-badge {
                position: absolute;
                top: -6px;
                right: -10px;
                min-width: 18px;
                height: 18px;
                border-radius: 999px;
                font-size: 10px;
                font-weight: 700;
                line-height: 1;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0 5px;
                z-index: 5;
            }
        `;
        document.head.appendChild(style);
    }

    let badge = document.getElementById('sidebarHomeNotificationBadge');
    if (!badge) {
        badge = document.createElement('span');
        badge.id = 'sidebarHomeNotificationBadge';
        badge.className = 'badge bg-danger sidebar-home-notification-badge';
        badge.style.display = 'none';

        const iconNode = homeLink.querySelector('.icon') || homeLink;
        iconNode.appendChild(badge);
    }

    function renderBadge(payload) {
        const totalUnread = Number(payload.total_unread || 0);
        if (totalUnread > 0) {
            badge.textContent = totalUnread > 99 ? '99+' : String(totalUnread);
            badge.style.display = 'inline-flex';
        } else {
            badge.style.display = 'none';
        }
    }

    async function refreshSidebarBadge() {
        try {
            const response = await fetch(endpoint, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            if (!response.ok) return;

            const payload = await response.json();
            renderBadge(payload);
        } catch (error) {
            console.error('Failed to refresh sidebar home notifications:', error);
        }
    }

    refreshSidebarBadge();
    setInterval(refreshSidebarBadge, 15000);
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
            refreshSidebarBadge();
        }
    });
});
