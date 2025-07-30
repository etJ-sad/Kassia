// web/static/js/ui.js
// Kassia WebUI - UI Manager

class UIManager {
    constructor() {
        this.currentTab = 'dashboard';
        this.toastQueue = [];
        this.isShowingToast = false;
        
        console.log('🎨 UI Manager initialized');
    }
    
    // Tab Management
    switchTab(tabName) {
        console.log(`🔄 Switching to tab: ${tabName}`);
        
        // Update navigation
        this.updateNavigation(tabName);
        
        // Update tab buttons
        this.updateTabButtons(tabName);
        
        // Show/hide tab content
        this.updateTabContent(tabName);
        
        // Update current tab
        this.currentTab = tabName;
        
        // Trigger tab-specific actions
        this.onTabSwitch(tabName);
    }
    
    updateNavigation(tabName) {
        const navItems = document.querySelectorAll('.nav-item');
        
        navItems.forEach(item => {
            item.classList.remove('active');
            
            // Check if this nav item corresponds to the tab
            const itemText = item.textContent.toLowerCase();
            if ((tabName === 'dashboard' && itemText.includes('dashboard')) ||
                (tabName === 'build' && itemText.includes('build')) ||
                (tabName === 'assets' && itemText.includes('assets')) ||
                (tabName === 'jobs' && itemText.includes('jobs'))) {
                item.classList.add('active');
            }
        });
    }
    
