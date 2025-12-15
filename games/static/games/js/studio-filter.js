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
            const isSelected = newSelection.has(studioId);
            const isIndeterminate = !isSelected && this.isIndeterminate(studioId, childIds);

            if (isSelected) {
                // Checked → Unchecked: Uncheck studio + all children recursively
                newSelection.delete(studioId);
                this.uncheckChildrenInSet(newSelection, childIds);
            } else if (isIndeterminate) {
                // Indeterminate → Checked: Check studio + all children recursively
                newSelection.add(studioId);
                this.checkChildrenInSet(newSelection, childIds);
            } else {
                // Unchecked → Checked: Check studio + all children recursively
                newSelection.add(studioId);
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
         * Select all studios
         */
        selectAll() {
            // Create a new Set to trigger Alpine reactivity
            const allIds = new Set();
            Object.keys(this.studioChildMap).forEach(id => {
                allIds.add(parseInt(id));
            });
            this.selectedStudioIds = allIds;
            this.updateURL();
            this.updateIndeterminateStates();
        },

        /**
         * Clear all selections
         */
        clearAll() {
            // Create a new empty Set to trigger Alpine reactivity
            this.selectedStudioIds = new Set();
            this.updateURL();
            this.updateIndeterminateStates();
        },

        /**
         * Check if a studio should be in indeterminate state
         * Returns true if some (but not all) descendants are selected
         */
        isIndeterminate(studioId, childIds) {
            if (childIds.length === 0) return false;

            // Get all descendant IDs (children + their descendants recursively)
            const getAllDescendants = (ids) => {
                const descendants = new Set();
                ids.forEach(id => {
                    descendants.add(id);
                    const grandchildIds = this.studioChildMap[id] || [];
                    getAllDescendants(grandchildIds).forEach(d => descendants.add(d));
                });
                return descendants;
            };

            const allDescendants = getAllDescendants(childIds);
            if (allDescendants.size === 0) return false;

            // Count how many descendants are selected
            let selectedCount = 0;
            allDescendants.forEach(id => {
                if (this.selectedStudioIds.has(id)) {
                    selectedCount++;
                }
            });

            // Indeterminate if some (but not all) descendants are selected
            return selectedCount > 0 && selectedCount < allDescendants.size;
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
