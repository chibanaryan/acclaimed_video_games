/**
 * Alpine.js component for studio filtering on company detail pages
 * Provides client-side filtering with hierarchical checkbox selection
 */
function studioFilter() {
    return {
        // State
        selectedStudioIds: new Set(),
        sortBy: 'year', // 'year', 'rank', or 'name'
        showMobileFilters: false, // Controls mobile filter modal

        // Data loaded from Django context via window globals
        studioGameMap: {},
        studioChildMap: {},

        /**
         * Check if a game should be visible based on selected studios
         */
        gameIsVisible(gameId) {
            // If no studios selected, show all games
            if (this.selectedStudioIds.size === 0) {
                return true;
            }

            // Ensure gameId is a number for consistent comparison
            const gameIdNum = typeof gameId === 'number' ? gameId : parseInt(gameId);

            // Check if game belongs to any selected studio
            for (const studioId of this.selectedStudioIds) {
                const gameIds = this.studioGameMap[studioId] || [];
                // Check both number and string versions for safety
                if (gameIds.includes(gameIdNum) || gameIds.includes(gameId)) {
                    return true;
                }
            }

            return false;
        },

        /**
         * Count how many games are currently visible
         */
        countVisibleGames() {
            if (this.selectedStudioIds.size === 0) {
                // Count all games in DOM
                return document.querySelectorAll('#games-container > div').length;
            }

            // Count visible games
            const allGameIds = new Set();
            for (const studioId of this.selectedStudioIds) {
                const gameIds = this.studioGameMap[studioId] || [];
                gameIds.forEach(id => allGameIds.add(id));
            }
            return allGameIds.size;
        },

        /**
         * Sort games in the DOM based on current sortBy value
         */
        sortGames() {
            const container = document.getElementById('games-container');
            if (!container) return;

            const games = Array.from(container.children);

            games.sort((a, b) => {
                if (this.sortBy === 'year') {
                    const yearA = parseInt(a.dataset.year) || 0;
                    const yearB = parseInt(b.dataset.year) || 0;
                    return yearA - yearB;
                } else if (this.sortBy === 'rank') {
                    const rankA = parseInt(a.dataset.rank) || 999999;
                    const rankB = parseInt(b.dataset.rank) || 999999;
                    return rankA - rankB;
                } else if (this.sortBy === 'name') {
                    const nameA = a.dataset.name || '';
                    const nameB = b.dataset.name || '';
                    return nameA.localeCompare(nameB);
                }
                return 0;
            });

            // Re-append in sorted order
            games.forEach(game => container.appendChild(game));
        },

        /**
         * Toggle studio selection (with hierarchical child handling)
         */
        toggleStudio(studioId, childIds) {
            // Create a new Set to trigger Alpine reactivity
            const newSelection = new Set(this.selectedStudioIds);
            // Use shouldBeChecked to determine visual state (includes implicit selection)
            const isChecked = this.shouldBeChecked(studioId, childIds);
            const isIndeterminate = this.isIndeterminate(studioId, childIds);

            // Company (id: 0) is a virtual node - don't add it to selection
            const isCompany = studioId === 0;

            if (isChecked) {
                // Checked → Unchecked: Uncheck studio + all children recursively
                if (!isCompany) newSelection.delete(studioId);
                this.uncheckChildrenInSet(newSelection, childIds);
            } else if (isIndeterminate) {
                // Indeterminate → Checked: Check studio + all children recursively
                if (!isCompany) newSelection.add(studioId);
                this.checkChildrenInSet(newSelection, childIds);
            } else {
                // Unchecked → Checked: Check studio + all children recursively
                if (!isCompany) newSelection.add(studioId);
                this.checkChildrenInSet(newSelection, childIds);
            }

            // Assign new Set to trigger reactivity
            this.selectedStudioIds = newSelection;
            this.updateURL();
            this.updateIndeterminateStates();
        },

        /**
         * Recursively check all child studios in a Set
         */
        checkChildrenInSet(set, childIds) {
            childIds.forEach(childId => {
                set.add(childId);
                const grandchildIds = this.studioChildMap[childId] || [];
                this.checkChildrenInSet(set, grandchildIds);
            });
        },

        /**
         * Recursively uncheck all child studios in a Set
         */
        uncheckChildrenInSet(set, childIds) {
            childIds.forEach(childId => {
                set.delete(childId);
                const grandchildIds = this.studioChildMap[childId] || [];
                this.uncheckChildrenInSet(set, grandchildIds);
            });
        },

        /**
         * Get all descendant IDs for a set of child IDs
         */
        getAllDescendants(childIds) {
            const descendants = new Set();
            childIds.forEach(id => {
                descendants.add(id);
                const grandchildIds = this.studioChildMap[id] || [];
                this.getAllDescendants(grandchildIds).forEach(d => descendants.add(d));
            });
            return descendants;
        },

        /**
         * Check if a studio should appear checked
         * Returns true if explicitly selected OR all children are checked (recursively)
         */
        shouldBeChecked(studioId, childIds) {
            // If explicitly selected, it's checked
            if (this.selectedStudioIds.has(studioId)) return true;

            // If no children, not checked (would need to be explicit)
            if (childIds.length === 0) return false;

            // Check if ALL direct children are checked (recursively)
            for (const childId of childIds) {
                const grandchildIds = this.studioChildMap[childId] || [];
                if (!this.shouldBeChecked(childId, grandchildIds)) {
                    return false;
                }
            }
            return true;
        },

        /**
         * Check if a studio should be in indeterminate state
         * Returns true if some (but not all) children are checked
         */
        isIndeterminate(studioId, childIds) {
            if (childIds.length === 0) return false;

            // Count how many direct children are checked (using recursive shouldBeChecked)
            let checkedCount = 0;
            for (const childId of childIds) {
                const grandchildIds = this.studioChildMap[childId] || [];
                if (this.shouldBeChecked(childId, grandchildIds)) {
                    checkedCount++;
                }
            }

            // Indeterminate if some (but not all) children are checked
            // Also indeterminate if no children are fully checked but some descendants are selected
            if (checkedCount > 0 && checkedCount < childIds.length) {
                return true;
            }

            // Check if any descendants are selected (for partial selection within a child)
            if (checkedCount === 0) {
                const allDescendants = this.getAllDescendants(childIds);
                for (const id of allDescendants) {
                    if (this.selectedStudioIds.has(id)) {
                        return true;
                    }
                }
            }

            return false;
        },

        /**
         * Update indeterminate states for all checkboxes
         * Note: With x-effect in the template, this is now handled reactively by Alpine.js
         * Keeping this method for backwards compatibility but it's no longer needed
         */
        updateIndeterminateStates() {
            // No-op: Alpine.js x-effect handles this now
        },

        /**
         * Update URL hash with current selection
         */
        updateURL() {
            const ids = Array.from(this.selectedStudioIds).sort((a, b) => a - b);
            if (ids.length > 0) {
                window.location.hash = `studios=${ids.join(',')}`;
            } else {
                // Clear hash
                history.replaceState(null, '', window.location.pathname);
            }
        },

        /**
         * Initialize component - parse URL hash for deep linking
         */
        init() {
            // Load data from window globals (set by Django template)
            this.studioGameMap = window.STUDIO_GAME_MAP || {};
            this.studioChildMap = window.STUDIO_CHILD_MAP || {};

            // Parse URL hash for selection state
            const hash = window.location.hash;

            // New format: #studios=1,5,12
            if (hash.startsWith('#studios=')) {
                const ids = hash.slice(9).split(',').map(Number).filter(id => !isNaN(id));
                const newSelection = new Set(ids);
                this.selectedStudioIds = newSelection;
            }

            // Legacy format: #studio-123-game-456 or #studio-123
            else if (hash.match(/^#studio-(\d+)/)) {
                const match = hash.match(/^#studio-(\d+)(?:-game-(\d+))?$/);
                if (match) {
                    const studioId = parseInt(match[1]);
                    const gameId = match[2] ? parseInt(match[2]) : null;

                    // Select the studio and all its children (same as manual click)
                    const newSelection = new Set([studioId]);
                    const childIds = this.studioChildMap[studioId] || [];
                    this.checkChildrenInSet(newSelection, childIds);
                    this.selectedStudioIds = newSelection;

                    // If game ID is present, scroll to and highlight it
                    if (gameId) {
                        this.$nextTick(() => {
                            setTimeout(() => {
                                const gameEl = document.getElementById(`game-${gameId}`);
                                if (gameEl) {
                                    gameEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                    gameEl.classList.add('bg-primary/10', 'rounded-lg');
                                    // Remove highlight after 2 seconds
                                    setTimeout(() => {
                                        gameEl.classList.remove('bg-primary/10');
                                    }, 2000);
                                }
                            }, 100);
                        });
                    }
                }
            }

            // Listen for hash changes (browser back/forward)
            window.addEventListener('hashchange', () => {
                // Re-parse hash when it changes
                const newHash = window.location.hash;
                if (newHash.startsWith('#studios=')) {
                    const ids = newHash.slice(9).split(',').map(Number).filter(id => !isNaN(id));
                    this.selectedStudioIds = new Set(ids);
                } else {
                    this.selectedStudioIds = new Set();
                }
                this.updateIndeterminateStates();
            });

            // Sort games on initial load
            this.$nextTick(() => {
                this.sortGames();
                this.updateIndeterminateStates();
            });
        }
    };
}
