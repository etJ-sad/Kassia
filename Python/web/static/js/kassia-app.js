// web/static/js/kassia-app.js
// Kassia WebUI - Main Application Controller (FIXED)

class KassiaApp {
    constructor() {
        this.devices = [];
        this.currentAssets = null;
        this.jobs = [];
        this.activeJob = null;
        this.refreshInterval = null;
        
        console.log('🚀 Kassia Application initializing...');
        this.initialize();
    }
    
    async initialize() {
        try {
            // Setup WebSocket message handlers
            this.setupWebSocketHandlers();
            
            // Setup form handlers
            this.setupFormHandlers();
            
            // Setup UI event handlers
            this.setupUIHandlers();
            
            // Load initial data
            await this.loadInitialData();
            
            // Start periodic refresh
            this.startPeriodicRefresh();
            
            console.log('✅ Kassia Application initialized successfully');
            
            // Show success toast
            uiManager.showToast(
                window.t('application_ready', 'Kassia WebUI ready'), 
                'success'
            );
            
        } catch (error) {
            console.error('❌ Failed to initialize Kassia Application:', error);
            uiManager.showToast(
                window.t('initialization_failed', 'Failed to initialize application'), 
                'error'
            );
        }
    }
    
	setupWebSocketHandlers() {
		// Job update handler with enhanced logging
		wsManager.addMessageHandler('job_update', (data) => {
			console.log('🔌 WebSocket job update received:', data);
			this.handleJobUpdate(data);
		});
		
		// Connection status handler
		wsManager.addMessageHandler('connection', (data) => {
			console.log('🔌 WebSocket connection status:', data.connected);
			
			if (data.connected) {
				// When reconnected, force refresh jobs to sync state
				console.log('🔄 WebSocket reconnected, syncing job state...');
				setTimeout(() => {
					this.loadJobs();
				}, 1000);
			}
		});
		
		// Heartbeat handler with job sync check
		wsManager.addMessageHandler('heartbeat', (data) => {
			console.log('💓 Heartbeat received:', data);
			
			// If heartbeat indicates different job count than we have, refresh
			if (data.active_jobs !== undefined) {
				const ourRunningCount = this.jobs.filter(j => j.status === 'running').length;
				if (data.active_jobs !== ourRunningCount) {
					console.log(`🔄 Job count mismatch: server=${data.active_jobs}, client=${ourRunningCount}, refreshing...`);
					this.loadJobs();
				}
			}
		});
	}
    
