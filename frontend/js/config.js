// Configuration
const CONFIG = {
    // API Base URL - auto-detect based on environment
    API_BASE_URL: window.location.hostname === 'localhost'
        ? 'http://localhost:5000'
        : window.location.origin,

    // API Endpoints
    ENDPOINTS: {
        CHAT: '/api/chat',
        HEALTH: '/api/health',
        AUTH_LOGIN: '/api/auth/login',
        AUTH_REGISTER: '/api/auth/register',
        DOCUMENTS_UPLOAD: '/api/documents/upload',
        DOCUMENTS_TEXT: '/api/documents/text',
        DOCUMENTS_LIST: '/api/documents',
        SEARCH: '/api/search',
        CONVERSATIONS: '/api/conversations',
    },

    // App Settings
    MAX_MESSAGE_LENGTH: 3000,
    AUTO_SAVE_INTERVAL: 5000,
    TYPING_INDICATOR_DELAY: 300,

    // Chat Settings
    DEFAULT_MODEL: 'gpt-3.5-turbo',
    DEFAULT_TEMPERATURE: 0.7,
    DEFAULT_MAX_TOKENS: 500,

    // UI Settings
    THEME_STORAGE_KEY: 'mitra-bot-theme',
    CONVERSATIONS_STORAGE_KEY: 'mitra-bot-conversations',
    SESSION_STORAGE_KEY: 'mitra-bot-session',

    // Timeouts
    API_TIMEOUT: 30000,
    TOAST_DURATION: 4000,

    // File Upload
    MAX_FILE_SIZE: 16 * 1024 * 1024, // 16MB
    ALLOWED_FILE_TYPES: [
        '.txt', '.md', '.csv', '.html', '.xml', '.json',
        '.js', '.py', '.css', '.docx', '.doc', '.pdf'
    ],
};

// Export for use in other modules
window.CONFIG = CONFIG;
