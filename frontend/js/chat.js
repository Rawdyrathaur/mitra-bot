// Chat Module - Handles all chat functionality
class Chat {
    constructor() {
        this.currentConversation = null;
        this.sessionId = null;
        this.messages = [];
        this.isTyping = false;
        this.init();
    }

    init() {
        this.setupInputHandlers();
        this.loadConversationsList();
    }

    setupInputHandlers() {
        const input = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');

        // Auto-resize textarea
        input?.addEventListener('input', (e) => {
            this.handleInput(e);
            this.autoResizeInput(e.target);
        });

        // Send on Enter (Shift+Enter for new line)
        input?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Send button
        sendBtn?.addEventListener('click', () => {
            this.sendMessage();
        });

        // Attach file
        document.getElementById('attachBtn')?.addEventListener('click', () => {
            this.attachFile();
        });

        // Voice input
        document.getElementById('voiceBtn')?.addEventListener('click', () => {
            this.startVoiceInput();
        });

        // Suggestions
        document.getElementById('suggestBtn')?.addEventListener('click', () => {
            this.showSuggestions();
        });

        // Prompt templates
        document.querySelectorAll('.prompt-card').forEach(card => {
            card.addEventListener('click', () => {
                const prompt = card.dataset.prompt;
                input.value = prompt;
                this.sendMessage();
            });
        });
    }

    handleInput(e) {
        const input = e.target;
        const sendBtn = document.getElementById('sendBtn');
        const charCounter = document.getElementById('charCounter');
        const charCount = document.getElementById('charCount');

        const length = input.value.length;

        // Enable/disable send button
        sendBtn.disabled = length === 0;

        // Show character counter near limit
        if (length > CONFIG.MAX_MESSAGE_LENGTH - 300) {
            charCounter.style.display = 'block';
            charCount.textContent = length;

            if (length > CONFIG.MAX_MESSAGE_LENGTH) {
                charCounter.classList.add('error');
                sendBtn.disabled = true;
            } else if (length > CONFIG.MAX_MESSAGE_LENGTH - 100) {
                charCounter.classList.add('warning');
                charCounter.classList.remove('error');
            } else {
                charCounter.classList.remove('warning', 'error');
            }
        } else {
            charCounter.style.display = 'none';
        }
    }

    autoResizeInput(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    async sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();

        if (!message) return;

        // Add user message to UI
        this.addMessage({
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        });

        // Clear input
        input.value = '';
        input.style.height = 'auto';
        document.getElementById('sendBtn').disabled = true;

        // Hide empty state
        const emptyState = document.getElementById('emptyState');
        if (emptyState) {
            emptyState.style.display = 'none';
        }

        // Show typing indicator
        this.showTypingIndicator();

        try {
            // Send to API
            const response = await window.api.sendMessage(message, this.sessionId);

            // Hide typing indicator
            this.hideTypingIndicator();

            // Add AI response
            if (response.response) {
                this.addMessage({
                    role: 'ai',
                    content: response.response,
                    timestamp: new Date().toISOString(),
                    confidence: response.confidence,
                    sources: response.sources
                });
            }

            // Update conversation
            this.updateConversation(message, response.response);

        } catch (error) {
            this.hideTypingIndicator();
            window.ui.showToast('Error', error.message || 'Failed to send message', 'error');
        }
    }

    addMessage(message) {
        this.messages.push(message);
        const chatMessages = document.getElementById('chatMessages');

        const messageEl = document.createElement('div');
        messageEl.className = `message ${message.role}`;

        messageEl.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-${message.role === 'user' ? 'user' : 'robot'}"></i>
            </div>
            <div class="message-content">
                <div class="message-bubble">
                    <div class="message-text">${this.formatMessage(message.content)}</div>
                </div>
                <div class="message-actions">
                    <button class="message-action-btn copy-btn">
                        <i class="fas fa-copy"></i> Copy
                    </button>
                    ${message.role === 'ai' ? '<button class="message-action-btn"><i class="fas fa-redo"></i> Regenerate</button>' : ''}
                </div>
                <div class="message-timestamp">${window.ui.formatTime(message.timestamp)}</div>
            </div>
        `;

        chatMessages.appendChild(messageEl);

        // Add copy functionality
        messageEl.querySelector('.copy-btn')?.addEventListener('click', () => {
            navigator.clipboard.writeText(message.content);
            window.ui.showToast('Copied', 'Message copied to clipboard', 'success');
        });

        window.ui.scrollToBottom();
    }

    formatMessage(content) {
        // Convert markdown-like syntax to HTML
        let formatted = window.ui.escapeHtml(content);

        // Code blocks
        formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            return `
                <div class="code-block">
                    <div class="code-header">
                        <span class="code-language">${lang || 'code'}</span>
                        <button class="code-copy-btn">Copy</button>
                    </div>
                    <div class="code-content"><code>${code.trim()}</code></div>
                </div>
            `;
        });

        // Inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic
        formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');

        return formatted;
    }

    showTypingIndicator() {
        this.isTyping = true;
        const chatMessages = document.getElementById('chatMessages');

        const indicator = document.createElement('div');
        indicator.className = 'message ai typing-message';
        indicator.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="message-bubble">
                    <div class="typing-indicator">
                        <span class="typing-dot"></span>
                        <span class="typing-dot"></span>
                        <span class="typing-dot"></span>
                    </div>
                </div>
            </div>
        `;

        chatMessages.appendChild(indicator);
        window.ui.scrollToBottom();
    }

