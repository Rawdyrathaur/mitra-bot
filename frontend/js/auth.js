// Authentication Module - Handles user authentication and session management
class Auth {
    constructor() {
        this.user = null;
        this.init();
    }

    init() {
        this.loadUser();
        this.checkAuth();
        // Update UI for guest mode if applicable
        if (localStorage.getItem('auth_mode') === 'guest') {
            this.updateUI();
        }
    }

    // Load user from token
    async loadUser() {
        const token = window.api.getToken();
        if (!token) return;

        try {
            // Decode JWT to get user info (basic decode, not verification)
            const payload = JSON.parse(atob(token.split('.')[1]));
            this.user = {
                id: payload.sub || payload.user_id,
                email: payload.email,
                name: payload.name || payload.username,
                exp: payload.exp
            };

            // Check if token is expired
            if (this.user.exp && Date.now() >= this.user.exp * 1000) {
                this.logout();
                return;
            }

            this.updateUI();
        } catch (error) {
            console.error('Failed to load user:', error);
            this.logout();
        }
    }

    // Check authentication status
    checkAuth() {
        const currentPath = window.location.pathname;
        const isAuthPage = currentPath.includes('auth.html');
        const isLoggedIn = !!window.api.getToken();
        const isGuestMode = localStorage.getItem('auth_mode') === 'guest';

        // Allow access if logged in OR in guest mode
        const hasAccess = isLoggedIn || isGuestMode;

        // Redirect to auth page if no access and not already on auth page
        if (!hasAccess && !isAuthPage) {
            window.location.href = '/auth.html';
            return false;
        }

        // Redirect to home if has access and on auth page
        if (hasAccess && isAuthPage) {
            window.location.href = '/';
            return false;
        }

        return true;
    }

    // Update UI with user info
    updateUI() {
        const isGuestMode = localStorage.getItem('auth_mode') === 'guest';

        // Update user profile in sidebar
        const userName = document.querySelector('.user-name');
        const userEmail = document.querySelector('.user-status');

        if (isGuestMode) {
            // Guest mode UI
            if (userName) {
                userName.textContent = 'Guest User';
            }
            if (userEmail) {
                userEmail.textContent = 'Browsing as Guest';
            }
        } else if (this.user) {
            // Logged in user UI
            if (userName) {
                userName.textContent = this.user.name || 'User';
            }
            if (userEmail) {
                userEmail.textContent = this.user.email || 'Online';
            }

            // Add user avatar if available
            const userAvatar = document.querySelector('.user-avatar');
            if (userAvatar && this.user.avatar) {
                userAvatar.innerHTML = `<img src="${this.user.avatar}" alt="${this.user.name}">`;
            }
        }
    }

    // Logout
    logout() {
        window.api.removeToken();
        this.user = null;
        localStorage.clear(); // Clear all local storage
        window.location.href = '/auth.html';
    }

    // Get current user
    getCurrentUser() {
        return this.user;
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.user && !!window.api.getToken();
    }

    // Update user profile
    async updateProfile(data) {
        try {
            const response = await window.api.request('/api/auth/profile', {
                method: 'PUT',
                body: JSON.stringify(data)
            });

            if (response.success) {
                this.user = { ...this.user, ...data };
                this.updateUI();
                return true;
            }

            return false;
        } catch (error) {
            console.error('Failed to update profile:', error);
            return false;
        }
    }

    // Change password
    async changePassword(currentPassword, newPassword) {
        try {
            const response = await window.api.request('/api/auth/change-password', {
                method: 'POST',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });

            return response.success;
        } catch (error) {
            console.error('Failed to change password:', error);
            return false;
        }
    }
}

// Create global Auth instance
window.auth = new Auth();

// Add logout button handler
document.addEventListener('DOMContentLoaded', () => {
    // Add logout button to user profile dropdown
    const userProfile = document.querySelector('.user-profile');
    if (userProfile) {
        userProfile.addEventListener('click', () => {
            showUserMenu();
        });
    }
});

