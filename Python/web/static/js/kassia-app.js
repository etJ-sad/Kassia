document.getElementById('jobLogCount').textContent = `${totalCount} entries`;
        document.getElementById('jobLogErrors').textContent = `${errorCount} errors`;
        document.getElementById('jobLogLastUpdate').textContent = new Date().toLocaleTimeString();
    }

async downloadJobLogs() {
        if (!this.currentJobViewer) return;
        
        const jobId = this.currentJobViewer.jobId;
        const source = document.getElementById('jobLogSource').value;
        const logType = source === 'errors' ? 'error' : 'main';
        
        try {
            const response = await fetch(`/api/jobs/${jobId}/download-log?log_type=${logType}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Create download link
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `kassia_job_${jobId}_${logType}.log`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showToast('Log file downloaded successfully', 'success');
            
        } catch (error) {
            console.error('❌ Failed to download logs:', error);
            this.showToast(`Failed to download logs: ${error.message}`, 'error');
        }
    }

    startJobLogAutoRefresh() {
        if (this.jobLogRefreshInterval) {
            clearInterval(this.jobLogRefreshInterval);
        }
        
        this.jobLogRefreshInterval = setInterval(() => {
            if (this.currentJobViewer) {
                this.refreshJobLogs();
            }
        }, 5000); // Refresh every 5 seconds
    }

    stopJobLogAutoRefresh() {
        if (this.jobLogRefreshInterval) {
            clearInterval(this.jobLogRefreshInterval);
            this.jobLogRefreshInterval = null;
        }
    }

    closeJobLogModal() {
        const modal = document.getElementById('jobLogModal');
        modal.style.display = 'none';
        this.currentJobViewer = null;
        this.stopJobLogAutoRefresh();
    }

    handleDeviceChange(deviceId) {
        const osSelect = document.getElementById('osSelect');
        if (!osSelect) return;

        // Clear OS options
        osSelect.innerHTML = '<option value="">Select OS...</option>';
        osSelect.disabled = !deviceId;

        if (!deviceId) return;

        // Find selected device
        const device = this.devices.find(d => d.device_id === deviceId);
        if (!device) return;

        // Populate OS options
        device.supported_os.forEach(osId => {
            const option = document.createElement('option');
            option.value = osId;
            option.textContent = `OS ${osId}`;
            osSelect.appendChild(option);
        });

        osSelect.disabled = false;
    }

    async handleOSChange(osId) {
        const deviceSelect = document.getElementById('deviceSelect');
        if (!deviceSelect || !deviceSelect.value || !osId) return;

        // Load assets for preview
        await this.loadAssets(deviceSelect.value, parseInt(osId));
        this.updateBuildPreview(deviceSelect.value, osId);
    }

    async loadAssets(deviceId, osId) {
        try {
            console.log(`📂 Loading assets for ${deviceId} OS ${osId}...`);
            const response = await fetch(`/api/assets/${deviceId}/${osId}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const assets = await response.json();
            this.assets[`${deviceId}_${osId}`] = assets;

            console.log(`✅ Loaded assets:`, {
                sbi: assets.sbi ? '✅' : '❌',
                drivers: assets.drivers.length,
                updates: assets.updates.length,
                yunona: assets.yunona_scripts.length
            });

            return assets;

        } catch (error) {
            console.error('❌ Failed to load assets:', error);
            this.showToast('Failed to load assets', 'error');
            return null;
        }
    }

    updateBuildPreview(deviceId, osId) {
        const assets = this.assets[`${deviceId}_${osId}`];
        if (!assets) return;

        // Update preview elements
        const previewDevice = document.getElementById('previewDevice');
        const previewOS = document.getElementById('previewOS');
        const previewWimPath = document.getElementById('previewWimPath');
        const previewSBI = document.getElementById('previewSBI');
        const previewDrivers = document.getElementById('previewDrivers');
        const previewUpdates = document.getElementById('previewUpdates');
        const buildPreview = document.getElementById('buildPreview');

        if (previewDevice) previewDevice.textContent = deviceId;
        if (previewOS) previewOS.textContent = `OS ${osId}`;
        if (previewWimPath) previewWimPath.textContent = assets.wim_path || 'Not configured';
        if (previewSBI) previewSBI.textContent = assets.sbi ? '✅ Found' : '❌ Missing';
        if (previewDrivers) previewDrivers.textContent = `${assets.drivers.length} packages`;
        if (previewUpdates) previewUpdates.textContent = `${assets.updates.length} packages`;

        if (buildPreview) {
            buildPreview.style.display = 'block';
        }
    }

    async handleBuildSubmit(event) {
        event.preventDefault();

        const deviceSelect = document.getElementById('deviceSelect');
        const osSelect = document.getElementById('osSelect');
        const skipDrivers = document.getElementById('skipDrivers');
        const skipUpdates = document.getElementById('skipUpdates');
        const startBuildBtn = document.getElementById('startBuildBtn');

        if (!deviceSelect?.value || !osSelect?.value) {
            this.showToast('Please select device and OS', 'error');
            return;
        }

        // Disable form
        if (startBuildBtn) {
            startBuildBtn.disabled = true;
            startBuildBtn.innerHTML = `
                <div class="loading-spinner" style="margin-right: 8px;"></div>
                Starting Build...
            `;
        }

        try {
            const buildRequest = {
                device: deviceSelect.value,
                os_id: parseInt(osSelect.value),
                skip_drivers: skipDrivers?.checked || false,
                skip_updates: skipUpdates?.checked || false
            };

            console.log('🚀 Starting build:', buildRequest);

            const response = await fetch('/api/build', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(buildRequest)
            });

            if (!response.ok) {
                const error = await response.text();
                throw new Error(`HTTP ${response.status}: ${error}`);
            }

            const result = await response.json();
            console.log('✅ Build started:', result.job_id);

            this.showToast('Build started successfully!', 'success');

            // Switch to dashboard to show progress
            this.switchTab('dashboard');

            // Refresh jobs to show new job
            await this.loadJobs();

        } catch (error) {
            console.error('❌ Failed to start build:', error);
            this.showToast(`Failed to start build: ${error.message}`, 'error');
        } finally {
            // Re-enable form
            if (startBuildBtn) {
                startBuildBtn.disabled = false;
                startBuildBtn.innerHTML = `
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="m11.596 8.697-6.363 3.692c-.54.313-1.233-.066-1.233-.697V4.308c0-.63.692-1.01 1.233-.696l6.363 3.692a.802.802 0 0 1 0 1.393z"/>
                    </svg>
                    Start Build
                `;
            }
        }
    }

    async handleAssetFilterChange() {
        const deviceFilter = document.getElementById('assetDeviceFilter');
        const osFilter = document.getElementById('assetOSFilter');

        if (!deviceFilter?.value || !osFilter?.value) {
            this.displayAssetsMessage('Select device and OS to view available assets');
            return;
        }

        const assets = await this.loadAssets(deviceFilter.value, parseInt(osFilter.value));
        if (assets) {
            this.displayAssets(assets);
        }
    }

    displayAssets(assets) {
        const assetsContent = document.getElementById('assetsContent');
        if (!assetsContent) return;

        let html = '';

        // SBI Section
        html += this.createAssetSection('System Base Image (SBI)', assets.sbi ? [assets.sbi] : [], 'sbi');

        // Drivers Section
        html += this.createAssetSection('Drivers', assets.drivers, 'drivers');

        // Updates Section
        html += this.createAssetSection('Updates', assets.updates, 'updates');

        // Yunona Scripts Section
        html += this.createAssetSection('Yunona Scripts', assets.yunona_scripts, 'scripts');

        assetsContent.innerHTML = html;
    }

    createAssetSection(title, items, type) {
        const count = items.length;
        const iconMap = {
            'sbi': 'wim',
            'drivers': 'inf',
            'updates': 'msu',
            'scripts': 'ps1'
        };

        let html = `
            <div class="asset-section">
                <div class="asset-section-title">
                    <div class="file-icon ${iconMap[type]}">${iconMap[type].toUpperCase()}</div>
                    ${title}
                    <span class="asset-section-count">${count}</span>
                </div>
        `;

        if (count === 0) {
            html += `<div class="asset-section-empty">No ${title.toLowerCase()} found</div>`;
        } else {
            html += '<div class="asset-grid">';
            items.forEach(item => {
                html += this.createAssetItem(item);
            });
            html += '</div>';
        }

        html += '</div>';
        return html;
    }

    createAssetItem(asset) {
        const validClass = asset.valid ? 'valid' : 'invalid';
        const statusClass = asset.valid ? 'status-success' : 'status-error';
        const statusText = asset.valid ? 'Valid' : 'Invalid';
        const sizeText = asset.size ? this.formatBytes(asset.size) : 'Unknown size';

        return `
            <div class="asset-item ${validClass}">
                <div class="asset-title">${asset.name}</div>
                <div class="asset-type">${asset.type}</div>
                <div class="asset-path">${asset.path}</div>
                <div class="asset-status">
                    <span style="font-size: 14px; color: var(--siemens-text-secondary);">${sizeText}</span>
                    <span class="status-badge ${statusClass}">${statusText}</span>
                </div>
            </div>
        `;
    }

    displayAssetsMessage(message) {
        const assetsContent = document.getElementById('assetsContent');
        if (!assetsContent) return;

        assetsContent.innerHTML = `
            <p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">
                ${message}
            </p>
        `;
    }

    updateActiveJobDisplay(jobData) {
        const activeJobCard = document.getElementById('activeJobCard');
        const activeJobTitle = document.getElementById('activeJobTitle');
        const activeJobStatus = document.getElementById('activeJobStatus');
        const activeJobStep = document.getElementById('activeJobStep');
        const activeJobProgress = document.getElementById('activeJobProgress');
        const activeJobProgressBar = document.getElementById('activeJobProgressBar');
        const activeJobLogs = document.getElementById('activeJobLogs');

        if (!activeJobCard) return;

        // Show card
        activeJobCard.style.display = 'block';

        // Update content
        if (activeJobTitle) {
            activeJobTitle.textContent = `${jobData.device} - OS ${jobData.os_id}`;
        }

        if (activeJobStatus) {
            activeJobStatus.textContent = jobData.status.charAt(0).toUpperCase() + jobData.status.slice(1);
            activeJobStatus.className = `status-badge ${this.getStatusClass(jobData.status)}`;
        }

        if (activeJobStep) {
            activeJobStep.textContent = `Step ${jobData.step_number}/${jobData.total_steps}: ${jobData.current_step}`;
        }

        if (activeJobProgress) {
            activeJobProgress.textContent = `${jobData.progress}%`;
        }

        if (activeJobProgressBar) {
            activeJobProgressBar.style.width = `${jobData.progress}%`;
        }

        // Update logs (show last few entries)
        if (activeJobLogs && jobData.logs) {
            const recentLogs = jobData.logs.slice(-5); // Show last 5 logs
            const logsHtml = recentLogs.map(log => `<div>${log.message || log}</div>`).join('');
            activeJobLogs.innerHTML = logsHtml || '<div>Waiting for job updates...</div>';
            activeJobLogs.scrollTop = activeJobLogs.scrollHeight;
        }
    }

    hideActiveJobDisplay() {
        const activeJobCard = document.getElementById('activeJobCard');
        if (activeJobCard) {
            activeJobCard.style.display = 'none';
        }
    }

    updateDashboardStats() {
        const totalJobs = document.getElementById('totalJobs');
        const runningJobs = document.getElementById('runningJobs');
        const completedJobs = document.getElementById('completedJobs');
        const failedJobs = document.getElementById('failedJobs');

        const stats = {
            total: this.jobs.length,
            running: this.jobs.filter(job => job.status === 'running').length,
            completed: this.jobs.filter(job => job.status === 'completed').length,
            failed: this.jobs.filter(job => job.status === 'failed').length
        };

        if (totalJobs) totalJobs.textContent = stats.total;
        if (runningJobs) runningJobs.textContent = stats.running;
        if (completedJobs) completedJobs.textContent = stats.completed;
        if (failedJobs) failedJobs.textContent = stats.failed;

        // Update recent jobs list
        this.updateRecentJobsList();
    }

    updateRecentJobsList() {
        const recentJobsList = document.getElementById('recentJobsList');
        if (!recentJobsList) return;

        if (this.jobs.length === 0) {
            recentJobsList.innerHTML = `
                <p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">
                    No jobs yet. Start a new build to see activity here.
                </p>
            `;
            return;
        }

        // Show last 5 jobs
        const recentJobs = this.jobs
            .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
            .slice(0, 5);

        const html = recentJobs.map(job => this.createJobItem(job, true)).join('');
        recentJobsList.innerHTML = html;
    }

    updateJobsList() {
        const jobsList = document.getElementById('jobsList');
        if (!jobsList) return;

        if (this.jobs.length === 0) {
            jobsList.innerHTML = `
                <p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">
                    No build jobs found. Start your first build to see it here.
                </p>
            `;
            return;
        }

        // Sort jobs by creation date (newest first)
        const sortedJobs = this.jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        const html = sortedJobs.map(job => this.createJobItem(job, false)).join('');
        jobsList.innerHTML = html;
    }

    createJobItem(job, isCompact = false) {
        const statusClass = this.getStatusClass(job.status);
        const duration = this.calculateDuration(job);
        const createdAt = new Date(job.created_at).toLocaleString();

        let progressHtml = '';
        if (job.status === 'running') {
            progressHtml = `
                <div class="job-progress">
                    <div class="job-progress-text">
                        <span>Step ${job.step_number}/${job.total_steps}: ${job.current_step}</span>
                        <span>${job.progress}%</span>
                    </div>
                    <div class="progress-container">
                        <div class="progress-bar" style="width: ${job.progress}%"></div>
                    </div>
                </div>
            `;
        }

        let actionsHtml = '';
        if (!isCompact) {
            if (job.status === 'running') {
                actionsHtml = `
                    <div class="job-actions">
                        <button class="btn btn-secondary" onclick="kassiaApp.showJobLogs('${job.id}')">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M3 14s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1H3zm5-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/>
                            </svg>
                            View Logs
                        </button>
                        <button class="btn btn-warning" onclick="kassiaApp.cancelJob('${job.id}')">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                                <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
                            </svg>
                            Cancel
                        </button>
                    </div>
                `;
            } else {
                actionsHtml = `
                    <div class="job-actions">
                        <button class="btn btn-secondary" onclick="kassiaApp.showJobLogs('${job.id}')">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M3 14s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1H3zm5-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/>
                            </svg>
                            View Logs
                        </button>
                        ${job.status === 'completed' ? `
                        <button class="btn btn-primary" onclick="kassiaApp.showJobDetails('${job.id}')">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                <path d="m8.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533L8.93 6.588zM9 4.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"/>
                            </svg>
                            Details
                        </button>
                        ` : ''}
                    </div>
                `;
            }
        }

        return `
            <div class="job-item">
                <div class="job-header">
                    <div>
                        <h3 class="job-title">${job.device} - OS ${job.os_id}</h3>
                        <div class="job-id">Job ID: ${job.id}</div>
                    </div>
                    <span class="status-badge ${statusClass}">${job.status.charAt(0).toUpperCase() + job.status.slice(1)}</span>
                </div>
                
                <div class="job-meta">
                    <div class="job-meta-item">
                        <span class="job-meta-label">Created</span>
                        <span class="job-meta-value">${createdAt}</span>
                    </div>
                    <div class="job-meta-item">
                        <span class="job-meta-label">Duration</span>
                        <span class="job-meta-value">${duration}</span>
                    </div>
                    ${job.results?.final_wim_size_mb ? `
                    <div class="job-meta-item">
                        <span class="job-meta-label">Final Size</span>
                        <span class="job-meta-value">${job.results.final_wim_size_mb.toFixed(1)} MB</span>
                    </div>
                    ` : ''}
                    ${job.error ? `
                    <div class="job-meta-item">
                        <span class="job-meta-label">Error</span>
                        <span class="job-meta-value" style="color: #e74c3c;">${job.error}</span>
                    </div>
                    ` : ''}
                </div>
                
                ${progressHtml}
                ${actionsHtml}
            </div>
        `;
    }

    getStatusClass(status) {
        const statusMap = {
            'created': 'status-info',
            'running': 'status-info',
            'completed': 'status-success',
            'failed': 'status-error',
            'cancelled': 'status-warning'
        };
        return statusMap[status] || 'status-info';
    }

    calculateDuration(job) {
        if (!job.started_at) return 'Not started';

        const startTime = new Date(job.started_at);
        const endTime = job.completed_at ? new Date(job.completed_at) : new Date();
        const duration = Math.floor((endTime - startTime) / 1000);

        if (duration < 60) return `${duration}s`;
        if (duration < 3600) return `${Math.floor(duration / 60)}m ${duration % 60}s`;

        const hours = Math.floor(duration / 3600);
        const minutes = Math.floor((duration % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showToast(message, type = 'info', duration = 5000) {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            // Create toast container if it doesn't exist
            const container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                max-width: 300px;
            `;
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.style.cssText = `
            background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#007bff'};
            color: white;
            padding: 12px 16px;
            margin-bottom: 10px;
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            opacity: 0;
            transform: translateX(100%);
            transition: all 0.3s ease;
            font-size: 14px;
            position: relative;
        `;
        
        toast.innerHTML = `
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" style="
                background: none;
                border: none;
                color: white;
                font-size: 18px;
                font-weight: bold;
                position: absolute;
                top: 8px;
                right: 8px;
                cursor: pointer;
                padding: 0;
                width: 20px;
                height: 20px;
                line-height: 1;
            ">×</button>
        `;

        document.getElementById('toastContainer').appendChild(toast);

        // Trigger animation
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        }, 10);

        // Auto remove after duration
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
    }

    async cancelJob(jobId) {
        if (!confirm('Are you sure you want to cancel this build job?')) {
            return;
        }

        try {
            const response = await fetch(`/api/jobs/${jobId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.showToast('Job cancelled successfully', 'success');
            await this.loadJobs();

        } catch (error) {
            console.error('❌ Failed to cancel job:', error);
            this.showToast('Failed to cancel job', 'error');
        }
    }

    showJobDetails(jobId) {
        const job = this.jobs.find(j => j.id === jobId);
        if (!job) return;

        const details = {
            'Job ID': job.id,
            'Device': job.device,
            'OS ID': job.os_id,
            'Status': job.status,
            'Created': new Date(job.created_at).toLocaleString(),
            'Started': job.started_at ? new Date(job.started_at).toLocaleString() : 'Not started',
            'Completed': job.completed_at ? new Date(job.completed_at).toLocaleString() : 'Not completed',
            'Duration': this.calculateDuration(job)
        };

        if (job.results?.final_wim_path) {
            details['Output File'] = job.results.final_wim_path;
            details['File Size'] = `${job.results.final_wim_size_mb.toFixed(1)} MB`;
        }

        if (job.error) {
            details['Error'] = job.error;
        }

        let detailsText = 'Build Job Details:\n\n';
        Object.entries(details).forEach(([key, value]) => {
            detailsText += `${key}: ${value}\n`;
        });

        alert(detailsText);
    }

    setupPeriodicRefresh() {
        // Refresh jobs every 30 seconds if not connected via WebSocket
        setInterval(() => {
            if (!this.isConnected) {
                console.log('🔄 Periodic refresh (WebSocket disconnected)');
                this.loadJobs();
            }
        }, 30000);
    }

    performSearch(query) {
        if (!query) return;

        console.log('🔍 Searching for:', query);
        this.showToast(`Search functionality coming soon: "${query}"`, 'info');
    }

    switchTab(tabName) {
        // Update navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.getAttribute('href') === `#${tabName}`) {
                item.classList.add('active');
            }
        });

        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-tab') === tabName) {
                btn.classList.add('active');
            }
        });

        // Show/hide tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });

        const targetTab = document.getElementById(tabName);
        if (targetTab) {
            targetTab.classList.add('active');
        }
    }

    switchLanguage(langCode) {
        localStorage.setItem('kassiaLanguage', langCode);
        window.location.href = `/index-${langCode}.html`;
    }
}

