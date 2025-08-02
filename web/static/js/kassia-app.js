// web/static/js/kassia-app.js - Main Application Logic

// ============= GLOBAL APPLICATION STATE =============
window.kassiaState = {
    devices: [],
    selectedDevice: null,
    selectedOS: null,
    currentAssets: null,
    isInitialized: false,
    activeJobId: null,
    currentLogLevel: 'all',
    jobUpdateSubscriptions: new Set(),
    lastHeartbeat: null,
    connectionStatus: 'connecting'
};

// ============= ENHANCED WEBSOCKET INTEGRATION =============
function setupWebSocketHandlers() {
    if (window.websocketManager) {
        // Enhanced job update handler
        window.websocketManager.onJobUpdate = function(data) {
            console.log('📡 Job update received:', data);
            
            if (data.type === 'job_update') {
                updateJobDisplay(data.job_id, data.data);
                updateDashboardStats();
                
                // Update active job if it's the current one
                if (window.kassiaState.activeJobId === data.job_id) {
                    updateActiveJobDisplay(data.data);
                }
            } else if (data.type === 'job_log') {
                addLogToDisplay(data.job_id, data.log);
            } else if (data.type === 'system_status') {
                updateSystemStatus(data);
            } else if (data.type === 'heartbeat') {
                window.kassiaState.lastHeartbeat = new Date();
                updateConnectionStatus('connected');
            }
        };
        
        // Connection status handlers
        window.websocketManager.onConnect = function() {
            console.log('✅ WebSocket connected');
            updateConnectionStatus('connected');
            if (window.uiManager) {
                window.uiManager.showToast('Connected to server', 'success');
            }
        };
        
        window.websocketManager.onDisconnect = function() {
            console.log('❌ WebSocket disconnected');
            updateConnectionStatus('disconnected');
            if (window.uiManager) {
                window.uiManager.showToast('Connection lost. Attempting to reconnect...', 'warning');
            }
        };
        
        window.websocketManager.onError = function(error) {
            console.error('❌ WebSocket error:', error);
            updateConnectionStatus('error');
            if (window.uiManager) {
                window.uiManager.showToast('Connection error: ' + error, 'error');
            }
        };
    }
}

