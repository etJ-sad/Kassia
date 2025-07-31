// web/static/js/websocket.js - FIXED VERSION
// Kassia WebUI - WebSocket Manager (FIXED for Job Updates)

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 3000; // Start with 3 seconds
        this.maxReconnectDelay = 30000; // Max 30 seconds
        this.heartbeatInterval = null;
        this.messageHandlers = new Map();
        this.lastHeartbeat = null;
        
        console.log('🔌 WebSocket Manager initialized');
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => this.handleOpen();
            this.ws.onmessage = (event) => this.handleMessage(event);
            this.ws.onclose = (event) => this.handleClose(event);
            this.ws.onerror = (error) => this.handleError(error);
            
        } catch (error) {
            console.error('❌ Failed to create WebSocket connection:', error);
            this.scheduleReconnect();
        }
    }
    
    handleOpen() {
        console.log('✅ WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 3000; // Reset delay
        this.lastHeartbeat = Date.now();
        
        this.updateConnectionStatus(true);
        this.startHeartbeat();
        
        // Notify handlers
        this.notifyHandlers('connection', { connected: true });
        
        // Request immediate job update after connection
        this.requestJobUpdates();
    }
    
    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('📨 WebSocket message received:', data.type, data);
            
            // Update last heartbeat time
            this.lastHeartbeat = Date.now();
            
            // Handle different message types
            switch (data.type) {
                case 'job_update':
                    this.handleJobUpdate(data);
                    break;
                case 'heartbeat':
                    this.handleHeartbeat(data);
                    break;
                case 'system_update':
                    this.notifyHandlers('system_update', data);
                    break;
                default:
                    console.log('📨 Unknown WebSocket message type:', data.type, data);
                    this.notifyHandlers('unknown', data);
            }
            
        } catch (error) {
            console.error('❌ Failed to parse WebSocket message:', error, event.data);
        }
    }
    
    handleJobUpdate(data) {
        console.log('🔄 Processing job update:', data.job_id, data.data?.status, data.data?.progress);
        
        // Ensure we have proper job data structure
        if (!data.data) {
            console.error('❌ Invalid job update - missing data:', data);
            return;
        }
        
        // Notify job update handlers
        this.notifyHandlers('job_update', data);
        
        // Force UI refresh for completed/failed jobs
        if (data.data.status === 'completed' || data.data.status === 'failed') {
            console.log('🏁 Job finished, forcing UI refresh');
            setTimeout(() => {
                if (window.kassiaApp && window.kassiaApp.loadJobs) {
                    window.kassiaApp.loadJobs();
                }
            }, 1000); // Small delay to ensure backend is updated
        }
    }
    
    handleClose(event) {
        console.log('🔌 WebSocket disconnected:', event.code, event.reason);
        this.isConnected = false;
        this.lastHeartbeat = null;
        
        this.updateConnectionStatus(false);
        this.stopHeartbeat();
        
        // Notify handlers
        this.notifyHandlers('connection', { connected: false, code: event.code, reason: event.reason });
        
        // Schedule reconnection if not a clean close
        if (event.code !== 1000) { // 1000 = normal closure
            this.scheduleReconnect();
        }
    }
    
    handleError(error) {
        console.error('❌ WebSocket error:', error);
        this.isConnected = false;
        this.lastHeartbeat = null;
        this.updateConnectionStatus(false);
        
        // Notify handlers
        this.notifyHandlers('error', { error });
    }
    
    handleHeartbeat(data) {
        // Update connection info with heartbeat data
        this.lastHeartbeat = Date.now();
        
        if (data.active_connections !== undefined) {
            console.log(`💓 Heartbeat: ${data.active_connections} connections, ${data.active_jobs || 0} active jobs`);
        }
        
        // Notify handlers
        this.notifyHandlers('heartbeat', data);
        
        // Check if we need to refresh jobs based on heartbeat data
        if (data.active_jobs !== undefined && window.kassiaApp) {
            const currentRunningJobs = window.kassiaApp.jobs ? 
                window.kassiaApp.jobs.filter(j => j.status === 'running').length : 0;
            
            if (data.active_jobs !== currentRunningJobs) {
                console.log('🔄 Job count mismatch detected, refreshing jobs');
                if (window.kassiaApp.loadJobs) {
                    window.kassiaApp.loadJobs();
                }
            }
        }
    }
    
    requestJobUpdates() {
        // Send a message to request current job status
        if (this.isConnected) {
            this.send({
                type: 'request_job_updates',
                timestamp: new Date().toISOString()
            });
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Max reconnection attempts reached');
            this.updateConnectionStatus(false, 'Max reconnection attempts reached');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), this.maxReconnectDelay);
        
        console.log(`🔄 Scheduling reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.connect();
            }
        }, delay);
    }
    
    startHeartbeat() {
        // Monitor connection health and request updates
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected && this.ws) {
                // Check if we've received a heartbeat recently
                const now = Date.now();
                const timeSinceLastHeartbeat = now - (this.lastHeartbeat || now);
                
                if (timeSinceLastHeartbeat > 60000) { // 1 minute without heartbeat
                    console.warn('⚠️ No heartbeat for 1 minute, connection may be stale');
                    // Force reconnection
                    this.ws.close();
                    return;
                }
                
                // Send ping to keep connection alive
                this.send({ 
                    type: 'ping', 
                    timestamp: new Date().toISOString() 
                });
                
                // Request job updates periodically
                this.requestJobUpdates();
            }
        }, 30000); // Every 30 seconds
    }
    
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    
    send(data) {
        if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
                const message = typeof data === 'string' ? data : JSON.stringify(data);
                this.ws.send(message);
                console.log('📤 WebSocket message sent:', data.type || 'raw');
                return true;
            } catch (error) {
                console.error('❌ Failed to send WebSocket message:', error);
                return false;
            }
        } else {
            console.warn('⚠️ Cannot send message: WebSocket not connected');
            return false;
        }
    }
    
    updateConnectionStatus(connected, message = null) {
        const statusEl = document.getElementById('connectionStatus');
        if (!statusEl) return;
        
        if (connected) {
            statusEl.className = 'connection-status status-online';
            statusEl.innerHTML = `<span>${window.t('connection_connected', '🟢 Connected')}</span>`;
        } else {
            statusEl.className = 'connection-status status-offline';
            const msg = message || window.t('connection_disconnected', '🔴 Disconnected');
            statusEl.innerHTML = `<span>${msg}</span>`;
            
            if (this.reconnectAttempts > 0 && this.reconnectAttempts <= this.maxReconnectAttempts) {
                statusEl.innerHTML = `<span>${window.t('connection_reconnecting', '🔄 Reconnecting')} (${this.reconnectAttempts}/${this.maxReconnectAttempts})</span>`;
            }
        }
    }
    
    // Message handler registration
    addMessageHandler(type, handler) {
        if (!this.messageHandlers.has(type)) {
            this.messageHandlers.set(type, []);
        }
        this.messageHandlers.get(type).push(handler);
        console.log(`📝 Added message handler for type: ${type}`);
    }
    
    removeMessageHandler(type, handler) {
        if (this.messageHandlers.has(type)) {
            const handlers = this.messageHandlers.get(type);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
                console.log(`🗑️ Removed message handler for type: ${type}`);
            }
        }
    }
    
    notifyHandlers(type, data) {
        if (this.messageHandlers.has(type)) {
            const handlers = this.messageHandlers.get(type);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`❌ Error in message handler for ${type}:`, error);
                }
            });
        }
    }
    
    disconnect() {
        console.log('🔌 Manually disconnecting WebSocket');
        
        this.stopHeartbeat();
        
        if (this.ws) {
            this.ws.close(1000, 'Manual disconnect'); // Clean closure
            this.ws = null;
        }
        
        this.isConnected = false;
        this.reconnectAttempts = this.maxReconnectAttempts; // Prevent reconnection
    }
    
    getConnectionInfo() {
        return {
            connected: this.isConnected,
            reconnectAttempts: this.reconnectAttempts,
            maxReconnectAttempts: this.maxReconnectAttempts,
            readyState: this.ws ? this.ws.readyState : null,
            url: this.ws ? this.ws.url : null,
            lastHeartbeat: this.lastHeartbeat
        };
    }
}

// Global WebSocket manager instance
window.wsManager = new WebSocketManager();

// Auto-connect when page loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.wsManager.connect();
    });
} else {
    window.wsManager.connect();
}

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('📱 Page hidden - WebSocket will continue in background');
    } else {
        console.log('📱 Page visible - checking WebSocket connection');
        if (!window.wsManager.isConnected) {
            window.wsManager.connect();
        } else {
            // Request job updates when page becomes visible
            window.wsManager.requestJobUpdates();
        }
    }
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    window.wsManager.disconnect();
});

console.log('📦 WebSocket manager loaded');