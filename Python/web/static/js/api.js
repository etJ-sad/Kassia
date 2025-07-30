// web/static/js/api.js
// Kassia WebUI - API Manager

class ApiManager {
    constructor() {
        this.baseUrl = '';
        this.requestTimeouts = new Map();
        this.defaultTimeout = 30000; // 30 seconds
        
        console.log('🌐 API Manager initialized');
    }
    
    async request(endpoint, options = {}) {
        const {
            method = 'GET',
            body = null,
            headers = {},
            timeout = this.defaultTimeout,
            ...otherOptions
        } = options;
        
        const url = `${this.baseUrl}${endpoint}`;
        const requestId = `${method}-${endpoint}-${Date.now()}`;
        
        // Default headers
        const defaultHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
        
        const config = {
            method,
            headers: { ...defaultHeaders, ...headers },
            ...otherOptions
        };
        
        // Add body for POST/PUT requests
        if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
            config.body = typeof body === 'string' ? body : JSON.stringify(body);
        }
        
        console.log(`📡 API Request: ${method} ${endpoint}`);
        
        try {
            // Create timeout promise
            const timeoutPromise = new Promise((_, reject) => {
                const timeoutId = setTimeout(() => {
                    reject(new Error(`Request timeout after ${timeout}ms`));
                }, timeout);
                this.requestTimeouts.set(requestId, timeoutId);
            });
            
            // Make the request
            const fetchPromise = fetch(url, config);
            
            // Race between fetch and timeout
            const response = await Promise.race([fetchPromise, timeoutPromise]);
            
            // Clear timeout
            const timeoutId = this.requestTimeouts.get(requestId);
            if (timeoutId) {
                clearTimeout(timeoutId);
                this.requestTimeouts.delete(requestId);
            }
            
            // Handle HTTP errors
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
            }
            
            // Parse response
            const contentType = response.headers.get('content-type');
            let data;
            
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }
            
            console.log(`✅ API Response: ${method} ${endpoint} (${response.status})`);
            return data;
            
        } catch (error) {
            // Clear timeout on error
            const timeoutId = this.requestTimeouts.get(requestId);
            if (timeoutId) {
                clearTimeout(timeoutId);
                this.requestTimeouts.delete(requestId);
            }
            
            console.error(`❌ API Error: ${method} ${endpoint}:`, error.message);
            throw error;
        }
    }
    
    // Convenience methods
    async get(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'GET' });
    }
    
    async post(endpoint, body, options = {}) {
        return this.request(endpoint, { ...options, method: 'POST', body });
    }
    
    async put(endpoint, body, options = {}) {
        return this.request(endpoint, { ...options, method: 'PUT', body });
    }
    
    async patch(endpoint, body, options = {}) {
        return this.request(endpoint, { ...options, method: 'PATCH', body });
    }
    
    async delete(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'DELETE' });
    }
    
    // Specific API methods
    async getDevices() {
        return this.get('/api/devices');
    }
    
    async getAssets(device, osId) {
        return this.get(`/api/assets/${device}/${osId}`);
    }
    
    async startBuild(buildRequest) {
        return this.post('/api/build', buildRequest);
    }
    
    async getJobs() {
        return this.get('/api/jobs');
    }
    
    async getJob(jobId) {
        return this.get(`/api/jobs/${jobId}`);
    }
    
    async getJobLogs(jobId, source = 'buffer') {
        return this.get(`/api/jobs/${jobId}/logs?source=${source}`);
    }
    
    async getJobLogFiles(jobId) {
        return this.get(`/api/jobs/${jobId}/log-files`);
    }
    
    async downloadJobLog(jobId, logType = 'main') {
        const response = await fetch(`/api/jobs/${jobId}/download-log?log_type=${logType}`);
        if (!response.ok) {
            throw new Error(`Failed to download log: ${response.statusText}`);
        }
        
        // Create download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `kassia_job_${jobId}_${logType}.log`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        return true;
    }
    
    async cancelJob(jobId) {
        return this.delete(`/api/jobs/${jobId}`);
    }
    
    async getSystemLogs(limit = 100, level = null) {
        const params = new URLSearchParams({ limit: limit.toString() });
        if (level) {
            params.append('level', level);
        }
        return this.get(`/api/system/logs?${params}`);
    }
    
    async getSystemHealth() {
        return this.get('/api/system/health');
    }
    
    async getHealth() {
        return this.get('/api/health');
    }
    
    // Batch operations
    async batchRequest(requests) {
        console.log(`📦 Batch API request: ${requests.length} requests`);
        
        try {
            const promises = requests.map(req => 
                this.request(req.endpoint, req.options).catch(error => ({ error, request: req }))
            );
            
            const results = await Promise.all(promises);
            
            const successful = results.filter(r => !r.error);
            const failed = results.filter(r => r.error);
            
            console.log(`✅ Batch completed: ${successful.length} successful, ${failed.length} failed`);
            
            return {
                successful,
                failed,
                results
            };
            
        } catch (error) {
            console.error('❌ Batch request failed:', error);
            throw error;
        }
    }
    
    // Error handling helpers
    isNetworkError(error) {
        return error.message.includes('fetch') || 
               error.message.includes('Network') ||
               error.message.includes('timeout');
    }
    
    isServerError(error) {
        return error.message.includes('HTTP 5');
    }
    
    isClientError(error) {
        return error.message.includes('HTTP 4');
    }
    
    // Retry mechanism
    async requestWithRetry(endpoint, options = {}, maxRetries = 3) {
        let lastError;
        
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                console.log(`🔄 API Request attempt ${attempt}/${maxRetries}: ${options.method || 'GET'} ${endpoint}`);
                return await this.request(endpoint, options);
                
            } catch (error) {
                lastError = error;
                
                // Don't retry client errors (4xx)
                if (this.isClientError(error)) {
                    throw error;
                }
                
                // Don't retry on last attempt
                if (attempt === maxRetries) {
                    break;
                }
                
                // Exponential backoff
                const delay = Math.pow(2, attempt - 1) * 1000; // 1s, 2s, 4s, etc.
                console.log(`⏳ Retrying in ${delay}ms...`);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
        
        console.error(`❌ All retry attempts failed for ${endpoint}`);
        throw lastError;
    }
    
    // Request cancellation
    cancelAllRequests() {
        console.log(`🛑 Cancelling ${this.requestTimeouts.size} pending requests`);
        
        this.requestTimeouts.forEach((timeoutId, requestId) => {
            clearTimeout(timeoutId);
            console.log(`🛑 Cancelled request: ${requestId}`);
        });
        
        this.requestTimeouts.clear();
    }
    
    // Request statistics
    getRequestStats() {
        return {
            pendingRequests: this.requestTimeouts.size,
            pendingRequestIds: Array.from(this.requestTimeouts.keys())
        };
    }
}