// ============= ENHANCED JOB DISPLAY FUNCTIONS =============
function updateActiveJobDisplay(jobData) {
    const activeJobCard = document.getElementById('activeJobCard');
    
    if (!jobData || jobData.status === 'completed' || jobData.status === 'failed' || jobData.status === 'cancelled') {
        if (activeJobCard) activeJobCard.style.display = 'none';
        window.kassiaState.activeJobId = null;
        return;
    }
    
    if (jobData.status === 'running') {
        window.kassiaState.activeJobId = jobData.id;
        if (activeJobCard) activeJobCard.style.display = 'block';
        
        // Update job info
        const elements = {
            'activeJobTitle': `${jobData.device} - OS ${jobData.os_id}`,
            'activeJobStatus': jobData.status,
            'activeJobProgress': `${jobData.progress || 0}%`,
            'activeJobStep': jobData.current_step || 'Initializing'
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
        
        // Update progress bar
        const progressFill = document.querySelector('#activeJobProgressBar .progress-fill');
        if (progressFill) {
            progressFill.style.width = `${jobData.progress || 0}%`;
        }
        
        // Update step indicators
        updateStepIndicators(jobData.step_number || 0, jobData.total_steps || 9);
        
        // Update status badge class
        const statusBadge = document.getElementById('activeJobStatus');
        if (statusBadge) {
            statusBadge.className = `status-badge status-${jobData.status}`;
        }
        
        // Show action buttons
        const viewBtn = document.getElementById('viewJobBtn');
        const cancelBtn = document.getElementById('cancelJobBtn');
        if (viewBtn) viewBtn.style.display = 'inline-flex';
        if (cancelBtn) cancelBtn.style.display = 'inline-flex';
        
        // Update logs if available
        if (jobData.logs && jobData.logs.length > 0) {
            updateActiveJobLogs(jobData.logs);
        }
    }
}

function updateStepIndicators(currentStep, totalSteps) {
    const stepsContainer = document.getElementById('activeJobSteps');
    if (!stepsContainer) return;
    
    stepsContainer.innerHTML = '';
    
    for (let i = 1; i <= totalSteps; i++) {
        const stepIndicator = document.createElement('div');
        stepIndicator.className = 'step-indicator';
        
        if (i < currentStep) {
            stepIndicator.classList.add('completed');
        } else if (i === currentStep) {
            stepIndicator.classList.add('active');
        }
        
        stepIndicator.textContent = i;
        stepIndicator.title = `Step ${i} of ${totalSteps}`;
        stepsContainer.appendChild(stepIndicator);
    }
}

function updateActiveJobLogs(logs) {
    const logsDisplay = document.getElementById('activeJobLogs');
    if (!logsDisplay) return;
    
    // Clear existing logs except the initial message
    const existingLogs = logsDisplay.querySelectorAll('.log-entry:not(.log-placeholder)');
    existingLogs.forEach(log => log.remove());
    
    // Add new logs
    logs.forEach(log => {
        addLogToActiveDisplay(log);
    });
    
    // Scroll to bottom
    logsDisplay.scrollTop = logsDisplay.scrollHeight;
}

function addLogToActiveDisplay(log) {
    const logsDisplay = document.getElementById('activeJobLogs');
    if (!logsDisplay) return;
    
    // Filter by log level if needed
    if (window.kassiaState.currentLogLevel !== 'all' && log.level !== window.kassiaState.currentLogLevel.toUpperCase()) {
        return;
    }
    
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${log.level.toLowerCase()}`;
    
    const timestamp = new Date(log.timestamp).toLocaleTimeString();
    
    logEntry.innerHTML = `
        <span class="log-timestamp">${timestamp}</span>
        <span class="log-level">${log.level}</span>
        <span class="log-message">${log.message}</span>
    `;
    
    logsDisplay.appendChild(logEntry);
    
    // Keep only last 50 log entries for performance
    const logEntries = logsDisplay.querySelectorAll('.log-entry:not(.log-placeholder)');
    if (logEntries.length > 50) {
        logEntries[0].remove();
    }
    
    // Auto-scroll to bottom
    logsDisplay.scrollTop = logsDisplay.scrollHeight;
}

function addLogToDisplay(jobId, log) {
    if (window.kassiaState.activeJobId === jobId) {
        addLogToActiveDisplay(log);
    }
}

// ============= LOG CONTROL FUNCTIONS =============
function toggleLogLevel() {
    const levels = ['all', 'info', 'warning', 'error'];
    const currentIndex = levels.indexOf(window.kassiaState.currentLogLevel);
    const nextIndex = (currentIndex + 1) % levels.length;
    window.kassiaState.currentLogLevel = levels[nextIndex];
    
    const btn = document.getElementById('logLevelBtn');
    if (btn) {
        btn.textContent = window.kassiaState.currentLogLevel.charAt(0).toUpperCase() + window.kassiaState.currentLogLevel.slice(1) + ' Logs';
    }
    
    // Refresh log display
    const activeJob = window.kassiaState.activeJobId;
    if (activeJob) {
        fetchJobLogs(activeJob);
    }
}

function clearLogDisplay() {
    const logsDisplay = document.getElementById('activeJobLogs');
    if (logsDisplay) {
        logsDisplay.innerHTML = `
            <div class="log-entry log-info log-placeholder">
                <span class="log-timestamp">--:--:--</span>
                <span class="log-level">INFO</span>
                <span class="log-message">Log display cleared</span>
            </div>
        `;
    }
}

async function fetchJobLogs(jobId) {
    try {
        const apiManager = window.apiManager || window.api;
        const logs = await apiManager.get(`/api/jobs/${jobId}/logs?limit=20`);
        updateActiveJobLogs(logs);
    } catch (error) {
        console.error('Failed to fetch job logs:', error);
    }
}

// ============= CONNECTION STATUS MANAGEMENT =============
function updateConnectionStatus(status) {
    window.kassiaState.connectionStatus = status;
    
    const statusElement = document.getElementById('connectionStatus');
    const statusDot = document.getElementById('systemStatusDot');
    const statusText = document.getElementById('systemStatusText');
    
    if (statusElement) {
        statusElement.className = `connection-status status-${status}`;
        
        switch (status) {
            case 'connected':
                statusElement.innerHTML = '<span>🟢 Connected</span>';
                break;
            case 'connecting':
                statusElement.innerHTML = '<span>🟡 Connecting...</span>';
                break;
            case 'disconnected':
                statusElement.innerHTML = '<span>🟠 Disconnected</span>';
                break;
            case 'error':
                statusElement.innerHTML = '<span>🔴 Connection Error</span>';
                break;
        }
    }
    
    if (statusDot && statusText) {
        statusDot.className = `status-dot status-${status}`;
        statusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }
}

function updateSystemStatus(statusData) {
    updateConnectionStatus('connected');
    
    // Update job counts if provided
    if (statusData.active_jobs !== undefined) {
        const runningJobsEl = document.getElementById('runningJobs');
        if (runningJobsEl) {
            runningJobsEl.textContent = statusData.active_jobs;
        }
    }
    
    if (statusData.total_jobs !== undefined) {
        const totalJobsEl = document.getElementById('totalJobs');
        if (totalJobsEl) {
            totalJobsEl.textContent = statusData.total_jobs;
        }
    }
}

// ============= ENHANCED JOB MANAGEMENT =============
function updateJobDisplay(jobId, jobData) {
    // Update job in the jobs list
    const jobElement = document.querySelector(`[data-job-id="${jobId}"]`);
    if (jobElement) {
        updateJobElement(jobElement, jobData);
    }
    
    // Update in recent jobs list if visible
    const recentJobElement = document.querySelector(`#recentJobsList [data-job-id="${jobId}"]`);
    if (recentJobElement) {
        updateJobElement(recentJobElement, jobData);
    }
}

function updateJobElement(element, jobData) {
    // Update status badge
    const statusBadge = element.querySelector('.status-badge');
    if (statusBadge) {
        statusBadge.textContent = jobData.status;
        statusBadge.className = `status-badge status-${jobData.status}`;
    }
    
    // Update progress bar
    const progressBar = element.querySelector('.progress-fill');
    if (progressBar) {
        progressBar.style.width = `${jobData.progress || 0}%`;
    }
    
    // Update step text
    const stepText = element.querySelector('.job-step');
    if (stepText) {
        stepText.textContent = `${jobData.current_step || 'Initializing'} (${jobData.step_number || 0}/${jobData.total_steps || 9})`;
    }
    
    // Update progress percentage
    const progressText = element.querySelector('.progress-text');
    if (progressText) {
        progressText.textContent = `Progress: ${jobData.progress || 0}%`;
    }
}

async function cancelActiveJob() {
    if (!window.kassiaState.activeJobId) return;
    
    if (!confirm('Are you sure you want to cancel the active job?')) return;
    
    try {
        const apiManager = window.apiManager || window.api;
        await apiManager.delete(`/api/jobs/${window.kassiaState.activeJobId}`);
        
        if (window.uiManager) {
            window.uiManager.showToast('Job cancelled successfully', 'success');
        }
        
        // Hide active job display
        const activeJobCard = document.getElementById('activeJobCard');
        if (activeJobCard) activeJobCard.style.display = 'none';
        window.kassiaState.activeJobId = null;
        
        // Refresh job lists
        setTimeout(() => {
            if (typeof refreshJobs === 'function') refreshJobs();
            if (typeof refreshRecentJobs === 'function') refreshRecentJobs();
        }, 500);
        
    } catch (error) {
        console.error('Failed to cancel job:', error);
        if (window.uiManager) {
            window.uiManager.showToast('Failed to cancel job: ' + error.message, 'error');
        }
    }
}

// ============= ENHANCED DASHBOARD FUNCTIONS =============
async function updateDashboardStats() {
    try {
        const apiManager = window.apiManager || window.api;
        const jobs = await apiManager.get('/api/jobs');
        
        const stats = {
            total: jobs.length,
            running: jobs.filter(j => j.status === 'running').length,
            completed: jobs.filter(j => j.status === 'completed').length,
            failed: jobs.filter(j => j.status === 'failed' || j.status === 'cancelled').length
        };
        
        // Update dashboard counters
        const elements = {
            'totalJobs': stats.total,
            'runningJobs': stats.running,
            'completedJobs': stats.completed,
            'failedJobs': stats.failed
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
        
        // Update active job display
        const runningJob = jobs.find(j => j.status === 'running');
        if (runningJob) {
            updateActiveJobDisplay(runningJob);
        } else {
            const activeJobCard = document.getElementById('activeJobCard');
            if (activeJobCard) activeJobCard.style.display = 'none';
            window.kassiaState.activeJobId = null;
        }
        
        return stats;
        
    } catch (error) {
        console.error('Failed to update dashboard stats:', error);
        return null;
    }
}

async function refreshRecentJobs() {
    try {
        const apiManager = window.apiManager || window.api;
        const jobs = await apiManager.get('/api/jobs?limit=10');
        
        displayRecentJobs(jobs);
        
    } catch (error) {
        console.error('Failed to refresh recent jobs:', error);
        if (window.uiManager) {
            window.uiManager.showToast('Failed to refresh recent jobs: ' + error.message, 'error');
        }
    }
}

function displayRecentJobs(jobs) {
    const recentJobsList = document.getElementById('recentJobsList');
    if (!recentJobsList) return;
    
    if (!jobs || jobs.length === 0) {
        recentJobsList.innerHTML = `
            <p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;" data-translate="no_jobs_yet">
                No jobs yet. Start a new build to see activity here.
            </p>
        `;
        return;
    }
    
    let html = '<div class="recent-jobs-grid">';
    
    jobs.slice(0, 5).forEach(job => {
        const statusClass = getStatusClass(job.status);
        const progress = job.progress || 0;
        const createdAt = new Date(job.created_at).toLocaleString();
        
        html += `
            <div class="recent-job-item" data-job-id="${job.id}">
                <div class="job-header">
                    <div class="job-title">
                        <strong>${job.device} - OS ${job.os_id}</strong>
                        <span class="status-badge ${statusClass}">${job.status}</span>
                    </div>
                    <div class="job-timestamp">${createdAt}</div>
                </div>
                
                <div class="job-details">
                    <div class="job-step">${job.current_step || 'Initializing'} (${job.step_number || 0}/${job.total_steps || 9})</div>
                    <div class="job-progress">
                        <div class="progress-bar-small">
                            <div class="progress-fill" style="width: ${progress}%;"></div>
                        </div>
                        <span class="progress-text">Progress: ${progress}%</span>
                    </div>
                </div>
                
                <div class="job-actions">
                    <button class="btn btn-sm btn-secondary" onclick="viewJobDetails('${job.id}')">
                        View Details
                    </button>
                    ${job.status === 'running' ? 
                        `<button class="btn btn-sm btn-warning" onclick="cancelJob('${job.id}')">Cancel</button>` : 
                        ''
                    }
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    recentJobsList.innerHTML = html;
}

// ============= UTILITY FUNCTIONS =============
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
}

function getStatusClass(status) {
    switch (status) {
        case 'completed': return 'status-success';
        case 'running': return 'status-running';
        case 'failed': 
        case 'cancelled': return 'status-error';
        default: return 'status-pending';
    }
}

function showToast(message, type = 'info') {
    if (window.uiManager && window.uiManager.showToast) {
        window.uiManager.showToast(message, type);
    } else {
        // Fallback
        console.log(`${type.toUpperCase()}: ${message}`);
    }
}

// ============= JOB FUNCTIONS =============
async function cancelJob(jobId) {
    if (!confirm('Are you sure you want to cancel this job?')) return;
    
    try {
        const apiManager = window.apiManager || window.api;
        await apiManager.delete(`/api/jobs/${jobId}`);
        showToast('Job cancelled successfully', 'success');
        
        // Refresh displays
        setTimeout(() => {
            refreshJobs();
            refreshRecentJobs();
            updateDashboardStats();
        }, 500);
        
    } catch (error) {
        console.error('Failed to cancel job:', error);
        showToast('Failed to cancel job: ' + error.message, 'error');
    }
}

async function deleteJob(jobId) {
    if (!confirm('Are you sure you want to permanently delete this job? This action cannot be undone.')) {
        return;
    }
    
    try {
        const apiManager = window.apiManager || window.api;
        await apiManager.delete(`/api/jobs/${jobId}/delete`);
        showToast('Job deleted successfully', 'success');
        
        // Refresh displays
        setTimeout(() => {
            refreshJobs();
            refreshRecentJobs();
            updateDashboardStats();
        }, 500);
        
    } catch (error) {
        console.error('Failed to delete job:', error);
        showToast('Failed to delete job: ' + error.message, 'error');
    }
}

function downloadWim(wimPath) {
    console.log('Downloading WIM:', wimPath);
    showToast(`WIM download would start: ${wimPath}`, 'info');
    // This would typically trigger a download or provide download instructions
}

async function refreshJobs() {
    console.log('🔄 Refreshing jobs...');
    
    try {
        const apiManager = window.apiManager || window.api;
        const jobs = await apiManager.get('/api/jobs');
        
        console.log('✅ Jobs loaded:', jobs);
        displayJobs(jobs);
        
    } catch (error) {
        console.error('❌ Failed to refresh jobs:', error);
        showToast('Failed to refresh jobs: ' + error.message, 'error');
    }
}

function displayJobs(jobs) {
    const jobsList = document.getElementById('jobsList');
    if (!jobsList) return;
    
    if (!jobs || jobs.length === 0) {
        jobsList.innerHTML = '<p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">No build jobs found. Start your first build to see it here.</p>';
        return;
    }
    
    let html = '<div style="display: grid; gap: 16px;">';
    
    jobs.forEach(job => {
        const statusClass = getStatusClass(job.status);
        const progress = job.progress || 0;
        const createdAt = new Date(job.created_at).toLocaleString();
        const duration = job.completed_at ? 
            formatDuration(Math.floor((new Date(job.completed_at) - new Date(job.started_at || job.created_at)) / 1000)) : 
            '';
        
        html += `
            <div class="job-item enhanced" data-job-id="${job.id}" data-status="${job.status}">
                <div class="job-header">
                    <div class="job-main-info">
                        <div class="job-title">
                            <strong>${job.device} - OS ${job.os_id}</strong>
                            <span class="job-id">ID: ${job.id.substring(0, 8)}</span>
                        </div>
                        <span class="status-badge ${statusClass}">${job.status}</span>
                    </div>
                    <div class="job-metadata">
                        <div class="job-timestamp">Created: ${createdAt}</div>
                        ${duration ? `<div class="job-duration">Duration: ${duration}</div>` : ''}
                    </div>
                </div>
                
                <div class="job-body">
                    <div class="job-progress-section">
                        <div class="job-step">${job.current_step || 'Initializing'} (${job.step_number || 0}/${job.total_steps || 9})</div>
                        <div class="progress-container">
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${progress}%;"></div>
                            </div>
                            <span class="progress-text">${progress}%</span>
                        </div>
                    </div>
                    
                    ${job.error ? `
                        <div class="job-error">
                            <strong>Error:</strong> ${job.error}
                        </div>
                    ` : ''}
                    
                    ${job.results && job.results.final_wim_size_mb ? `
                        <div class="job-results">
                            <strong>Final WIM:</strong> ${job.results.final_wim_size_mb.toFixed(1)} MB
                            ${job.results.export_name ? `<br><strong>File:</strong> ${job.results.export_name}` : ''}
                        </div>
                    ` : ''}
                </div>
                
                <div class="job-actions">
                    <button class="btn btn-sm btn-secondary" onclick="viewJobDetails('${job.id}')">
                        <svg width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm1 3.5a.5.5 0 0 1 .5.5v3.5a.5.5 0 0 1-1 0V5a.5.5 0 0 1 .5-.5z"/>
                        </svg>
                        Details
                    </button>
                    
                    ${job.status === 'running' ? `
                        <button class="btn btn-sm btn-warning" onclick="cancelJob('${job.id}')">
                            <svg width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm4.646 5.646a.5.5 0 0 1-.646.708L8 4.854 5.354 7.5a.5.5 0 1 1-.708-.708l3-3a.5.5 0 0 1 .708 0l3 3z"/>
                            </svg>
                            Cancel
                        </button>
                    ` : ''}
                    
                    ${job.status === 'completed' || job.status === 'failed' ? `
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteJob('${job.id}')">
                            <svg width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
                            </svg>
                            Delete
                        </button>
                    ` : ''}
                    
                    ${job.status === 'completed' && job.results && job.results.final_wim_path ? `
                        <button class="btn btn-sm btn-success" onclick="downloadWim('${job.results.final_wim_path}')">
                            <svg width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
                                <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/>
                            </svg>
                            Download
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    jobsList.innerHTML = html;
}

function filterJobs() {
    const filter = document.getElementById('jobsStatusFilter').value;
    console.log('Filtering jobs by status:', filter);
    
    // This would filter the displayed jobs
    refreshJobs();
}

function filterRecentJobs() {
    const filter = document.getElementById('jobStatusFilter').value;
    console.log('Filtering recent jobs by status:', filter);
    
    // This would filter the displayed jobs
    refreshRecentJobs();
}

async function cleanupCompletedJobs() {
    if (!confirm('Are you sure you want to remove all completed and failed jobs from the display? This will not delete them from the database.')) {
        return;
    }
    
    try {
        // This would typically call an API to cleanup the display
        showToast('Cleaning up completed jobs...', 'info');
        
        // For now, just refresh the jobs list
        setTimeout(() => {
            refreshJobs();
            refreshRecentJobs();
            showToast('Jobs display refreshed', 'success');
        }, 500);
        
    } catch (error) {
        console.error('Failed to cleanup jobs:', error);
        showToast('Failed to cleanup jobs: ' + error.message, 'error');
    }
}

// ============= TAB MANAGEMENT =============
function switchTab(tabName) {
    console.log(`🔄 Switching to tab: ${tabName}`);
    
    // Remove active from all tabs and nav items
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Activate selected tab and nav item
    const targetTab = document.getElementById(tabName);
    const navItem = document.querySelector(`.nav-item[onclick="switchTab('${tabName}')"]`);
    
    if (targetTab) {
        targetTab.classList.add('active');
        console.log(`✅ Tab ${tabName} activated`);
    } else {
        console.error(`❌ Tab ${tabName} not found`);
    }
    
    if (navItem) {
        navItem.classList.add('active');
    }
    
    // Tab-specific initialization
    if (tabName === 'dashboard') {
        setTimeout(() => {
            updateDashboardStats();
            refreshRecentJobs();
        }, 100);
    } else if (tabName === 'build') {
        initializeBuildTab();
    } else if (tabName === 'assets') {
        initializeAssetsTab();
    } else if (tabName === 'jobs') {
        setTimeout(() => refreshJobs(), 100);
    } else if (tabName === 'admin') {
        setTimeout(() => {
            loadDatabaseInfo();
            loadStatistics();
        }, 100);
    }
    
    // Update UI manager if available
    if (window.uiManager) {
        window.uiManager.currentTab = tabName;
        if (window.uiManager.onTabSwitch) {
            window.uiManager.onTabSwitch(tabName);
        }
    }
}

// ============= BUILD TAB FUNCTIONS =============
async function initializeBuildTab() {
    console.log('🔄 Initializing Build tab...');
    
    try {
        // Load devices if not already loaded
        if (!window.kassiaState.devices.length) {
            await loadDevices();
        }
        
        // Set up form handlers
        setupBuildForm();
        
        console.log('✅ Build tab initialized');
        
    } catch (error) {
        console.error('❌ Failed to initialize Build tab:', error);
        showToast('Failed to initialize build form: ' + error.message, 'error');
    }
}

async function loadDevices() {
    console.log('🔄 Loading devices...');
    
    try {
        const apiManager = window.apiManager || window.api;
        if (!apiManager) {
            throw new Error('API manager not available');
        }
        
        const devices = await apiManager.get('/api/devices');
        window.kassiaState.devices = devices;
        
        console.log('✅ Devices loaded:', devices);
        
        // Populate device dropdown
        const deviceSelect = document.getElementById('deviceSelect');
        if (deviceSelect) {
            deviceSelect.innerHTML = '<option value="">Select device...</option>';
            devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.device_id;
                option.textContent = `${device.device_id} (${device.supported_os.length} OS versions)`;
                deviceSelect.appendChild(option);
            });
        }
        
        return devices;
        
    } catch (error) {
        console.error('❌ Failed to load devices:', error);
        showToast('Failed to load device configurations: ' + error.message, 'error');
        throw error;
    }
}

function setupBuildForm() {
    const deviceSelect = document.getElementById('deviceSelect');
    const osSelect = document.getElementById('osSelect');
    const buildForm = document.getElementById('buildForm');
    
    if (!deviceSelect || !osSelect || !buildForm) {
        console.error('❌ Build form elements not found');
        return;
    }
    
    // Device selection handler
    deviceSelect.addEventListener('change', function() {
        const deviceId = this.value;
        window.kassiaState.selectedDevice = deviceId;
        
        console.log('Device selected:', deviceId);
        
        if (deviceId) {
            const device = window.kassiaState.devices.find(d => d.device_id === deviceId);
            if (device) {
                // Populate OS dropdown
                osSelect.innerHTML = '<option value="">Select OS...</option>';
                device.supported_os.forEach(osId => {
                    const option = document.createElement('option');
                    option.value = osId;
                    option.textContent = `OS ${osId}`;
                    osSelect.appendChild(option);
                });
                osSelect.disabled = false;
            }
        } else {
            osSelect.innerHTML = '<option value="">Select OS...</option>';
            osSelect.disabled = true;
            window.kassiaState.selectedOS = null;
        }
        
        updateBuildPreview();
    });
    
    // OS selection handler
    osSelect.addEventListener('change', function() {
        const osId = this.value;
        window.kassiaState.selectedOS = osId ? parseInt(osId) : null;
        
        console.log('OS selected:', osId);
        
        if (osId) {
            loadAssetPreview(window.kassiaState.selectedDevice, parseInt(osId));
        }
        
        updateBuildPreview();
    });
    
    // Form submission handler
    buildForm.addEventListener('submit', function(e) {
        e.preventDefault();
        startBuild();
    });
    
    console.log('✅ Build form handlers set up');
}

async function loadAssetPreview(device, osId) {
    if (!device || !osId) return;
    
    try {
        const apiManager = window.apiManager || window.api;
        const assets = await apiManager.get(`/api/assets/${device}/${osId}`);
        window.kassiaState.currentAssets = assets;
        
        console.log('✅ Asset preview loaded:', assets);
        updateBuildPreview();
        
    } catch (error) {
        console.error('❌ Failed to load asset preview:', error);
    }
}

function updateBuildPreview() {
    const preview = document.getElementById('buildPreview');
    const device = window.kassiaState.selectedDevice;
    const osId = window.kassiaState.selectedOS;
    const assets = window.kassiaState.currentAssets;
    
    if (!preview) return;
    
    if (device && osId) {
        preview.style.display = 'block';
        
        document.getElementById('previewDevice').textContent = device;
        document.getElementById('previewOS').textContent = `OS ${osId}`;
        
        if (assets) {
            document.getElementById('previewWimPath').textContent = assets.wim_path || 'Not found';
            document.getElementById('previewSBI').textContent = assets.sbi ? '✅ Found' : '❌ Missing';
            document.getElementById('previewDrivers').textContent = `${assets.drivers?.length || 0} found`;
            document.getElementById('previewUpdates').textContent = `${assets.updates?.length || 0} found`;
        } else {
            ['previewWimPath', 'previewSBI', 'previewDrivers', 'previewUpdates'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.textContent = 'Loading...';
            });
        }
    } else {
        preview.style.display = 'none';
    }
}

async function startBuild() {
    const device = window.kassiaState.selectedDevice;
    const osId = window.kassiaState.selectedOS;
    
    if (!device || !osId) {
        showToast('Please select device and OS first', 'error');
        return;
    }
    
    const skipDrivers = document.getElementById('skipDrivers')?.checked || false;
    const skipUpdates = document.getElementById('skipUpdates')?.checked || false;
    
    try {
        const startBtn = document.getElementById('startBuildBtn');
        startBtn.disabled = true;
        startBtn.innerHTML = '<div class="loading-spinner" style="margin-right: 8px;"></div>Starting...';
        
        const apiManager = window.apiManager || window.api;
        const result = await apiManager.post('/api/build', {
            device: device,
            os_id: osId,
            skip_drivers: skipDrivers,
            skip_updates: skipUpdates,
            skip_validation: false
        });
        
        console.log('✅ Build started:', result);
        showToast('Build started successfully! Job ID: ' + result.job_id, 'success');
        
        // Subscribe to job updates
        if (window.websocketManager) {
            window.websocketManager.subscribeToJob(result.job_id);
        }
        
        // Switch to dashboard to monitor progress
        setTimeout(() => {
            switchTab('dashboard');
            updateDashboardStats();
        }, 1000);
        
    } catch (error) {
        console.error('❌ Failed to start build:', error);
        showToast('Failed to start build: ' + error.message, 'error');
    } finally {
        const startBtn = document.getElementById('startBuildBtn');
        startBtn.disabled = false;
        startBtn.innerHTML = `
            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="m11.596 8.697-6.363 3.692c-.54.313-1.233-.066-1.233-.697V4.308c0-.63.692-1.01 1.233-.696l6.363 3.692a.802.802 0 0 1 0 1.393z"/>
            </svg>
            <span data-translate="start_build">Start Build</span>
        `;
    }
}

// ============= ASSETS TAB FUNCTIONS =============
async function initializeAssetsTab() {
    console.log('🔄 Initializing Assets tab...');
    
    try {
        // Load devices if not already loaded
        if (!window.kassiaState.devices.length) {
            await loadDevices();
        }
        
        // Populate device filter
        populateAssetFilters();
        
        // Set up filter handlers
        setupAssetFilters();
        
        console.log('✅ Assets tab initialized');
        
    } catch (error) {
        console.error('❌ Failed to initialize Assets tab:', error);
        showToast('Failed to initialize assets view: ' + error.message, 'error');
    }
}

function populateAssetFilters() {
    const deviceFilter = document.getElementById('assetDeviceFilter');
    const osFilter = document.getElementById('assetOSFilter');
    
    if (deviceFilter && window.kassiaState.devices.length) {
        deviceFilter.innerHTML = '<option value="">All Devices</option>';
        window.kassiaState.devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.device_id;
            option.textContent = device.device_id;
            deviceFilter.appendChild(option);
        });
    }
    
    if (osFilter) {
        osFilter.innerHTML = '<option value="">All OS</option>';
        // Collect all unique OS IDs
        const allOsIds = new Set();
        window.kassiaState.devices.forEach(device => {
            device.supported_os.forEach(osId => allOsIds.add(osId));
        });
        
        Array.from(allOsIds).sort((a, b) => a - b).forEach(osId => {
            const option = document.createElement('option');
            option.value = osId;
            option.textContent = `OS ${osId}`;
            osFilter.appendChild(option);
        });
    }
}

function setupAssetFilters() {
    const deviceFilter = document.getElementById('assetDeviceFilter');
    const osFilter = document.getElementById('assetOSFilter');
    
    if (deviceFilter) {
        deviceFilter.addEventListener('change', loadAssetsForFilter);
    }
    
    if (osFilter) {
        osFilter.addEventListener('change', loadAssetsForFilter);
    }
}

async function loadAssetsForFilter() {
    const deviceFilter = document.getElementById('assetDeviceFilter');
    const osFilter = document.getElementById('assetOSFilter');
    const assetsContent = document.getElementById('assetsContent');
    
    if (!deviceFilter || !osFilter || !assetsContent) return;
    
    const selectedDevice = deviceFilter.value;
    const selectedOS = osFilter.value;
    
    if (!selectedDevice || !selectedOS) {
        assetsContent.innerHTML = '<p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">Select device and OS to view available assets</p>';
        return;
    }
    
    try {
        assetsContent.innerHTML = '<div style="text-align: center; padding: 40px;"><div class="loading-spinner"></div><br>Loading assets...</div>';
        
        const apiManager = window.apiManager || window.api;
        const assets = await apiManager.get(`/api/assets/${selectedDevice}/${selectedOS}`);
        
        console.log('✅ Assets loaded for filter:', assets);
        displayAssets(assets);
        
    } catch (error) {
        console.error('❌ Failed to load assets:', error);
        assetsContent.innerHTML = `<div style="text-align: center; color: #dc3545; padding: 40px;">Failed to load assets: ${error.message}</div>`;
    }
}

function displayAssets(assets) {
    const assetsContent = document.getElementById('assetsContent');
    if (!assetsContent) return;
    
    let html = `
        <div style="display: grid; gap: 24px;">
            <div class="asset-section">
                <h4 style="margin-bottom: 16px; color: var(--siemens-text-primary);">📀 SBI (System Base Image)</h4>
    `;
    
    if (assets.sbi) {
        html += `
            <div class="asset-item ${assets.sbi.valid ? 'valid' : 'invalid'}">
                <div class="asset-info">
                    <strong>${assets.sbi.name}</strong>
                    <div class="asset-details">
                        Path: ${assets.sbi.path}<br>
                        Size: ${formatBytes(assets.sbi.size || 0)}
                    </div>
                </div>
                <div class="asset-status ${assets.sbi.valid ? 'valid' : 'invalid'}">
                    ${assets.sbi.valid ? '✅ Valid' : '❌ Invalid'}
                </div>
            </div>
        `;
    } else {
        html += '<p style="color: #dc3545;">❌ No SBI found for this configuration</p>';
    }
    
    html += '</div>';
    
    // Drivers section
    html += `
        <div class="asset-section">
            <h4 style="margin-bottom: 16px; color: var(--siemens-text-primary);">🔧 Drivers (${assets.drivers?.length || 0})</h4>
    `;
    
    if (assets.drivers && assets.drivers.length > 0) {
        assets.drivers.forEach(driver => {
            html += `
                <div class="asset-item ${driver.valid ? 'valid' : 'invalid'}">
                    <div class="asset-info">
                        <strong>${driver.name}</strong>
                        <div class="asset-details">
                            Type: ${driver.type}<br>
                            Path: ${driver.path}<br>
                            Size: ${formatBytes(driver.size || 0)}
                        </div>
                    </div>
                    <div class="asset-status ${driver.valid ? 'valid' : 'invalid'}">
                        ${driver.valid ? '✅ Valid' : '❌ Invalid'}
                    </div>
                </div>
            `;
        });
    } else {
        html += '<p style="color: #6c757d;">No drivers found for this configuration</p>';
    }
    
    html += '</div>';
    
    // Updates section
    html += `
        <div class="asset-section">
            <h4 style="margin-bottom: 16px; color: var(--siemens-text-primary);">📦 Updates (${assets.updates?.length || 0})</h4>
    `;
    
    if (assets.updates && assets.updates.length > 0) {
        assets.updates.forEach(update => {
            html += `
                <div class="asset-item ${update.valid ? 'valid' : 'invalid'}">
                    <div class="asset-info">
                        <strong>${update.name}</strong>
                        <div class="asset-details">
                            Type: ${update.type}<br>
                            Path: ${update.path}<br>
                            Size: ${formatBytes(update.size || 0)}
                        </div>
                    </div>
                    <div class="asset-status ${update.valid ? 'valid' : 'invalid'}">
                        ${update.valid ? '✅ Valid' : '❌ Invalid'}
                    </div>
                </div>
            `;
        });
    } else {
        html += '<p style="color: #6c757d;">No updates found for this configuration</p>';
    }
    
    html += '</div></div>';
    
    assetsContent.innerHTML = html;
}

function refreshAssets() {
    console.log('🔄 Refreshing assets...');
    loadAssetsForFilter();
}

// ============= ADMIN PANEL FUNCTIONS =============
async function loadDatabaseInfo() {
    console.log('🔄 Loading database info...');
    
    try {
        const elements = ['dbJobCount', 'dbLogCount', 'dbSize', 'dbEventCount'];
        elements.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '...';
        });
        
        const apiManager = window.apiManager || window.api;
        const dbInfo = await apiManager.get('/api/admin/database/info');
        
        console.log('✅ Database info received:', dbInfo);
        
        const dbJobCount = document.getElementById('dbJobCount');
        const dbLogCount = document.getElementById('dbLogCount');
        const dbSize = document.getElementById('dbSize');
        const dbEventCount = document.getElementById('dbEventCount');
        const dbPath = document.getElementById('dbPath');
        
        if (dbJobCount) dbJobCount.textContent = dbInfo.job_count || 0;
        if (dbLogCount) dbLogCount.textContent = dbInfo.log_count || 0;
        if (dbSize) dbSize.textContent = formatBytes(dbInfo.database_size_bytes || 0);
        if (dbEventCount) dbEventCount.textContent = dbInfo.event_count || 0;
        if (dbPath) dbPath.textContent = dbInfo.database_path || 'Unknown';
        
        showToast('Database info loaded successfully', 'success');
        
    } catch (error) {
        console.error('❌ Failed to load database info:', error);
        
        const elements = ['dbJobCount', 'dbLogCount', 'dbSize', 'dbEventCount'];
        elements.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '❌';
        });
        
        showToast('Failed to load database information: ' + error.message, 'error');
    }
}

async function cleanupDatabase() {
    const cleanupDaysSelect = document.getElementById('cleanupDays');
    const days = cleanupDaysSelect ? cleanupDaysSelect.value : 90;
    
    if (!confirm(`Are you sure you want to delete all data older than ${days} days? This action cannot be undone.`)) {
        return;
    }
    
    try {
        const cleanupBtn = document.getElementById('cleanupBtn');
        cleanupBtn.disabled = true;
        cleanupBtn.innerHTML = '<div class="loading-spinner" style="margin-right: 8px;"></div>Cleaning...';
        
        const apiManager = window.apiManager || window.api;
        const result = await apiManager.post(`/api/admin/maintenance/cleanup?days=${days}`);
        
        console.log('✅ Cleanup result:', result);
        showToast(`Database cleanup completed for data older than ${days} days`, 'success');
        
        setTimeout(() => {
            loadDatabaseInfo();
        }, 1000);
        
    } catch (error) {
        console.error('❌ Failed to cleanup database:', error);
        showToast('Failed to cleanup database: ' + error.message, 'error');
    } finally {
        const cleanupBtn = document.getElementById('cleanupBtn');
        cleanupBtn.disabled = false;
        cleanupBtn.innerHTML = `
            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
            </svg>
            <span data-translate="cleanup_now">Cleanup Now</span>
        `;
    }
}

async function updateStatistics() {
    console.log('🔄 Updating statistics...');
    
    try {
        const apiManager = window.apiManager || window.api;
        const result = await apiManager.post('/api/admin/maintenance/update-statistics');
        
        console.log('✅ Statistics update result:', result);
        showToast('Statistics updated successfully', 'success');
        
        setTimeout(() => {
            loadStatistics();
        }, 1000);
        
    } catch (error) {
        console.error('❌ Failed to update statistics:', error);
        showToast('Failed to update statistics: ' + error.message, 'error');
    }
}

async function downloadDatabaseBackup() {
    console.log('📥 Getting database backup info...');
    
    try {
        const apiManager = window.apiManager || window.api;
        const dbInfo = await apiManager.get('/api/admin/database/info');
        
        const message = `Database backup location:\n${dbInfo.database_path}\n\nSize: ${formatBytes(dbInfo.database_size_bytes)}\n\nTo create a backup, copy this file to a safe location.\n\nNote: Stop the application before copying the database file to ensure consistency.`;
        
        alert(message);
        showToast('Backup information displayed', 'info');
        
    } catch (error) {
        console.error('❌ Failed to get database backup info:', error);
        showToast('Failed to get backup information: ' + error.message, 'error');
    }
}

async function loadStatistics() {
    console.log('📊 Loading statistics...');
    
    const statsDaysSelect = document.getElementById('statsDays');
    const days = statsDaysSelect ? statsDaysSelect.value : 30;
    
    try {
        const chartEl = document.getElementById('statisticsChart');
        if (chartEl) {
            chartEl.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 200px;"><div class="loading-spinner" style="margin-right: 10px;"></div>Loading statistics...</div>';
        }
        
        const apiManager = window.apiManager || window.api;
        const stats = await apiManager.get(`/api/admin/statistics?days=${days}`);
        
        console.log('✅ Statistics loaded:', stats);
        displayStatistics(stats);
        
    } catch (error) {
        console.error('❌ Failed to load statistics:', error);
        
        const chartEl = document.getElementById('statisticsChart');
        if (chartEl) {
            chartEl.innerHTML = '<div style="text-align: center; color: #dc3545; padding: 40px;">Failed to load statistics: ' + error.message + '</div>';
        }
        
        showToast('Failed to load statistics: ' + error.message, 'error');
    }
}

function displayStatistics(stats) {
    const chartEl = document.getElementById('statisticsChart');
    const tableEl = document.getElementById('statisticsTable');
    
    if (!chartEl || !tableEl) {
        console.error('❌ Statistics elements not found');
        return;
    }
    
    if (!stats || stats.length === 0) {
        chartEl.innerHTML = '<p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">No statistics data available for the selected period</p>';
        tableEl.innerHTML = '';
        return;
    }
    
    // Simple chart visualization
    let chartHtml = '<div style="display: flex; align-items: end; gap: 4px; height: 200px; padding: 20px; background: #f8f9fa; border-radius: 8px; overflow-x: auto;">';
    
    const maxJobs = Math.max(...stats.map(s => s.total_jobs || 0), 1);
    const reversedStats = [...stats].reverse().slice(-14);
    
    reversedStats.forEach((stat, index) => {
        const totalJobs = stat.total_jobs || 0;
        const completedJobs = stat.completed_jobs || 0;
        const height = maxJobs > 0 ? Math.max((totalJobs / maxJobs) * 150, 4) : 4;
        const completedRatio = totalJobs > 0 ? (completedJobs / totalJobs) * 100 : 0;
        
        let color = '#dc3545';
        if (totalJobs === 0) color = '#6c757d';
        else if (completedRatio >= 80) color = '#28a745';
        else if (completedRatio >= 50) color = '#ffc107';
        
        const dateStr = stat.date || 'Unknown';
        const dateParts = dateStr.split('-');
        const displayDate = dateParts.length >= 3 ? `${dateParts[2]}/${dateParts[1]}` : dateStr.slice(-5);
        
        chartHtml += `
            <div style="display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 30px;">
                <div style="display: flex; flex-direction: column; align-items: center; margin-bottom: 8px;">
                    <div style="font-size: 12px; font-weight: bold; margin-bottom: 2px;">${totalJobs}</div>
                    <div style="width: 20px; height: ${height}px; background: ${color}; border-radius: 2px; min-height: 4px;" title="${totalJobs} jobs on ${dateStr}"></div>
                </div>
                <div style="font-size: 10px; transform: rotate(-45deg); margin-top: 8px; white-space: nowrap;">${displayDate}</div>
            </div>
        `;
    });
    
    chartHtml += '</div>';
    chartEl.innerHTML = chartHtml;
    
    // Statistics table
    let tableHtml = `
        <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 20px;">
            <thead>
                <tr style="background: var(--siemens-light-gray);">
                    <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Date</th>
                    <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">Total</th>
                    <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">Completed</th>
                    <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">Failed</th>
                    <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">Success Rate</th>
                    <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">Avg Duration</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    stats.forEach(stat => {
        const totalJobs = stat.total_jobs || 0;
        const completedJobs = stat.completed_jobs || 0;
        const failedJobs = stat.failed_jobs || 0;
        const successRate = totalJobs > 0 ? ((completedJobs / totalJobs) * 100).toFixed(1) : '0.0';
        const avgDuration = stat.avg_duration_seconds ? 
            formatDuration(Math.round(stat.avg_duration_seconds)) : '-';
        
        const successRateNum = parseFloat(successRate);
        let successColor = '#dc3545';
        if (totalJobs === 0) successColor = '#6c757d';
        else if (successRateNum >= 80) successColor = '#28a745';
        else if (successRateNum >= 50) successColor = '#ffc107';
        
        tableHtml += `
            <tr>
                <td style="padding: 12px; border: 1px solid #ddd;">${stat.date || 'Unknown'}</td>
                <td style="padding: 12px; text-align: center; border: 1px solid #ddd; font-weight: bold;">${totalJobs}</td>
                <td style="padding: 12px; text-align: center; border: 1px solid #ddd; color: #28a745; font-weight: bold;">${completedJobs}</td>
                <td style="padding: 12px; text-align: center; border: 1px solid #ddd; color: #dc3545; font-weight: bold;">${failedJobs}</td>
                <td style="padding: 12px; text-align: center; border: 1px solid #ddd; font-weight: bold; color: ${successColor};">${successRate}%</td>
                <td style="padding: 12px; text-align: center; border: 1px solid #ddd;">${avgDuration}</td>
            </tr>
        `;
    });
    
    tableHtml += '</tbody></table>';
    tableEl.innerHTML = tableHtml;
}

// ============= LANGUAGE MANAGEMENT =============
async function switchLanguage(lang) {
    console.log(`🌍 Switching to language: ${lang}`);
    
    try {
        // Update language selector UI
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`.lang-btn[onclick="switchLanguage('${lang}')"]`)?.classList.add('active');
        
        // Load translations if translation system is available
        if (window.translationManager) {
            await window.translationManager.setLanguage(lang);
        } else {
            console.warn('Translation manager not available');
        }
        
        console.log(`✅ Language switched to: ${lang}`);
        
    } catch (error) {
        console.error('❌ Failed to switch language:', error);
    }
}

// ============= APPLICATION INITIALIZATION =============
async function initializeKassiaApp() {
    console.log('🚀 Initializing Enhanced Kassia WebUI Application...');
    
    try {
        // Check for required managers
        const managers = ['apiManager', 'websocketManager', 'uiManager'];
        const missingManagers = [];
        
        managers.forEach(manager => {
            if (!window[manager] && !window[manager.replace('Manager', '')]) {
                missingManagers.push(manager);
            }
        });
        
        if (missingManagers.length > 0) {
            console.warn('⚠️ Missing managers:', missingManagers);
        }
        
        // Set up WebSocket handlers
        setupWebSocketHandlers();
        
        // Set up global state
        window.kassiaState.isInitialized = true;
        
        // Load initial data
        await loadDevices();
        
        // Initialize dashboard
        await updateDashboardStats();
        
        // Set up event listeners
        setupGlobalEventListeners();
        
        // Start heartbeat monitoring
        startHeartbeatMonitoring();
        
        console.log('✅ Enhanced Kassia WebUI Application initialized successfully');
        showToast('Application initialized successfully', 'success');
        
    } catch (error) {
        console.error('❌ Failed to initialize application:', error);
        showToast('Failed to initialize application: ' + error.message, 'error');
    }
}

function setupGlobalEventListeners() {
    // Handle page refresh confirmation for active builds
    window.addEventListener('beforeunload', function(e) {
        const activeJobId = window.kassiaState.activeJobId;
        if (activeJobId) {
            e.preventDefault();
            e.returnValue = 'You have an active build job running. Are you sure you want to leave?';
            return e.returnValue;
        }
    });
    
    // Handle keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + R to refresh current tab
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            const currentTab = document.querySelector('.tab-content.active')?.id;
            if (currentTab === 'jobs') {
                e.preventDefault();
                refreshJobs();
            } else if (currentTab === 'assets') {
                e.preventDefault();
                refreshAssets();
            } else if (currentTab === 'dashboard') {
                e.preventDefault();
                updateDashboardStats();
                refreshRecentJobs();
            }
        }
    });
    
    console.log('✅ Global event listeners set up');
}

