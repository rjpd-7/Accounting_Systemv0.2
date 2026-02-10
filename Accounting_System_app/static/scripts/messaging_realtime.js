// Real-time Messaging System using WebSockets

let websocket = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
const reconnectDelay = 3000; // 3 seconds

document.addEventListener('DOMContentLoaded', function() {
    // Initialize messaging on page load
    initializeMessaging();
});

// Initialize messaging system
function initializeMessaging() {
    connectWebSocket();
    loadAllUsers();
    loadMessages();
    setupEventListeners();
}

// Connect to WebSocket
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/messages/`;
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = function(event) {
        console.log('WebSocket connected');
        reconnectAttempts = 0;
        
        // Request unread count when connected
        sendWebSocketMessage({
            type: 'get_unread_count'
        });
    };
    
    websocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    websocket.onclose = function(event) {
        console.log('WebSocket disconnected');
        attemptReconnect();
    };
    
    websocket.onerror = function(event) {
        console.error('WebSocket error:', event);
        websocket.close();
    };
}

// Attempt to reconnect
function attemptReconnect() {
    if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        console.log(`Attempting to reconnect... (${reconnectAttempts}/${maxReconnectAttempts})`);
        setTimeout(connectWebSocket, reconnectDelay);
    } else {
        console.error('Max reconnection attempts reached. Falling back to polling.');
        // Fall back to polling if WebSocket fails
        setInterval(refreshMessages, 5000);
    }
}

// Handle WebSocket messages
function handleWebSocketMessage(data) {
    const messageType = data.type;
    
    if (messageType === 'new_message') {
        // New message received
        const messageData = data.data;
        displayNewMessage(messageData);
        
        // Mark message as read
        setTimeout(() => {
            sendWebSocketMessage({
                type: 'mark_as_read',
                message_id: messageData.message_id
            });
        }, 500);
        
        // Show notification
        showNotification(`New message from ${messageData.sender}`, messageData.subject);
        
        // Request unread count
        sendWebSocketMessage({
            type: 'get_unread_count'
        });
        
        // Refresh messages list
        loadMessages();
    } else if (messageType === 'message_sent') {
        console.log('Message sent successfully');
    } else if (messageType === 'message_read') {
        console.log('Message marked as read');
    } else if (messageType === 'unread_count') {
        updateUnreadCount(data.unread_count);
    } else if (messageType === 'error') {
        console.error('WebSocket error:', data.error);
    }
}

// Send message via WebSocket
function sendWebSocketMessage(data) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify(data));
    } else {
        console.error('WebSocket not connected');
    }
}

// Display new message notification
function displayNewMessage(messageData) {
    const container = document.getElementById('received-messages-list');
    if (!container) return;
    
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = 'message-item unread';
    messageElement.setAttribute('data-message-id', messageData.message_id);
    messageElement.innerHTML = `
        <div class="message-header">
            <strong>${messageData.sender}</strong>
            <small class="text-muted">${messageData.created_at}</small>
        </div>
        <div class="message-subject">${messageData.subject}</div>
        <div class="message-preview">${messageData.content.substring(0, 80)}${messageData.content.length > 80 ? '...' : ''}</div>
    `;
    messageElement.addEventListener('click', function() {
        viewMessage('received', messageData.message_id);
    });
    
    // Add to top of list
    const existingMessages = container.querySelectorAll('.message-item');
    if (existingMessages.length === 0) {
        container.innerHTML = '';
    }
    
    container.insertBefore(messageElement, container.firstChild);
}

// Show notification (browser notification)
function showNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, {
            body: body,
            icon: '/static/images/icon.png'
        });
    }
}

// Load all users for recipient dropdown
function loadAllUsers() {
    fetch(window.messagingApiUrls.getUsers, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        loadRecipientsList(data.users || []);
    })
    .catch(error => console.error('Error loading users:', error));
}

// Load recipients list (other users)
function loadRecipientsList(users) {
    const recipientSelect = document.getElementById('recipient');
    if (!recipientSelect) return;
    
    recipientSelect.innerHTML = '<option value="">-- Select Recipient --</option>';
    
    if (users && users.length > 0) {
        users.forEach(user => {
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
        <div class="message-item ${msg.is_read ? '' : 'unread'}" onclick="viewMessage('received', ${msg.id})">
            <div class="message-header">
                <strong>${msg.sender}</strong>
                <small class="text-muted">${msg.created_at}</small>
            </div>
            <div class="message-subject">${msg.subject}</div>
            <div class="message-preview">${msg.content.substring(0, 80)}${msg.content.length > 80 ? '...' : ''}</div>
            ${msg.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${msg.attachments.length} file(s)</div>` : ''}
        </div>
    `).join('');
    
    // Add click event listeners
    container.querySelectorAll('.message-item').forEach(item => {
        item.addEventListener('click', function(e) {
            const messageId = this.getAttribute('data-message-id');
            viewMessage('received', messageId);
        });
    });
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
        <div class="message-item" onclick="viewMessage('sent', ${msg.id})">
            <div class="message-header">
                <strong>To: ${msg.recipient}</strong>
                <small class="text-muted">${msg.created_at}</small>
            </div>
            <div class="message-subject">${msg.subject}</div>
            <div class="message-preview">${msg.content.substring(0, 80)}${msg.content.length > 80 ? '...' : ''}</div>
            ${msg.attachments.length > 0 ? `<div class="message-attachments"><i class="bi bi-paperclip"></i> ${msg.attachments.length} file(s)</div>` : ''}
        </div>
    `).join('');
    
    // Add click event listeners
    container.querySelectorAll('.message-item').forEach(item => {
        item.addEventListener('click', function(e) {
            const messageId = this.getAttribute('data-message-id');
            viewMessage('sent', messageId);
        });
    });
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
            
            // Mark as read if received message
            if (type === 'received') {
                sendWebSocketMessage({
                    type: 'mark_as_read',
                    message_id: messageId
                });
            }
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
    
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
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
