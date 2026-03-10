/**
 * Hybrid AJAX + WebSocket Journal Code Manager
 * 
 * Features:
 * - AJAX: Quick initial preview fetch on modal open
 * - WebSocket: Real-time updates when OTHER users create journals
 * - Server-side atomic: Final code generation on submit
 */

class HybridJournalCodeManager {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.pollingInterval = null;
        this.pollingDelay = 3000;
        this.isSubmitting = false;
        
        this.initializeElements();
        this.connectWebSocket();
        this.setupEventListeners();
    }

    initializeElements() {
        this.modal = document.getElementById("staticBackdrop");
        this.form = document.getElementById("journal_form") || document.querySelector('form[name="journal_form"]');
        this.journalCodeInput = document.getElementById("journal_code");
        this.statusIndicator = document.getElementById("journal-socket-status");
    }

    setupEventListeners() {
        if (!this.modal || !this.form || !this.journalCodeInput) {
            console.warn("Journal form elements not found");
            return;
        }

        // Fetch preview code when modal opens
        this.modal.addEventListener("shown.bs.modal", () => {
            this.fetchPreviewCode();
        });

        // Refresh preview right before submit
        this.form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (this.isSubmitting) return;

            const submitBtn = this.form.querySelector('input[type="submit"], button[type="submit"]');

            // If form validation passes, refresh the code right before sending
            if (submitBtn) submitBtn.disabled = true;
            this.isSubmitting = true;

            try {
                // Get the latest code just before submission to minimize race condition window
                await this.fetchPreviewCode();

                // Prevent submitting placeholders or failed preview values.
                const code = (this.journalCodeInput.value || '').trim();
                if (!/^JE-\d{10}$/.test(code)) {
                    alert('Unable to get a valid journal code. Please try again.');
                    return;
                }

                this.form.submit();
            } finally {
                if (submitBtn) submitBtn.disabled = false;
                this.isSubmitting = false;
            }
        });

        // Reset form when modal closes
        this.modal.addEventListener("hidden.bs.modal", () => {
            this.form.reset();
            this.journalCodeInput.value = "";
        });
    }

    async fetchPreviewCode() {
        this.journalCodeInput.value = "Loading...";
        this.journalCodeInput.readOnly = true;

        try {
            const response = await fetch('/api/next_journal_code/');
            const data = await response.json();

            if (data.success) {
                this.journalCodeInput.value = data.code;
            } else {
                this.journalCodeInput.value = "Error loading code";
                console.error("Failed to fetch journal code:", data.error);
            }
        } catch (error) {
            this.journalCodeInput.value = "Error";
            console.error("❌ AJAX fetch failed:", error);
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${protocol}${window.location.host}/ws/journal-codes/`;
        
        try {
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = () => this.onWebSocketOpen();
            this.socket.onmessage = (event) => this.onWebSocketMessage(event);
            this.socket.onclose = (event) => this.onWebSocketClose(event);
            this.socket.onerror = (event) => this.onWebSocketError(event);
            
            console.log('🔌 Connecting to journal code WebSocket...');
        } catch (error) {
            console.error('❌ WebSocket connection failed:', error);
            this.scheduleReconnect();
        }
    }

    onWebSocketOpen() {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.stopPolling();
        console.log('✅ Journal code WebSocket connected');
        this.updateConnectionStatus(true);
    }

    onWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'journal_created') {
                this.handleJournalCreated(data);
                this.emitRealtimeUpdate(data);
            } else if (data.type === 'journal_feed_updated') {
                this.handleJournalFeedUpdate(data);
                this.emitRealtimeUpdate(data);
            }
        } catch (error) {
            console.error('❌ Failed to parse WebSocket message:', error);
        }
    }

    handleJournalCreated(data) {
        const nextCode = data.next_code;
        console.log(`📦 Received journal creation: ${data.journal_code} → Next: ${nextCode}`);
        
        // Update preview code to next available
        this.journalCodeInput.value = nextCode;
        
        // Highlight the change
        this.journalCodeInput.classList.add('code-updated');
        setTimeout(() => {
            this.journalCodeInput.classList.remove('code-updated');
        }, 1500);
    }

    handleJournalFeedUpdate(data) {
        if (data.next_code && this.journalCodeInput) {
            this.journalCodeInput.value = data.next_code;
        }
    }

    emitRealtimeUpdate(data) {
        window.dispatchEvent(new CustomEvent('journal:realtime-update', {
            detail: data
        }));
    }

    onWebSocketClose(event) {
        console.log('⚠️ Journal code WebSocket closed');
        this.isConnected = false;
        this.updateConnectionStatus(false);
        
        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
        }
    }

    onWebSocketError(event) {
        console.error('❌ Journal code WebSocket error:', event);
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Max WebSocket reconnection attempts reached');
            this.startPolling();
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1);
        console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            this.connectWebSocket();
        }, delay);
    }

    startPolling() {
        if (this.pollingInterval) {
            return;
        }

        console.log(`🔄 Starting fallback polling every ${this.pollingDelay}ms`);
        this.updateConnectionStatus(true, 'polling');

        this.pollingInterval = setInterval(() => {
            if (!this.modal || !this.modal.classList.contains('show')) {
                return;
            }
            this.fetchPreviewCode();
        }, this.pollingDelay);
    }

    stopPolling() {
        if (!this.pollingInterval) {
            return;
        }

        clearInterval(this.pollingInterval);
        this.pollingInterval = null;
    }

    updateConnectionStatus(isConnected, mode = 'websocket') {
        if (!this.statusIndicator) return;
        
        if (isConnected) {
            if (mode === 'polling') {
                this.statusIndicator.textContent = '🔄 Polling';
                this.statusIndicator.title = `Fallback polling active (${this.pollingDelay / 1000}s interval)`;
            } else {
                this.statusIndicator.textContent = '🟢 Live';
                this.statusIndicator.title = 'Real-time updates active';
            }
            this.statusIndicator.classList.remove('disconnected');
            this.statusIndicator.classList.add('connected');
        } else {
            this.statusIndicator.textContent = '🟡 AJAX Only';
            this.statusIndicator.title = 'Using AJAX preview (WebSocket offline)';
            this.statusIndicator.classList.remove('connected');
            this.statusIndicator.classList.add('disconnected');
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.close(1000);
        }
        this.stopPolling();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.journalCodeManager = new HybridJournalCodeManager();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.journalCodeManager) {
        window.journalCodeManager.disconnect();
    }
});