function startHeartbeatMonitoring() {
    // Monitor WebSocket heartbeats
    setInterval(() => {
        const now = new Date();
        const lastHeartbeat = window.kassiaState.lastHeartbeat;
        
        if (lastHeartbeat) {
            const timeSinceHeartbeat = now - lastHeartbeat;
            
            if (timeSinceHeartbeat > 60000) { // 1 minute
                updateConnectionStatus('disconnected');
            } else if (timeSinceHeartbeat > 45000) { // 45 seconds
                updateConnectionStatus('connecting');
            }
        }
    }, 10000); // Check every 10 seconds
}

// ============= Make Functions Available Globally =============
window.switchTab = switchTab;
window.switchLanguage = switchLanguage;
window.refreshAssets = refreshAssets;
window.refreshJobs = refreshJobs;
window.refreshRecentJobs = refreshRecentJobs;
window.loadDatabaseInfo = loadDatabaseInfo;
window.cleanupDatabase = cleanupDatabase;
window.updateStatistics = updateStatistics;
window.downloadDatabaseBackup = downloadDatabaseBackup;
window.loadStatistics = loadStatistics;
window.displayStatistics = displayStatistics;
window.cancelActiveJob = cancelActiveJob;
window.cancelJob = cancelJob;
window.deleteJob = deleteJob;
window.downloadWim = downloadWim;
window.filterJobs = filterJobs;
window.filterRecentJobs = filterRecentJobs;
window.cleanupCompletedJobs = cleanupCompletedJobs;
window.toggleLogLevel = toggleLogLevel;
window.clearLogDisplay = clearLogDisplay;

// ============= Document Ready Handler =============
document.addEventListener('DOMContentLoaded', function() {
    console.log('📄 DOM Content Loaded - Setting up Enhanced Kassia WebUI...');
    
    // Wait for all managers to load
    setTimeout(async () => {
        try {
            await initializeKassiaApp();
            
        } catch (error) {
            console.error('❌ Failed to initialize Enhanced Kassia App:', error);
        }
    }, 200);
});

console.log('✅ Enhanced Kassia WebUI JavaScript loaded and ready');