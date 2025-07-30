class SystemLogViewer {
    constructor() {
        this.logContainer = null;
        this.autoRefresh = true;
        this.refreshInterval = null;
        this.filters = {
            level: 'all',
            category: 'all',
            search: ''
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    init() {
        this.createUI();
        this.loadLogs();
        this.startAutoRefresh();
    }

    createUI() {
        const wrapper = document.getElementById('systemLogsWrapper');
        if (!wrapper) return;
        wrapper.className = 'system-log-viewer';
        wrapper.innerHTML = `
            <div class="log-controls">
                <div class="log-filters">
                    <select id="sysLevelFilter">
                        <option value="all">All Levels</option>
                        <option value="DEBUG">Debug</option>
                        <option value="INFO">Info</option>
                        <option value="WARNING">Warning</option>
                        <option value="ERROR">Error</option>
                        <option value="CRITICAL">Critical</option>
                    </select>

                    <select id="sysCategoryFilter">
                        <option value="all">All Categories</option>
                        <option value="SYSTEM">System</option>
                        <option value="WIM">WIM</option>
                        <option value="DRIVER">Driver</option>
                        <option value="UPDATE">Update</option>
                        <option value="WORKFLOW">Workflow</option>
                        <option value="JOB">Job</option>
                    </select>

                    <input type="text" id="sysSearchFilter" placeholder="Search logs..." />
                </div>

                <div class="log-actions">
                    <button id="sysRefreshLogs">Refresh</button>
                    <button id="sysClearLogs">Clear</button>
                    <label>
                        <input type="checkbox" id="sysAutoRefresh" checked> Auto-refresh
                    </label>
                </div>
            </div>

            <div class="log-stats">
                <span id="sysLogCount">0 entries</span>
                <span id="sysErrorCount">0 errors</span>
                <span id="sysLastUpdate">Never</span>
            </div>

            <div class="log-container" id="sysLogContainer">
                <div class="loading">Loading logs...</div>
            </div>
        `;
        this.logContainer = document.getElementById('sysLogContainer');
        this.bindEvents();
    }

    bindEvents() {
        document.getElementById('sysLevelFilter').addEventListener('change', e => {
            this.filters.level = e.target.value;
            this.applyFilters();
        });

        document.getElementById('sysCategoryFilter').addEventListener('change', e => {
            this.filters.category = e.target.value;
            this.applyFilters();
        });

        document.getElementById('sysSearchFilter').addEventListener('input', e => {
            this.filters.search = e.target.value.toLowerCase();
            this.applyFilters();
        });

        document.getElementById('sysRefreshLogs').addEventListener('click', () => {
            this.loadLogs();
        });

        document.getElementById('sysClearLogs').addEventListener('click', () => {
            this.clearDisplay();
        });

        document.getElementById('sysAutoRefresh').addEventListener('change', e => {
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
            let url = '/api/system/logs';
            if (this.filters.level !== 'all') {
                url += `?level=${this.filters.level}`;
            }
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const logs = await response.json();
            this.displayLogs(logs);
            this.updateStats(logs);
        } catch (error) {
            console.error('Failed to load system logs:', error);
            this.logContainer.innerHTML = `<div class="error">Failed to load logs: ${error.message}</div>`;
        }
    }

    displayLogs(logs) {
        if (!logs || logs.length === 0) {
            this.logContainer.innerHTML = '<div class="no-logs">No logs available</div>';
            return;
        }

        logs.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        const logHtml = logs.map(log => this.formatLogEntry(log)).join('');
        this.logContainer.innerHTML = logHtml;
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
        this.applyFilters();
    }

    formatLogEntry(log) {
        const timestamp = new Date(log.timestamp).toLocaleTimeString();
        const level = log.level || 'INFO';
        const category = log.category || 'SYSTEM';
        const component = log.component || 'unknown';
        const message = log.message || '';

        const levelColors = {
            'DEBUG': 'text-muted',
            'INFO': 'text-success',
            'WARNING': 'text-warning',
            'ERROR': 'text-danger',
            'CRITICAL': 'text-danger'
        };
        const levelClass = levelColors[level] || 'text-muted';

        let detailsHtml = '';
        if (log.details && typeof log.details === 'object') {
            const detailItems = Object.entries(log.details)
                .filter(([key]) => key !== 'exception')
                .map(([key, value]) => `${key}=${value}`)
                .join(', ');
            if (detailItems) {
                detailsHtml = `<div class="log-details">📋 ${detailItems}</div>`;
            }
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
            if (this.filters.level !== 'all') {
                const entryLevel = entry.dataset.level;
                if (entryLevel !== this.filters.level) visible = false;
            }
            if (this.filters.category !== 'all') {
                const entryCategory = entry.dataset.category;
                if (entryCategory !== this.filters.category) visible = false;
            }
            if (this.filters.search) {
                const entryText = entry.textContent.toLowerCase();
                if (!entryText.includes(this.filters.search)) visible = false;
            }
            entry.style.display = visible ? 'block' : 'none';
            if (visible) visibleCount++;
        });
        document.getElementById('sysLogCount').textContent = `${visibleCount}/${entries.length} entries`;
    }

    updateStats(logs) {
        const totalCount = logs.length;
        const errorCount = logs.filter(log => log.level === 'ERROR' || log.level === 'CRITICAL').length;
        document.getElementById('sysLogCount').textContent = `${totalCount} entries`;
        document.getElementById('sysErrorCount').textContent = `${errorCount} errors`;
        document.getElementById('sysLastUpdate').textContent = new Date().toLocaleTimeString();
    }

    clearDisplay() {
        this.logContainer.innerHTML = '<div class="no-logs">Logs cleared</div>';
        document.getElementById('sysLogCount').textContent = '0 entries';
        document.getElementById('sysErrorCount').textContent = '0 errors';
    }

    startAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        if (this.autoRefresh) {
            this.refreshInterval = setInterval(() => this.loadLogs(), 5000);
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
}

const logViewerStyles = `
<style>
.system-log-viewer {
    max-width: 100%;
    margin: 20px;
    background: #f8f9fa;
    border-radius: 8px;
    overflow: hidden;
}

.system-log-viewer .log-controls {
    background: #e9ecef;
    padding: 15px;
    display: flex;
    gap: 15px;
    align-items: center;
    flex-wrap: wrap;
}

.system-log-viewer .log-controls label {
    font-weight: 500;
    margin-right: 5px;
}

.system-log-viewer .log-controls select,
.system-log-viewer .log-controls input[type="text"] {
    padding: 5px 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
}

.system-log-viewer .log-controls button {
    padding: 5px 12px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.system-log-viewer .log-controls button:hover {
    background: #0056b3;
}

.system-log-viewer .log-stats {
    background: #dee2e6;
    padding: 10px 15px;
    display: flex;
    gap: 20px;
    font-size: 0.9em;
}

.system-log-viewer .log-container {
    max-height: 600px;
    overflow-y: auto;
    background: white;
    padding: 10px;
}

.system-log-viewer .log-entry {
    border-bottom: 1px solid #eee;
    padding: 8px 0;
    font-family: 'Courier New', monospace;
    font-size: 0.85em;
}

.system-log-viewer .log-header {
    display: flex;
    gap: 10px;
    margin-bottom: 4px;
}

.system-log-viewer .log-timestamp {
    color: #6c757d;
    font-weight: 500;
}

.system-log-viewer .log-level {
    font-weight: 600;
    min-width: 60px;
}

.system-log-viewer .log-category {
    background: #e9ecef;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.8em;
}

.system-log-viewer .log-component {
    color: #495057;
    font-style: italic;
}

.system-log-viewer .log-message {
    margin-left: 20px;
    color: #212529;
}

.system-log-viewer .log-details {
    margin-left: 20px;
    color: #6c757d;
    font-size: 0.8em;
    font-style: italic;
}

.system-log-viewer .log-exception {
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

document.head.insertAdjacentHTML('beforeend', logViewerStyles);

window.SystemLogViewer = SystemLogViewer;
