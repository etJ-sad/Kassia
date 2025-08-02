// web/static/js/websocket.js - WebSocket Manager for Real-time Updates

class WebSocketManager {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 1000; // Start with 1 second
        this.heartbeatInterval = null;
        this.lastHeartbeat = null;
        
        // Event handlers
        this.onConnect = null;
        this.onDisconnect = null;
        this.onError = null;
        this.onJobUpdate = null;
        this.onMessage = null;
        
        console.log('🔌 WebSocket Manager initialized');
    }
    
    connect() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            console.log('🔌 WebSocket already connected');
            return;
        }
        
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = (event) => {
                console.log('✅ WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.reconnectInterval = 1000;
                
                if (this.onConnect) {
                    this.onConnect(event);
                }
                
                this.startHeartbeat();
            };
            
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('❌ Failed to parse WebSocket message:', error);
                }
            };
            
            this.socket.onclose = (event) => {
                console.log('🔌 WebSocket disconnected', event);
                this.isConnected = false;
                this.stopHeartbeat();
                
                if (this.onDisconnect) {
                    this.onDisconnect(event);
                }
                
                // Attempt to reconnect
                this.attemptReconnect();
            };
            
            this.socket.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
                
                if (this.onError) {
                    this.onError(error);
                }
            };
            
        } catch (error) {
            console.error('❌ Failed to create WebSocket connection:', error);
            this.attemptReconnect();
        }
    }
    
    disconnect() {
        console.log('🔌 Disconnecting WebSocket');
        this.stopHeartbeat();
        
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        
        this.isConnected = false;
    }
    
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            const message = typeof data === 'string' ? data : JSON.stringify(data);
            this.socket.send(message);
            console.log('📤 Sent WebSocket message:', data);
        } else {
            console.warn('⚠️ Cannot send message: WebSocket not connected');
        }
    }
    
    handleMessage(data) {
        console.log('📥 Received WebSocket message:', data);
        
        switch (data.type) {
            case 'heartbeat':
                this.lastHeartbeat = new Date();
                break;
                
            case 'job_update':
                if (this.onJobUpdate) {
                    this.onJobUpdate(data);
                }
                break;
                
            case 'job_log':
                if (this.onJobUpdate) {
                    this.onJobUpdate(data);
                }
                break;
                
            case 'system_status':
                if (this.onJobUpdate) {
                    this.onJobUpdate(data);
                }
                break;
                
            case 'pong':
                console.log('🏓 Received pong');
                break;
                
            default:
                console.log('📥 Unknown message type:', data.type);
                if (this.onMessage) {
                    this.onMessage(data);
                }
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Max reconnection attempts reached');
            return;
        }
        
        this.reconnectAttempts++;
        console.log(`🔄 Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${this.reconnectInterval}ms`);
        
        setTimeout(() => {
            this.connect();
        }, this.reconnectInterval);
        
        // Exponential backoff
        this.reconnectInterval = Math.min(this.reconnectInterval * 2, 30000);
    }
    
    startHeartbeat() {
        this.stopHeartbeat();
        
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.send({ type: 'ping', timestamp: new Date().toISOString() });
            }
        }, 30000); // Send ping every 30 seconds
    }
    
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    
    subscribeToJob(jobId) {
        this.send({
            type: 'subscribe_job',
            job_id: jobId
        });
    }
    
    requestStatus() {
        this.send({
            type: 'request_status'
        });
    }
}

// Create global WebSocket manager
window.websocketManager = new WebSocketManager();

// Auto-connect when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔌 Starting WebSocket connection...');
    window.websocketManager.connect();
});

console.log('✅ WebSocket Manager loaded');