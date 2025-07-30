// web/static/job-logs.js - Enhanced Job Log Viewer

class JobLogViewer {
    constructor(jobId) {
        this.jobId = jobId;
        this.logContainer = null;
        this.currentSource = 'buffer';
        this.autoRefresh = true;
        this.refreshInterval = null;
        this.filters = {
            level: 'all',
            category: 'all',
            search: ''
        };
        
        this.init();
    }
    
    init() {
        this.createUI();
        this.loadLogs();
        this.startAutoRefresh();
    }
    
    createUI() {
        // Create log viewer container
        const container = document.createElement('div');
        container.className = 'job-log-viewer';
        container.innerHTML = `
            <div class="log-controls">
                <div class="log-source-selector">
                    <label>Log Source:</label>
                    <select id="logSource">
                        <option value="buffer">Live Buffer</option>
                        <option value="file">Job File</option>
                        <option value="errors">Errors Only</option>
                    </select>
                </div>
                
                <div class="log-filters">
                    <select id="levelFilter">
                        <option value="all">All Levels</option>
                        <option value="DEBUG">Debug</option>
                        <option value="INFO">Info</option>
                        <option value="WARNING">Warning</option>
                        <option value="ERROR">Error</option>
                        <option value="CRITICAL">Critical</option>
                    </select>
                    
                    <select id="categoryFilter">
                        <option value="all">All Categories</option>
                        <option value="SYSTEM">System</option>
                        <option value="WIM">WIM</option>
                        <option value="DRIVER">Driver</option>
                        <option value="UPDATE">Update</option>
                        <option value="WORKFLOW">Workflow</option>
                        <option value="JOB">Job</option>
                    </select>
                    
                    <input type="text" id="searchFilter" placeholder="Search logs..." />
                </div>
                
                <div class="log-actions">
                    <button id="refreshLogs">Refresh</button>
                    <button id="clearLogs">Clear</button>
                    <button id="downloadLogs">Download</button>
                    <label>
                        <input type="checkbox" id="autoRefresh" checked> Auto-refresh
                    </label>
                </div>
            </div>
            
            <div class="log-stats">
                <span id="logCount">0 entries</span>
                <span id="errorCount">0 errors</span>
                <span id="lastUpdate">Never</span>
            </div>
            
            <div class="log-container" id="logContainer">
                <div class="loading">Loading logs...</div>
            </div>
        `;
        
        document.body.appendChild(container);
        this.logContainer = document.getElementById('logContainer');
        
        this.bindEvents();
    }
    
    bindEvents() {
        // Source selector
        document.getElementById('logSource').addEventListener('change', (e) => {
            this.currentSource = e.target.value;
            this.loadLogs();
        });
        
        // Filters
        document.getElementById('levelFilter').addEventListener('change', (e) => {
            this.filters.level = e.target.value;
            this.applyFilters();
        });
        
        document.getElementById('categoryFilter').addEventListener('change', (e) => {
            this.filters.category = e.target.value;
            this.applyFilters();
        });
        
        document.getElementById('searchFilter').addEventListener('input', (e) => {
            this.filters.search = e.target.value.toLowerCase();
            this.applyFilters();
        });
        
        // Actions
        document.getElementById('refreshLogs').addEventListener('click', () => {
            this.loadLogs();
        });
        
        document.getElementById('clearLogs').addEventListener('click', () => {
            this.clearDisplay();
        });
        
        document.getElementById('downloadLogs').addEventListener('click', () => {
            this.downloadLogs();
        });
        
        document.getElementById('autoRefresh').addEventListener('change', (e) => {
            this.autoRefresh = e.target.checked;
            if (this.autoRefresh) {
                this.startAutoRefresh();
            } else {
                this.stopAutoRefresh();
            }
        });
    }
    
