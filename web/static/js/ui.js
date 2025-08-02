// web/static/js/ui.js - UI Manager for Interface Components

class UiManager {
    constructor() {
        this.currentTab = 'dashboard';
        this.toastCounter = 0;
        this.modalStack = [];
        
        console.log('🎨 UI Manager initialized');
    }
    
    // ============= TOAST NOTIFICATIONS =============
    showToast(message, type = 'info', duration = 5000) {
        const toastContainer = document.getElementById('toastContainer') || this.createToastContainer();
        
        const toastId = `toast-${++this.toastCounter}`;
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast toast-${type}`;
        
        const icon = this.getToastIcon(type);
        
        toast.innerHTML = `
            <div class="toast-content">
                <span class="toast-icon">${icon}</span>
                <span class="toast-message">${message}</span>
                <button class="toast-close" onclick="window.uiManager.closeToast('${toastId}')">&times;</button>
            </div>
            <div class="toast-progress"></div>
        `;
        
        // Add styles if not present
        this.ensureToastStyles();
        
        toastContainer.appendChild(toast);
        
        // Animate in
        setTimeout(() => {
            toast.classList.add('toast-show');
        }, 100);
        
        // Auto close
        if (duration > 0) {
            setTimeout(() => {
                this.closeToast(toastId);
            }, duration);
        }
        
        console.log(`🍞 Toast shown: ${type} - ${message}`);
        return toastId;
    }
    
    closeToast(toastId) {
        const toast = document.getElementById(toastId);
        if (toast) {
            toast.classList.add('toast-hide');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }
    }
    
    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
        return container;
    }
    
    getToastIcon(type) {
        switch (type) {
            case 'success': return '✅';
            case 'error': return '❌';
            case 'warning': return '⚠️';
            case 'info': return 'ℹ️';
            default: return 'ℹ️';
        }
    }
    
    ensureToastStyles() {
        if (document.getElementById('toast-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.textContent = `
            .toast-container {
                position: fixed;
                top: 80px;
                right: 20px;
                z-index: 1000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                max-width: 400px;
            }
            
            .toast {
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                overflow: hidden;
                transform: translateX(100%);
                transition: transform 0.3s ease;
                position: relative;
                min-width: 300px;
            }
            
            .toast-show {
                transform: translateX(0);
            }
            
            .toast-hide {
                transform: translateX(100%);
            }
            
            .toast-content {
                display: flex;
                align-items: center;
                padding: 16px;
                gap: 12px;
            }
            
            .toast-icon {
                font-size: 18px;
                flex-shrink: 0;
            }
            
            .toast-message {
                flex: 1;
                font-size: 14px;
                line-height: 1.4;
            }
            
            .toast-close {
                background: none;
                border: none;
                font-size: 20px;
                cursor: pointer;
                color: #6c757d;
                padding: 0;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .toast-close:hover {
                color: #495057;
            }
            
            .toast-progress {
                height: 3px;
                background: linear-gradient(90deg, var(--siemens-bright-petrol), #0099cc);
                animation: toast-progress 5s linear forwards;
            }
            
            .toast-success {
                border-left: 4px solid #28a745;
            }
            
            .toast-error {
                border-left: 4px solid #dc3545;
            }
            
            .toast-warning {
                border-left: 4px solid #ffc107;
            }
            
            .toast-info {
                border-left: 4px solid var(--siemens-bright-petrol);
            }
            
            @keyframes toast-progress {
                from { width: 100%; }
                to { width: 0%; }
            }
            
            @media (max-width: 480px) {
                .toast-container {
                    right: 10px;
                    left: 10px;
                    max-width: none;
                }
                
                .toast {
                    min-width: 0;
                }
            }
        `;
        
        document.head.appendChild(style);
    }
    
    // ============= MODAL MANAGEMENT =============
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error(`❌ Modal not found: ${modalId}`);
            return;
        }
        
        modal.style.display = 'flex';
        this.modalStack.push(modalId);
        
        // Add event listener for escape key
        document.addEventListener('keydown', this.handleModalEscape);
        
        // Add backdrop click to close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal(modalId);
            }
        });
        
        console.log(`📱 Modal opened: ${modalId}`);
    }
    
    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        modal.style.display = 'none';
        
        // Remove from stack
        const index = this.modalStack.indexOf(modalId);
        if (index > -1) {
            this.modalStack.splice(index, 1);
        }
        
        // Remove escape listener if no modals open
        if (this.modalStack.length === 0) {
            document.removeEventListener('keydown', this.handleModalEscape);
        }
        
        console.log(`📱 Modal closed: ${modalId}`);
    }
    
    handleModalEscape = (e) => {
        if (e.key === 'Escape' && this.modalStack.length > 0) {
            const topModal = this.modalStack[this.modalStack.length - 1];
            this.closeModal(topModal);
        }
    }
    
    // ============= JOB DETAIL MODAL =============
    async openJobDetailModal(jobId) {
        try {
            // Create modal if it doesn't exist
            this.ensureJobDetailModal();
            
            // Load job data
            const job = await window.apiManager.getJob(jobId);
            const logs = await window.apiManager.getJobLogs(jobId, { limit: 100 });
            
            // Populate modal
            this.populateJobDetailModal(job, logs);
            
            // Open modal
            this.openModal('jobDetailModal');
            
        } catch (error) {
            console.error('❌ Failed to open job detail modal:', error);
            this.showToast('Failed to load job details: ' + error.message, 'error');
        }
    }
    
    ensureJobDetailModal() {
        if (document.getElementById('jobDetailModal')) return;
        
        const modal = document.createElement('div');
        modal.id = 'jobDetailModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 900px;">
                <div class="modal-header">
                    <h3 id="jobDetailTitle">Job Details</h3>
                    <button class="modal-close" onclick="window.uiManager.closeModal('jobDetailModal')">&times;</button>
                </div>
                <div class="modal-body">
                    <div id="jobDetailContent">
                        <!-- Job details will be loaded here -->
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
    }
    
    populateJobDetailModal(job, logs) {
        const title = document.getElementById('jobDetailTitle');
        const content = document.getElementById('jobDetailContent');
        
        if (title) {
            title.textContent = `Job: ${job.device} - OS ${job.os_id}`;
        }
        
        if (content) {
            const statusClass = this.getStatusClass(job.status);
            const createdAt = new Date(job.created_at).toLocaleString();
            const completedAt = job.completed_at ? new Date(job.completed_at).toLocaleString() : '-';
            const duration = this.calculateDuration(job);
            
            content.innerHTML = `
                <div class="job-detail-grid">
                    <div class="job-detail-section">
                        <h4>Job Information</h4>
                        <div class="job-detail-item">
                            <label>Job ID:</label>
                            <span class="job-id-text">${job.id}</span>
                        </div>
                        <div class="job-detail-item">
                            <label>Device:</label>
                            <span>${job.device}</span>
                        </div>
                        <div class="job-detail-item">
                            <label>OS ID:</label>
                            <span>${job.os_id}</span>
                        </div>
                        <div class="job-detail-item">
                            <label>Status:</label>
                            <span class="status-badge ${statusClass}">${job.status}</span>
                        </div>
                        <div class="job-detail-item">
                            <label>Progress:</label>
                            <span>${job.progress || 0}%</span>
                        </div>
                        <div class="job-detail-item">
                            <label>Current Step:</label>
                            <span>${job.current_step || 'N/A'}</span>
                        </div>
                    </div>
                    
                    <div class="job-detail-section">
                        <h4>Timing</h4>
                        <div class="job-detail-item">
                            <label>Created:</label>
                            <span>${createdAt}</span>
                        </div>
                        <div class="job-detail-item">
                            <label>Completed:</label>
                            <span>${completedAt}</span>
                        </div>
                        <div class="job-detail-item">
                            <label>Duration:</label>
                            <span>${duration}</span>
                        </div>
                    </div>
                </div>
                
                ${job.error ? `
                    <div class="job-detail-section">
                        <h4>Error Details</h4>
                        <div class="error-box">
                            ${job.error}
                        </div>
                    </div>
                ` : ''}
                
                ${job.results && Object.keys(job.results).length > 0 ? `
                    <div class="job-detail-section">
                        <h4>Results</h4>
                        <div class="results-box">
                            <pre>${JSON.stringify(job.results, null, 2)}</pre>
                        </div>
                    </div>
                ` : ''}
                
                <div class="job-detail-section">
                    <h4>Logs (${logs.length} entries)</h4>
                    <div class="logs-container">
                        ${logs.map(log => `
                            <div class="log-entry log-${log.level.toLowerCase()}">
                                <span class="log-timestamp">${new Date(log.timestamp).toLocaleTimeString()}</span>
                                <span class="log-level">${log.level}</span>
                                <span class="log-message">${log.message}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                <div class="job-detail-actions">
                    ${job.status === 'running' ? `
                        <button class="btn btn-warning" onclick="window.uiManager.cancelJobFromModal('${job.id}')">
                            Cancel Job
                        </button>
                    ` : ''}
                    ${job.status === 'completed' || job.status === 'failed' ? `
                        <button class="btn btn-outline-danger" onclick="window.uiManager.deleteJobFromModal('${job.id}')">
                            Delete Job
                        </button>
                    ` : ''}
                    <button class="btn btn-secondary" onclick="window.uiManager.closeModal('jobDetailModal')">
                        Close
                    </button>
                </div>
            `;
            
            this.ensureJobDetailStyles();
        }
    }
    
    async cancelJobFromModal(jobId) {
        if (!confirm('Are you sure you want to cancel this job?')) return;
        
        try {
            await window.apiManager.cancelJob(jobId);
            this.showToast('Job cancelled successfully', 'success');
            this.closeModal('jobDetailModal');
            
            // Refresh displays
            if (typeof refreshJobs === 'function') refreshJobs();
            if (typeof refreshRecentJobs === 'function') refreshRecentJobs();
            
        } catch (error) {
            this.showToast('Failed to cancel job: ' + error.message, 'error');
        }
    }
    
    async deleteJobFromModal(jobId) {
        if (!confirm('Are you sure you want to permanently delete this job?')) return;
        
        try {
            await window.apiManager.deleteJob(jobId);
            this.showToast('Job deleted successfully', 'success');
            this.closeModal('jobDetailModal');
            
            // Refresh displays
            if (typeof refreshJobs === 'function') refreshJobs();
            if (typeof refreshRecentJobs === 'function') refreshRecentJobs();
            
        } catch (error) {
            this.showToast('Failed to delete job: ' + error.message, 'error');
        }
    }
    
    ensureJobDetailStyles() {
        if (document.getElementById('job-detail-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'job-detail-styles';
        style.textContent = `
            .job-detail-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
                margin-bottom: 24px;
            }
            
            .job-detail-section {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
            }
            
            .job-detail-section h4 {
                margin: 0 0 16px 0;
                color: var(--siemens-text-primary);
            }
            
            .job-detail-item {
                display: flex;
                justify-content: space-between;
                margin-bottom: 12px;
                padding-bottom: 8px;
                border-bottom: 1px solid #dee2e6;
            }
            
            .job-detail-item:last-child {
                margin-bottom: 0;
                border-bottom: none;
            }
            
            .job-detail-item label {
                font-weight: 600;
                color: #495057;
            }
            
            .job-id-text {
                font-family: monospace;
                background: #e9ecef;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 12px;
            }
            
            .error-box {
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 4px;
                padding: 12px;
                color: #721c24;
                font-family: monospace;
                font-size: 12px;
                white-space: pre-wrap;
            }
            
            .results-box {
                background: #d4edda;
                border: 1px solid #c3e6cb;
                border-radius: 4px;
                padding: 12px;
                color: #155724;
            }
            
            .results-box pre {
                margin: 0;
                font-size: 12px;
                white-space: pre-wrap;
            }
            
            .logs-container {
                max-height: 300px;
                overflow-y: auto;
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
            }
            
            .job-detail-actions {
                display: flex;
                gap: 12px;
                justify-content: flex-end;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
                margin-top: 20px;
            }
            
            @media (max-width: 768px) {
                .job-detail-grid {
                    grid-template-columns: 1fr;
                }
            }
        `;
        
        document.head.appendChild(style);
    }
    
    // ============= UTILITY FUNCTIONS =============
    getStatusClass(status) {
        switch (status) {
            case 'completed': return 'status-success';
            case 'running': return 'status-running';
            case 'failed': 
            case 'cancelled': return 'status-error';
            default: return 'status-pending';
        }
    }
    
    calculateDuration(job) {
        if (!job.started_at) return '-';
        
        const start = new Date(job.started_at);
        const end = job.completed_at ? new Date(job.completed_at) : new Date();
        const durationMs = end - start;
        
        const seconds = Math.floor(durationMs / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    }
    
    // ============= TAB MANAGEMENT =============
    onTabSwitch(tabName) {
        this.currentTab = tabName;
        console.log(`🎨 Tab switched to: ${tabName}`);
    }
    
    // ============= LOADING STATES =============
    showLoading(elementId, message = 'Loading...') {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; padding: 40px; color: #6c757d;">
                    <div class="loading-spinner" style="margin-bottom: 16px;"></div>
                    <span>${message}</span>
                </div>
            `;
        }
    }
    
    hideLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = '';
        }
    }
}

// Create global UI manager
window.uiManager = new UiManager();

// Make viewJobDetails globally available
window.viewJobDetails = function(jobId) {
    console.log('🔍 Opening job details for:', jobId);
    window.uiManager.openJobDetailModal(jobId);
};

// Make closeJobDetailModal globally available
window.closeJobDetailModal = function() {
    window.uiManager.closeModal('jobDetailModal');
};

console.log('✅ UI Manager loaded');