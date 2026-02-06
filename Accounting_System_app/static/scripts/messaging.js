// Messaging System JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize messaging on page load
    initializeMessaging();
    
    // Refresh messages every 5 seconds
    setInterval(refreshMessages, 5000);
});

// Initialize messaging system
function initializeMessaging() {
    loadAllUsers();
    loadMessages();
    setupEventListeners();
}

// Load all users for recipient dropdown
function loadAllUsers() {
    fetch(window.messagingApiUrls.getMessages, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        // Extract unique user list from messages or load from backend
        loadRecipientsList();
    })
    .catch(error => console.error('Error loading users:', error));
}

// Load recipients list (other users)
function loadRecipientsList() {
    const recipientSelect = document.getElementById('recipient');
    if (!recipientSelect) return;
    
    // Fetch users from the API endpoint
    fetch(window.messagingApiUrls.getUsers, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => {
        if (!response.ok) throw new Error('Failed to load users');
        return response.json();
    })
    .then(data => {
        recipientSelect.innerHTML = '<option value="">-- Select Recipient --</option>';        
        if (data.users && data.users.length > 0) {
            data.users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                option.textContent = user.full_name;
                recipientSelect.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.textContent = 'No users available';
            option.disabled = true;
            recipientSelect.appendChild(option);
        }
    })
    .catch(error => {
        console.error('Error loading users:', error);
        const option = document.createElement('option');
        option.textContent = 'Error loading users';
        option.disabled = true;
        recipientSelect.appendChild(option);
    });
}

// Load messages
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
        displayReceivedMessages(data.received || []);
        displaySentMessages(data.sent || []);
        updateUnreadCount(data.unread_count || 0);
    })
    .catch(error => console.error('Error loading messages:', error));
}

// Refresh messages
function refreshMessages() {
    loadMessages();
    updateUnreadBadge();
}

// Display received messages
function displayReceivedMessages(messages) {
    const container = document.getElementById('received-messages-list');
    if (!container) return;
    
    if (messages.length === 0) {
        container.innerHTML = '<div class="text-center text-muted p-4"><p>No received messages</p></div>';
        return;
    }
    
    container.innerHTML = messages.map(msg => `
        <div class="message-item ${msg.is_read ? '' : 'unread'}" onclick="viewMessage('${msg.type}', ${msg.id})">
            <div class="message-header">
                <strong>${msg.sender}</strong>
                <small class="text-muted">${msg.created_at}</small>
            </div>
            <div class="message-subject">${msg.subject}</div>
            <div class="message-preview">${msg.content.substring(0, 80)}${msg.content.length > 80 ? '...' : ''}</div>
            ${msg.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${msg.attachments.length} file(s)</div>` : ''}
        </div>
    `).join('');
}

// Display sent messages
function displaySentMessages(messages) {
    const container = document.getElementById('sent-messages-list');
    if (!container) return;
    
    if (messages.length === 0) {
        container.innerHTML = '<div class="text-center text-muted p-4"><p>No sent messages</p></div>';
        return;
    }
    
    container.innerHTML = messages.map(msg => `
        <div class="message-item" onclick="viewMessage('${msg.type}', ${msg.id})">
            <div class="message-header">
                <strong>To: ${msg.recipient}</strong>
                <small class="text-muted">${msg.created_at}</small>
            </div>
            <div class="message-subject">${msg.subject}</div>
            <div class="message-preview">${msg.content.substring(0, 80)}${msg.content.length > 80 ? '...' : ''}</div>
            ${msg.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${msg.attachments.length} file(s)</div>` : ''}
        </div>
    `).join('');
}

// Update unread count badge
function updateUnreadCount(count) {
    const badge = document.getElementById('unread-badge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count;
            badge.style.display = 'inline-block';
        } else {
            badge.style.display = 'none';
        }
    }
}

// Update unread badge periodically
function updateUnreadBadge() {
    fetch(window.messagingApiUrls.unreadCount, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => updateUnreadCount(data.unread_count || 0))
    .catch(error => console.error('Error updating unread count:', error));
}

// View message details
function viewMessage(type, messageId) {
    fetch(window.messagingApiUrls.getMessages, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        const messages = type === 'received' ? data.received : data.sent;
        const message = messages.find(m => m.id === messageId);
        
        if (message) {
            displayMessageDetail(message);
            const modal = new bootstrap.Modal(document.getElementById('messageDetailModal'));
            modal.show();
            
            // Store current message ID for delete action
            document.getElementById('deleteMessageBtn').setAttribute('data-message-id', messageId);
        }
    })
    .catch(error => console.error('Error loading message:', error));
}