// Global API manager instance
window.apiManager = new ApiManager();

// Helper functions for common operations
window.api = {
    // Device operations
    getDevices: () => window.apiManager.getDevices(),
    
    // Asset operations
    getAssets: (device, osId) => window.apiManager.getAssets(device, osId),
    
    // Build operations
    startBuild: (buildRequest) => window.apiManager.startBuild(buildRequest),
    
    // Job operations
    getJobs: () => window.apiManager.getJobs(),
    getJob: (jobId) => window.apiManager.getJob(jobId),
    getJobLogs: (jobId, source) => window.apiManager.getJobLogs(jobId, source),
    getJobLogFiles: (jobId) => window.apiManager.getJobLogFiles(jobId),
    downloadJobLog: (jobId, logType) => window.apiManager.downloadJobLog(jobId, logType),
    cancelJob: (jobId) => window.apiManager.cancelJob(jobId),
    
    // System operations
    getSystemLogs: (limit, level) => window.apiManager.getSystemLogs(limit, level),
    getSystemHealth: () => window.apiManager.getSystemHealth(),
    getHealth: () => window.apiManager.getHealth(),
    
    // Utilities
    requestWithRetry: (endpoint, options, maxRetries) => 
        window.apiManager.requestWithRetry(endpoint, options, maxRetries),
    cancelAllRequests: () => window.apiManager.cancelAllRequests(),
    getRequestStats: () => window.apiManager.getRequestStats()
};

// Auto-retry for critical operations
window.api.getDevicesWithRetry = () => window.api.requestWithRetry('/api/devices', { method: 'GET' });
window.api.getJobsWithRetry = () => window.api.requestWithRetry('/api/jobs', { method: 'GET' });

// Error handling interceptor
const originalRequest = window.apiManager.request.bind(window.apiManager);
window.apiManager.request = async function(endpoint, options = {}) {
    try {
        return await originalRequest(endpoint, options);
    } catch (error) {
        // Global error handling
        if (window.kassiaApp && window.kassiaApp.showToast) {
            if (window.apiManager.isNetworkError(error)) {
                window.kassiaApp.showToast(
                    window.t('error_network', 'Network connection error'), 
                    'error'
                );
            } else if (window.apiManager.isServerError(error)) {
                window.kassiaApp.showToast(
                    window.t('error_server', 'Server error - please try again'), 
                    'error'
                );
            }
        }
        
        throw error;
    }
};

console.log('📦 API manager loaded');