    setupFormHandlers() {
        // Build form submission
        const buildForm = document.getElementById('buildForm');
        if (buildForm) {
            buildForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleBuildSubmit();
            });
        }
        
        // Device selection change
        const deviceSelect = document.getElementById('deviceSelect');
        if (deviceSelect) {
            deviceSelect.addEventListener('change', () => {
                this.handleDeviceChange();
            });
        }
        
        // OS selection change
        const osSelect = document.getElementById('osSelect');
        if (osSelect) {
            osSelect.addEventListener('change', () => {
                this.updateBuildPreview();
            });
        }
        
        // Asset filter changes
        const assetDeviceFilter = document.getElementById('assetDeviceFilter');
        const assetOSFilter = document.getElementById('assetOSFilter');
        
        if (assetDeviceFilter) {
            assetDeviceFilter.addEventListener('change', () => {
                this.handleAssetFilterChange();
            });
        }
        
        if (assetOSFilter) {
            assetOSFilter.addEventListener('change', () => {
                this.handleAssetFilterChange();
            });
        }
    }
    
    setupUIHandlers() {
        // Override UI manager refresh methods
        uiManager.refreshDashboard = () => this.refreshDashboard();
        uiManager.refreshBuildForm = () => this.refreshBuildForm();
        uiManager.refreshAssets = () => this.handleAssetFilterChange();
        uiManager.refreshJobs = () => this.loadJobs();
    }
    
    async loadInitialData() {
        try {
            // Load devices
            console.log('📱 Loading devices...');
            await this.loadDevices();
            
            // Load jobs
            console.log('📋 Loading jobs...');
            await this.loadJobs();
            
            // Update dashboard
            this.updateDashboardStats();
            
        } catch (error) {
            console.error('❌ Failed to load initial data:', error);
            throw error;
        }
    }
    
    async loadDevices() {
        try {
            this.devices = await api.getDevices();
            console.log(`✅ Loaded ${this.devices.length} devices`);
            
            this.populateDeviceSelects();
            
        } catch (error) {
            console.error('❌ Failed to load devices:', error);
            uiManager.showToast(
                window.t('error_loading_devices', 'Failed to load devices'), 
                'error'
            );
        }
    }
    
    populateDeviceSelects() {
        const deviceSelect = document.getElementById('deviceSelect');
        const assetDeviceFilter = document.getElementById('assetDeviceFilter');
        const assetOSFilter = document.getElementById('assetOSFilter');
        
        // Clear existing options (except first)
        [deviceSelect, assetDeviceFilter].forEach(select => {
            if (select) {
                while (select.children.length > 1) {
                    select.removeChild(select.lastChild);
                }
            }
        });
        
        // Add device options
        this.devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.device_id;
            option.textContent = `${device.device_id} (${device.supported_os.join(', ')})`;
            
            if (deviceSelect) {
                deviceSelect.appendChild(option.cloneNode(true));
            }
            if (assetDeviceFilter) {
                assetDeviceFilter.appendChild(option.cloneNode(true));
            }
        });
        
        // Populate OS filter with all unique OS IDs
        if (assetOSFilter) {
            // Clear existing OS options (except first)
            while (assetOSFilter.children.length > 1) {
                assetOSFilter.removeChild(assetOSFilter.lastChild);
            }
            
            // Get all unique OS IDs
            const allOSIds = [...new Set(this.devices.flatMap(device => device.supported_os))];
            
            const osMap = {
                10: 'Windows 10 IoT Enterprise LTSC 2021',
                21656: 'Windows 11 IoT Enterprise LTSC 2024',
                21651: 'Windows 10 IoT Enterprise LTSB 2016',
                21652: 'Windows 10 IoT Enterprise LTSC 2019',
                21653: 'Windows 11 IoT Enterprise 22H2',
                21654: 'Windows 11 IoT Enterprise 23H2',
                21655: 'Windows 11 IoT Enterprise 24H2'
            };
            
            allOSIds.sort((a, b) => a - b).forEach(osId => {
                const option = document.createElement('option');
                option.value = osId;
                option.textContent = osMap[osId] || `OS ${osId}`;
                assetOSFilter.appendChild(option);
            });
        }
    }
    
    async handleDeviceChange() {
        const deviceSelect = document.getElementById('deviceSelect');
        const osSelect = document.getElementById('osSelect');
        
        if (!deviceSelect || !osSelect) return;
        
        const selectedDeviceId = deviceSelect.value;
        
        // Clear OS options
        osSelect.innerHTML = '<option value="">' + window.t('select_os', 'Select OS...') + '</option>';
        osSelect.disabled = true;
        
        if (!selectedDeviceId) {
            this.hideBuildPreview();
            return;
        }
        
        // Find selected device
        const selectedDevice = this.devices.find(d => d.device_id === selectedDeviceId);
        if (!selectedDevice) return;
        
        // Populate OS options
        const osMap = {
            10: 'Windows 10 IoT Enterprise LTSC 2021',
            21656: 'Windows 11 IoT Enterprise LTSC 2024',
            21651: 'Windows 10 IoT Enterprise LTSB 2016',
            21652: 'Windows 10 IoT Enterprise LTSC 2019',
            21653: 'Windows 11 IoT Enterprise 22H2',
            21654: 'Windows 11 IoT Enterprise 23H2',
            21655: 'Windows 11 IoT Enterprise 24H2'
        };
        
        selectedDevice.supported_os.forEach(osId => {
            const option = document.createElement('option');
            option.value = osId;
            option.textContent = osMap[osId] || `OS ${osId}`;
            osSelect.appendChild(option);
        });
        
        osSelect.disabled = false;
        
        // Clear any existing preview
        this.hideBuildPreview();
    }
    
    async updateBuildPreview() {
        const deviceSelect = document.getElementById('deviceSelect');
        const osSelect = document.getElementById('osSelect');
        
        const deviceId = deviceSelect?.value;
        const osId = osSelect?.value;
        
        if (!deviceId || !osId) {
            this.hideBuildPreview();
            return;
        }
        
        try {
            const startBuildBtn = document.getElementById('startBuildBtn');
            if (startBuildBtn) {
                uiManager.showLoading('startBuildBtn', window.t('loading_assets', 'Loading assets...'));
            }
            
            // Load assets for preview
            const assets = await api.getAssets(deviceId, parseInt(osId));
            
            // Update preview
            this.showBuildPreview(deviceId, osId, assets);
            
        } catch (error) {
            console.error('❌ Failed to load assets for preview:', error);
            uiManager.showToast(
                window.t('error_loading_assets', 'Failed to load assets for preview'), 
                'error'
            );
        } finally {
            const startBuildBtn = document.getElementById('startBuildBtn');
            if (startBuildBtn) {
                uiManager.hideLoading('startBuildBtn');
            }
        }
    }
    
    showBuildPreview(deviceId, osId, assets) {
        const previewEl = document.getElementById('buildPreview');
        if (!previewEl) return;
        
        // Update preview content
        const elements = {
            previewDevice: document.getElementById('previewDevice'),
            previewOS: document.getElementById('previewOS'),
            previewWimPath: document.getElementById('previewWimPath'),
            previewSBI: document.getElementById('previewSBI'),
            previewDrivers: document.getElementById('previewDrivers'),
            previewUpdates: document.getElementById('previewUpdates')
        };
        
        if (elements.previewDevice) elements.previewDevice.textContent = deviceId;
        if (elements.previewOS) elements.previewOS.textContent = osId;
        if (elements.previewWimPath) elements.previewWimPath.textContent = assets.wim_path || 'Not configured';
        if (elements.previewSBI) elements.previewSBI.textContent = assets.sbi ? '✅ Available' : '❌ Missing';
        if (elements.previewDrivers) elements.previewDrivers.textContent = `${assets.drivers?.length || 0} found`;
        if (elements.previewUpdates) elements.previewUpdates.textContent = `${assets.updates?.length || 0} found`;
        
        previewEl.style.display = 'block';
    }
    
    hideBuildPreview() {
        const previewEl = document.getElementById('buildPreview');
        if (previewEl) {
            previewEl.style.display = 'none';
        }
    }
    
    async handleBuildSubmit() {
        console.log('🚀 Build form submitted');
        
        const deviceSelect = document.getElementById('deviceSelect');
        const osSelect = document.getElementById('osSelect');
        const skipDrivers = document.getElementById('skipDrivers');
        const skipUpdates = document.getElementById('skipUpdates');
        
        // Manual validation instead of using the problematic validateForm method
        const errors = [];
        
        if (!deviceSelect || !deviceSelect.value) {
            errors.push(window.t('validation_device_required', 'Device selection is required'));
        }
        
        if (!osSelect || !osSelect.value) {
            errors.push(window.t('validation_os_required', 'Operating system selection is required'));
        }
        
        if (errors.length > 0) {
            errors.forEach(error => {
                uiManager.showToast(error, 'error');
            });
            return;
        }
        
        const buildRequest = {
            device: deviceSelect.value,
            os_id: parseInt(osSelect.value),
            skip_drivers: skipDrivers ? skipDrivers.checked : false,
            skip_updates: skipUpdates ? skipUpdates.checked : false
        };
        
        console.log('📋 Build request:', buildRequest);
        
        try {
            uiManager.showLoading('startBuildBtn', window.t('starting_build', 'Starting build...'));
            
            const response = await api.startBuild(buildRequest);
            console.log('✅ Build started:', response);
            
            uiManager.showToast(
                window.t('build_started', 'Build started successfully!'), 
                'success'
            );
            
            // Reset form
            if (deviceSelect) deviceSelect.value = '';
            if (osSelect) {
                osSelect.innerHTML = '<option value="">' + window.t('select_os', 'Select OS...') + '</option>';
                osSelect.disabled = true;
            }
            if (skipDrivers) skipDrivers.checked = false;
            if (skipUpdates) skipUpdates.checked = false;
            
            this.hideBuildPreview();
            
            // Switch to jobs tab
            uiManager.switchTab('jobs');
            
            // Refresh jobs
            await this.loadJobs();
            
        } catch (error) {
            console.error('❌ Failed to start build:', error);
            uiManager.showToast(
                window.t('build_start_failed', 'Failed to start build: ' + error.message), 
                'error'
            );
        } finally {
            uiManager.hideLoading('startBuildBtn');
        }
    }
    
    async handleAssetFilterChange() {
        const deviceFilter = document.getElementById('assetDeviceFilter');
        const osFilter = document.getElementById('assetOSFilter');
        
        const deviceId = deviceFilter?.value;
        const osId = osFilter?.value;
        
        if (!deviceId || !osId) {
            this.clearAssetsDisplay();
            return;
        }
        
        try {
            const assetsContent = document.getElementById('assetsContent');
            if (assetsContent) {
                assetsContent.innerHTML = '<div style="text-align: center; padding: 40px;">' + 
                    '<div class="loading-spinner"></div> ' + 
                    window.t('loading_assets', 'Loading assets...') + '</div>';
            }
            
            const assets = await api.getAssets(deviceId, parseInt(osId));
            this.currentAssets = assets;
            this.displayAssets(assets);
            
        } catch (error) {
            console.error('❌ Failed to load assets:', error);
            uiManager.showToast(
                window.t('error_loading_assets', 'Failed to load assets'), 
                'error'
            );
            this.clearAssetsDisplay();
        }
    }
    
    displayAssets(assets) {
        const assetsContent = document.getElementById('assetsContent');
        if (!assetsContent) return;
        
        let html = '';
        
        // SBI Section
        html += '<div class="content-card" style="margin-bottom: 24px;">';
        html += '<div class="card-header"><h3 class="card-title">System Base Image (SBI)</h3></div>';
        html += '<div class="card-content">';
        
        if (assets.sbi) {
            const sizeText = assets.sbi.size ? uiManager.formatBytes(assets.sbi.size) : 'Unknown size';
            const statusClass = assets.sbi.valid ? 'valid' : 'invalid';
            const statusText = assets.sbi.valid ? '✅ Valid' : '❌ Invalid';
            
            html += `
                <div class="asset-item ${statusClass}">
                    <div class="asset-name">${uiManager.escapeHtml(assets.sbi.name)}</div>
                    <div class="asset-type">WIM File</div>
                    <div class="asset-path">${uiManager.escapeHtml(assets.sbi.path)}</div>
                    <div class="asset-footer">
                        <span class="asset-size">${sizeText}</span>
                        <span class="asset-status ${statusClass}">${statusText}</span>
                    </div>
                </div>
            `;
        } else {
            html += '<p style="text-align: center; color: var(--siemens-text-secondary); padding: 20px;">No SBI found for this configuration</p>';
        }
        
        html += '</div></div>';
        
        // Drivers Section
        html += '<div class="content-card" style="margin-bottom: 24px;">';
        html += '<div class="card-header"><h3 class="card-title">Drivers (' + (assets.drivers?.length || 0) + ')</h3></div>';
        html += '<div class="card-content">';
        
        if (assets.drivers && assets.drivers.length > 0) {
            html += '<div class="asset-grid">';
            assets.drivers.forEach(driver => {
                const sizeText = driver.size ? uiManager.formatBytes(driver.size) : 'Unknown size';
                const statusClass = driver.valid ? 'valid' : 'invalid';
                const statusText = driver.valid ? '✅ Valid' : '❌ Invalid';
                
                html += `
                    <div class="asset-item ${statusClass}">
                        <div class="asset-name">${uiManager.escapeHtml(driver.name)}</div>
                        <div class="asset-type">${uiManager.escapeHtml(driver.type)}</div>
                        <div class="asset-path">${uiManager.escapeHtml(driver.path)}</div>
                        <div class="asset-footer">
                            <span class="asset-size">${sizeText}</span>
                            <span class="asset-status ${statusClass}">${statusText}</span>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        } else {
            html += '<p style="text-align: center; color: var(--siemens-text-secondary); padding: 20px;">No drivers found for this configuration</p>';
        }
        
        html += '</div></div>';
        
        // Updates Section
        html += '<div class="content-card" style="margin-bottom: 24px;">';
        html += '<div class="card-header"><h3 class="card-title">Updates (' + (assets.updates?.length || 0) + ')</h3></div>';
        html += '<div class="card-content">';
        
        if (assets.updates && assets.updates.length > 0) {
            html += '<div class="asset-grid">';
            assets.updates.forEach(update => {
                const sizeText = update.size ? uiManager.formatBytes(update.size) : 'Unknown size';
                const statusClass = update.valid ? 'valid' : 'invalid';
                const statusText = update.valid ? '✅ Valid' : '❌ Invalid';
                
                html += `
                    <div class="asset-item ${statusClass}">
                        <div class="asset-name">${uiManager.escapeHtml(update.name)}</div>
                        <div class="asset-type">${uiManager.escapeHtml(update.type)}</div>
                        <div class="asset-path">${uiManager.escapeHtml(update.path)}</div>
                        <div class="asset-footer">
                            <span class="asset-size">${sizeText}</span>
                            <span class="asset-status ${statusClass}">${statusText}</span>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        } else {
            html += '<p style="text-align: center; color: var(--siemens-text-secondary); padding: 20px;">No updates found for this configuration</p>';
        }
        
        html += '</div></div>';
        
        // Yunona Scripts Section
        if (assets.yunona_scripts && assets.yunona_scripts.length > 0) {
            html += '<div class="content-card">';
            html += '<div class="card-header"><h3 class="card-title">Yunona Scripts (' + assets.yunona_scripts.length + ')</h3></div>';
            html += '<div class="card-content">';
            html += '<div class="asset-grid">';
            
            assets.yunona_scripts.forEach(script => {
                const sizeText = script.size ? uiManager.formatBytes(script.size) : 'Unknown size';
                const statusClass = script.valid ? 'valid' : 'invalid';
                const statusText = script.valid ? '✅ Valid' : '❌ Invalid';
                
                html += `
                    <div class="asset-item ${statusClass}">
                        <div class="asset-name">${uiManager.escapeHtml(script.name)}</div>
                        <div class="asset-type">${uiManager.escapeHtml(script.type)}</div>
                        <div class="asset-path">${uiManager.escapeHtml(script.path)}</div>
                        <div class="asset-footer">
                            <span class="asset-size">${sizeText}</span>
                            <span class="asset-status ${statusClass}">${statusText}</span>
                        </div>
                    </div>
                `;
            });
            
            html += '</div></div></div>';
        }
        
        assetsContent.innerHTML = html;
    }
    
    clearAssetsDisplay() {
        const assetsContent = document.getElementById('assetsContent');
        if (assetsContent) {
            assetsContent.innerHTML = '<p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">' + 
                window.t('select_device_os_assets', 'Select device and OS to view available assets') + '</p>';
        }
    }
    
	async loadJobs() {
		try {
			console.log('📋 Loading jobs from API...');
			const startTime = Date.now();
			
			this.jobs = await api.getJobs();
			
			const loadTime = Date.now() - startTime;
			console.log(`✅ Loaded ${this.jobs.length} jobs in ${loadTime}ms`);
			
			// Update all UI components
			this.displayJobs();
			this.updateDashboardStats();
			this.updateActiveJob();
			
			// Debug log current job statuses
			const statusCounts = this.jobs.reduce((acc, job) => {
				acc[job.status] = (acc[job.status] || 0) + 1;
				return acc;
			}, {});
			console.log('📊 Job status breakdown:', statusCounts);
			
		} catch (error) {
			console.error('❌ Failed to load jobs:', error);
			uiManager.showToast(
				window.t('error_loading_jobs', 'Failed to load jobs: ' + error.message), 
				'error'
			);
			
			// Retry after a delay if this was a network error
			if (error.message.includes('fetch') || error.message.includes('Network')) {
				console.log('🔄 Retrying job load after network error...');
				setTimeout(() => {
					this.loadJobs();
				}, 5000);
			}
		}
	}
	
	async forceRefreshJobs() {
		console.log('🔄 Force refreshing all job data...');
		
		try {
			// Clear current data
			this.jobs = [];
			this.activeJob = null;
			
			// Update UI to show loading state
			const jobsList = document.getElementById('jobsList');
			if (jobsList) {
				jobsList.innerHTML = '<div style="text-align: center; padding: 40px;"><div class="loading-spinner"></div> Refreshing jobs...</div>';
			}
			
			// Hide active job card
			const activeJobCard = document.getElementById('activeJobCard');
			if (activeJobCard) {
				activeJobCard.style.display = 'none';
			}
			
			// Reload from API
			await this.loadJobs();
			
			console.log('✅ Force refresh completed');
			
		} catch (error) {
			console.error('❌ Force refresh failed:', error);
			uiManager.showToast('Failed to refresh jobs', 'error');
		}
	}
    
    displayJobs() {
        const jobsList = document.getElementById('jobsList');
        if (!jobsList) return;
        
        if (this.jobs.length === 0) {
            jobsList.innerHTML = '<p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">' + 
                window.t('no_build_jobs', 'No build jobs found. Start your first build to see it here.') + '</p>';
            return;
        }
        
        // Sort jobs by creation time (newest first)
        const sortedJobs = [...this.jobs].sort((a, b) => 
            new Date(b.created_at) - new Date(a.created_at)
        );
        
        let html = '';
        
        sortedJobs.forEach(job => {
            const statusClass = this.getJobStatusClass(job.status);
            const progress = job.progress || 0;
            const duration = this.calculateJobDuration(job);
            
            html += `
                <div class="job-item">
                    <div class="job-header">
                        <div>
                            <h3 class="job-title">${job.device} - OS ${job.os_id}</h3>
                            <div class="job-id">Job ID: ${job.id}</div>
                        </div>
                        <span class="status-badge ${statusClass}">${job.status}</span>
                    </div>
                    
                    <div class="job-meta">
                        <div class="job-meta-item">
                            <span class="job-meta-label">Progress</span>
                            <span class="job-meta-value">${progress}% - ${job.current_step || 'Waiting'}</span>
                        </div>
                        <div class="job-meta-item">
                            <span class="job-meta-label">Duration</span>
                            <span class="job-meta-value">${duration}</span>
                        </div>
                        <div class="job-meta-item">
                            <span class="job-meta-label">Created</span>
                            <span class="job-meta-value">${uiManager.formatDate(job.created_at)}</span>
                        </div>
                        <div class="job-meta-item">
                            <span class="job-meta-label">Status</span>
                            <span class="job-meta-value">${job.status}</span>
                        </div>
                    </div>
                    
                    ${job.status === 'running' ? `
                        <div class="progress-bar" style="margin-bottom: 15px;">
                            <div class="progress-fill" style="width: ${progress}%;"></div>
                        </div>
                    ` : ''}
                    
                    ${job.error ? `
                        <div style="background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 10px; border-radius: 4px; margin-bottom: 15px;">
                            <strong>Error:</strong> ${uiManager.escapeHtml(job.error)}
                        </div>
                    ` : ''}
                    
                    <div class="job-actions">
                        <button class="btn btn-secondary" onclick="kassiaApp.showJobLogs('${job.id}')">
                            View Logs
                        </button>
                        ${job.status === 'running' ? `
                            <button class="btn btn-danger" onclick="kassiaApp.cancelJob('${job.id}')">
                                Cancel
                            </button>
                        ` : ''}
                        ${job.status === 'completed' && job.results?.final_wim_path ? `
                            <button class="btn btn-secondary" onclick="kassiaApp.downloadResult('${job.id}')">
                                Download WIM
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        
        jobsList.innerHTML = html;
    }
    
    getJobStatusClass(status) {
        switch (status) {
            case 'completed': return 'status-success';
            case 'failed': case 'cancelled': return 'status-error';
            case 'running': return 'status-info';
            default: return 'status-warning';
        }
    }
    
    calculateJobDuration(job) {
        const start = new Date(job.created_at);
        const end = job.completed_at ? new Date(job.completed_at) : new Date();
        const duration = Math.floor((end - start) / 1000);
        return uiManager.formatDuration(duration);
    }
    
    updateDashboardStats() {
        const stats = {
            total: this.jobs.length,
            running: this.jobs.filter(j => j.status === 'running').length,
            completed: this.jobs.filter(j => j.status === 'completed').length,
            failed: this.jobs.filter(j => j.status === 'failed' || j.status === 'cancelled').length
        };
        
        // Update dashboard counters
        const elements = {
            totalJobs: document.getElementById('totalJobs'),
            runningJobs: document.getElementById('runningJobs'),
            completedJobs: document.getElementById('completedJobs'),
            failedJobs: document.getElementById('failedJobs')
        };
        
        if (elements.totalJobs) elements.totalJobs.textContent = stats.total;
        if (elements.runningJobs) elements.runningJobs.textContent = stats.running;
        if (elements.completedJobs) elements.completedJobs.textContent = stats.completed;
        if (elements.failedJobs) elements.failedJobs.textContent = stats.failed;
        
        // Update recent jobs in dashboard
        this.updateRecentJobsList();
    }
    
    updateRecentJobsList() {
        const recentJobsList = document.getElementById('recentJobsList');
        if (!recentJobsList) return;
        
        const recentJobs = this.jobs
            .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
            .slice(0, 5); // Show last 5 jobs
        
        if (recentJobs.length === 0) {
            recentJobsList.innerHTML = '<p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">' + 
                window.t('no_jobs_yet', 'No jobs yet. Start a new build to see activity here.') + '</p>';
            return;
        }
        
        let html = '';
        recentJobs.forEach(job => {
            const statusClass = this.getJobStatusClass(job.status);
            const duration = this.calculateJobDuration(job);
            
            html += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; border: 1px solid #dee2e6; border-radius: 6px; margin-bottom: 8px;">
                    <div>
                        <strong>${job.device} - OS ${job.os_id}</strong><br>
                        <small style="color: var(--siemens-text-secondary);">${uiManager.formatDate(job.created_at)}</small>
                    </div>
                    <div style="text-align: right;">
                        <span class="status-badge ${statusClass}">${job.status}</span><br>
                        <small style="color: var(--siemens-text-secondary);">${duration}</small>
                    </div>
                </div>
            `;
        });
        
        recentJobsList.innerHTML = html;
    }
    
    updateActiveJob() {
		const runningJobs = this.jobs.filter(j => j.status === 'running');
		const activeJobCard = document.getElementById('activeJobCard');
		
		if (!activeJobCard) return;
		
		if (runningJobs.length === 0) {
			// No active jobs, hide the card
			activeJobCard.style.display = 'none';
			this.activeJob = null;
			console.log('👻 No active jobs, hiding active job card');
			return;
		}
		
		// Show the most recent running job
		const activeJob = runningJobs[0];
		this.activeJob = activeJob;
		
		console.log('🎯 Updating active job display:', activeJob.id, activeJob.status, activeJob.progress);
		
		// Update active job display elements
		const elements = {
			title: document.getElementById('activeJobTitle'),
			status: document.getElementById('activeJobStatus'),
			progress: document.getElementById('activeJobProgress'),
			step: document.getElementById('activeJobStep'),
			progressBar: document.getElementById('activeJobProgressBar'),
			logs: document.getElementById('activeJobLogs')
		};
		
		if (elements.title) {
			elements.title.textContent = `${activeJob.device} - OS ${activeJob.os_id}`;
		}
		
		if (elements.status) {
			elements.status.textContent = activeJob.status;
			elements.status.className = `status-badge ${this.getJobStatusClass(activeJob.status)}`;
		}
		
		if (elements.progress) {
			elements.progress.textContent = `${activeJob.progress || 0}%`;
		}
		
		if (elements.step) {
			elements.step.textContent = activeJob.current_step || 'Waiting';
		}
		
		if (elements.progressBar) {
			const progress = Math.min(Math.max(activeJob.progress || 0, 0), 100);
			elements.progressBar.style.width = `${progress}%`;
		}
		
		// Update logs if available
		if (elements.logs) {
			if (activeJob.logs && activeJob.logs.length > 0) {
				const logLines = activeJob.logs.slice(-10).map(log => 
					`[${log.timestamp.split('T')[1].split('.')[0]}] ${log.level}: ${log.message}`
				).join('\n');
				elements.logs.textContent = logLines;
				elements.logs.scrollTop = elements.logs.scrollHeight;
			} else {
				elements.logs.textContent = 'Waiting for job updates...';
			}
		}
		
		activeJobCard.style.display = 'block';
	}
    
    handleJobUpdate(data) {
		console.log('📋 Job update received:', data.job_id, data.data?.status, data.data?.progress);
		
		if (!data.data) {
			console.error('❌ Invalid job update - missing data:', data);
			return;
		}
		
		// Find and update job in local array
		const jobIndex = this.jobs.findIndex(j => j.id === data.job_id);
		if (jobIndex >= 0) {
			// Update existing job
			const oldStatus = this.jobs[jobIndex].status;
			this.jobs[jobIndex] = { ...this.jobs[jobIndex], ...data.data };
			
			console.log(`🔄 Updated job ${data.job_id}: ${oldStatus} -> ${data.data.status}`);
		} else {
			// New job, add to array
			this.jobs.push(data.data);
			console.log(`➕ Added new job ${data.job_id}: ${data.data.status}`);
		}
		
		// Force immediate UI refresh
		this.updateDashboardStats();
		this.updateActiveJob();
		
		// If currently viewing jobs tab, refresh the display immediately
		if (uiManager.currentTab === 'jobs') {
			this.displayJobs();
		}
		
		// Show notification for status changes
		const job = data.data;
		if (job.status === 'completed') {
			uiManager.showToast(
				window.t('build_completed', `Build completed successfully! Device: ${job.device}, OS: ${job.os_id}`), 
				'success',
				8000 // Show longer for completed jobs
			);
			
			// Auto-refresh after completion to ensure UI is in sync
			setTimeout(() => {
				console.log('🔄 Auto-refreshing jobs after completion');
				this.loadJobs();
			}, 2000);
			
		} else if (job.status === 'failed') {
			uiManager.showToast(
				window.t('build_failed', `Build failed: ${job.device}, OS: ${job.os_id}`), 
				'error',
				10000 // Show longer for failed jobs
			);
			
			// Auto-refresh after failure
			setTimeout(() => {
				console.log('🔄 Auto-refreshing jobs after failure');
				this.loadJobs();
			}, 2000);
			
		} else if (job.status === 'running' && job.progress) {
			// Update progress for running jobs
			console.log(`⏳ Job ${job.device} progress: ${job.progress}% - ${job.current_step}`);
		}
	}
    
    async cancelJob(jobId) {
        if (!confirm(window.t('confirm_cancel_job', 'Are you sure you want to cancel this job?'))) {
            return;
        }
        
        try {
            await api.cancelJob(jobId);
            uiManager.showToast(
                window.t('job_cancelled', 'Job cancelled successfully'), 
                'success'
            );
            
            // Refresh jobs
            await this.loadJobs();
            
        } catch (error) {
            console.error('❌ Failed to cancel job:', error);
            uiManager.showToast(
                window.t('error_canceling_job', 'Failed to cancel job'), 
                'error'
            );
        }
    }
    
    async showJobLogs(jobId) {
        try {
            const logs = await api.getJobLogs(jobId, 'database');
            
            // Create modal or new window to show logs
            const logWindow = window.open('', '_blank', 'width=800,height=600');
            logWindow.document.title = `Job Logs - ${jobId}`;
            
            let logHtml = `
                <html>
                <head>
                    <title>Job Logs - ${jobId}</title>
                    <style>
                        body { 
                            font-family: monospace; 
                            margin: 20px; 
                            background: #1e1e1e; 
                            color: #d4d4d4; 
                        }
                        .log-entry { 
                            margin-bottom: 5px; 
                            padding: 2px 0;
                        }
                        .log-level-ERROR { color: #f14c4c; }
                        .log-level-WARNING { color: #ffcc02; }
                        .log-level-INFO { color: #3794ff; }
                        .log-level-DEBUG { color: #b5b5b5; }
                        .log-timestamp { color: #9d9d9d; }
                        .header { 
                            position: sticky; 
                            top: 0; 
                            background: #1e1e1e; 
                            padding: 10px 0; 
                            border-bottom: 1px solid #3c3c3c; 
                            margin-bottom: 20px;
                        }
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h2>Job Logs: ${jobId}</h2>
                        <p>Total entries: ${logs.length}</p>
                    </div>
                    <div class="logs">
            `;
            
            logs.forEach(log => {
                const timestamp = new Date(log.timestamp).toLocaleString();
                logHtml += `
                    <div class="log-entry log-level-${log.level}">
                        <span class="log-timestamp">[${timestamp}]</span> 
                        <strong>${log.level}</strong> 
                        ${log.category} - ${log.component}: ${log.message}
                        ${log.details ? '<br><small>' + JSON.stringify(log.details, null, 2) + '</small>' : ''}
                    </div>
                `;
            });
            
            logHtml += `
                    </div>
                </body>
                </html>
            `;
            
            logWindow.document.write(logHtml);
            logWindow.document.close();
            
        } catch (error) {
            console.error('❌ Failed to load job logs:', error);
            uiManager.showToast(
                window.t('error_loading_logs', 'Failed to load job logs'), 
                'error'
            );
        }
    }
    
    async downloadResult(jobId) {
        const job = this.jobs.find(j => j.id === jobId);
        if (!job || !job.results?.final_wim_path) {
            uiManager.showToast(
                window.t('no_result_available', 'No result file available'), 
                'warning'
            );
            return;
        }
        
        // Note: In a real implementation, you'd need a download endpoint
        uiManager.showToast(
            window.t('download_info', 'WIM file location: ') + job.results.final_wim_path, 
            'info'
        );
    }
    
    refreshDashboard() {
        console.log('🔄 Refreshing dashboard...');
        this.loadJobs();
    }
    
    refreshBuildForm() {
        console.log('🔄 Refreshing build form...');
        this.loadDevices();
    }
    
	startPeriodicRefresh() {
		// Refresh every 15 seconds instead of 30 for better responsiveness
		this.refreshInterval = setInterval(() => {
			const hasRunningJobs = this.jobs.some(j => j.status === 'running');
			
			if (hasRunningJobs) {
				console.log('🔄 Periodic refresh: updating jobs...');
				this.loadJobs();
			} else {
				// Even without running jobs, do a lighter refresh every 2 minutes
				const now = Date.now();
				if (!this.lastFullRefresh || (now - this.lastFullRefresh) > 120000) {
					console.log('🔄 Periodic full refresh (no active jobs)');
					this.loadJobs();
					this.lastFullRefresh = now;
				}
			}
		}, 15000); // Every 15 seconds
	}
	
    stopPeriodicRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    // Utility methods
    showToast(message, type = 'info') {
        uiManager.showToast(message, type);
    }
    
    async healthCheck() {
        try {
            const health = await api.getHealth();
            console.log('💓 Health check passed:', health);
            return health;
        } catch (error) {
            console.error('❌ Health check failed:', error);
            return null;
        }
    }
    
    getAppInfo() {
        return {
            devices: this.devices.length,
            jobs: this.jobs.length,
            activeJob: this.activeJob?.id || null,
            currentTab: uiManager.currentTab,
            connected: wsManager.isConnected,
            version: '2.0.0'
        };
    }
    
    // Cleanup method
    destroy() {
        console.log('🧹 Cleaning up Kassia Application...');
        
        this.stopPeriodicRefresh();
        
        // Remove WebSocket handlers
        wsManager.messageHandlers.clear();
        
        // Clear data
        this.devices = [];
        this.jobs = [];
        this.currentAssets = null;
        this.activeJob = null;
        
        console.log('✅ Kassia Application cleaned up');
    }
}

// Make KassiaApp available globally
window.KassiaApp = KassiaApp;

// Add global functions for HTML onclick handlers
window.kassiaApp = null; // Will be set when app initializes

// Global helper functions for HTML
window.startNewBuild = function() {
    uiManager.switchTab('build');
};

window.viewAllJobs = function() {
    uiManager.switchTab('jobs');
};

window.refreshDashboard = function() {
    if (window.kassiaApp) {
        window.kassiaApp.refreshDashboard();
    }
};

// Error boundary for the application
window.addEventListener('error', (event) => {
    console.error('💥 Global error caught:', event.error);
    
    if (window.kassiaApp) {
        window.kassiaApp.showToast(
            window.t('unexpected_error', 'An unexpected error occurred'), 
            'error'
        );
    }
});

window.forceRefreshJobs = function() {
    if (window.kassiaApp && window.kassiaApp.forceRefreshJobs) {
        window.kassiaApp.forceRefreshJobs();
    }
};

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.kassiaApp) {
        window.kassiaApp.destroy();
    }
});

console.log('📦 Kassia Application loaded');