// Display message details
function displayMessageDetail(message) {
    const container = document.getElementById('message-detail-content');
    
    let attachmentsHtml = '';
    if (message.attachments && message.attachments.length > 0) {
        attachmentsHtml = `
            <div class="mt-3">
                <strong>Attachments:</strong>
                <ul class="list-unstyled mt-2">
                    ${message.attachments.map(att => `
                        <li>
                            <i class="bi bi-file"></i>
                            <a href="${att.url}" download="${att.filename}" class="ms-2">
                                ${att.filename} (${formatFileSize(att.file_size)})
                            </a>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }
    
    const fromTo = message.type === 'received' 
        ? `From: <strong>${message.sender}</strong>`
        : `To: <strong>${message.recipient}</strong>`;
    
    container.innerHTML = `
        <div class="message-detail">
            <div class="mb-3 pb-3 border-bottom">
                <p class="mb-1">${fromTo}</p>
                <small class="text-muted">${message.created_at}</small>
            </div>
            <div class="mb-3">
                <h6>${message.subject}</h6>
            </div>
            <div class="mb-3">
                <p style="white-space: pre-wrap; word-wrap: break-word;">${message.content}</p>
            </div>
            ${attachmentsHtml}
        </div>
    `;
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

// Setup event listeners
function setupEventListeners() {
    // Handle file input
    const attachmentsInput = document.getElementById('attachments');
    if (attachmentsInput) {
        attachmentsInput.addEventListener('change', handleFileSelection);
    }
    
    // Handle message form submission
    const messageForm = document.getElementById('messageForm');
    if (messageForm) {
        messageForm.addEventListener('submit', handleMessageSubmit);
    }
    
    // Handle message deletion
    const deleteBtn = document.getElementById('deleteMessageBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', handleDeleteMessage);
    }
}

// Handle file selection
function handleFileSelection(event) {
    const files = event.target.files;
    const fileList = document.getElementById('file-list');
    
    if (files.length === 0) {
        fileList.innerHTML = '';
        return;
    }
    
    let html = '<div class="alert alert-info">Selected files:</div><ul class="list-unstyled">';
    for (let file of files) {
        html += `<li><i class="bi bi-file"></i> ${file.name} (${formatFileSize(file.size)})</li>`;
    }
    html += '</ul>';
    
    fileList.innerHTML = html;
}

// Handle message submission
function handleMessageSubmit(event) {
    event.preventDefault();
    
    const formData = new FormData(this);
    const submitBtn = document.getElementById('sendMessageBtn');
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';
    
    fetch(window.messagingApiUrls.sendMessage, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Reset form
            document.getElementById('messageForm').reset();
            document.getElementById('file-list').innerHTML = '';
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('sendMessageModal'));
            if (modal) modal.hide();
            
            // Show success message
            showAlert('Message sent successfully!', 'success');
            
            // Refresh messages
            loadMessages();
        } else {
            showAlert('Failed to send message: ' + (data.message || 'Unknown error'), 'danger');
        }
    })
    .catch(error => {
        console.error('Error sending message:', error);
        showAlert('Error sending message', 'danger');
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Send Message';
    });
}

// Handle message deletion
function handleDeleteMessage() {
    const messageId = this.getAttribute('data-message-id');
    
    if (!confirm('Are you sure you want to delete this message?')) {
        return;
    }
    
    const deleteUrl = window.messagingApiUrls.deleteMessage.replace('0', messageId);
    fetch(deleteUrl, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('messageDetailModal'));
            if (modal) modal.hide();
            
            showAlert('Message deleted', 'success');
            
            // Refresh messages
            loadMessages();
        } else {
            showAlert('Failed to delete message', 'danger');
        }
    })
    .catch(error => {
        console.error('Error deleting message:', error);
        showAlert('Error deleting message', 'danger');
    });
}

// Show alert message
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Insert at the top of the messaging container
    const messagingContainer = document.querySelector('.messaging-container');
    if (messagingContainer) {
        messagingContainer.insertBefore(alertDiv, messagingContainer.firstChild);
        
        // Auto-dismiss after 4 seconds
        setTimeout(() => {
            alertDiv.remove();
        }, 4000);
    }
}