// Global functions for HTML onclick handlers
function switchTab(tabName) {
    if (window.kassiaApp) {
        window.kassiaApp.switchTab(tabName);
    }
}

function refreshAssets() {
    if (window.kassiaApp) {
        window.kassiaApp.handleAssetFilterChange();
    }
}

function refreshJobs() {
    if (window.kassiaApp) {
        window.kassiaApp.loadJobs();
    }
}

function performSearch() {
    const headerSearch = document.getElementById('headerSearch');
    if (headerSearch && window.kassiaApp) {
        window.kassiaApp.performSearch(headerSearch.value);
    }
}

function switchLanguage(langCode) {
    if (window.kassiaApp) {
        window.kassiaApp.switchLanguage(langCode);
    }
}

// Initialize app when DOM is loaded
window.kassiaApp = new KassiaApp();

console.log('📦 Kassia WebUI JavaScript loaded successfully');

// Add CSS for job log modal
const jobLogModalStyles = `
<style>
.job-log-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 10000;
}

.modal-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
}

.modal-content {
    position: absolute;
    top: 5%;
    left: 5%;
    width: 90%;
    height: 90%;
    background: white;
    border-radius: 8px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    display: flex;
    flex-direction: column;
}

.modal-header {
    padding: 20px;
    border-bottom: 1px solid #dee2e6;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--siemens-deep-blue);
    color: white;
    border-radius: 8px 8px 0 0;
}

.modal-header h3 {
    margin: 0;
    font-size: 1.25rem;
}

.modal-controls {
    display: flex;
    gap: 10px;
    align-items: center;
}

.modal-controls select {
    padding: 5px 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
}

.modal-controls button {
    padding: 5px 12px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    color: white;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 5px;
}

.btn-close {
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    font-size: 18px !important;
    width: 30px;
    height: 30px;
    border-radius: 50% !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center;
    justify-content: center;
}

.btn-close:hover {
    background: rgba(255,255,255,0.2) !important;
}

.modal-body {
    flex: 1;
    padding: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.log-stats {
    background: #f8f9fa;
    padding: 10px 20px;
    border-bottom: 1px solid #dee2e6;
    display: flex;
    gap: 20px;
    font-size: 0.9em;
    color: #6c757d;
}

.job-log-container {
    flex: 1;
    overflow-y: auto;
    padding: 10px 20px;
    background: #1e1e1e;
    color: #f8f8f2;
    font-family: 'Courier New', monospace;
    font-size: 0.85em;
}

.log-entry {
    border-bottom: 1px solid #333;
    padding: 8px 0;
}

.log-entry:last-child {
    border-bottom: none;
}

.log-header {
    display: flex;
    gap: 10px;
    margin-bottom: 4px;
    font-size: 0.9em;
}

.log-timestamp {
    color: #6c757d;
    font-weight: 500;
    min-width: 80px;
}

.log-level {
    font-weight: 600;
    min-width: 60px;
}

.log-category {
    background: #333;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.8em;
    color: #adb5bd;
}

.log-component {
    color: #adb5bd;
    font-style: italic;
    min-width: 120px;
}

.log-message {
    margin-left: 20px;
    color: #f8f8f2;
    line-height: 1.4;
}

.log-details {
    margin-left: 20px;
    color: #6c757d;
    font-size: 0.8em;
    font-style: italic;
    margin-top: 2px;
}

.log-exception {
    margin-left: 20px;
    color: #dc3545;
    font-size: 0.8em;
    font-weight: 500;
    margin-top: 2px;
}

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
    margin: 20px;
}

.no-logs {
    color: #6c757d;
}

/* Job item styling improvements */
.job-item {
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 15px;
    transition: box-shadow 0.2s ease;
}

.job-item:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.job-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 15px;
}

.job-title {
    margin: 0;
    font-size: 1.1rem;
    color: var(--siemens-deep-blue);
}

.job-id {
    font-size: 0.85em;
    color: #6c757d;
    font-family: monospace;
}

.job-meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
    margin-bottom: 15px;
}

.job-meta-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.job-meta-label {
    font-size: 0.85em;
    color: #6c757d;
    font-weight: 500;
}

.job-meta-value {
    font-size: 0.9em;
    color: #212529;
}

.job-progress {
    margin-bottom: 15px;
}

.job-progress-text {
    display: flex;
    justify-content: space-between;
    margin-bottom: 5px;
    font-size: 0.9em;
    color: #6c757d;
}

.job-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.job-actions .btn {
    padding: 6px 12px;
    font-size: 0.9em;
    border-radius: 4px;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 5px;
    text-decoration: none;
}

.btn-secondary {
    background: #6c757d;
    color: white;
}

.btn-secondary:hover {
    background: #5a6268;
}

.btn-primary {
    background: var(--siemens-bright-petrol);
    color: white;
}

.btn-primary:hover {
    background: #0ea5e9;
}

.btn-warning {
    background: #ffc107;
    color: #212529;
}

.btn-warning:hover {
    background: #e0a800;
}

.status-badge {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: 600;
    text-transform: uppercase;
}

.status-success {
    background: #d4edda;
    color: #155724;
}

.status-error {
    background: #f8d7da;
    color: #721c24;
}

.status-info {
    background: #cce7ff;
    color: #004085;
}

.status-warning {
    background: #fff3cd;
    color: #856404;
}

.progress-container {
    width: 100%;
    height: 8px;
    background: #e9ecef;
    border-radius: 4px;
    overflow: hidden;
}

.progress-bar {
    height: 100%;
    background: var(--siemens-bright-petrol);
    transition: width 0.3s ease;
    border-radius: 4px;
}

/* Asset styling improvements */
.asset-section {
    margin-bottom: 30px;
}

.asset-section-title {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 15px;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--siemens-deep-blue);
}

.file-icon {
    background: var(--siemens-bright-petrol);
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.7em;
    font-weight: bold;
}

.asset-section-count {
    background: #e9ecef;
    color: #6c757d;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.8em;
}

.asset-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 15px;
}

.asset-item {
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 15px;
    transition: box-shadow 0.2s ease;
}

.asset-item:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.asset-item.invalid {
    border-color: #dc3545;
    background: #fff5f5;
}

.asset-title {
    font-weight: 600;
    margin-bottom: 5px;
    color: var(--siemens-deep-blue);
}

.asset-type {
    font-size: 0.85em;
    color: #6c757d;
    margin-bottom: 8px;
}

.asset-path {
    font-family: monospace;
    font-size: 0.8em;
    color: #495057;
    margin-bottom: 10px;
    word-break: break-all;
}

.asset-status {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.asset-section-empty {
    text-align: center;
    color: #6c757d;
    font-style: italic;
    padding: 20px;
}

/* Loading spinner */
.loading-spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255,255,255,.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
    .modal-content {
        top: 2%;
        left: 2%;
        width: 96%;
        height: 96%;
    }
    
    .modal-controls {
        flex-wrap: wrap;
        gap: 5px;
    }
    
    .job-meta {
        grid-template-columns: 1fr;
        gap: 10px;
    }
    
    .asset-grid {
        grid-template-columns: 1fr;
    }
}
</style>
`;

