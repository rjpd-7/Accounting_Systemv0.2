// Messaging System JavaScript (Messenger-style thread view)

let allConnectedRecipients = [];
let archiveMessagesCache = [];
let archiveLoadedOnce = false;
let latestMessagesPayload = { received: [], sent: [], archive: [], unread_count: 0 };
let activeThreadUserId = null;
let activeThreadName = '';

function getPdfPreviewAttrs(filename, fileUrl) {
    const source = String(filename || fileUrl || '').toLowerCase();
    return source.endsWith('.pdf') ? ' target="_blank" rel="noopener"' : '';
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function toEpoch(dateText) {
    if (!dateText) return 0;
    const normalized = String(dateText).replace(' ', 'T');
    const parsed = Date.parse(normalized);
    return Number.isNaN(parsed) ? 0 : parsed;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

document.addEventListener('DOMContentLoaded', function () {
    initializeMessaging();
    setInterval(refreshMessages, 5000);
});

function initializeMessaging() {
    loadAllUsers();
    loadMessages();
    setupEventListeners();
}

function loadAllUsers() {
    const recipientContainer = document.getElementById('recipient_list');
    const roleFilter = document.getElementById('recipient_role_filter');
    const sectionFilter = document.getElementById('recipient_section_filter');
    if (!recipientContainer) return;

    fetch(window.messagingApiUrls.getUsers, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
        .then(response => {
            if (!response.ok) throw new Error('Failed to load users');
            return response.json();
        })
        .then(data => {
            allConnectedRecipients = Array.isArray(data.users) ? data.users : [];
            if (roleFilter) roleFilter.value = '';
            if (sectionFilter) sectionFilter.value = '';

            populateSectionFilterOptions(allConnectedRecipients, sectionFilter);
            renderRecipientCheckboxes(recipientContainer, allConnectedRecipients);
        })
        .catch(error => {
            console.error('Error loading users:', error);
            recipientContainer.innerHTML = '<div class="alert alert-danger">Error loading recipients: ' + escapeHtml(error.message) + '</div>';
        });
}

function renderRecipientCheckboxes(container, recipients) {
    container.innerHTML = '';

    if (!recipients.length) {
        container.innerHTML = '<div class="text-muted">No recipients available.</div>';
        return;
    }

    recipients.forEach((user, index) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'form-check mb-1';

        const input = document.createElement('input');
        input.className = 'form-check-input recipient-checkbox';
        input.type = 'checkbox';
        input.value = user.id;
        input.id = `recipient_${user.id}_${index}`;

        const label = document.createElement('label');
        label.className = 'form-check-label';
        label.setAttribute('for', input.id);

        const roleLabel = user.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : 'User';
        const sectionLabel = Array.isArray(user.sections) && user.sections.length > 0
            ? ` | ${user.sections.join(', ')}`
            : '';

        label.textContent = `${user.full_name} (${roleLabel}${sectionLabel})`;

        wrapper.appendChild(input);
        wrapper.appendChild(label);
        container.appendChild(wrapper);
    });
}

function populateSectionFilterOptions(users, sectionFilter) {
    if (!sectionFilter) return;

    const uniqueSections = new Set();
    users.forEach(user => {
        if (Array.isArray(user.sections)) {
            user.sections.forEach(sectionName => {
                if (sectionName) uniqueSections.add(sectionName);
            });
        }
    });

    sectionFilter.innerHTML = '<option value="">All Sections</option>';
    Array.from(uniqueSections)
        .sort((a, b) => a.localeCompare(b))
        .forEach(sectionName => {
            const option = document.createElement('option');
            option.value = sectionName;
            option.textContent = sectionName;
            sectionFilter.appendChild(option);
        });
}

function applyRecipientFilters() {
    const recipientContainer = document.getElementById('recipient_list');
    const roleFilter = document.getElementById('recipient_role_filter');
    const sectionFilter = document.getElementById('recipient_section_filter');
    if (!recipientContainer) return;

    const selectedRole = roleFilter ? roleFilter.value : '';
    const selectedSection = sectionFilter ? sectionFilter.value : '';

    const filteredUsers = allConnectedRecipients.filter(user => {
        const roleMatch = !selectedRole || user.role === selectedRole;
        const sectionMatch = !selectedSection || (Array.isArray(user.sections) && user.sections.includes(selectedSection));
        return roleMatch && sectionMatch;
    });

    renderRecipientCheckboxes(recipientContainer, filteredUsers);
}

function getSelectedRecipientIds() {
    return Array.from(document.querySelectorAll('input.recipient-checkbox:checked')).map(el => el.value);
}

function setAllRecipients(checked) {
    document.querySelectorAll('input.recipient-checkbox').forEach(el => {
        el.checked = checked;
    });
}

function loadMessages() {
    fetch(window.messagingApiUrls.getMessages, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(response => {
            if (!response.ok) throw new Error('Failed to load messages');
            return response.json();
        })
        .then(data => {
            latestMessagesPayload = {
                received: data.received || [],
                sent: data.sent || [],
                archive: data.archive || [],
                unread_count: data.unread_count || 0,
            };

            displayReceivedMessages(latestMessagesPayload.received);
            displaySentMessages(latestMessagesPayload.sent);
            updateUnreadCount(latestMessagesPayload.unread_count);

            if (window.reapplySearchFilters) {
                window.reapplySearchFilters();
            }

            if (activeThreadUserId) {
                renderActiveThread();
                highlightSelectedConversation(activeThreadUserId);
            }
        })
        .catch(error => console.error('Error loading messages:', error));
}

function refreshMessages() {
    loadMessages();
    updateUnreadBadge();
}

function displayReceivedMessages(messages) {
    const container = document.getElementById('received-messages-list');
    if (!container) return;

    if (messages.length === 0) {
        container.innerHTML = '<div class="text-center text-muted p-4"><p>No received messages</p></div>';
        return;
    }

    container.innerHTML = messages.map(msg => `
        <div class="message-item ${msg.is_read ? '' : 'unread'}"
            data-message-id="${msg.id}"
            data-other-user-id="${msg.sender_id}"
            data-other-user-name="${escapeHtml(msg.sender || '')}"
            data-sender="${escapeHtml((msg.sender || '').toLowerCase())}"
            data-subject="${escapeHtml((msg.subject || 'No Subject').toLowerCase())}"
            data-content="${escapeHtml((msg.content || '').toLowerCase())}">
            <div class="message-header">
                <strong>${escapeHtml(msg.sender)}</strong>
                <small class="text-muted">${escapeHtml(msg.created_at)}</small>
            </div>
            <div class="message-subject">${escapeHtml(msg.subject)}</div>
            <div class="message-preview">${escapeHtml((msg.content || '').substring(0, 80))}${(msg.content || '').length > 80 ? '...' : ''}</div>
            ${msg.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${msg.attachments.length} file(s)</div>` : ''}
        </div>
    `).join('');
}

function displaySentMessages(messages) {
    const container = document.getElementById('sent-messages-list');
    if (!container) return;

    if (messages.length === 0) {
        container.innerHTML = '<div class="text-center text-muted p-4"><p>No sent messages</p></div>';
        return;
    }

    container.innerHTML = messages.map(msg => `
        <div class="message-item"
            data-message-id="${msg.id}"
            data-other-user-id="${msg.recipient_id}"
            data-other-user-name="${escapeHtml(msg.recipient || '')}"
            data-recipient="${escapeHtml((msg.recipient || '').toLowerCase())}"
            data-subject="${escapeHtml((msg.subject || 'No Subject').toLowerCase())}"
            data-content="${escapeHtml((msg.content || '').toLowerCase())}">
            <div class="message-header">
                <strong>To: ${escapeHtml(msg.recipient)}</strong>
                <small class="text-muted">${escapeHtml(msg.created_at)}</small>
            </div>
            <div class="message-subject">${escapeHtml(msg.subject)}</div>
            <div class="message-preview">${escapeHtml((msg.content || '').substring(0, 80))}${(msg.content || '').length > 80 ? '...' : ''}</div>
            ${msg.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${msg.attachments.length} file(s)</div>` : ''}
        </div>
    `).join('');
}

function getAllThreadMessages() {
    return [...(latestMessagesPayload.received || []), ...(latestMessagesPayload.sent || [])]
        .sort((a, b) => toEpoch(a.created_at) - toEpoch(b.created_at));
}

function getThreadMessagesByUser(userId) {
    return getAllThreadMessages().filter(msg => msg.sender_id === userId || msg.recipient_id === userId);
}

function renderActiveThread() {
    const content = document.getElementById('messenger-conversation-content');
    const title = document.getElementById('messenger-preview-title');
    const meta = document.getElementById('messenger-preview-meta');
    const inlineReplyInput = document.getElementById('inlineReplyContent');
    const inlineReplySendBtn = document.getElementById('inlineReplySendBtn');

    if (!content || !title || !meta || !inlineReplyInput || !inlineReplySendBtn) return;

    if (!activeThreadUserId) {
        title.textContent = 'Select a conversation';
        meta.textContent = 'Choose a user from Inbox or Sent to open the full thread.';
        content.innerHTML = `
            <div class="messenger-placeholder text-center text-muted">
                <i class="bi bi-chat-left-text"></i>
                <p class="mb-1">No conversation selected yet.</p>
                <small>Select a message on the left to open a persistent thread.</small>
            </div>
        `;
        inlineReplyInput.disabled = true;
        inlineReplySendBtn.disabled = true;
        return;
    }

    const threadMessages = getThreadMessagesByUser(activeThreadUserId);
    title.textContent = activeThreadName || 'Conversation';
    meta.textContent = `${threadMessages.length} message(s)`;

    if (!threadMessages.length) {
        content.innerHTML = '<div class="messenger-placeholder text-center text-muted"><p class="mb-0">No messages in this thread yet.</p></div>';
    } else {
        let previousDate = '';
        const rows = threadMessages.map(msg => {
            const dayToken = (msg.created_at || '').split(' ')[0] || '';
            const dayDivider = dayToken && dayToken !== previousDate
                ? `<div class="messenger-day-divider">${escapeHtml(dayToken)}</div>`
                : '';
            previousDate = dayToken;

            const isOutgoing = msg.type === 'sent';
            const attachmentsHtml = Array.isArray(msg.attachments) && msg.attachments.length > 0
                ? `<div class="message-bubble-attachments">${msg.attachments.map(att => `
                    <a href="${att.download_url || att.url}"${getPdfPreviewAttrs(att.filename, att.download_url || att.url)}>
                        <i class="bi bi-paperclip"></i> ${escapeHtml(att.filename)} (${escapeHtml(formatFileSize(att.file_size))})
                    </a>
                `).join('')}</div>`
                : '';

            return `
                ${dayDivider}
                <div class="message-row ${isOutgoing ? 'outgoing' : 'incoming'}">
                    <div class="message-bubble" data-message-id="${msg.id}">
                        ${msg.subject && msg.subject !== 'No Subject' ? `<div class="message-bubble-subject">${escapeHtml(msg.subject)}</div>` : ''}
                        <div>${escapeHtml(msg.content)}</div>
                        ${attachmentsHtml}
                        <div class="message-bubble-meta">${escapeHtml(msg.created_at)}</div>
                    </div>
                </div>
            `;
        }).join('');

        content.innerHTML = `<div class="messenger-thread">${rows}</div>`;
        content.scrollTop = content.scrollHeight;
    }

    inlineReplyInput.disabled = false;
    inlineReplySendBtn.disabled = false;
}

function highlightSelectedConversation(userId) {
    document.querySelectorAll('.messages-list .message-item.active').forEach(item => item.classList.remove('active'));
    const selector = `.messages-list .message-item[data-other-user-id="${userId}"]`;
    const firstMatch = document.querySelector(selector);
    if (firstMatch) {
        firstMatch.classList.add('active');
    }
}

function selectConversationFromElement(messageElement) {
    const otherUserId = Number(messageElement.getAttribute('data-other-user-id'));
    const otherUserName = messageElement.getAttribute('data-other-user-name') || 'Conversation';

    if (!otherUserId) return;
    activeThreadUserId = otherUserId;
    activeThreadName = otherUserName;

    highlightSelectedConversation(otherUserId);
    renderActiveThread();
}

function displayArchiveMessages(messages) {
    const container = document.getElementById('archive-messages-list');
    if (!container) return;

    if (messages.length === 0) {
        container.innerHTML = '<div class="text-center text-muted p-4"><p>No archived messages</p></div>';
        return;
    }

    container.innerHTML = messages.map(msg => {
        const directionLabel = msg.type === 'received' ? `From: ${escapeHtml(msg.sender)}` : `To: ${escapeHtml(msg.recipient)}`;
        return `
            <div class="message-item ${msg.type === 'received' && !msg.is_read ? 'unread' : ''}" onclick="viewMessage('archive', ${msg.id})"
                data-sender="${escapeHtml((msg.sender || '').toLowerCase())}"
                data-recipient="${escapeHtml((msg.recipient || '').toLowerCase())}"
                data-subject="${escapeHtml((msg.subject || '').toLowerCase())}"
                data-content="${escapeHtml((msg.content || '').toLowerCase())}">
                <div class="message-header">
                    <strong>${directionLabel}</strong>
                    <small class="text-muted">${escapeHtml(msg.created_at)}</small>
                </div>
                <div class="message-subject">${escapeHtml(msg.subject)}</div>
                <div class="message-preview">${escapeHtml((msg.content || '').substring(0, 80))}${(msg.content || '').length > 80 ? '...' : ''}</div>
                ${msg.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${msg.attachments.length} file(s)</div>` : ''}
            </div>
        `;
    }).join('');
}

function loadArchiveMessagesOnce() {
    if (archiveLoadedOnce) {
        displayArchiveMessages(archiveMessagesCache);
        return;
    }

    const container = document.getElementById('archive-messages-list');
    if (container) {
        container.innerHTML = '<div class="text-center text-muted p-4"><p>Loading archived messages...</p></div>';
    }

    fetch(window.messagingApiUrls.getMessages, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(response => {
            if (!response.ok) throw new Error('Failed to load archived messages');
            return response.json();
        })
        .then(data => {
            archiveMessagesCache = data.archive || [];
            archiveLoadedOnce = true;
            displayArchiveMessages(archiveMessagesCache);
        })
        .catch(error => {
            console.error('Error loading archive:', error);
            if (container) {
                container.innerHTML = '<div class="text-center text-danger p-4"><p>Failed to load archived messages.</p></div>';
            }
        });
}

function updateUnreadCount(count) {
    const badge = document.getElementById('unread-badge');
    if (!badge) return;

    if (count > 0) {
        badge.textContent = count;
        badge.style.display = 'inline-block';
    } else {
        badge.style.display = 'none';
    }
}

function updateUnreadBadge() {
    fetch(window.messagingApiUrls.unreadCount, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
        .then(response => response.json())
        .then(data => updateUnreadCount(data.unread_count || 0))
        .catch(error => console.error('Error updating unread count:', error));
}

function viewMessage(type, messageId) {
    if (type === 'archive') {
        const cachedMessage = (archiveMessagesCache || []).find(m => m.id === Number(messageId));
        if (cachedMessage) {
            displayMessageDetail(cachedMessage);
            const modal = new bootstrap.Modal(document.getElementById('messageDetailModal'));
            modal.show();
            document.getElementById('deleteMessageBtn').setAttribute('data-message-id', messageId);
            return;
        }
    }

    const all = [...(latestMessagesPayload.received || []), ...(latestMessagesPayload.sent || []), ...(latestMessagesPayload.archive || [])];
    const message = all.find(m => m.id === Number(messageId));
    if (message) {
        displayMessageDetail(message);
        const modal = new bootstrap.Modal(document.getElementById('messageDetailModal'));
        modal.show();
        document.getElementById('deleteMessageBtn').setAttribute('data-message-id', messageId);
    }
}

function displayMessageDetail(message) {
    const container = document.getElementById('message-detail-content');
    if (!container) return;

    let attachmentsHtml = '';
    if (message.attachments && message.attachments.length > 0) {
        attachmentsHtml = `
            <div class="mt-3">
                <strong>Attachments:</strong>
                <ul class="list-unstyled mt-2">
                    ${message.attachments.map(att => `
                        <li>
                            <i class="bi bi-file"></i>
                            <a href="${att.download_url || att.url}" class="ms-2"${getPdfPreviewAttrs(att.filename, att.download_url || att.url)}>
                                ${escapeHtml(att.filename)} (${formatFileSize(att.file_size)})
                            </a>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    const fromTo = message.type === 'received'
        ? `From: <strong>${escapeHtml(message.sender)}</strong>`
        : `To: <strong>${escapeHtml(message.recipient)}</strong>`;

    container.innerHTML = `
        <div class="message-detail">
            <div class="mb-3 pb-3 border-bottom">
                <p class="mb-1">${fromTo}</p>
                <small class="text-muted">${escapeHtml(message.created_at)}</small>
            </div>
            <div class="mb-3">
                <h6>${escapeHtml(message.subject)}</h6>
            </div>
            <div class="mb-3">
                <p style="white-space: pre-wrap; word-wrap: break-word;">${escapeHtml(message.content)}</p>
            </div>
            ${attachmentsHtml}
        </div>
    `;
}

function handleFileSelection(event) {
    const files = event.target.files;
    const fileList = document.getElementById('file-list');
    if (!fileList) return;

    if (files.length === 0) {
        fileList.innerHTML = '';
        return;
    }

    let html = '<div class="alert alert-info">Selected files:</div><ul class="list-unstyled">';
    for (let file of files) {
        html += `<li><i class="bi bi-file"></i> ${escapeHtml(file.name)} (${formatFileSize(file.size)})</li>`;
    }
    html += '</ul>';

    fileList.innerHTML = html;
}

function handleMessageSubmit(event) {
    event.preventDefault();

    const selectedRecipients = getSelectedRecipientIds();
    if (!selectedRecipients || selectedRecipients.length === 0) {
        showAlert('Please select at least one recipient', 'warning');
        return;
    }

    const subject = document.getElementById('subject').value;
    const content = document.getElementById('content').value;
    if (!content.trim()) {
        showAlert('Please enter a message', 'warning');
        return;
    }

    const formData = new FormData();
    selectedRecipients.forEach(id => {
        formData.append('recipients', id);
    });
    formData.append('subject', subject);
    formData.append('content', content);

    const attachmentsInput = document.getElementById('attachments');
    if (attachmentsInput && attachmentsInput.files.length > 0) {
        for (let file of attachmentsInput.files) {
            formData.append('attachments', file);
        }
    }

    const submitBtn = document.getElementById('sendMessageBtn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';

    fetch(window.messagingApiUrls.sendMessage, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]')?.value || ''
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
                throw new Error(data.error || data.message || `Request failed (${response.status})`);
            }
            return data;
        })
        .then(data => {
            if (data.status === 'success') {
                document.getElementById('messageForm').reset();
                document.getElementById('file-list').innerHTML = '';
                const modal = bootstrap.Modal.getInstance(document.getElementById('sendMessageModal'));
                if (modal) modal.hide();

                showAlert(data.message || 'Message sent successfully!', 'success');
                loadMessages();
                loadAllUsers();
            } else {
                showAlert('Failed to send message: ' + (data.error || data.message || 'Unknown error'), 'danger');
            }
        })
        .catch(error => {
            console.error('Error sending message:', error);
            showAlert('Error sending message: ' + error.message, 'danger');
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Send Message';
        });
}

function handleInlineReplySubmit(event) {
    event.preventDefault();

    if (!activeThreadUserId) {
        showAlert('Select a conversation first.', 'warning');
        return;
    }

    const replyInput = document.getElementById('inlineReplyContent');
    const sendBtn = document.getElementById('inlineReplySendBtn');
    if (!replyInput || !sendBtn) return;

    const content = (replyInput.value || '').trim();
    if (!content) {
        showAlert('Please type a reply.', 'warning');
        return;
    }

    const formData = new FormData();
    formData.append('recipients', String(activeThreadUserId));
    formData.append('subject', '');
    formData.append('content', content);

    sendBtn.disabled = true;
    const previousButtonHtml = sendBtn.innerHTML;
    sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Sending';

    fetch(window.messagingApiUrls.sendMessage, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]')?.value || ''
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
                throw new Error(data.error || data.message || `Request failed (${response.status})`);
            }
            return data;
        })
        .then(() => {
            replyInput.value = '';
            loadMessages();
        })
        .catch(error => {
            console.error('Error sending inline reply:', error);
            showAlert('Error sending reply: ' + error.message, 'danger');
        })
        .finally(() => {
            sendBtn.disabled = false;
            sendBtn.innerHTML = previousButtonHtml;
        });
}

function handleDeleteMessage() {
    const messageId = this.getAttribute('data-message-id');
    if (!confirm('Are you sure you want to delete this message?')) return;

    const deleteUrl = window.messagingApiUrls.deleteMessage.replace('0', messageId);
    fetch(deleteUrl, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]')?.value || ''
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const modal = bootstrap.Modal.getInstance(document.getElementById('messageDetailModal'));
                if (modal) modal.hide();
                showAlert('Message deleted', 'success');
                loadMessages();

                if (archiveLoadedOnce) {
                    archiveMessagesCache = archiveMessagesCache.filter(m => m.id !== Number(messageId));
                    displayArchiveMessages(archiveMessagesCache);
                }
            } else {
                showAlert('Failed to delete message', 'danger');
            }
        })
        .catch(error => {
            console.error('Error deleting message:', error);
            showAlert('Error deleting message', 'danger');
        });
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${escapeHtml(message)}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    const messagingContainer = document.querySelector('.messaging-container');
    if (messagingContainer) {
        messagingContainer.insertBefore(alertDiv, messagingContainer.firstChild);
        setTimeout(() => alertDiv.remove(), 4000);
    }
}

function setupEventListeners() {
    const attachmentsInput = document.getElementById('attachments');
    if (attachmentsInput) {
        attachmentsInput.addEventListener('change', handleFileSelection);
    }

    const messageForm = document.getElementById('messageForm');
    if (messageForm) {
        messageForm.addEventListener('submit', handleMessageSubmit);
    }

    const inlineReplyForm = document.getElementById('inlineReplyForm');
    if (inlineReplyForm) {
        inlineReplyForm.addEventListener('submit', handleInlineReplySubmit);
    }

    const roleFilter = document.getElementById('recipient_role_filter');
    if (roleFilter) {
        roleFilter.addEventListener('change', applyRecipientFilters);
    }

    const sectionFilter = document.getElementById('recipient_section_filter');
    if (sectionFilter) {
        sectionFilter.addEventListener('change', applyRecipientFilters);
    }

    const selectAllBtn = document.getElementById('select_all_recipients');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function (e) {
            e.preventDefault();
            setAllRecipients(true);
        });
    }

    const clearAllBtn = document.getElementById('clear_all_recipients');
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', function (e) {
            e.preventDefault();
            setAllRecipients(false);
        });
    }

    const receivedList = document.getElementById('received-messages-list');
    if (receivedList) {
        receivedList.addEventListener('click', function (event) {
            const item = event.target.closest('.message-item');
            if (!item) return;
            selectConversationFromElement(item);
        });
    }

    const sentList = document.getElementById('sent-messages-list');
    if (sentList) {
        sentList.addEventListener('click', function (event) {
            const item = event.target.closest('.message-item');
            if (!item) return;
            selectConversationFromElement(item);
        });
    }

    const archiveModal = document.getElementById('archiveMessagesModal');
    if (archiveModal) {
        archiveModal.addEventListener('show.bs.modal', function () {
            loadArchiveMessagesOnce();
        });
    }

    const deleteBtn = document.getElementById('deleteMessageBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', handleDeleteMessage);
    }
}
