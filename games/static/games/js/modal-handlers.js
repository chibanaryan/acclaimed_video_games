/**
 * Modal Handlers - Contact and Auth modal functionality
 * Loaded via requestIdleCallback for better performance
 *
 * Note: Modals (contactModal, authModal) are in the base layout and are NOT
 * swapped by HTMX. The guard prevents duplicate listener registration while
 * handlers re-query elements to be robust against any future DOM changes.
 */
(function() {
    'use strict';

    // Prevent duplicate listener registration (memory leak fix)
    if (window._modalHandlersInitialized) return;
    window._modalHandlersInitialized = true;

    // Auth modal trigger - re-query elements inside handler for robustness
    document.addEventListener('click', function(e) {
        var trigger = e.target.closest('.auth-modal-trigger');
        if (trigger) {
            var authModal = document.getElementById('authModal');
            if (!authModal) return;

            e.preventDefault();
            // Check for specific screen to load
            var screen = trigger.dataset.authScreen;
            var url = '/auth/modal/login/';
            if (screen === 'profile') {
                // Add cache-buster to ensure fresh data every time
                url = '/auth/modal/profile/?_=' + Date.now();
            } else if (screen === 'signup') {
                url = '/auth/modal/signup/?direct=1';
            }
            htmx.ajax('GET', url, {target: '#auth-modal-content', swap: 'innerHTML'});
            authModal.showModal();

            // Close mobile menu if open
            var mobileMenu = document.querySelector('[x-data]');
            if (mobileMenu && mobileMenu.__x) {
                mobileMenu.__x.$data.expanded = false;
            }
        }
    });

    // Ensure HTMX processes content after swaps into auth modal
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (e.detail.target.id === 'auth-modal-content') {
            htmx.process(e.detail.target);
        }
    });

    // Contact modal trigger - re-query elements inside handler for robustness
    document.addEventListener('click', function(e) {
        var trigger = e.target.closest('.contact-modal-trigger');
        if (trigger) {
            var contactModal = document.getElementById('contactModal');
            if (!contactModal) return;

            e.preventDefault();

            // Pre-fill form fields from data attributes
            var category = trigger.dataset.category;
            var message = trigger.dataset.message;

            if (category) {
                var categorySelect = document.getElementById('id_category');
                if (categorySelect) categorySelect.value = category;
            }
            if (message) {
                var messageField = document.getElementById('id_message');
                if (messageField) messageField.value = message;
            }

            contactModal.showModal();

            // Close mobile menu if open
            var mobileMenu = document.querySelector('[x-data]');
            if (mobileMenu && mobileMenu.__x) {
                mobileMenu.__x.$data.expanded = false;
            }
        }

        // Handle close button
        if (e.target.closest('.contact-modal-close')) {
            var contactModal = document.getElementById('contactModal');
            if (contactModal) contactModal.close();
        }
    });

    // Setup contact modal observer and auto-open (only if modal exists at init)
    var contactModal = document.getElementById('contactModal');
    var naviSound = document.getElementById('naviSound');

    if (contactModal) {
        // Create a MutationObserver to detect when dialog opens (for sound)
        var observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.attributeName === 'open' && contactModal.hasAttribute('open')) {
                    if (naviSound) {
                        naviSound.volume = 0.3;
                        naviSound.currentTime = 0;
                        naviSound.play().catch(function() {
                            // Autoplay might be blocked by browser
                        });
                    }
                }
            });
        });

        observer.observe(contactModal, { attributes: true });

        // Auto-open if hash is #contact
        if (window.location.hash === '#contact') {
            setTimeout(function() {
                contactModal.showModal();
                history.replaceState(null, '', window.location.pathname);
            }, 100);
        }
    }
})();
