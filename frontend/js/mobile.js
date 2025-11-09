/* ============================================
   MOBILE ENHANCEMENTS
   Touch gestures, keyboard handling, and mobile-specific features
   ============================================ */

(function() {
    'use strict';

    // Detect if running on mobile
    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);
    const isAndroid = /Android/i.test(navigator.userAgent);

    // Add mobile class to body
    if (isMobile) {
        document.body.classList.add('is-mobile');
        if (isIOS) document.body.classList.add('is-ios');
        if (isAndroid) document.body.classList.add('is-android');
    }

    /* ============================================
       VIEWPORT HEIGHT FIX (for mobile browsers)
       ============================================ */
    function setVhProperty() {
        // Get the actual viewport height and set custom property
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }

    // Set on load and resize
    setVhProperty();
    window.addEventListener('resize', setVhProperty);
    window.addEventListener('orientationchange', setVhProperty);

    /* ============================================
       MOBILE KEYBOARD HANDLING
       ============================================ */
    const chatInput = document.getElementById('chatInput');
    const chatComposer = document.querySelector('.chat-composer');
    const chatMessages = document.getElementById('chatMessages');

    if (chatInput && isMobile) {
        // Scroll to input when keyboard opens
        chatInput.addEventListener('focus', function() {
            setTimeout(() => {
                // Scroll input into view
                chatInput.scrollIntoView({ behavior: 'smooth', block: 'center' });

                // Add keyboard-open class
                document.body.classList.add('keyboard-open');
            }, 300); // Delay to wait for keyboard animation
        });

        // Remove keyboard-open class when keyboard closes
        chatInput.addEventListener('blur', function() {
            document.body.classList.remove('keyboard-open');

            // Scroll to bottom of messages
            if (chatMessages) {
                setTimeout(() => {
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }, 100);
            }
        });

        // Prevent page zoom on input focus (iOS)
        if (isIOS) {
            chatInput.addEventListener('touchstart', function() {
                chatInput.style.fontSize = '16px';
            });
        }
    }

    /* ============================================
       SIDEBAR DRAWER HANDLING
       ============================================ */
    const sidebar = document.getElementById('sidebar');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const appContainer = document.querySelector('.app-container');

    // Toggle sidebar on mobile
    if (mobileMenuBtn && sidebar) {
        mobileMenuBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebar.classList.toggle('active');

            // Add overlay
            if (sidebar.classList.contains('active')) {
                createOverlay();
            }
        });
    }

    // Create overlay for sidebar
    function createOverlay() {
        const overlay = document.createElement('div');
        overlay.className = 'mobile-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1019;
            backdrop-filter: blur(2px);
        `;

        // Close sidebar when clicking overlay
        overlay.addEventListener('click', function() {
            sidebar.classList.remove('active');
            overlay.remove();
        });

        document.body.appendChild(overlay);
    }

    // Close sidebar when clicking outside
    document.addEventListener('click', function(e) {
        if (sidebar && sidebar.classList.contains('active')) {
            if (!sidebar.contains(e.target) && e.target !== mobileMenuBtn) {
                sidebar.classList.remove('active');
                const overlay = document.querySelector('.mobile-overlay');
                if (overlay) overlay.remove();
            }
        }
    });

    /* ============================================
       SWIPE GESTURES
       ============================================ */
    let touchStartX = 0;
    let touchStartY = 0;
    let touchEndX = 0;
    let touchEndY = 0;

    // Swipe to open/close sidebar
    if (isMobile && appContainer) {
        appContainer.addEventListener('touchstart', function(e) {
            touchStartX = e.changedTouches[0].screenX;
            touchStartY = e.changedTouches[0].screenY;
        }, { passive: true });

        appContainer.addEventListener('touchend', function(e) {
            touchEndX = e.changedTouches[0].screenX;
            touchEndY = e.changedTouches[0].screenY;
            handleSwipe();
        }, { passive: true });
    }

    function handleSwipe() {
        const swipeThreshold = 100;
        const diffX = touchEndX - touchStartX;
        const diffY = Math.abs(touchEndY - touchStartY);

        // Only trigger if horizontal swipe is dominant
        if (Math.abs(diffX) > swipeThreshold && diffY < 100) {
            // Swipe right - open sidebar
            if (diffX > 0 && touchStartX < 50 && !sidebar.classList.contains('active')) {
                sidebar.classList.add('active');
                createOverlay();
            }
            // Swipe left - close sidebar
            else if (diffX < 0 && sidebar.classList.contains('active')) {
                sidebar.classList.remove('active');
                const overlay = document.querySelector('.mobile-overlay');
                if (overlay) overlay.remove();
            }
        }
    }

    /* ============================================
       PULL TO REFRESH PREVENTION
       ============================================ */
    // Prevent pull-to-refresh on chat messages area
    if (chatMessages) {
        let startY = 0;

        chatMessages.addEventListener('touchstart', function(e) {
            startY = e.touches[0].pageY;
        }, { passive: true });

        chatMessages.addEventListener('touchmove', function(e) {
            const y = e.touches[0].pageY;
            const scrollTop = chatMessages.scrollTop;

            // If at top and pulling down, prevent default
            if (scrollTop <= 0 && y > startY) {
                e.preventDefault();
            }
        }, { passive: false });
    }

    /* ============================================
       SCROLL TO BOTTOM ON NEW MESSAGE
       ============================================ */
    function scrollToBottom(smooth = true) {
        if (chatMessages) {
            chatMessages.scrollTo({
                top: chatMessages.scrollHeight,
                behavior: smooth ? 'smooth' : 'auto'
            });
        }
    }

    // Expose scroll function globally
    window.scrollToBottom = scrollToBottom;

    /* ============================================
       ACTIVE ELEMENT TRACKING (for better touch feedback)
       ============================================ */
    if (isMobile) {
        document.addEventListener('touchstart', function(e) {
            const target = e.target.closest('button, a, .clickable');
            if (target) {
                target.classList.add('touch-active');
            }
        }, { passive: true });

        document.addEventListener('touchend', function(e) {
            const target = e.target.closest('button, a, .clickable');
            if (target) {
                setTimeout(() => {
                    target.classList.remove('touch-active');
                }, 150);
            }
        }, { passive: true });

        document.addEventListener('touchcancel', function(e) {
            const target = e.target.closest('button, a, .clickable');
            if (target) {
                target.classList.remove('touch-active');
            }
        }, { passive: true });
    }

    /* ============================================
       TEXTAREA AUTO-RESIZE
       ============================================ */
    if (chatInput) {
        chatInput.addEventListener('input', function() {
            // Reset height to auto to get the correct scrollHeight
            this.style.height = 'auto';

            // Set new height based on content
            const newHeight = Math.min(this.scrollHeight, 120); // Max 120px
            this.style.height = newHeight + 'px';

            // Adjust composer height
            if (chatComposer) {
                chatComposer.style.minHeight = (newHeight + 40) + 'px';
            }
        });
    }

    /* ============================================
       SAFE AREA DETECTION
       ============================================ */
    function detectSafeArea() {
        const safeAreaTop = getComputedStyle(document.documentElement)
            .getPropertyValue('env(safe-area-inset-top)') || '0px';
        const safeAreaBottom = getComputedStyle(document.documentElement)
            .getPropertyValue('env(safe-area-inset-bottom)') || '0px';

        // Add class if device has notch/safe areas
        if (safeAreaTop !== '0px' || safeAreaBottom !== '0px') {
            document.body.classList.add('has-notch');
        }
    }

    detectSafeArea();

    /* ============================================
       PREVENT ZOOM ON DOUBLE TAP
       ============================================ */
    let lastTouchEnd = 0;
    document.addEventListener('touchend', function(e) {
        const now = Date.now();
        if (now - lastTouchEnd <= 300) {
            // Double tap detected - prevent default if on non-zoomable element
            if (!e.target.closest('img, canvas')) {
                e.preventDefault();
            }
        }
        lastTouchEnd = now;
    }, { passive: false });

    /* ============================================
       HAPTIC FEEDBACK (for supported devices)
       ============================================ */
    function hapticFeedback(type = 'light') {
        if (navigator.vibrate) {
            switch(type) {
                case 'light':
                    navigator.vibrate(10);
                    break;
                case 'medium':
                    navigator.vibrate(20);
                    break;
                case 'heavy':
                    navigator.vibrate(40);
                    break;
            }
        }
    }

    // Add haptic feedback to buttons
    if (isMobile) {
        document.addEventListener('click', function(e) {
            const button = e.target.closest('button, .btn, .icon-btn');
            if (button) {
                hapticFeedback('light');
            }
        }, { passive: true });
    }

    /* ============================================
       ORIENTATION CHANGE HANDLING
       ============================================ */
    window.addEventListener('orientationchange', function() {
        // Close sidebar on orientation change
        if (sidebar && sidebar.classList.contains('active')) {
            sidebar.classList.remove('active');
            const overlay = document.querySelector('.mobile-overlay');
            if (overlay) overlay.remove();
        }

        // Recalculate vh
        setVhProperty();

        // Blur active input to close keyboard
        if (document.activeElement && document.activeElement.tagName === 'INPUT' ||
            document.activeElement.tagName === 'TEXTAREA') {
            document.activeElement.blur();
        }
    });

    /* ============================================
       PERFORMANCE: Passive Event Listeners
       ============================================ */
    // Add passive flag to scroll events for better performance
    const scrollElements = document.querySelectorAll('.chat-messages, .conversations-container, .modal-body');
    scrollElements.forEach(element => {
        element.addEventListener('scroll', function() {
            // Scroll handler
        }, { passive: true });
    });

    /* ============================================
       NETWORK STATUS INDICATOR
       ============================================ */
    const connectionStatus = document.getElementById('connectionStatus');

    function updateOnlineStatus() {
        if (connectionStatus) {
            const statusDot = connectionStatus.querySelector('.status-dot');
            if (navigator.onLine) {
                statusDot.classList.remove('disconnected');
                connectionStatus.title = 'Connected';
            } else {
                statusDot.classList.add('disconnected');
                connectionStatus.title = 'Offline';
            }
        }
    }

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus();

    // Log mobile enhancements loaded
    console.log('📱 Mobile enhancements loaded');
    console.log('Device:', isMobile ? (isIOS ? 'iOS' : 'Android') : 'Desktop');
    console.log('Viewport:', window.innerWidth, 'x', window.innerHeight);

})();