    hideTypingIndicator() {
        this.isTyping = false;
        document.querySelector('.typing-message')?.remove();
    }

    startNewConversation() {
        this.currentConversation = {
            id: window.api.generateConversationId(),
            title: 'New conversation',
            messages: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            starred: false
        };

        this.sessionId = window.api.generateSessionId();
        this.messages = [];

        // Clear chat area
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = '';

        // Show empty state
        const emptyState = document.getElementById('emptyState');
        if (emptyState) {
            chatMessages.appendChild(emptyState);
            emptyState.style.display = 'flex';
        }

        // Update title
        document.getElementById('chatTitle').textContent = 'New conversation';

        // Close sidebar on mobile
        if (window.innerWidth < 768) {
            window.ui.toggleSidebar();
        }
    }

    async updateConversation(userMessage, aiResponse) {
        if (!this.currentConversation) {
            this.startNewConversation();
        }

        // Update title from first message
        if (this.messages.length === 2) {
            this.currentConversation.title = userMessage.substring(0, 50) + (userMessage.length > 50 ? '...' : '');
            document.getElementById('chatTitle').textContent = this.currentConversation.title;
        }

        this.currentConversation.messages = this.messages;
        this.currentConversation.lastMessage = aiResponse?.substring(0, 100);
        this.currentConversation.updated_at = new Date().toISOString();

        // Save to storage
        await window.api.saveConversation(this.currentConversation);

        // Refresh conversations list
        await this.loadConversationsList();
    }

    async loadConversationsList() {
        const conversations = await window.api.getConversations();

        // Separate pinned and recent
        const pinned = conversations.filter(c => c.pinned);
        const recent = conversations.filter(c => !c.pinned).slice(0, 15);

        // Render lists
        if (pinned.length > 0) {
            document.getElementById('pinnedSection').style.display = 'block';
            window.ui.renderConversationsList(pinned, 'pinnedList');
        } else {
            document.getElementById('pinnedSection').style.display = 'none';
        }

        window.ui.renderConversationsList(recent, 'recentList');
    }

    async loadConversation(id) {
        const conversations = await window.api.getConversations();
        const conv = conversations.find(c => c.id === id);

        if (!conv) return;

        this.currentConversation = conv;
        this.messages = conv.messages || [];
        this.sessionId = conv.session_id || window.api.generateSessionId();

        // Clear and render messages
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = '';

        if (this.messages.length === 0) {
            const emptyState = document.getElementById('emptyState');
            if (emptyState) {
                emptyState.style.display = 'flex';
            }
        } else {
            this.messages.forEach(msg => this.addMessage(msg));
        }

        // Update UI
        document.getElementById('chatTitle').textContent = conv.title;

        // Update active state
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.toggle('active', item.dataset.id === id);
        });

        // Close sidebar on mobile
        if (window.innerWidth < 768) {
            window.ui.toggleSidebar();
        }
    }

    attachFile() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = CONFIG.ALLOWED_FILE_TYPES.join(',');

        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (file.size > CONFIG.MAX_FILE_SIZE) {
                window.ui.showToast('File too large', `Maximum size is ${CONFIG.MAX_FILE_SIZE / 1024 / 1024}MB`, 'error');
                return;
            }

            try {
                const result = await window.api.uploadDocument(file);
                window.ui.showToast('Uploaded', 'File uploaded successfully', 'success');
            } catch (error) {
                window.ui.showToast('Upload failed', error.message, 'error');
            }
        };

        input.click();
    }

    startVoiceInput() {
        window.ui.showToast('Voice input', 'Voice input not yet implemented', 'info');
    }

    showSuggestions() {
        const suggestions = document.getElementById('quickSuggestions');
        if (suggestions.style.display === 'flex') {
            suggestions.style.display = 'none';
        } else {
            suggestions.innerHTML = `
                <button class="suggestion-btn">Summarize this</button>
                <button class="suggestion-btn">Explain in detail</button>
                <button class="suggestion-btn">Make it shorter</button>
                <button class="suggestion-btn">Expand on this</button>
            `;
            suggestions.style.display = 'flex';

            suggestions.querySelectorAll('.suggestion-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.getElementById('chatInput').value = btn.textContent;
                    suggestions.style.display = 'none';
                });
            });
        }
    }
}

// Create global Chat instance
window.chat = new Chat();
