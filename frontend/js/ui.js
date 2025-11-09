// UI Module - Handles all UI interactions
class UI {
    constructor() {
        this.theme = this.loadTheme();
        this.sidebarOpen = false;
        this.rightPanelOpen = false;
        this.init();
    }

    init() {
        this.applyTheme();
        this.setupEventListeners();
        this.checkConnectionStatus();
    }

    setupEventListeners() {
        // Theme toggle
        document.getElementById('themeToggle')?.addEventListener('click', () => {
            this.toggleTheme();
        });

        // Mobile menu
        document.getElementById('mobileMenuBtn')?.addEventListener('click', () => {
            this.toggleSidebar();
        });

        // New chat button
        document.getElementById('newChatBtn')?.addEventListener('click', () => {
            window.chat.startNewConversation();
            // Close sidebar on mobile after starting new chat
            if (window.innerWidth <= 768) {
                this.closeSidebar();
            }
        });

        // Search
        const searchInput = document.getElementById('searchInput');
        searchInput?.addEventListener('input', (e) => {
            this.handleSearch(e.target.value);
        });

        document.getElementById('clearSearch')?.addEventListener('click', () => {
            searchInput.value = '';
            this.handleSearch('');
        });

        // Filters
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.handleFilter(e.target.dataset.filter);
            });
        });

        // Close modals on backdrop click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal.id);
                }
            });
        });

        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modalId = e.target.closest('button').dataset.modal;
                this.closeModal(modalId);
            });
        });

        // Settings button
        document.getElementById('settingsBtn')?.addEventListener('click', () => {
            this.openModal('settingsModal');
        });

        // Share button
        document.getElementById('shareBtn')?.addEventListener('click', () => {
            this.shareConversation();
        });

        // Star button
        document.getElementById('starBtn')?.addEventListener('click', () => {
            this.toggleStar();
        });

        // Close right panel
        document.getElementById('closePanelBtn')?.addEventListener('click', () => {
            this.toggleRightPanel();
        });

        // Advanced options toggle
        document.getElementById('advancedToggle')?.addEventListener('click', () => {
            const panel = document.getElementById('advancedOptions');
            panel.style.display = panel.style.display === 'none' ? 'grid' : 'none';
        });

        // Scroll to bottom
        document.getElementById('scrollBottomBtn')?.addEventListener('click', () => {
            this.scrollToBottom();
        });

        // Chat messages scroll detection
        const chatMessages = document.getElementById('chatMessages');
        chatMessages?.addEventListener('scroll', () => {
            this.handleScroll();
        });

        // Help button
        document.querySelector('.sidebar-footer .icon-btn[title="Help"]')?.addEventListener('click', () => {
            this.showHelp();
        });

        // Feedback button
        document.querySelector('.sidebar-footer .icon-btn[title="Feedback"]')?.addEventListener('click', () => {
            this.showFeedback();
        });

        // Add Collection button
        document.getElementById('addCollectionBtn')?.addEventListener('click', () => {
            this.addCollection();
        });

        // Panel tabs
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchPanelTab(e.target.dataset.tab);
            });
        });
    }

    // Theme Management
    loadTheme() {
        return localStorage.getItem(CONFIG.THEME_STORAGE_KEY) || 'dark';
    }

    saveTheme(theme) {
        localStorage.setItem(CONFIG.THEME_STORAGE_KEY, theme);
    }

    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateThemeIcon();
    }

    toggleTheme() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        this.saveTheme(this.theme);
        this.applyTheme();
    }

    updateThemeIcon() {
        const icon = document.querySelector('#themeToggle i');
        if (icon) {
            icon.className = this.theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }

    // Sidebar Management
    toggleSidebar() {
        this.sidebarOpen = !this.sidebarOpen;
        const sidebar = document.getElementById('sidebar');

        if (this.sidebarOpen) {
            sidebar.classList.add('active');
            // Add backdrop for mobile
            if (window.innerWidth <= 768) {
                this.addSidebarBackdrop();
            }
        } else {
            sidebar.classList.remove('active');
            this.removeSidebarBackdrop();
        }
    }

    closeSidebar() {
        this.sidebarOpen = false;
        const sidebar = document.getElementById('sidebar');
        sidebar?.classList.remove('active');
        this.removeSidebarBackdrop();
    }

    addSidebarBackdrop() {
        // Check if backdrop already exists
        if (document.querySelector('.sidebar-backdrop')) return;

        const backdrop = document.createElement('div');
        backdrop.className = 'sidebar-backdrop';
        backdrop.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 999;
            animation: fadeIn 0.2s ease;
        `;

        // Close sidebar when clicking backdrop
        backdrop.addEventListener('click', () => {
            this.closeSidebar();
        });

        document.body.appendChild(backdrop);
    }

    removeSidebarBackdrop() {
        const backdrop = document.querySelector('.sidebar-backdrop');
        if (backdrop) {
            backdrop.style.animation = 'fadeOut 0.2s ease';
            setTimeout(() => backdrop.remove(), 200);
        }
    }

    // Right Panel Management
    toggleRightPanel() {
        this.rightPanelOpen = !this.rightPanelOpen;
        const panel = document.getElementById('rightPanel');
        panel.style.display = this.rightPanelOpen ? 'flex' : 'none';
    }

    // Search
    handleSearch(query) {
        const clearBtn = document.getElementById('clearSearch');
        clearBtn.style.display = query ? 'block' : 'none';

        const conversations = document.querySelectorAll('.conversation-item');
        conversations.forEach(item => {
            const title = item.querySelector('.conversation-title')?.textContent.toLowerCase();
            const preview = item.querySelector('.conversation-preview')?.textContent.toLowerCase();
            const matches = title?.includes(query.toLowerCase()) || preview?.includes(query.toLowerCase());
            item.style.display = matches || !query ? 'flex' : 'none';
        });
    }

    // Filters
    handleFilter(filter) {
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === filter);
        });

        // Filter logic would go here based on conversation metadata
        this.showToast('Filter applied', `Showing ${filter} conversations`, 'info');
    }

    // Modals
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
        }
    }

    // Toast Notifications
    showToast(title, message, type = 'info', duration = CONFIG.TOAST_DURATION) {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fas ${icons[type]}"></i>
            </div>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">
                <i class="fas fa-times"></i>
            </button>
        `;

        container.appendChild(toast);

        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.remove();
        });

        setTimeout(() => {
            toast.remove();
        }, duration);
    }

    // Scroll Management
    scrollToBottom(smooth = true) {
        const chatMessages = document.getElementById('chatMessages');
        chatMessages?.scrollTo({
            top: chatMessages.scrollHeight,
            behavior: smooth ? 'smooth' : 'auto'
        });
    }

    handleScroll() {
        const chatMessages = document.getElementById('chatMessages');
        const scrollBtn = document.getElementById('scrollBottomBtn');

        if (chatMessages && scrollBtn) {
            const isAtBottom = chatMessages.scrollHeight - chatMessages.scrollTop <= chatMessages.clientHeight + 100;
            scrollBtn.style.display = isAtBottom ? 'none' : 'flex';
        }
    }

    // Conversation Actions
    shareConversation() {
        const currentConv = window.chat?.currentConversation;
        if (!currentConv) {
            this.showToast('No conversation', 'Start a conversation first', 'warning');
            return;
        }

        // Copy link to clipboard
        const url = `${window.location.origin}?conv=${currentConv.id}`;
        navigator.clipboard.writeText(url).then(() => {
            this.showToast('Link copied', 'Conversation link copied to clipboard', 'success');
        }).catch(() => {
            this.showToast('Copy failed', 'Failed to copy link', 'error');
        });
    }

    toggleStar() {
        const btn = document.getElementById('starBtn');
        const icon = btn?.querySelector('i');
        if (icon) {
            const isStarred = icon.classList.contains('fas');
            icon.className = isStarred ? 'far fa-star' : 'fas fa-star';

            if (window.chat?.currentConversation) {
                window.chat.currentConversation.starred = !isStarred;
                window.api.saveConversation(window.chat.currentConversation);
            }

            this.showToast(
                isStarred ? 'Unstarred' : 'Starred',
                isStarred ? 'Removed from starred' : 'Added to starred',
                'success'
            );
        }
    }

    // Connection Status
    async checkConnectionStatus() {
        const statusDot = document.querySelector('.status-dot');
        const statusEl = document.getElementById('connectionStatus');

        try {
            await window.api.checkHealth();
            statusDot?.classList.remove('connecting', 'disconnected');
            statusEl?.setAttribute('title', 'Connected');
        } catch (error) {
            statusDot?.classList.add('disconnected');
            statusDot?.classList.remove('connecting');
            statusEl?.setAttribute('title', 'Connection lost');
        }

        // Check again in 30 seconds
        setTimeout(() => this.checkConnectionStatus(), 30000);
    }

    // Render Conversations List
    renderConversationsList(conversations, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = conversations.map(conv => `
            <div class="conversation-item" data-id="${conv.id}">
                <div class="conversation-content">
                    <div class="conversation-title">${this.escapeHtml(conv.title)}</div>
                    <div class="conversation-preview">${this.escapeHtml(conv.lastMessage || '')}</div>
                    <div class="conversation-meta">
                        <span class="conversation-time">${this.formatTime(conv.updated_at)}</span>
                        ${conv.unread ? '<span class="unread-badge"></span>' : ''}
                    </div>
                </div>
                <div class="conversation-actions">
                    <button class="icon-btn-sm pin-btn" title="Pin">
                        <i class="fas fa-thumbtack"></i>
                    </button>
                    <button class="icon-btn-sm delete-btn" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');

        // Add click listeners
        container.querySelectorAll('.conversation-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.conversation-actions')) {
                    window.chat.loadConversation(item.dataset.id);
                    // Close sidebar on mobile after selecting conversation
                    if (window.innerWidth <= 768) {
                        this.closeSidebar();
                    }
                }
            });

            item.querySelector('.delete-btn')?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteConversation(item.dataset.id);
            });

            item.querySelector('.pin-btn')?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.pinConversation(item.dataset.id);
            });
        });
    }

    async deleteConversation(id) {
        if (confirm('Delete this conversation?')) {
            await window.api.deleteConversation(id);
            await window.chat.loadConversationsList();
            this.showToast('Deleted', 'Conversation deleted', 'success');
        }
    }

    async pinConversation(id) {
        const conversations = await window.api.getConversations();
        const conv = conversations.find(c => c.id === id);

        if (conv) {
            conv.pinned = !conv.pinned;
            await window.api.saveConversation(conv);
            await window.chat.loadConversationsList();
            this.showToast(
                conv.pinned ? 'Pinned' : 'Unpinned',
                conv.pinned ? 'Conversation pinned' : 'Conversation unpinned',
                'success'
            );
        }
    }

    // Help & Feedback
    showHelp() {
        const helpContent = `
            <div class="help-content">
                <h3>Getting Started</h3>
                <p>Welcome to Mitra Bot! Here are some helpful tips:</p>
                <ul>
                    <li><strong>Ask Questions:</strong> Type your question in the input box and press Enter</li>
                    <li><strong>Use Templates:</strong> Click on prompt templates for quick starts</li>
                    <li><strong>Upload Files:</strong> Click the paperclip icon to upload documents</li>
                    <li><strong>Voice Input:</strong> Click the microphone icon for voice commands</li>
                    <li><strong>Star Important Chats:</strong> Click the star icon to save important conversations</li>
                </ul>
                <h3>Keyboard Shortcuts</h3>
                <ul>
                    <li><strong>Enter:</strong> Send message</li>
                    <li><strong>Shift + Enter:</strong> New line</li>
                    <li><strong>Ctrl + K:</strong> New chat</li>
                    <li><strong>Ctrl + /:</strong> Toggle this help</li>
                </ul>
            </div>
        `;
        this.showToast('Help', 'Check out keyboard shortcuts and tips!', 'info', 5000);
        this.openModal('settingsModal');
        document.querySelector('#settingsModal .modal-body').innerHTML = helpContent;
    }

    showFeedback() {
        const feedbackContent = `
            <div class="feedback-content">
                <h3>Send Feedback</h3>
                <p>We'd love to hear from you!</p>
                <textarea id="feedbackText" placeholder="Tell us what you think..." rows="5" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary); font-family: inherit; resize: vertical;"></textarea>
                <div style="margin-top: 16px; display: flex; gap: 8px; justify-content: flex-end;">
                    <button onclick="window.ui.closeModal('settingsModal')" style="padding: 10px 20px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); cursor: pointer;">Cancel</button>
                    <button onclick="window.ui.submitFeedback()" style="padding: 10px 20px; border-radius: 8px; border: none; background: var(--primary-color); color: white; cursor: pointer;">Submit</button>
                </div>
            </div>
        `;
        this.openModal('settingsModal');
        document.querySelector('#settingsModal .modal-body').innerHTML = feedbackContent;
    }

    submitFeedback() {
        const feedback = document.getElementById('feedbackText')?.value;
        if (feedback && feedback.trim()) {
            this.showToast('Thank you!', 'Your feedback has been submitted', 'success');
            this.closeModal('settingsModal');
            console.log('Feedback submitted:', feedback);
        } else {
            this.showToast('Empty feedback', 'Please enter your feedback', 'warning');
        }
    }

    // Collections
    addCollection() {
        const name = prompt('Enter collection name:');
        if (name && name.trim()) {
            const collections = JSON.parse(localStorage.getItem('collections') || '[]');
            collections.push({
                id: `coll_${Date.now()}`,
                name: name.trim(),
                conversations: [],
                created_at: new Date().toISOString()
            });
            localStorage.setItem('collections', JSON.stringify(collections));
            this.showToast('Created', `Collection "${name}" created`, 'success');
            this.renderCollections();
        }
    }

    renderCollections() {
        const collections = JSON.parse(localStorage.getItem('collections') || '[]');
        const container = document.getElementById('collectionsList');
        if (!container) return;

        container.innerHTML = collections.map(coll => `
            <div class="collection-item" data-id="${coll.id}">
                <i class="fas fa-folder"></i>
                <span>${this.escapeHtml(coll.name)}</span>
                <span class="collection-count">(${coll.conversations.length})</span>
            </div>
        `).join('');
    }

    exportConversation() {
        const conv = window.chat?.currentConversation;
        if (!conv || !conv.messages || conv.messages.length === 0) {
            this.showToast('No messages', 'No conversation to export', 'warning');
            return;
        }

        const text = conv.messages.map(m => `${m.role.toUpperCase()}: ${m.content}`).join('\n\n');
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `conversation_${Date.now()}.txt`;
        a.click();
        URL.revokeObjectURL(url);

        this.showToast('Exported', 'Conversation exported successfully', 'success');
        document.querySelector('.more-options-menu')?.remove();
    }

    clearConversation() {
        if (confirm('Clear all messages in this conversation?')) {
            if (window.chat?.currentConversation) {
                window.chat.currentConversation.messages = [];
                window.chat.messages = [];
                document.getElementById('chatMessages').innerHTML = '';
                const emptyState = document.getElementById('emptyState');
                if (emptyState) {
                    document.getElementById('chatMessages').appendChild(emptyState);
                    emptyState.style.display = 'flex';
                }
                this.showToast('Cleared', 'All messages cleared', 'success');
            }
        }
        document.querySelector('.more-options-menu')?.remove();
    }

    // Panel Tabs
    switchPanelTab(tabName) {
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        document.querySelectorAll('.panel-tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}Tab`);
        });
    }

    // Utilities
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (hours < 1) return 'Just now';
        if (hours < 24) return `${hours}h ago`;
        if (days === 1) return 'Yesterday';
        if (days < 7) return `${days}d ago`;
        return date.toLocaleDateString();
    }
}

// Create global UI instance
window.ui = new UI();