    async loadLogs() {
        try {
            const response = await fetch(`/api/jobs/${this.jobId}/logs?source=${this.currentSource}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const logs = await response.json();
            this.displayLogs(logs);
            this.updateStats(logs);
            
        } catch (error) {
            console.error('Failed to load logs:', error);
            this.logContainer.innerHTML = `
                <div class="error">
                    Failed to load logs: ${error.message}
                </div>
            `;
        }
    }
    
    displayLogs(logs) {
        if (!logs || logs.length === 0) {
            this.logContainer.innerHTML = '<div class="no-logs">No logs available</div>';
            return;
        }
        
        // Sort logs by timestamp
        logs.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        
        const logHtml = logs.map(log => this.formatLogEntry(log)).join('');
        this.logContainer.innerHTML = logHtml;
        
        // Scroll to bottom
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
        
        // Apply current filters
        this.applyFilters();
    }
    
    formatLogEntry(log) {
        const timestamp = new Date(log.timestamp).toLocaleTimeString();
        const level = log.level || 'INFO';
        const category = log.category || 'SYSTEM';
        const component = log.component || 'unknown';
        const message = log.message || '';
        
        // Level color mapping
        const levelColors = {
            'DEBUG': 'text-muted',
            'INFO': 'text-success',
            'WARNING': 'text-warning', 
            'ERROR': 'text-danger',
            'CRITICAL': 'text-danger'
        };
        
        const levelClass = levelColors[level] || 'text-muted';
        
        // Format details if present
        let detailsHtml = '';
        if (log.details && typeof log.details === 'object') {
            const detailItems = Object.entries(log.details)
                .filter(([key]) => key !== 'exception')
                .map(([key, value]) => `${key}=${value}`)
                .join(', ');
            
            if (detailItems) {
                detailsHtml = `<div class="log-details">📋 ${detailItems}</div>`;
            }
            
            // Exception details
            if (log.details.exception) {
                const exc = log.details.exception;
                detailsHtml += `<div class="log-exception">💥 ${exc.type}: ${exc.message}</div>`;
            }
        }
        
        return `
            <div class="log-entry" data-level="${level}" data-category="${category}">
                <div class="log-header">
                    <span class="log-timestamp">${timestamp}</span>
                    <span class="log-level ${levelClass}">${level}</span>
                    <span class="log-category">${category}</span>
                    <span class="log-component">${component}</span>
                </div>
                <div class="log-message">${this.escapeHtml(message)}</div>
                ${detailsHtml}
            </div>
        `;
    }
    
    applyFilters() {
        const entries = this.logContainer.querySelectorAll('.log-entry');
        let visibleCount = 0;
        
        entries.forEach(entry => {
            let visible = true;
            
            // Level filter
            if (this.filters.level !== 'all') {
                const entryLevel = entry.dataset.level;
                if (entryLevel !== this.filters.level) {
                    visible = false;
                }
            }
            
            // Category filter
            if (this.filters.category !== 'all') {
                const entryCategory = entry.dataset.category;
                if (entryCategory !== this.filters.category) {
                    visible = false;
                }
            }
            
            // Search filter
            if (this.filters.search) {
                const entryText = entry.textContent.toLowerCase();
                if (!entryText.includes(this.filters.search)) {
                    visible = false;
                }
            }
            
            entry.style.display = visible ? 'block' : 'none';
            if (visible) visibleCount++;
        });
        
        // Update visible count
        document.getElementById('logCount').textContent = 
            `${visibleCount}/${entries.length} entries`;
    }
    
    updateStats(logs) {
        const totalCount = logs.length;
        const errorCount = logs.filter(log => 
            log.level === 'ERROR' || log.level === 'CRITICAL'
        ).length;
        
        document.getElementById('logCount').textContent = `${totalCount} entries`;
        document.getElementById('errorCount').textContent = `${errorCount} errors`;
        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
    }
    
    clearDisplay() {
        this.logContainer.innerHTML = '<div class="no-logs">Logs cleared</div>';
        document.getElementById('logCount').textContent = '0 entries';
        document.getElementById('errorCount').textContent = '0 errors';
    }
    
    async downloadLogs() {
        try {
            const logType = this.currentSource === 'errors' ? 'error' : 'main';
            const response = await fetch(`/api/jobs/${this.jobId}/download-log?log_type=${logType}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Create download link
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `kassia_job_${this.jobId}_${logType}.log`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
        } catch (error) {
            console.error('Failed to download logs:', error);
            alert(`Failed to download logs: ${error.message}`);
        }
    }
    
    startAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        if (this.autoRefresh) {
            this.refreshInterval = setInterval(() => {
                this.loadLogs();
            }, 5000); // Refresh every 5 seconds
        }
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    destroy() {
        this.stopAutoRefresh();
        // Remove UI elements if needed
    }
}

// CSS styles for the log viewer
const logViewerStyles = `
<style>
.job-log-viewer {
    max-width: 100%;
    margin: 20px;
    background: #f8f9fa;
    border-radius: 8px;
    overflow: hidden;
}

.log-controls {
    background: #e9ecef;
    padding: 15px;
    display: flex;
    gap: 15px;
    align-items: center;
    flex-wrap: wrap;
}

.log-controls label {
    font-weight: 500;
    margin-right: 5px;
}

.log-controls select, .log-controls input[type="text"] {
    padding: 5px 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
}

.log-controls button {
    padding: 5px 12px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.log-controls button:hover {
    background: #0056b3;
}

.log-stats {
    background: #dee2e6;
    padding: 10px 15px;
    display: flex;
    gap: 20px;
    font-size: 0.9em;
}

.log-container {
    max-height: 600px;
    overflow-y: auto;
    background: white;
    padding: 10px;
}

.log-entry {
    border-bottom: 1px solid #eee;
    padding: 8px 0;
    font-family: 'Courier New', monospace;
    font-size: 0.85em;
}

.log-header {
    display: flex;
    gap: 10px;
    margin-bottom: 4px;
}

.log-timestamp {
    color: #6c757d;
    font-weight: 500;
}

.log-level {
    font-weight: 600;
    min-width: 60px;
}

.log-category {
    background: #e9ecef;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.8em;
}

.log-component {
    color: #495057;
    font-style: italic;
}

.log-message {
    margin-left: 20px;
    color: #212529;
}

.log-details {
    margin-left: 20px;
    color: #6c757d;
    font-size: 0.8em;
    font-style: italic;
}

.log-exception {
    margin-left: 20px;
    color: #dc3545;
    font-size: 0.8em;
    font-weight: 500;
}

.text-success { color: #28a745 !important; }
.text-warning { color: #ffc107 !important; }
.text-danger { color: #dc3545 !important; }
.text-muted { color: #6c757d !important; }

.loading, .no-logs, .error {
    text-align: center;
    padding: 40px;
    color: #6c757d;
    font-style: italic;
}

.error {
    color: #dc3545;
    background: #f8d7da;
    border: 1px solid #f5c6cb;
    border-radius: 4px;
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', logViewerStyles);

// Usage example:
// const logViewer = new JobLogViewer('your-job-id-here');

window.JobLogViewer = JobLogViewer;
