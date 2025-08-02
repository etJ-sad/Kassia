// web/static/js/translations.js - Translation Manager

class TranslationManager {
    constructor() {
        this.currentLanguage = 'en';
        this.translations = {};
        this.fallbackLanguage = 'en';
        this.loadedLanguages = new Set();
        
        console.log('🌍 Translation Manager initialized');
    }
    
    async initialize() {
        // Detect browser language
        const browserLang = this.detectBrowserLanguage();
        
        // Load saved language or use browser language
        const savedLang = localStorage.getItem('kassia_language') || browserLang;
        
        await this.setLanguage(savedLang);
    }
    
    detectBrowserLanguage() {
        const lang = navigator.language || navigator.userLanguage || 'en';
        const shortLang = lang.split('-')[0].toLowerCase();
        
        // Map known languages
        const supportedLanguages = ['en', 'de', 'ru', 'cs', 'cn'];
        return supportedLanguages.includes(shortLang) ? shortLang : 'en';
    }
    
    async setLanguage(languageCode) {
        try {
            console.log(`🌍 Setting language to: ${languageCode}`);
            
            // Load translations if not already loaded
            if (!this.loadedLanguages.has(languageCode)) {
                await this.loadTranslations(languageCode);
            }
            
            this.currentLanguage = languageCode;
            localStorage.setItem('kassia_language', languageCode);
            
            // Apply translations to the page
            this.applyTranslations();
            
            // Update language selector
            this.updateLanguageSelector();
            
            console.log(`✅ Language set to: ${languageCode}`);
            
        } catch (error) {
            console.error(`❌ Failed to set language to ${languageCode}:`, error);
            
            // Fallback to English if current language fails
            if (languageCode !== this.fallbackLanguage) {
                console.log(`🔄 Falling back to ${this.fallbackLanguage}`);
                await this.setLanguage(this.fallbackLanguage);
            }
        }
    }
    
    async loadTranslations(languageCode) {
        try {
            console.log(`📥 Loading translations for: ${languageCode}`);
            
            const response = await fetch(`/static/translations/${languageCode}.json`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const translations = await response.json();
            
            if (!translations || typeof translations !== 'object') {
                throw new Error('Invalid translation format');
            }
            
            this.translations[languageCode] = translations;
            this.loadedLanguages.add(languageCode);
            
            console.log(`✅ Loaded ${Object.keys(translations).length} translations for ${languageCode}`);
            
        } catch (error) {
            console.error(`❌ Failed to load translations for ${languageCode}:`, error);
            
            // If it's not the fallback language, try to load fallback
            if (languageCode !== this.fallbackLanguage && !this.loadedLanguages.has(this.fallbackLanguage)) {
                console.log(`🔄 Loading fallback language: ${this.fallbackLanguage}`);
                await this.loadTranslations(this.fallbackLanguage);
            }
            
            throw error;
        }
    }
    
    translate(key, fallback = null) {
        // Try current language first
        if (this.translations[this.currentLanguage] && this.translations[this.currentLanguage][key]) {
            return this.translations[this.currentLanguage][key];
        }
        
        // Try fallback language
        if (this.currentLanguage !== this.fallbackLanguage && 
            this.translations[this.fallbackLanguage] && 
            this.translations[this.fallbackLanguage][key]) {
            return this.translations[this.fallbackLanguage][key];
        }
        
        // Return fallback or key
        return fallback || key;
    }
    
    applyTranslations() {
        console.log('🔄 Applying translations to page...');
        
        // Translate elements with data-translate attribute
        const elements = document.querySelectorAll('[data-translate]');
        elements.forEach(element => {
            const key = element.getAttribute('data-translate');
            const translation = this.translate(key);
            
            if (translation && translation !== key) {
                element.textContent = translation;
            }
        });
        
        // Translate placeholder attributes
        const placeholderElements = document.querySelectorAll('[data-translate-placeholder]');
        placeholderElements.forEach(element => {
            const key = element.getAttribute('data-translate-placeholder');
            const translation = this.translate(key);
            
            if (translation && translation !== key) {
                element.setAttribute('placeholder', translation);
            }
        });
        
        // Translate title attributes
        const titleElements = document.querySelectorAll('[data-translate-title]');
        titleElements.forEach(element => {
            const key = element.getAttribute('data-translate-title');
            const translation = this.translate(key);
            
            if (translation && translation !== key) {
                element.setAttribute('title', translation);
            }
        });
        
        console.log(`✅ Applied translations for ${elements.length + placeholderElements.length + titleElements.length} elements`);
    }
    
    updateLanguageSelector() {
        // Update active language button
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const activeBtn = document.querySelector(`.lang-btn[onclick*="'${this.currentLanguage}'"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
    }
    
    // Helper method to get current language info
    getCurrentLanguageInfo() {
        const languageNames = {
            'en': 'English',
            'de': 'Deutsch',
            'ru': 'Русский',
            'cs': 'Čeština',
            'cn': '中文'
        };
        
        return {
            code: this.currentLanguage,
            name: languageNames[this.currentLanguage] || this.currentLanguage.toUpperCase(),
            isLoaded: this.loadedLanguages.has(this.currentLanguage),
            translationCount: this.translations[this.currentLanguage] ? Object.keys(this.translations[this.currentLanguage]).length : 0
        };
    }
    
    // Method to get all available languages
    async getAvailableLanguages() {
        try {
            const response = await fetch('/api/languages');
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Failed to get available languages:', error);
            return {
                languages: ['en', 'de', 'ru', 'cs', 'cn'],
                default: 'en'
            };
        }
    }
    
    // Method to preload multiple languages
    async preloadLanguages(languageCodes) {
        const promises = languageCodes.map(lang => {
            if (!this.loadedLanguages.has(lang)) {
                return this.loadTranslations(lang).catch(error => {
                    console.warn(`Failed to preload language ${lang}:`, error);
                });
            }
            return Promise.resolve();
        });
        
        await Promise.all(promises);
        console.log(`✅ Preloaded languages: ${languageCodes.join(', ')}`);
    }
    
    // Method to add translation dynamically
    addTranslation(languageCode, key, value) {
        if (!this.translations[languageCode]) {
            this.translations[languageCode] = {};
        }
        
        this.translations[languageCode][key] = value;
        console.log(`➕ Added translation: ${languageCode}.${key} = ${value}`);
    }
    
    // Method to get translation statistics
    getStatistics() {
        const stats = {
            currentLanguage: this.currentLanguage,
            loadedLanguages: Array.from(this.loadedLanguages),
            translationCounts: {}
        };
        
        for (const [lang, translations] of Object.entries(this.translations)) {
            stats.translationCounts[lang] = Object.keys(translations).length;
        }
        
        return stats;
    }
}

// Create global translation manager
window.translationManager = new TranslationManager();

// Global translate function for convenience
window.t = function(key, fallback = null) {
    return window.translationManager.translate(key, fallback);
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async function() {
    try {
        await window.translationManager.initialize();
        console.log('✅ Translation system initialized');
    } catch (error) {
        console.error('❌ Failed to initialize translation system:', error);
    }
});

console.log('✅ Translation Manager loaded');