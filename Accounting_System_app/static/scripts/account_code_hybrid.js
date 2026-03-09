/**
 * Hybrid AJAX + WebSocket Account Code Manager
 * 
 * Features:
 * - AJAX: Quick initial preview fetch on modal open/type change
 * - WebSocket: Real-time updates when OTHER users create accounts
 * - Server-side atomic: Final code generation on submit
 */

class HybridAccountCodeManager {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.currentAccountType = null;
        
        this.initializeElements();
        this.connectWebSocket();
        this.setupEventListeners();
    }

    initializeElements() {
        this.modal = document.getElementById("staticBackdrop");
        this.form = document.getElementById("account_form");
        this.accountCodeInput = document.getElementById("account_code");
        this.accountTypeSelect = document.getElementById("account_type");
        this.statusIndicator = document.getElementById("account-socket-status");
    }

    setupEventListeners() {
        if (!this.modal || !this.form || !this.accountCodeInput || !this.accountTypeSelect) {
            console.warn("Account form elements not found");
            return;
        }

        // Fetch preview code when modal opens
        this.modal.addEventListener("shown.bs.modal", () => {
            this.fetchPreviewCode(this.accountTypeSelect.value);
        });

        // Fetch preview code when account type changes
        this.accountTypeSelect.addEventListener("change", () => {
            this.currentAccountType = this.accountTypeSelect.value;
            this.fetchPreviewCode(this.currentAccountType);
        });

        // Refresh preview right before submit
        this.form.addEventListener("submit", async (event) => {
            const accountNameInput = document.getElementById("account_name");
            const submitBtn = this.form.querySelector('input[type="submit"], button[type="submit"]');

            if (!accountNameInput.value.trim() || !this.accountTypeSelect.value) {
                event.preventDefault();
                alert("Please complete all required fields.");
                return;
            }

            event.preventDefault();
            if (submitBtn) submitBtn.disabled = true;

            try {
                await this.fetchPreviewCode(this.accountTypeSelect.value);
                this.form.submit();
            } finally {
                if (submitBtn) submitBtn.disabled = false;
            }
        });

        // Reset form when modal closes
        this.modal.addEventListener("hidden.bs.modal", () => {
            this.form.reset();
            this.accountCodeInput.value = "";
            this.currentAccountType = null;
        });
    }

    async fetchPreviewCode(accountType) {
        if (!accountType) {
            this.accountCodeInput.value = "";
            return;
        }

        this.accountCodeInput.value = "Loading...";
        this.accountCodeInput.readOnly = true;

        try {
            const response = await fetch(`/api/next_account_code/?type=${encodeURIComponent(accountType)}`);
            const data = await response.json();

            if (data.success) {
                this.updateCodeField(data.code);
            } else {
                this.accountCodeInput.value = "";
                console.error("Failed to fetch account code:", data.error);
            }
        } catch (error) {
            this.accountCodeInput.value = "";
            console.error("Error fetching account code:", error);
        }
    }

    updateCodeField(code, highlight = false) {
        if (this.accountCodeInput) {
            this.accountCodeInput.value = code;
            
            if (highlight) {
                this.accountCodeInput.classList.add('code-updated');
                setTimeout(() => {
                    this.accountCodeInput.classList.remove('code-updated');
                }, 1500);
            }
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${protocol}${window.location.host}/ws/account-codes/`;
        
        try {
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = () => this.onWebSocketOpen();
            this.socket.onmessage = (event) => this.onWebSocketMessage(event);
            this.socket.onclose = (event) => this.onWebSocketClose(event);
            this.socket.onerror = (event) => this.onWebSocketError(event);
            
            console.log('🔌 Connecting to account code WebSocket...');
        } catch (error) {
            console.error('❌ WebSocket connection failed:', error);
            this.scheduleReconnect();
        }
    }

    onWebSocketOpen() {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        console.log('✅ Account code WebSocket connected');
        this.updateConnectionStatus(true);
        
        // Setup ping/pong keepalive
        this.keepaliveInterval = setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000); // Every 30 seconds
    }

    onWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'account_created') {
                this.handleAccountCreated(data);
            } else if (data.type === 'pong') {
                // Keepalive response
                console.debug('WebSocket keepalive OK');
            }
        } catch (error) {
            console.error('❌ Error parsing WebSocket message:', error);
        }
    }

    handleAccountCreated(data) {
        const { account_type, account_code, next_code } = data;
        
        console.log(`📨 Account created broadcast: ${account_type} ${account_code}, next: ${next_code}`);
        
        // If user is currently viewing the same account type, update their preview
        if (this.currentAccountType === account_type && this.accountCodeInput) {
            this.updateCodeField(next_code, true);
            console.log(`✨ Updated preview code to ${next_code} for ${account_type}`);
        }
    }

    onWebSocketClose(event) {
        this.isConnected = false;
        console.log('🔴 Account code WebSocket disconnected', event.code);
        this.updateConnectionStatus(false);
        
        if (this.keepaliveInterval) {
            clearInterval(this.keepaliveInterval);
        }
        
        // Auto-reconnect unless intentionally closed
        if (event.code !== 1000) {
            this.scheduleReconnect();
        }
    }

    onWebSocketError(event) {
        console.error('❌ WebSocket error:', event);
        this.updateConnectionStatus(false);
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Max WebSocket reconnection attempts reached');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`⏱️ Reconnecting WebSocket in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => this.connectWebSocket(), delay);
    }

    updateConnectionStatus(isConnected) {
        if (this.statusIndicator) {
            if (isConnected) {
                this.statusIndicator.className = 'socket-status connected';
                this.statusIndicator.innerHTML = '🟢 Live';
                this.statusIndicator.title = 'Real-time updates active';
            } else {
                this.statusIndicator.className = 'socket-status disconnected';
                this.statusIndicator.innerHTML = '🟡 AJAX Only';
                this.statusIndicator.title = 'Using AJAX preview (WebSocket offline)';
            }
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.close(1000);
        }
        if (this.keepaliveInterval) {
            clearInterval(this.keepaliveInterval);
        }
    }
}

// Global instance
let hybridAccountCodeManager = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    hybridAccountCodeManager = new HybridAccountCodeManager();
    console.log('🚀 Hybrid Account Code Manager initialized');
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (hybridAccountCodeManager) {
        hybridAccountCodeManager.disconnect();
    }
});
