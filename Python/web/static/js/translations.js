// web/static/js/translations.js
// Kassia WebUI - Translation System

class TranslationManager {
    constructor() {
        this.currentLanguage = 'en';
        this.translations = {};
        this.fallbackLanguage = 'en';
        
        // Load saved language preference
        const savedLang = localStorage.getItem('kassiaLanguage');
        if (savedLang) {
            this.currentLanguage = savedLang;
        } else {
            // Auto-detect from browser
            this.currentLanguage = this.detectBrowserLanguage();
        }
        
        console.log(`📢 Translation system initialized with language: ${this.currentLanguage}`);
    }
    
    detectBrowserLanguage() {
        const browserLang = navigator.language || navigator.userLanguage;
        const langCode = browserLang.split('-')[0].toLowerCase();
        
        // Check if we support this language
        const supportedLangs = ['en', 'de', 'ru', 'cs'];
        return supportedLangs.includes(langCode) ? langCode : 'en';
    }
    
    async loadTranslations(language) {
        try {
            // Load translation file
            const response = await fetch(`/static/translations/${language}.json`);
            if (!response.ok) {
                throw new Error(`Failed to load translations for ${language}`);
            }
            
            const translations = await response.json();
            this.translations[language] = translations;
            
            console.log(`✅ Loaded translations for ${language}:`, Object.keys(translations).length, 'keys');
            return translations;
            
        } catch (error) {
            console.error(`❌ Failed to load translations for ${language}:`, error);
            
            // Try to load fallback if not already loaded
            if (language !== this.fallbackLanguage && !this.translations[this.fallbackLanguage]) {
                console.log(`🔄 Loading fallback translations: ${this.fallbackLanguage}`);
                return await this.loadTranslations(this.fallbackLanguage);
            }
            
            return {};
        }
    }
    
    async setLanguage(language) {
        if (language === this.currentLanguage) {
            return; // Already set
        }
        
        console.log(`🌍 Switching language from ${this.currentLanguage} to ${language}`);
        
        // Load translations if not already loaded
        if (!this.translations[language]) {
            await this.loadTranslations(language);
        }
        
        // Update current language
        this.currentLanguage = language;
        
        // Save preference
        localStorage.setItem('kassiaLanguage', language);
        
        // Update UI
        this.updateLanguageButtons();
        this.translatePage();
        
        // Update document language
        document.documentElement.lang = language;
        
        console.log(`✅ Language switched to ${language}`);
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
        
        // Return provided fallback or key itself
        return fallback || key;
    }
    
    translatePage() {
        // Translate elements with data-translate attribute
        const translatableElements = document.querySelectorAll('[data-translate]');
        
        translatableElements.forEach(element => {
            const key = element.getAttribute('data-translate');
            const translation = this.translate(key);
            
            if (translation !== key) {
                element.textContent = translation;
            }
        });
        
        // Translate placeholder attributes
        const placeholderElements = document.querySelectorAll('[data-translate-placeholder]');
        
        placeholderElements.forEach(element => {
            const key = element.getAttribute('data-translate-placeholder');
            const translation = this.translate(key);
            
            if (translation !== key) {
                element.placeholder = translation;
            }
        });
        
        // Translate title attributes
        const titleElements = document.querySelectorAll('[data-translate-title]');
        
        titleElements.forEach(element => {
            const key = element.getAttribute('data-translate-title');
            const translation = this.translate(key);
            
            if (translation !== key) {
                element.title = translation;
            }
        });
        
        console.log(`🔄 Translated ${translatableElements.length + placeholderElements.length + titleElements.length} elements`);
    }
    
    updateLanguageButtons() {
        const langButtons = document.querySelectorAll('.lang-btn');
        
        langButtons.forEach(button => {
            const buttonLang = button.textContent.toLowerCase();
            
            if (buttonLang === this.currentLanguage) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }
    
    async initialize() {
        try {
            // Load initial translations
            await this.loadTranslations(this.currentLanguage);
            
            // Load fallback if different
            if (this.currentLanguage !== this.fallbackLanguage) {
                await this.loadTranslations(this.fallbackLanguage);
            }
            
            // Apply translations to page
            this.translatePage();
            this.updateLanguageButtons();
            
            // Set document language
            document.documentElement.lang = this.currentLanguage;
            
            console.log('✅ Translation system initialized successfully');
            
        } catch (error) {
            console.error('❌ Failed to initialize translation system:', error);
        }
    }
    
    // Method to add translations dynamically
    addTranslations(language, translations) {
        if (!this.translations[language]) {
            this.translations[language] = {};
        }
        
        Object.assign(this.translations[language], translations);
        console.log(`➕ Added ${Object.keys(translations).length} translations for ${language}`);
    }
    
    // Method to get all available languages
    getAvailableLanguages() {
        return Object.keys(this.translations);
    }
    
    // Method to get current language info
    getCurrentLanguageInfo() {
        return {
            current: this.currentLanguage,
            fallback: this.fallbackLanguage,
            available: this.getAvailableLanguages(),
            loadedKeys: this.translations[this.currentLanguage] ? 
                       Object.keys(this.translations[this.currentLanguage]).length : 0
        };
    }
}

// Global translation manager instance
window.translationManager = new TranslationManager();

// Global function for easy translation access
window.t = function(key, fallback = null) {
    return window.translationManager.translate(key, fallback);
};

// Global function for language switching (used by HTML onclick)
window.switchLanguage = async function(language) {
    await window.translationManager.setLanguage(language);
    
    // Show toast notification
    if (window.kassiaApp && window.kassiaApp.showToast) {
        const languageNames = {
            'en': 'English',
            'de': 'Deutsch',
            'ru': 'Русский',
            'cs': 'Čeština'
        };
        
        const langName = languageNames[language] || language.toUpperCase();
        window.kassiaApp.showToast(`Language switched to ${langName}`, 'info');
    }
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.translationManager.initialize();
    });
} else {
    window.translationManager.initialize();
}

console.log('📦 Translation system loaded');