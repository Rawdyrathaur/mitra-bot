// API Module - Handles all backend communication
class API {
    constructor() {
        this.baseURL = CONFIG.API_BASE_URL;
        this.token = this.getToken();
    }

    getToken() {
        return localStorage.getItem('auth_token');
    }

    setToken(token) {
        localStorage.setItem('auth_token', token);
        this.token = token;
    }

    removeToken() {
        localStorage.removeItem('auth_token');
        this.token = null;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (this.token && !options.skipAuth) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const config = {
            ...options,
            headers,
            timeout: CONFIG.API_TIMEOUT
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `HTTP error! status: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // Health Check
    async checkHealth() {
        return this.request(CONFIG.ENDPOINTS.HEALTH, { skipAuth: true });
    }

    // Authentication
    async login(email, password) {
        const data = await this.request(CONFIG.ENDPOINTS.AUTH_LOGIN, {
            method: 'POST',
            body: JSON.stringify({ email, password }),
            skipAuth: true
        });
        if (data.access_token) {
            this.setToken(data.access_token);
        }
        return data;
    }

    async register(email, username, password) {
        const data = await this.request(CONFIG.ENDPOINTS.AUTH_REGISTER, {
            method: 'POST',
            body: JSON.stringify({ email, username, password }),
            skipAuth: true
        });
        if (data.access_token) {
            this.setToken(data.access_token);
        }
        return data;
    }

    // Chat
    async sendMessage(message, sessionId = null) {
        return this.request(CONFIG.ENDPOINTS.CHAT, {
            method: 'POST',
            body: JSON.stringify({
                message,
                session_id: sessionId || this.generateSessionId()
            })
        });
    }

    // Documents
    async uploadDocument(file, title = null, category = null) {
        const formData = new FormData();
        formData.append('file', file);
        if (title) formData.append('title', title);
        if (category) formData.append('category', category);

        return this.request(CONFIG.ENDPOINTS.DOCUMENTS_UPLOAD, {
            method: 'POST',
            body: formData,
            headers: {} // Let browser set Content-Type for FormData
        });
    }

    async uploadTextContent(title, content, category = null) {
        return this.request(CONFIG.ENDPOINTS.DOCUMENTS_TEXT, {
            method: 'POST',
            body: JSON.stringify({ title, content, category })
        });
    }

    async listDocuments(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`${CONFIG.ENDPOINTS.DOCUMENTS_LIST}?${query}`);
    }

    // Search
    async search(query, type = 'semantic', limit = 10) {
        const params = new URLSearchParams({ q: query, type, limit }).toString();
        return this.request(`${CONFIG.ENDPOINTS.SEARCH}?${params}`);
    }

    // Conversations
    async getConversations() {
        const stored = localStorage.getItem(CONFIG.CONVERSATIONS_STORAGE_KEY);
        return stored ? JSON.parse(stored) : [];
    }

    async saveConversation(conversation) {
        const conversations = await this.getConversations();
        const index = conversations.findIndex(c => c.id === conversation.id);

        if (index !== -1) {
            conversations[index] = conversation;
        } else {
            conversations.unshift(conversation);
        }

        localStorage.setItem(CONFIG.CONVERSATIONS_STORAGE_KEY, JSON.stringify(conversations));
        return conversation;
    }

    async deleteConversation(id) {
        const conversations = await this.getConversations();
        const filtered = conversations.filter(c => c.id !== id);
        localStorage.setItem(CONFIG.CONVERSATIONS_STORAGE_KEY, JSON.stringify(filtered));
    }

    // Utilities
    generateSessionId() {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    generateConversationId() {
        return `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
}

// Create global API instance
window.api = new API();
