// web/static/js/api.js - API Manager for HTTP Requests

class ApiManager {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.defaultHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
        
        console.log('🌐 API Manager initialized');
    }
    
    async request(method, url, data = null, headers = {}) {
        const requestHeaders = { ...this.defaultHeaders, ...headers };
        const requestUrl = this.baseUrl + url;
        
        const requestOptions = {
            method: method.toUpperCase(),
            headers: requestHeaders,
            credentials: 'same-origin'
        };
        
        if (data && (method.toUpperCase() === 'POST' || method.toUpperCase() === 'PUT' || method.toUpperCase() === 'PATCH')) {
            requestOptions.body = JSON.stringify(data);
        }
        
        console.log(`🌐 ${method.toUpperCase()} ${requestUrl}`, data ? data : '');
        
        try {
            const response = await fetch(requestUrl, requestOptions);
            
            // Handle different content types
            const contentType = response.headers.get('content-type');
            let responseData;
            
            if (contentType && contentType.includes('application/json')) {
                responseData = await response.json();
            } else {
                responseData = await response.text();
            }
            
            if (!response.ok) {
                const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
                error.status = response.status;
                error.data = responseData;
                throw error;
            }
            
            console.log(`✅ ${method.toUpperCase()} ${requestUrl} - Success`, responseData);
            return responseData;
            
        } catch (error) {
            console.error(`❌ ${method.toUpperCase()} ${requestUrl} - Error:`, error);
            
            // Add user-friendly error messages
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                error.message = 'Network error: Unable to connect to server';
            } else if (error.status === 404) {
                error.message = 'Resource not found';
            } else if (error.status === 500) {
                error.message = 'Internal server error';
            } else if (error.status === 403) {
                error.message = 'Access forbidden';
            } else if (error.status === 401) {
                error.message = 'Unauthorized';
            }
            
            throw error;
        }
    }
    
    async get(url, params = null) {
        let requestUrl = url;
        
        if (params) {
            const urlParams = new URLSearchParams();
            Object.keys(params).forEach(key => {
                if (params[key] !== null && params[key] !== undefined) {
                    urlParams.append(key, params[key]);
                }
            });
            
            if (urlParams.toString()) {
                requestUrl += (url.includes('?') ? '&' : '?') + urlParams.toString();
            }
        }
        
        return this.request('GET', requestUrl);
    }
    
    async post(url, data) {
        return this.request('POST', url, data);
    }
    
    async put(url, data) {
        return this.request('PUT', url, data);
    }
    
    async patch(url, data) {
        return this.request('PATCH', url, data);
    }
    
    async delete(url) {
        return this.request('DELETE', url);
    }
    
    // Specific API methods for Kassia
    async getDevices() {
        return this.get('/api/devices');
    }
    
    async getAssets(device, osId) {
        return this.get(`/api/assets/${device}/${osId}`);
    }
    
    async startBuild(buildData) {
        return this.post('/api/build', buildData);
    }
    
    async getJobs(params = {}) {
        return this.get('/api/jobs', params);
    }
    
    async getJob(jobId) {
        return this.get(`/api/jobs/${jobId}`);
    }
    
    async getJobLogs(jobId, params = {}) {
        return this.get(`/api/jobs/${jobId}/logs`, params);
    }
    
    async cancelJob(jobId) {
        return this.delete(`/api/jobs/${jobId}`);
    }
    
    async deleteJob(jobId) {
        return this.delete(`/api/jobs/${jobId}/delete`);
    }
    
    async getDatabaseInfo() {
        return this.get('/api/admin/database/info');
    }
    
    async getStatistics(days = 30) {
        return this.get('/api/admin/statistics', { days });
    }
    
    async cleanupDatabase(days = 90) {
        return this.post(`/api/admin/maintenance/cleanup?days=${days}`);
    }
    
    async updateStatistics() {
        return this.post('/api/admin/maintenance/update-statistics');
    }
    
    async getLanguages() {
        return this.get('/api/languages');
    }
    
    async getTranslations(language) {
        return this.get(`/static/translations/${language}.json`);
    }
    
    async healthCheck() {
        return this.get('/api/health');
    }
}

// Create global API manager
window.apiManager = new ApiManager();
window.api = window.apiManager; // Alias for backward compatibility

console.log('✅ API Manager loaded');