// Inject styles into document head
document.head.insertAdjacentHTML('beforeend', jobLogModalStyles);// Kassia WebUI - JavaScript Application with Job-specific Logging
// Enhanced version with job log viewing capabilities

class KassiaApp {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.currentActiveJob = null;
        this.devices = [];
        this.assets = {};
        this.jobs = [];
        this.currentLanguage = document.documentElement.lang || 'en';
        this.currentJobViewer = null; // For job log modal
        
        // Initialize app when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    async init() {
        console.log('🚀 Initializing Kassia WebUI...');

        // Setup WebSocket connection
        this.setupWebSocket();

        // Load initial data
        await this.loadDevices();
        await this.loadJobs();

        // Setup event listeners
        this.setupEventListeners();

        // Setup periodic refresh
        this.setupPeriodicRefresh();

        // Setup job log modal
        this.setupJobLogModal();

        console.log('✅ Kassia WebUI initialized successfully');
    }

    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('🔌 WebSocket connected');
                this.isConnected = true;
                this.updateConnectionStatus(true);
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.error('❌ Failed to parse WebSocket message:', error);
                }
            };

            this.ws.onclose = () => {
                console.log('🔌 WebSocket disconnected');
                this.isConnected = false;
                this.updateConnectionStatus(false);

                // Attempt reconnection after 3 seconds
                setTimeout(() => this.setupWebSocket(), 3000);
            };

            this.ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
                this.isConnected = false;
                this.updateConnectionStatus(false);
            };

        } catch (error) {
            console.error('❌ Failed to setup WebSocket:', error);
            this.updateConnectionStatus(false);
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'job_update':
                this.handleJobUpdate(data.job_id, data.data);
                break;
            case 'heartbeat':
                // Keep-alive heartbeat, no action needed
                break;
            default:
                console.log('📨 Unknown WebSocket message type:', data.type);
        }
    }

    handleJobUpdate(jobId, jobData) {
        console.log(`📊 Job update for ${jobId}:`, jobData.status);

        // Update jobs list
        const jobIndex = this.jobs.findIndex(job => job.id === jobId);
        if (jobIndex >= 0) {
            this.jobs[jobIndex] = jobData;
        } else {
            this.jobs.push(jobData);
        }

        // Update active job display if this is the current active job
        if (jobData.status === 'running') {
            this.currentActiveJob = jobData;
            this.updateActiveJobDisplay(jobData);
        } else if (this.currentActiveJob && this.currentActiveJob.id === jobId) {
            this.currentActiveJob = null;
            this.hideActiveJobDisplay();
        }

        // Refresh displays
        this.updateDashboardStats();
        this.updateJobsList();

        // Update job log viewer if open for this job
        if (this.currentJobViewer && this.currentJobViewer.jobId === jobId) {
            this.currentJobViewer.refreshLogs();
        }

        // Show completion notification
        if (jobData.status === 'completed') {
            this.showToast('Build completed successfully!', 'success');
        } else if (jobData.status === 'failed') {
            this.showToast(`Build failed: ${jobData.error || 'Unknown error'}`, 'error');
        }
    }

    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connectionStatus');
        if (!statusEl) return;

        if (connected) {
            statusEl.className = 'connection-status status-online';
            statusEl.innerHTML = '<span>🟢 Connected</span>';
        } else {
            statusEl.className = 'connection-status status-offline';
            statusEl.innerHTML = '<span>🔴 Disconnected</span>';
        }
    }

    async loadDevices() {
        try {
            console.log('📱 Loading devices...');
            const response = await fetch('/api/devices');

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.devices = await response.json();
            console.log(`✅ Loaded ${this.devices.length} devices`);

            this.populateDeviceSelect();
            this.populateAssetFilters();

        } catch (error) {
            console.error('❌ Failed to load devices:', error);
            this.showToast('Failed to load device configurations', 'error');
        }
    }

    async loadJobs() {
        try {
            console.log('📋 Loading jobs...');
            const response = await fetch('/api/jobs');

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.jobs = await response.json();
            console.log(`✅ Loaded ${this.jobs.length} jobs`);

            this.updateDashboardStats();
            this.updateJobsList();

            // Check for active job
            const activeJob = this.jobs.find(job => job.status === 'running');
            if (activeJob) {
                this.currentActiveJob = activeJob;
                this.updateActiveJobDisplay(activeJob);
            }

        } catch (error) {
            console.error('❌ Failed to load jobs:', error);
            this.showToast('Failed to load build jobs', 'error');
        }
    }

    populateDeviceSelect() {
        const deviceSelect = document.getElementById('deviceSelect');
        const assetDeviceFilter = document.getElementById('assetDeviceFilter');

        if (!deviceSelect) return;

        // Clear existing options
        deviceSelect.innerHTML = '<option value="">Select device...</option>';
        if (assetDeviceFilter) {
            assetDeviceFilter.innerHTML = '<option value="">All Devices</option>';
        }

        // Add device options
        this.devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.device_id;
            option.textContent = `${device.device_id} (OS: ${device.supported_os.join(', ')})`;
            deviceSelect.appendChild(option);

            if (assetDeviceFilter) {
                const filterOption = option.cloneNode(true);
                assetDeviceFilter.appendChild(filterOption);
            }
        });
    }

    populateAssetFilters() {
        const osFilter = document.getElementById('assetOSFilter');
        if (!osFilter) return;

        // Clear existing options
        osFilter.innerHTML = '<option value="">All OS</option>';

        // Get unique OS IDs from all devices
        const osIds = new Set();
        this.devices.forEach(device => {
            device.supported_os.forEach(osId => osIds.add(osId));
        });

        // Add OS options
        Array.from(osIds).sort((a, b) => a - b).forEach(osId => {
            const option = document.createElement('option');
            option.value = osId;
            option.textContent = `OS ${osId}`;
            osFilter.appendChild(option);
        });
    }

    setupEventListeners() {
        // Device selection change
        const deviceSelect = document.getElementById('deviceSelect');
        if (deviceSelect) {
            deviceSelect.addEventListener('change', (e) => this.handleDeviceChange(e.target.value));
        }

        // OS selection change
        const osSelect = document.getElementById('osSelect');
        if (osSelect) {
            osSelect.addEventListener('change', (e) => this.handleOSChange(e.target.value));
        }

        // Build form submission
        const buildForm = document.getElementById('buildForm');
        if (buildForm) {
            buildForm.addEventListener('submit', (e) => this.handleBuildSubmit(e));
        }

        // Asset filters
        const assetDeviceFilter = document.getElementById('assetDeviceFilter');
        const assetOSFilter = document.getElementById('assetOSFilter');

        if (assetDeviceFilter) {
            assetDeviceFilter.addEventListener('change', () => this.handleAssetFilterChange());
        }

        if (assetOSFilter) {
            assetOSFilter.addEventListener('change', () => this.handleAssetFilterChange());
        }

        // Search functionality
        const headerSearch = document.getElementById('headerSearch');
        if (headerSearch) {
            headerSearch.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.performSearch(e.target.value);
                }
            });
        }
    }

    setupJobLogModal() {
        // Create job log modal if it doesn't exist
        if (!document.getElementById('jobLogModal')) {
            const modal = document.createElement('div');
            modal.id = 'jobLogModal';
            modal.className = 'job-log-modal';
            modal.style.display = 'none';
            modal.innerHTML = `
                <div class="modal-overlay" onclick="kassiaApp.closeJobLogModal()"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h3 id="jobLogModalTitle">Job Logs</h3>
                        <div class="modal-controls">
                            <select id="jobLogSource">
                                <option value="buffer">Live Buffer</option>
                                <option value="file">Job File</option>
                                <option value="errors">Errors Only</option>
                            </select>
                            <button onclick="kassiaApp.refreshJobLogs()" class="btn btn-secondary">
                                <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                    <path fill-rule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z"/>
                                    <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466z"/>
                                </svg>
                                Refresh
                            </button>
                            <button onclick="kassiaApp.downloadJobLogs()" class="btn btn-secondary">
                                <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                    <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
                                    <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/>
                                </svg>
                                Download
                            </button>
                            <button onclick="kassiaApp.closeJobLogModal()" class="btn-close">×</button>
                        </div>
                    </div>
                    <div class="modal-body">
                        <div class="log-stats">
                            <span id="jobLogCount">0 entries</span>
                            <span id="jobLogErrors">0 errors</span>
                            <span id="jobLogLastUpdate">Never</span>
                        </div>
                        <div class="job-log-container" id="jobLogContainer">
                            <div class="loading">Loading logs...</div>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            // Add event listener for log source change
            document.getElementById('jobLogSource').addEventListener('change', () => {
                this.refreshJobLogs();
            });
        }
    }

    async showJobLogs(jobId) {
        this.currentJobViewer = { jobId: jobId };
        
        const modal = document.getElementById('jobLogModal');
        const title = document.getElementById('jobLogModalTitle');
        
        const job = this.jobs.find(j => j.id === jobId);
        if (job) {
            title.textContent = `Job Logs - ${job.device} OS ${job.os_id}`;
        } else {
            title.textContent = `Job Logs - ${jobId}`;
        }
        
        modal.style.display = 'block';
        
        // Load initial logs
        await this.refreshJobLogs();
        
        // Start auto-refresh for running jobs
        if (job && job.status === 'running') {
            this.startJobLogAutoRefresh();
        }
    }

    async refreshJobLogs() {
        if (!this.currentJobViewer) return;
        
        const jobId = this.currentJobViewer.jobId;
        const source = document.getElementById('jobLogSource').value;
        const container = document.getElementById('jobLogContainer');
        
        try {
            const response = await fetch(`/api/jobs/${jobId}/logs?source=${source}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const logs = await response.json();
            this.displayJobLogs(logs);
            this.updateJobLogStats(logs);
            
        } catch (error) {
            console.error('❌ Failed to load job logs:', error);
            container.innerHTML = `<div class="error">Failed to load logs: ${error.message}</div>`;
        }
    }

    displayJobLogs(logs) {
        const container = document.getElementById('jobLogContainer');
        
        if (!logs || logs.length === 0) {
            container.innerHTML = '<div class="no-logs">No logs available</div>';
            return;
        }
        
        // Sort logs by timestamp
        logs.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        
        const logHtml = logs.map(log => this.formatJobLogEntry(log)).join('');
        container.innerHTML = logHtml;
        
        // Scroll to bottom
        container.scrollTop = container.scrollHeight;
    }

    formatJobLogEntry(log) {
        const timestamp = new Date(log.timestamp).toLocaleTimeString();
        const level = log.level || 'INFO';
        const category = log.category || 'SYSTEM';
        const component = log.component || 'unknown';
        const message = log.message || '';
        
        // Level color mapping
        const levelColors = {
            'DEBUG': '#6c757d',
            'INFO': '#28a745',
            'WARNING': '#ffc107',
            'ERROR': '#dc3545',
            'CRITICAL': '#6f42c1'
        };
        
        const levelColor = levelColors[level] || '#6c757d';
        
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
            <div class="log-entry" data-level="${level}">
                <div class="log-header">
                    <span class="log-timestamp">${timestamp}</span>
                    <span class="log-level" style="color: ${levelColor}; font-weight: 600;">${level}</span>
                    <span class="log-category">${category}</span>
                    <span class="log-component">${component}</span>
                </div>
                <div class="log-message">${this.escapeHtml(message)}</div>
                ${detailsHtml}
            </div>
        `;
    }

    updateJobLogStats(logs) {
        const totalCount = logs.length;
        const errorCount = logs.filter(log =>
            log.level === 'ERROR' || log.level === 'CRITICAL'
        ).length;

        document.getElementById('jobLogCount').textContent = `${totalCount} entries`;
        document.getElementById('jobLogErrors').textContent = `${errorCount} errors`;
        document.getElementById('jobLogLastUpdate').textContent = new Date().toLocaleTimeString();
    }
}