function showUserMenu() {
    const existingMenu = document.querySelector('.user-menu');
    if (existingMenu) {
        existingMenu.remove();
        return;
    }

    const isGuestMode = localStorage.getItem('auth_mode') === 'guest';

    const menu = document.createElement('div');
    menu.className = 'user-menu';
    menu.style.cssText = `
        position: absolute;
        bottom: 80px;
        left: 20px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 1000;
        min-width: 200px;
    `;

    if (isGuestMode) {
        // Guest mode menu
        menu.innerHTML = `
            <button onclick="goToSignIn()" style="width: 100%; padding: 10px; text-align: left; background: none; border: none; color: var(--primary-color); cursor: pointer; border-radius: 6px; display: flex; align-items: center; gap: 10px;">
                <i class="fas fa-sign-in-alt"></i> Sign In / Register
            </button>
        `;
    } else {
        // Logged in user menu
        menu.innerHTML = `
            <button onclick="showProfile()" style="width: 100%; padding: 10px; text-align: left; background: none; border: none; color: var(--text-primary); cursor: pointer; border-radius: 6px; display: flex; align-items: center; gap: 10px;">
                <i class="fas fa-user"></i> Profile
            </button>
            <button onclick="showSettings()" style="width: 100%; padding: 10px; text-align: left; background: none; border: none; color: var(--text-primary); cursor: pointer; border-radius: 6px; display: flex; align-items: center; gap: 10px;">
                <i class="fas fa-cog"></i> Settings
            </button>
            <hr style="border: none; border-top: 1px solid var(--border-color); margin: 8px 0;">
            <button onclick="window.auth.logout()" style="width: 100%; padding: 10px; text-align: left; background: none; border: none; color: var(--error-color); cursor: pointer; border-radius: 6px; display: flex; align-items: center; gap: 10px;">
                <i class="fas fa-sign-out-alt"></i> Logout
            </button>
        `;
    }

    document.body.appendChild(menu);

    // Close on outside click
    setTimeout(() => {
        document.addEventListener('click', function closeMenu(e) {
            if (!e.target.closest('.user-menu') && !e.target.closest('.user-profile')) {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            }
        });
    }, 0);
}

function goToSignIn() {
    localStorage.removeItem('auth_mode');
    localStorage.removeItem('guest_id');
    window.location.href = '/auth.html';
}

function showProfile() {
    const user = window.auth.getCurrentUser();
    if (!user) return;

    const content = `
        <div class="profile-content">
            <h3>Profile Settings</h3>
            <div style="margin: 20px 0;">
                <div style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 500;">Name</label>
                    <input type="text" id="profileName" value="${user.name || ''}" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary);">
                </div>
                <div style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 500;">Email</label>
                    <input type="email" id="profileEmail" value="${user.email || ''}" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary);">
                </div>
                <div style="margin-top: 16px; display: flex; gap: 8px; justify-content: flex-end;">
                    <button onclick="window.ui.closeModal('settingsModal')" style="padding: 10px 20px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); cursor: pointer;">Cancel</button>
                    <button onclick="saveProfile()" style="padding: 10px 20px; border-radius: 8px; border: none; background: var(--primary-color); color: white; cursor: pointer;">Save Changes</button>
                </div>
            </div>
        </div>
    `;

    window.ui.openModal('settingsModal');
    document.querySelector('#settingsModal .modal-body').innerHTML = content;
    document.querySelector('.user-menu')?.remove();
}

async function saveProfile() {
    const name = document.getElementById('profileName').value;
    const email = document.getElementById('profileEmail').value;

    const success = await window.auth.updateProfile({ name, email });

    if (success) {
        window.ui.showToast('Profile updated', 'Your profile has been updated successfully', 'success');
        window.ui.closeModal('settingsModal');
    } else {
        window.ui.showToast('Update failed', 'Failed to update profile', 'error');
    }
}

function showSettings() {
    const content = `
        <div class="settings-content">
            <h3>Account Settings</h3>
            <div style="margin: 20px 0;">
                <h4 style="margin-bottom: 16px;">Change Password</h4>
                <div style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 500;">Current Password</label>
                    <input type="password" id="currentPassword" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary);">
                </div>
                <div style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 500;">New Password</label>
                    <input type="password" id="newPassword" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary);">
                </div>
                <div style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 500;">Confirm New Password</label>
                    <input type="password" id="confirmPassword" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary);">
                </div>
                <div style="margin-top: 16px; display: flex; gap: 8px; justify-content: flex-end;">
                    <button onclick="window.ui.closeModal('settingsModal')" style="padding: 10px 20px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); cursor: pointer;">Cancel</button>
                    <button onclick="changePassword()" style="padding: 10px 20px; border-radius: 8px; border: none; background: var(--primary-color); color: white; cursor: pointer;">Change Password</button>
                </div>
            </div>
        </div>
    `;

    window.ui.openModal('settingsModal');
    document.querySelector('#settingsModal .modal-body').innerHTML = content;
    document.querySelector('.user-menu')?.remove();
}

async function changePassword() {
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    if (!currentPassword || !newPassword || !confirmPassword) {
        window.ui.showToast('Missing fields', 'Please fill in all fields', 'warning');
        return;
    }

    if (newPassword !== confirmPassword) {
        window.ui.showToast('Passwords do not match', 'New passwords do not match', 'error');
        return;
    }

    if (newPassword.length < 8) {
        window.ui.showToast('Password too short', 'Password must be at least 8 characters', 'error');
        return;
    }

    const success = await window.auth.changePassword(currentPassword, newPassword);

    if (success) {
        window.ui.showToast('Password changed', 'Your password has been changed successfully', 'success');
        window.ui.closeModal('settingsModal');
    } else {
        window.ui.showToast('Change failed', 'Failed to change password. Check your current password.', 'error');
    }
}