    updateTabButtons(tabName) {
        const tabButtons = document.querySelectorAll('.tab-btn');
        
        tabButtons.forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-tab') === tabName) {
                btn.classList.add('active');
            }
        });
    }
    
    updateTabContent(tabName) {
        // Hide all tab content
        const tabContents = document.querySelectorAll('.tab-content');
        tabContents.forEach(content => {
            content.classList.remove('active');
        });
        
        // Show target tab
        const targetTab = document.getElementById(tabName);
        if (targetTab) {
            targetTab.classList.add('active');
        }
    }
    
    onTabSwitch(tabName) {
        // Tab-specific actions
        switch (tabName) {
            case 'dashboard':
                this.refreshDashboard();
                break;
            case 'build':
                this.refreshBuildForm();
                break;
            case 'assets':
                this.refreshAssets();
                break;
            case 'jobs':
                this.refreshJobs();
                break;
        }
    }
    
    // Toast Notifications
    showToast(message, type = 'info', duration = 5000) {
        const toast = {
            message,
            type,
            duration,
            id: Date.now() + Math.random()
        };
        
        this.toastQueue.push(toast);
        
        if (!this.isShowingToast) {
            this.processToastQueue();
        }
    }
    
    async processToastQueue() {
        if (this.toastQueue.length === 0) {
            this.isShowingToast = false;
            return;
        }
        
        this.isShowingToast = true;
        const toast = this.toastQueue.shift();
        
        await this.displayToast(toast);
        
        // Process next toast
        setTimeout(() => {
            this.processToastQueue();
        }, 300); // Small delay between toasts
    }
    
    async displayToast(toast) {
        const toastContainer = this.getOrCreateToastContainer();
        
        const toastElement = document.createElement('div');
        toastElement.className = `toast ${toast.type}`;
        toastElement.setAttribute('data-toast-id', toast.id);
        
        // Toast content
        toastElement.innerHTML = `
            <div class="toast-content">
                <span class="toast-message">${toast.message}</span>
                <button class="toast-close" onclick="uiManager.closeToast('${toast.id}')">×</button>
            </div>
        `;
        
        // Add to container
        toastContainer.appendChild(toastElement);
        
        // Auto-remove after duration
        setTimeout(() => {
            this.closeToast(toast.id);
        }, toast.duration);
        
        return new Promise(resolve => {
            setTimeout(resolve, toast.duration);
        });
    }
    
    closeToast(toastId) {
        const toastElement = document.querySelector(`[data-toast-id="${toastId}"]`);
        if (toastElement) {
            toastElement.style.animation = 'slideOut 0.3s ease-in forwards';
            setTimeout(() => {
                if (toastElement.parentElement) {
                    toastElement.remove();
                }
            }, 300);
        }
    }
    
    getOrCreateToastContainer() {
        let container = document.getElementById('toastContainer');
        
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        return container;
    }
    
    // Loading States
    showLoading(element, text = null) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        
        if (!element) return;
        
        const loadingText = text || window.t('loading', 'Loading...');
        const originalContent = element.innerHTML;
        
        element.setAttribute('data-original-content', originalContent);
        element.disabled = true;
        
        element.innerHTML = `
            <div class="loading-spinner"></div>
            <span>${loadingText}</span>
        `;
    }
    
    hideLoading(element) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        
        if (!element) return;
        
        const originalContent = element.getAttribute('data-original-content');
        if (originalContent) {
            element.innerHTML = originalContent;
            element.removeAttribute('data-original-content');
        }
        
        element.disabled = false;
    }
    
    // Form Helpers
    getFormData(formElement) {
        if (typeof formElement === 'string') {
            formElement = document.getElementById(formElement);
        }
        
        if (!formElement) return {};
        
        const formData = new FormData(formElement);
        const data = {};
        
        for (let [key, value] of formData.entries()) {
            // Handle checkboxes
            if (formElement.querySelector(`[name="${key}"]`).type === 'checkbox') {
                data[key] = formElement.querySelector(`[name="${key}"]`).checked;
            } else {
                data[key] = value;
            }
        }
        
        return data;
    }
    
    setFormData(formElement, data) {
        if (typeof formElement === 'string') {
            formElement = document.getElementById(formElement);
        }
        
        if (!formElement) return;
        
        Object.entries(data).forEach(([key, value]) => {
            const field = formElement.querySelector(`[name="${key}"]`);
            if (field) {
                if (field.type === 'checkbox') {
                    field.checked = Boolean(value);
                } else {
                    field.value = value;
                }
            }
        });
    }
    
    resetForm(formElement) {
        if (typeof formElement === 'string') {
            formElement = document.getElementById(formElement);
        }
        
        if (formElement) {
            formElement.reset();
        }
    }
    
    // Validation
    validateForm(formElement, rules = {}) {
        if (typeof formElement === 'string') {
            formElement = document.getElementById(formElement);
        }
        
        if (!formElement) return { valid: false, errors: ['Form not found'] };
        
        const errors = [];
        const data = this.getFormData(formElement);
        
        Object.entries(rules).forEach(([field, rule]) => {
            const value = data[field];
            
            if (rule.required && (!value || value.trim() === '')) {
                errors.push(window.t(`validation_${field}_required`, `${field} is required`));
            }
            
            if (rule.minLength && value && value.length < rule.minLength) {
                errors.push(window.t(`validation_${field}_min_length`, `${field} must be at least ${rule.minLength} characters`));
            }
            
            if (rule.pattern && value && !rule.pattern.test(value)) {
                errors.push(window.t(`validation_${field}_pattern`, `${field} format is invalid`));
            }
            
            if (rule.custom && typeof rule.custom === 'function') {
                const customError = rule.custom(value, data);
                if (customError) {
                    errors.push(customError);
                }
            }
        });
        
        return {
            valid: errors.length === 0,
            errors,
            data
        };
    }
    
    // Utility Functions
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    formatDuration(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }
    
    formatDate(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleString();
        } catch (error) {
            return dateString;
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Animation helpers
    fadeIn(element, duration = 300) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        
        if (!element) return;
        
        element.style.opacity = '0';
        element.style.display = 'block';
        
        const start = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - start;
            const progress = Math.min(elapsed / duration, 1);
            
            element.style.opacity = progress;
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }
    
    fadeOut(element, duration = 300) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        
        if (!element) return;
        
        const start = performance.now();
        const startOpacity = parseFloat(window.getComputedStyle(element).opacity);
        
        const animate = (currentTime) => {
            const elapsed = currentTime - start;
            const progress = Math.min(elapsed / duration, 1);
            
            element.style.opacity = startOpacity * (1 - progress);
            
            if (progress >= 1) {
                element.style.display = 'none';
            } else {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }
    
    // Tab-specific refresh methods (to be called by KassiaApp)
    refreshDashboard() {
        console.log('🔄 Refreshing dashboard');
        // Will be implemented by KassiaApp
    }
    
    refreshBuildForm() {
        console.log('🔄 Refreshing build form');
        // Will be implemented by KassiaApp
    }
    
    refreshAssets() {
        console.log('🔄 Refreshing assets');
        // Will be implemented by KassiaApp
    }
    
    refreshJobs() {
        console.log('🔄 Refreshing jobs');
        // Will be implemented by KassiaApp
    }
}

// Global UI manager instance
window.uiManager = new UIManager();

// Global functions for HTML onclick handlers
window.switchTab = function(tabName) {
    window.uiManager.switchTab(tabName);
};

window.refreshAssets = function() {
    if (window.kassiaApp && window.kassiaApp.handleAssetFilterChange) {
        window.kassiaApp.handleAssetFilterChange();
    }
};

window.refreshJobs = function() {
    if (window.kassiaApp && window.kassiaApp.loadJobs) {
        window.kassiaApp.loadJobs();
    }
};

// Add slideOut animation for toasts
const style = document.createElement('style');
style.textContent = `
@keyframes slideOut {
    from {
        transform: translateX(0);
        opacity: 1;
    }
    to {
        transform: translateX(100%);
        opacity: 0;
    }
}

.toast-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
}

.toast-close {
    background: none;
    border: none;
    color: inherit;
    font-size: 18px;
    font-weight: bold;
    margin-left: 10px;
    cursor: pointer;
    padding: 0;
    line-height: 1;
}

.toast-close:hover {
    opacity: 0.7;
}
`;
document.head.appendChild(style);

console.log('📦 UI manager loaded');