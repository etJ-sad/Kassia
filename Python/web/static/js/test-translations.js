// web/static/js/translations.js
// Kassia WebUI - Translation System (FIXED)

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
            // FIXED: Try multiple possible paths for translation files
            const possiblePaths = [
                `/static/translations/${language}.json`,  // Current path
                `/web/translations/${language}.json`,     // Alternative path
                `/translations/${language}.json`          // Root path
            ];
            
            let translations = null;
            let loadedFrom = null;
            
            for (const path of possiblePaths) {
                try {
                    console.log(`🔍 Trying to load translations from: ${path}`);
                    const response = await fetch(path);
                    
                    if (response.ok) {
                        translations = await response.json();
                        loadedFrom = path;
                        break;
                    }
                } catch (error) {
                    console.log(`❌ Failed to load from ${path}:`, error.message);
                    continue;
                }
            }
            
            if (!translations) {
                throw new Error(`No translation file found for ${language} in any of the expected locations`);
            }
            
            this.translations[language] = translations;
            
            console.log(`✅ Loaded translations for ${language} from ${loadedFrom}:`, Object.keys(translations).length, 'keys');
            return translations;
            
        } catch (error) {
            console.error(`❌ Failed to load translations for ${language}:`, error);
            
            // Try to load fallback if not already loaded
            if (language !== this.fallbackLanguage && !this.translations[this.fallbackLanguage]) {
                console.log(`🔄 Loading fallback translations: ${this.fallbackLanguage}`);
                return await this.loadTranslations(this.fallbackLanguage);
            }
            
            // If all else fails, return empty object but don't crash
            console.warn(`⚠️ Using empty translations for ${language}`);
            return {};
        }
    }
    
    async setLanguage(language) {
        if (language === this.currentLanguage) {
            return; // Already set
        }
        
        console.log(`🌍 Switching language from ${this.currentLanguage} to ${language}`);
        
        try {
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
            
            // Show success notification
            if (window.uiManager && window.uiManager.showToast) {
                const languageNames = {
                    'en': 'English',
                    'de': 'Deutsch', 
                    'ru': 'Русский',
                    'cs': 'Čeština'
                };
                
                const langName = languageNames[language] || language.toUpperCase();
                window.uiManager.showToast(`Language switched to ${langName}`, 'success');
            }
            
        } catch (error) {
            console.error(`❌ Failed to switch language to ${language}:`, error);
            
            if (window.uiManager && window.uiManager.showToast) {
                window.uiManager.showToast(`Failed to switch language to ${language}`, 'error');
            }
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
        
        // Return provided fallback or key itself
        return fallback || key;
    }
    
    translatePage() {
        console.log(`🔄 Translating page elements to ${this.currentLanguage}`);
        
        // Translate elements with data-translate attribute
        const translatableElements = document.querySelectorAll('[data-translate]');
        let translatedCount = 0;
        
        translatableElements.forEach(element => {
            const key = element.getAttribute('data-translate');
            const translation = this.translate(key);
            
            if (translation !== key) {
                element.textContent = translation;
                translatedCount++;
            } else {
                console.warn(`⚠️ No translation found for key: ${key}`);
            }
        });
        
        // Translate placeholder attributes
        const placeholderElements = document.querySelectorAll('[data-translate-placeholder]');
        
        placeholderElements.forEach(element => {
            const key = element.getAttribute('data-translate-placeholder');
            const translation = this.translate(key);
            
            if (translation !== key) {
                element.placeholder = translation;
                translatedCount++;
            }
        });
        
        // Translate title attributes
        const titleElements = document.querySelectorAll('[data-translate-title]');
        
        titleElements.forEach(element => {
            const key = element.getAttribute('data-translate-title');
            const translation = this.translate(key);
            
            if (translation !== key) {
                element.title = translation;
                translatedCount++;
            }
        });
        
        console.log(`🔄 Translated ${translatedCount} elements out of ${translatableElements.length + placeholderElements.length + titleElements.length} total`);
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
        
        console.log(`🔄 Updated language buttons, active: ${this.currentLanguage}`);
    }
    
    async initialize() {
        try {
            console.log(`🚀 Initializing translation system with language: ${this.currentLanguage}`);
            
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
            
            // Fall back to English if initialization fails
            if (this.currentLanguage !== 'en') {
                console.log('🔄 Falling back to English due to initialization failure');
                this.currentLanguage = 'en';
                await this.initialize();
            }
        }
    }
    
    // Method to add translations dynamically
    addTranslations(language, translations) {
        if (!this.translations[language]) {
            this.translations[language] = {};
        }
        
        Object.assign(this.translations[language], translations);
        console.log(`➕ Added ${Object.keys(translations).length} translations for ${language}`);
        
        // Re-translate page if this is the current language
        if (language === this.currentLanguage) {
            this.translatePage();
        }
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
    
    // Debug method to check what translations are loaded
    debugTranslations() {
        console.log('🐛 Translation Debug Info:', {
            currentLanguage: this.currentLanguage,
            availableLanguages: this.getAvailableLanguages(),
            currentTranslations: this.translations[this.currentLanguage] || {},
            fallbackTranslations: this.translations[this.fallbackLanguage] || {}
        });
    }
}

// Global translation manager instance
window.translationManager = new TranslationManager();

// Global function for easy translation access
window.t = function(key, fallback = null) {
    return window.translationManager.translate(key, fallback);
};

// FIXED: Enhanced global function for language switching
window.switchLanguage = async function(language) {
    console.log(`🌍 Language switch requested: ${language}`);
    
    try {
        await window.translationManager.setLanguage(language);
        console.log(`✅ Language switch completed: ${language}`);
    } catch (error) {
        console.error(`❌ Language switch failed:`, error);
        
        if (window.uiManager && window.uiManager.showToast) {
            window.uiManager.showToast(`Failed to switch to ${language}`, 'error');
        }
    }
};

// Debug function to check translation status
window.debugTranslations = function() {
    if (window.translationManager) {
        window.translationManager.debugTranslations();
    }
};

// Initialize when DOM is ready with better error handling
function initializeTranslations() {
    if (window.translationManager) {
        window.translationManager.initialize().catch(error => {
            console.error('❌ Translation initialization failed:', error);
        });
    } else {
        console.error('❌ Translation manager not found');
    }
}

// Multiple initialization approaches to ensure it works
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTranslations);
} else {
    // DOM is already ready
    initializeTranslations();
}

// Fallback initialization after a delay
setTimeout(() => {
    if (window.translationManager && !window.translationManager.translations[window.translationManager.currentLanguage]) {
        console.log('🔄 Fallback translation initialization...');
        initializeTranslations();
    }
}, 2000);

console.log('📦 Translation system loaded (FIXED VERSION)');