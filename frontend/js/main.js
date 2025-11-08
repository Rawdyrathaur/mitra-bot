// Main Application Initialization
document.addEventListener('DOMContentLoaded', () => {
    console.log('Mitra Bot initializing...');

    // Initialize modules (already created as global instances)
    // window.api, window.ui, window.chat

    // Check if user is logged in (optional - for now allow anonymous)
    initializeApp();

    // Set up keyboard shortcuts
    setupKeyboardShortcuts();

    // Handle URL parameters (for shared conversations)
    handleURLParams();

    console.log('Mitra Bot ready!');
});

async function initializeApp() {
    try {
        // Check API health
        const health = await window.api.checkHealth();
        console.log('API Status:', health);

        // Load existing conversations
        await window.chat.loadConversationsList();

        // Start with new conversation or load from URL
        const urlParams = new URLSearchParams(window.location.search);
        const convId = urlParams.get('conv');

        if (convId) {
            await window.chat.loadConversation(convId);
        } else {
            window.chat.startNewConversation();
        }

    } catch (error) {
        console.error('Initialization error:', error);
        window.ui.showToast(
            'Connection Error',
            'Could not connect to server. Please check your connection.',
            'error'
        );
    }
}

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Cmd/Ctrl + N: New chat
        if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
            e.preventDefault();
            window.chat.startNewConversation();
        }

        // Cmd/Ctrl + K: Focus search
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById('searchInput')?.focus();
        }

        // Cmd/Ctrl + /: Show shortcuts
        if ((e.metaKey || e.ctrlKey) && e.key === '/') {
            e.preventDefault();
            showKeyboardShortcuts();
        }

        // Cmd/Ctrl + Shift + L: Toggle theme
        if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'L') {
            e.preventDefault();
            window.ui.toggleTheme();
        }

        // Escape: Close modals/panels
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal.active').forEach(modal => {
                window.ui.closeModal(modal.id);
            });

            if (window.innerWidth < 768 && window.ui.sidebarOpen) {
                window.ui.toggleSidebar();
            }
        }
    });
}

function showKeyboardShortcuts() {
    const shortcuts = [
        { keys: 'Ctrl/Cmd + N', action: 'New chat' },
        { keys: 'Ctrl/Cmd + K', action: 'Search conversations' },
        { keys: 'Ctrl/Cmd + /', action: 'Show shortcuts' },
        { keys: 'Ctrl/Cmd + Shift + L', action: 'Toggle theme' },
        { keys: 'Shift + Enter', action: 'New line in message' },
        { keys: 'Enter', action: 'Send message' },
        { keys: 'Escape', action: 'Close modals' }
    ];

    const list = shortcuts.map(s =>
        `<li><kbd>${s.keys}</kbd> - ${s.action}</li>`
    ).join('');

    const modal = document.getElementById('settingsModal');
    const body = modal.querySelector('.modal-body');
    body.innerHTML = `
        <h3>Keyboard Shortcuts</h3>
        <ul style="list-style: none; padding: 0;">
            ${list}
        </ul>
        <style>
            kbd {
                background: var(--bg-tertiary);
                padding: 4px 8px;
                border-radius: 4px;
                font-family: var(--font-mono);
                font-size: 12px;
            }
            li {
                padding: 8px 0;
            }
        </style>
    `;

    window.ui.openModal('settingsModal');
}

function handleURLParams() {
    const params = new URLSearchParams(window.location.search);

    // Handle shared conversation
    if (params.has('conv')) {
        console.log('Loading shared conversation:', params.get('conv'));
    }

    // Handle document reference
    if (params.has('doc')) {
        console.log('Loading document:', params.get('doc'));
    }
}

// Service Worker Registration (for offline support - future enhancement)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        // Uncomment when service worker is implemented
        // navigator.serviceWorker.register('/sw.js').then(registration => {
        //     console.log('ServiceWorker registered:', registration);
        // }).catch(error => {
        //     console.log('ServiceWorker registration failed:', error);
        // });
    });
}

// Handle online/offline events
window.addEventListener('online', () => {
    window.ui.showToast('Connected', 'Back online', 'success');
    window.ui.checkConnectionStatus();
});

window.addEventListener('offline', () => {
    window.ui.showToast('Offline', 'No internet connection', 'warning');
});

// Prevent accidental page close with unsaved messages
window.addEventListener('beforeunload', (e) => {
    const input = document.getElementById('chatInput');
    if (input && input.value.trim()) {
        e.preventDefault();
        e.returnValue = '';
    }
});

// Export for debugging
window.mitraBot = {
    version: '1.0.0',
    api: window.api,
    ui: window.ui,
    chat: window.chat,
    config: CONFIG
};

console.log('Mitra Bot v1.0.0 - AI Customer Support Assistant');
