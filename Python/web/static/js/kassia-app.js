const startingText = {
            'de': 'Build wird gestartet...',
            'en': 'Starting Build...',
            'ru': 'Запуск сборки...',
            'cs': 'Spouštění buildu...'
        }[this.currentLanguage] || 'Starting Build...';
        
        // Disable form
        if (startBuildBtn) {
            startBuildBtn.disabled = true;
            startBuildBtn.innerHTML = `
                <div class="loading-spinner" style="margin-right: 8px;"></div>
                ${startingText}
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
            
            const message = this.getLocalizedMessage('buildStarted');
            this.showToast(message, 'success');
            
            // Switch to dashboard to show progress
            this.switchTab('dashboard');
            
            // Refresh jobs to show new job
            await this.loadJobs();
            
        } catch (error) {
            console.error('❌ Failed to start build:', error);
            const message = this.getLocalizedMessage('buildStartFailed', error.message);
            this.showToast(message, 'error');
        } finally {
            // Re-enable form with localized text
            if (startBuildBtn) {
                startBuildBtn.disabled = false;
                const startBuildText = {
                    'de': 'Build starten',
                    'en': 'Start Build',
                    'ru': 'Запустить сборку',
                    'cs': 'Spustit build'
                }[this.currentLanguage] || 'Start Build';
                
                startBuildBtn.innerHTML = `
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="m11.596 8.697-6.363 3.692c-.54.313-1.233-.066-1.233-.697V4.308c0-.63.692-1.01 1.233-.696l6.363 3.692a.802.802 0 0 1 0 1.393z"/>
                    </svg>
                    ${startBuildText}
                `;
            }
        }
    }
    
    async handleAssetFilterChange() {
        const deviceFilter = document.getElementById('assetDeviceFilter');
        const osFilter = document.getElementById('assetOSFilter');
        
        if (!deviceFilter?.value || !osFilter?.value) {
            const message = this.getLocalizedMessage('selectDeviceAndOS');
            this.displayAssetsMessage(message);
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
        
        // Get localized section titles
        const sectionTitles = {
            'de': {
                'sbi': 'System Base Image (SBI)',
                'drivers': 'Treiber',
                'updates': 'Updates',
                'scripts': 'Yunona Scripts'
            },
            'en': {
                'sbi': 'System Base Image (SBI)',
                'drivers': 'Drivers',
                'updates': 'Updates',
                'scripts': 'Yunona Scripts'
            },
            'ru': {
                'sbi': 'Системный базовый образ (SBI)',
                'drivers': 'Драйверы',
                'updates': 'Обновления',
                'scripts': 'Yunona Scripts'
            },
            'cs': {
                'sbi': 'Systémový základní obraz (SBI)',
                'drivers': 'Ovladače',
                'updates': 'Aktualizace',
                'scripts': 'Yunona Scripts'
            }
        }[this.currentLanguage] || {
            'sbi': 'System Base Image (SBI)',
            'drivers': 'Drivers',
            'updates': 'Updates',
            'scripts': 'Yunona Scripts'
        };
        
        // SBI Section
        html += this.createAssetSection(sectionTitles.sbi, assets.sbi ? [assets.sbi] : [], 'sbi');
        
        // Drivers Section
        html += this.createAssetSection(sectionTitles.drivers, assets.drivers, 'drivers');
        
        // Updates Section
        html += this.createAssetSection(sectionTitles.updates, assets.updates, 'updates');
        
        // Yunona Scripts Section
        html += this.createAssetSection(sectionTitles.scripts, assets.yunona_scripts, 'scripts');
        
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
        
        // Get localized "not found" text
        const notFoundText = {
            'de': `Keine ${title.toLowerCase()} gefunden`,
            'en': `No ${title.toLowerCase()} found`,
            'ru': `${title} не найдены`,
            'cs': `Žádné ${title.toLowerCase()} nenalezeny`
        }[this.currentLanguage] || `No ${title.toLowerCase()} found`;
        
        let html = `
            <div class="asset-section">
                <div class="asset-section-title">
                    <div class="file-icon ${iconMap[type]}">${iconMap[type].toUpperCase()}</div>
                    ${title}
                    <span class="asset-section-count">${count}</span>
                </div>
        `;
        
        if (count === 0) {
            html += `<div class="asset-section-empty">${notFoundText}</div>`;
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
        
        // Get localized status text
        const statusText = {
            'de': asset.valid ? 'Gültig' : 'Ungültig',
            'en': asset.valid ? 'Valid' : 'Invalid',
            'ru': asset.valid ? 'Действительный' : 'Недействительный',
            'cs': asset.valid ? 'Platný' : 'Neplatný'
        }[this.currentLanguage] || (asset.valid ? 'Valid' : 'Invalid');
        
        // Get localized size text
        const sizeText = asset.size ? 
            this.formatBytes(asset.size) : 
            {
                'de': 'Unbekannte Größe',
                'en': 'Unknown size',
                'ru': 'Неизвестный размер',
                'cs': 'Neznámá velikost'
            }[this.currentLanguage] || 'Unknown size';
        
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
        
        // Get localized texts
        const statusText = {
            'de': {
                'running': 'Läuft',
                'completed': 'Abgeschlossen',
                'failed': 'Fehlgeschlagen',
                'cancelled': 'Abgebrochen'
            },
            'en': {
                'running': 'Running',
                'completed': 'Completed',
                'failed': 'Failed',
                'cancelled': 'Cancelled'
            },
            'ru': {
                'running': 'Выполняется',
                'completed': 'Завершено',
                'failed': 'Не удалось',
                'cancelled': 'Отменено'
            },
            'cs': {
                'running': 'Běží',
                'completed': 'Dokončeno',
                'failed': 'Selhalo',
                'cancelled': 'Zrušeno'
            }
        }[this.currentLanguage] || {
            'running': 'Running',
            'completed': 'Completed',
            'failed': 'Failed',
            'cancelled': 'Cancelled'
        };
        
        const stepText = {
            'de': 'Schritt',
            'en': 'Step',
            'ru': 'Шаг',
            'cs': 'Krok'
        }[this.currentLanguage] || 'Step';
        
        const waitingText = {
            'de': 'Warten auf Auftragsupdates...',
            'en': 'Waiting for job updates...',
            'ru': 'Ожидание обновлений задачи...',
            'cs': 'Čekání na aktualizace úlohy...'
        }[this.currentLanguage] || 'Waiting for job updates...';
        
        // Update content
        if (activeJobTitle) {
            activeJobTitle.textContent = `${jobData.device} - OS ${jobData.os_id}`;
        }
        
        if (activeJobStatus) {
            activeJobStatus.textContent = statusText[jobData.status] || jobData.status;
            activeJobStatus.className = `status-badge ${this.getStatusClass(jobData.status)}`;
        }
        
        if (activeJobStep) {
            activeJobStep.textContent = `${stepText} ${jobData.step_number}/${jobData.total_steps}: ${jobData.current_step}`;
        }
        
        if (activeJobProgress) {
            activeJobProgress.textContent = `${jobData.progress}%`;
        }
        
        if (activeJobProgressBar) {
            activeJobProgressBar.style.width = `${jobData.progress}%`;
        }
        
        // Update logs
        if (activeJobLogs && jobData.logs) {
            const logsHtml = jobData.logs.map(log => `<div>${log}</div>`).join('');
            activeJobLogs.innerHTML = logsHtml || `<div>${waitingText}</div>`;
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
            const noJobsText = this.getLocalizedMessage('noJobsFound');
            recentJobsList.innerHTML = `
                <p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">
                    ${noJobsText}
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
            const noJobsText = {
                'de': 'Keine Build-Aufträge gefunden. Starten Sie Ihren ersten Build, um ihn hier zu sehen.',
                'en': 'No build jobs found. Start your first build to see it here.',
                'ru': 'Задачи сборки не найдены. Запустите первую сборку, чтобы увидеть её здесь.',
                'cs': 'Nebyly nalezeny žádné build úlohy. Spusťte první build a uvidíte jej zde.'
            }[this.currentLanguage] || 'No build jobs found. Start your first build to see it here.';
            
            jobsList.innerHTML = `
                <p style="text-align: center; color: var(--siemens-text-secondary); padding: 40px;">
                    ${noJobsText}
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
        
        // Get localized texts
        const labels = {
            'de': {
                'created': 'Erstellt',
                'duration': 'Dauer',
                'finalSize': 'Endgröße',
                'error': 'Fehler',
                'cancel': 'Abbrechen',
                'details': 'Details'
            },
            'en': {
                'created': 'Created',
                'duration': 'Duration',
                'finalSize': 'Final Size',
                'error': 'Error',
                'cancel': 'Cancel',
                'details': 'Details'
            },
            'ru': {
                'created': 'Создано',
                'duration': 'Продолжительность',
                'finalSize': 'Финальный размер',
                'error': 'Ошибка',
                'cancel': 'Отменить',
                'details': 'Детали'
            },
            'cs': {
                'created': 'Vytvořeno',
                'duration': 'Trvání',
                'finalSize': 'Konečná velikost',
                'error': 'Chyba',
                'cancel': 'Zrušit',
                'details': 'Detaily'
            }
        }[this.currentLanguage] || {
            'created': 'Created',
            'duration': 'Duration',
            'finalSize': 'Final Size',
            'error': 'Error',
            'cancel': 'Cancel',
            'details': 'Details'
        };
        
        const statusText = {
            'de': {
                'running': 'Läuft',
                'completed': 'Abgeschlossen',
                'failed': 'Fehlgeschlagen',
                'cancelled': 'Abgebrochen',
                'created': 'Erstellt'
            },
            'en': {
                'running': 'Running',
                'completed': 'Completed',
                'failed': 'Failed',
                'cancelled': 'Cancelled',
                'created': 'Created'
            },
            'ru': {
                'running': 'Выполняется',
                'completed': 'Завершено',
                'failed': 'Не удалось',
                'cancelled': 'Отменено',
                'created': 'Создано'
            },
            'cs': {
                'running': 'Běží',
                'completed': 'Dokončeno',
                'failed': 'Selhalo',
                'cancelled': 'Zrušeno',
                'created': 'Vytvořeno'
            }
        }[this.currentLanguage] || {
            'running': 'Running',
            'completed': 'Completed',
            'failed': 'Failed',
            'cancelled': 'Cancelled',
            'created': 'Created'
        };
        
        let progressHtml = '';
        if (job.status === 'running') {
            const stepText = {
                'de': 'Schritt',
                'en': 'Step',
                'ru': 'Шаг',
                'cs': 'Krok'
            }[this.currentLanguage] || 'Step';
            
            progressHtml = `
                <div class="job-progress">
                    <div class="job-progress-text">
                        <span>${stepText} ${job.step_number}/${job.total_steps}: ${job.current_step}</span>
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
                        <button class="btn btn-secondary" onclick="kassiaApp.cancelJob('${job.id}')">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                                <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
                            </svg>
                            ${labels.cancel}
                        </button>
                    </div>
                `;
            } else if (job.status === 'completed' && job.results?.final_wim_path) {
                actionsHtml = `
                    <div class="job-actions">
                        <button class="btn btn-secondary" onclick="kassiaApp.showJobDetails('${job.id}')">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                                <path d="m8.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533L8.93 6.588zM9 4.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"/>
                            </svg>
                            ${labels.details}
                        </button>
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
                    <span class="status-badge ${statusClass}">${statusText[job.status] || job.status}</span>
                </div>
                
                <div class="job-meta">
                    <div class="job-meta-item">
                        <span class="job-meta-label">${labels.created}</span>
                        <span class="job-meta-value">${createdAt}</span>
                    </div>
                    <div class="job-meta-item">
                        <span class="job-meta-label">${labels.duration}</span>
                        <span class="job-meta-value">${duration}</span>
                    </div>
                    ${job.results?.final_wim_size_mb ? `
                    <div class="job-meta-item">
                        <span class="job-meta-label">${labels.finalSize}</span>
                        <span class="job-meta-value">${job.results.final_wim_size_mb.toFixed(1)} MB</span>
                    </div>
                    ` : ''}
                    ${job.error ? `
                    <div class="job-meta-item">
                        <span class="job-meta-label">${labels.error}</span>
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
        const notStartedText = {
            'de': 'Nicht gestartet',
            'en': 'Not started',
            'ru': 'Не запущено',
            'cs': 'Nezahájeno'
        }[this.currentLanguage] || 'Not started';
        
        if (!job.started_at) return notStartedText;
        
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
    
    showToast(message, type = 'info', duration = 5000) {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span>${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
                </svg>
            </button>
        `;
        
        toastContainer.appendChild(toast);
        
        // Auto remove after duration
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, duration);
    }
    
    async cancelJob(jobId) {
        const confirmText = {
            'de': 'Sind Sie sicher, dass Sie diesen Build-Auftrag abbrechen möchten?',
            'en': 'Are you sure you want to cancel this build job?',
            'ru': 'Вы уверены, что хотите отменить эту задачу сборки?',
            'cs': 'Jste si jisti, že chcete zrušit tento build úkol?'
        }[this.currentLanguage] || 'Are you sure you want to cancel this build job?';
        
        if (!confirm(confirmText)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/jobs/${jobId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const successText = {
                'de': 'Auftrag erfolgreich abgebrochen',
                'en': 'Job cancelled successfully',
                'ru': 'Задача успешно отменена',
                'cs': 'Úloha úspěšně zrušena'
            }[this.currentLanguage] || 'Job cancelled successfully';
            
            this.showToast(successText, 'success');
            await this.loadJobs();
            
        } catch (error) {
            console.error('❌ Failed to cancel job:', error);
            const errorText = {
                'de': 'Auftrag konnte nicht abgebrochen werden',
                'en': 'Failed to cancel job',
                'ru': 'Не удалось отменить задачу',
                'cs': 'Nepodařilo se zrušit úlohu'
            }[this.currentLanguage] || 'Failed to cancel job';
            
            this.showToast(errorText, 'error');
        }
    }
    
    showJobDetails(jobId) {
        const job = this.jobs.find(j => j.id === jobId);
        if (!job) return;
        
        // Get localized labels
        const labels = {
            'de': {
                'title': 'Build-Auftrag Details',
                'jobId': 'Auftrags-ID',
                'device': 'Gerät',
                'osId': 'OS-ID',
                'status': 'Status',
                'created': 'Erstellt',
                'started': 'Gestartet',
                'completed': 'Abgeschlossen',
                'duration': 'Dauer',
                'outputFile': 'Ausgabedatei',
                'fileSize': 'Dateigröße',
                'error': 'Fehler',
                'notStarted': 'Nicht gestartet',
                'notCompleted': 'Nicht abgeschlossen'
            },
            'en': {
                'title': 'Build Job Details',
                'jobId': 'Job/**
 * Kassia WebUI - Multi-Language JavaScript Application
 * Handles all frontend functionality including language switching
 */

class KassiaApp {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.currentActiveJob = null;
        this.devices = [];
        this.assets = {};
        this.jobs = [];
        this.currentLanguage = 'de'; // Default language
        this.supportedLanguages = ['de', 'en', 'ru', 'cs'];
        
        // Initialize app when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }
    
    async init() {
        console.log('🚀 Initializing Kassia WebUI...');
        
        // Detect current language from HTML lang attribute
        this.currentLanguage = document.documentElement.lang || 'de';
        
        // Setup WebSocket connection
        this.setupWebSocket();
        
        // Load initial data
        await this.loadDevices();
        await this.loadJobs();
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Setup periodic refresh
        this.setupPeriodicRefresh();
        
        console.log(`✅ Kassia WebUI initialized successfully (Language: ${this.currentLanguage})`);
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
            case 'ping':
                // Keep-alive ping, no action needed
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
        
        // Show completion notification (localized)
        if (jobData.status === 'completed') {
            const message = this.getLocalizedMessage('buildCompleted');
            this.showToast(message, 'success');
        } else if (jobData.status === 'failed') {
            const message = this.getLocalizedMessage('buildFailed', jobData.error || 'Unknown error');
            this.showToast(message, 'error');
        }
    }
    
    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connectionStatus');
        if (!statusEl) return;
        
        if (connected) {
            statusEl.className = 'connection-status status-online';
            const message = this.getLocalizedMessage('connected');
            statusEl.innerHTML = `<span>🟢 ${message}</span>`;
        } else {
            statusEl.className = 'connection-status status-offline';
            const message = this.getLocalizedMessage('disconnected');
            statusEl.innerHTML = `<span>🔴 ${message}</span>`;
        }
    }
    
    // Language switching functionality
    switchLanguage(langCode) {
        if (!this.supportedLanguages.includes(langCode)) {
            console.error(`❌ Unsupported language: ${langCode}`);
            return;
        }
        
        console.log(`🌐 Switching language to: ${langCode}`);
        
        // Save language preference
        localStorage.setItem('kassiaLanguage', langCode);
        
        // Load new language page
        const newUrl = langCode === 'en' ? '/index-en.html' : 
                      langCode === 'ru' ? '/index-ru.html' :
                      langCode === 'cs' ? '/index-cs.html' : 
                      '/index-de.html';
        
        window.location.href = newUrl;
    }
    
    // Get localized messages based on current language
    getLocalizedMessage(key, ...args) {
        const messages = {
            'de': {
                'connected': 'Verbunden',
                'disconnected': 'Getrennt',
                'buildCompleted': 'Build erfolgreich abgeschlossen!',
                'buildFailed': 'Build fehlgeschlagen: %s',
                'loadingDevices': 'Geräte werden geladen...',
                'noDevicesFound': 'Keine Gerätekonfigurationen gefunden',
                'loadingJobs': 'Aufträge werden geladen...',
                'noJobsFound': 'Noch keine Aufträge. Starten Sie einen neuen Build.',
                'selectDevice': 'Bitte Gerät und OS auswählen',
                'buildStarted': 'Build erfolgreich gestartet!',
                'buildStartFailed': 'Build konnte nicht gestartet werden: %s',
                'selectDeviceAndOS': 'Wählen Sie Gerät und OS, um verfügbare Assets anzuzeigen',
                'searchFunctionality': 'Such-Funktionalität kommt bald: "%s"'
            },
            'en': {
                'connected': 'Connected',
                'disconnected': 'Disconnected',
                'buildCompleted': 'Build completed successfully!',
                'buildFailed': 'Build failed: %s',
                'loadingDevices': 'Loading devices...',
                'noDevicesFound': 'No device configurations found',
                'loadingJobs': 'Loading jobs...',
                'noJobsFound': 'No jobs yet. Start a new build.',
                'selectDevice': 'Please select device and OS',
                'buildStarted': 'Build started successfully!',
                'buildStartFailed': 'Failed to start build: %s',
                'selectDeviceAndOS': 'Select device and OS to view available assets',
                'searchFunctionality': 'Search functionality coming soon: "%s"'
            },
            'ru': {
                'connected': 'Подключено',
                'disconnected': 'Отключено',
                'buildCompleted': 'Сборка успешно завершена!',
                'buildFailed': 'Сборка не удалась: %s',
                'loadingDevices': 'Загрузка устройств...',
                'noDevicesFound': 'Конфигурации устройств не найдены',
                'loadingJobs': 'Загрузка заданий...',
                'noJobsFound': 'Пока нет заданий. Запустите новую сборку.',
                'selectDevice': 'Пожалуйста, выберите устройство и ОС',
                'buildStarted': 'Сборка успешно запущена!',
                'buildStartFailed': 'Не удалось запустить сборку: %s',
                'selectDeviceAndOS': 'Выберите устройство и ОС для просмотра доступных ресурсов',
                'searchFunctionality': 'Функция поиска скоро появится: "%s"'
            },
            'cs': {
                'connected': 'Připojeno',
                'disconnected': 'Odpojeno',
                'buildCompleted': 'Build úspěšně dokončen!',
                'buildFailed': 'Build selhal: %s',
                'loadingDevices': 'Načítání zařízení...',
                'noDevicesFound': 'Nenalezeny žádné konfigurace zařízení',
                'loadingJobs': 'Načítání úloh...',
                'noJobsFound': 'Zatím žádné úlohy. Začněte nový build.',
                'selectDevice': 'Prosím vyberte zařízení a OS',
                'buildStarted': 'Build úspěšně spuštěn!',
                'buildStartFailed': 'Nepodařilo se spustit build: %s',
                'selectDeviceAndOS': 'Vyberte zařízení a OS pro zobrazení dostupných prostředků',
                'searchFunctionality': 'Funkce vyhledávání brzy: "%s"'
            }
        };
        
        const langMessages = messages[this.currentLanguage] || messages['en'];
        let message = langMessages[key] || key;
        
        // Replace placeholders with arguments
        args.forEach((arg, index) => {
            message = message.replace('%s', arg);
        });
        
        return message;
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
            const message = this.getLocalizedMessage('noDevicesFound');
            this.showToast(message, 'error');
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
            const message = this.getLocalizedMessage('loadingJobs');
            this.showToast(message, 'error');
        }
    }
    
    populateDeviceSelect() {
        const deviceSelect = document.getElementById('deviceSelect');
        const assetDeviceFilter = document.getElementById('assetDeviceFilter');
        
        if (!deviceSelect) return;
        
        // Get localized text
        const selectText = this.getLocalizedDeviceSelectText();
        const allDevicesText = this.getLocalizedAllDevicesText();
        
        // Clear existing options
        deviceSelect.innerHTML = `<option value="">${selectText}</option>`;
        if (assetDeviceFilter) {
            assetDeviceFilter.innerHTML = `<option value="">${allDevicesText}</option>`;
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
    
    getLocalizedDeviceSelectText() {
        const texts = {
            'de': 'Gerät auswählen...',
            'en': 'Select device...',
            'ru': 'Выберите устройство...',
            'cs': 'Vyberte zařízení...'
        };
        return texts[this.currentLanguage] || texts['en'];
    }
    
    getLocalizedAllDevicesText() {
        const texts = {
            'de': 'Alle Geräte',
            'en': 'All Devices',
            'ru': 'Все устройства',
            'cs': 'Všechna zařízení'
        };
        return texts[this.currentLanguage] || texts['en'];
    }
    
    populateAssetFilters() {
        const osFilter = document.getElementById('assetOSFilter');
        if (!osFilter) return;
        
        // Get localized text
        const allOSText = {
            'de': 'Alle OS',
            'en': 'All OS',
            'ru': 'Все ОС',
            'cs': 'Všechny OS'
        }[this.currentLanguage] || 'All OS';
        
        // Clear existing options
        osFilter.innerHTML = `<option value="">${allOSText}</option>`;
        
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
    
    handleDeviceChange(deviceId) {
        const osSelect = document.getElementById('osSelect');
        if (!osSelect) return;
        
        // Get localized text
        const selectOSText = {
            'de': 'OS auswählen...',
            'en': 'Select OS...',
            'ru': 'Выберите ОС...',
            'cs': 'Vyberte OS...'
        }[this.currentLanguage] || 'Select OS...';
        
        // Clear OS options
        osSelect.innerHTML = `<option value="">${selectOSText}</option>`;
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
            const message = this.getLocalizedMessage('loadingDevices');
            this.showToast(message, 'error');
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
        
        // Get localized texts
        const foundText = {
            'de': '✅ Gefunden',
            'en': '✅ Found',
            'ru': '✅ Найдено',
            'cs': '✅ Nalezeno'
        }[this.currentLanguage] || '✅ Found';
        
        const missingText = {
            'de': '❌ Fehlt',
            'en': '❌ Missing',
            'ru': '❌ Отсутствует',
            'cs': '❌ Chybí'
        }[this.currentLanguage] || '❌ Missing';
        
        const packagesText = {
            'de': 'Pakete',
            'en': 'packages',
            'ru': 'пакетов',
            'cs': 'balíčků'
        }[this.currentLanguage] || 'packages';
        
        const notConfiguredText = {
            'de': 'Nicht konfiguriert',
            'en': 'Not configured',
            'ru': 'Не настроено',
            'cs': 'Nenakonfigurováno'
        }[this.currentLanguage] || 'Not configured';
        
        if (previewDevice) previewDevice.textContent = deviceId;
        if (previewOS) previewOS.textContent = `OS ${osId}`;
        if (previewWimPath) previewWimPath.textContent = assets.wim_path || notConfiguredText;
        if (previewSBI) previewSBI.textContent = assets.sbi ? foundText : missingText;
        if (previewDrivers) previewDrivers.textContent = `${assets.drivers.length} ${packagesText}`;
        if (previewUpdates) previewUpdates.textContent = `${assets.updates.length} ${packagesText}`;
        
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
            const message = this.getLocalizedMessage('selectDevice');
            this.showToast(message, 'error');
            return;
        }
        
        // Get localized button text
        const startingText = {
            'de': 'Build wir