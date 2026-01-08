/**
 * Alpine.js component for developer filtering on developer detail pages
 * Provides client-side filtering with hierarchical checkbox selection
 */

// Explicit cleanup before HTMX swaps to ensure destroy() is called
// (Alpine's destroy hook may not fire reliably during HTMX swaps)
if (typeof window._developerFilterHtmxCleanupInitialized === 'undefined') {
    window._developerFilterHtmxCleanupInitialized = true;
    document.addEventListener('htmx:beforeSwap', (e) => {
        const swapTarget = e.detail.target;
        if (!swapTarget) return;

        const filterEl = swapTarget.matches('[x-data*="developerFilter"]')
            ? swapTarget
            : swapTarget.querySelector('[x-data*="developerFilter"]');

        if (filterEl && typeof Alpine !== 'undefined') {
            const component = Alpine.$data(filterEl);
            if (component && typeof component.destroy === 'function') {
                component.destroy();
            }
        }
    });
}

function developerFilter() {
    return {
        // State
        selectedDeveloperIds: new Set(),
        sortBy: 'rank', // 'rank', 'year', 'name', or 'playtime'
        sortDirection: 'asc', // 'asc' or 'desc'
        showMobileFilters: false, // Controls mobile filter modal

        // Data loaded from Django context via window globals
        developerGameMap: {},
        developerChildMap: {},
        developerNameMap: {},
        developerIgdbUrlMap: {},
        gameRankMap: {},
        gameMap: new Map(),  // Map of game ID -> game data with playtime
        rootDeveloperName: '',
        rootIgdbUrl: '',

        /**
         * Check if a game should be visible based on selected developers
         */
        gameIsVisible(gameId) {
            // If no developers selected, show all games
            if (this.selectedDeveloperIds.size === 0) {
                return true;
            }

            // Ensure gameId is a number for consistent comparison
            const gameIdNum = typeof gameId === 'number' ? gameId : parseInt(gameId);

            // Check if game belongs to any selected developer
            for (const developerId of this.selectedDeveloperIds) {
                const gameIds = this.developerGameMap[developerId] || [];
                // Check both number and string versions for safety
                if (gameIds.includes(gameIdNum) || gameIds.includes(gameId)) {
                    return true;
                }
            }

            return false;
        },

        /**
         * Count selected developers (includes root node when selected)
         */
        countSelectedDevelopers() {
            return this.selectedDeveloperIds.size;
        },

        /**
         * Count how many games are currently visible
         */
        countVisibleGames() {
            if (this.selectedDeveloperIds.size === 0) {
                // Count all games in DOM
                return document.querySelectorAll('#games-container > div').length;
            }

            // Count visible games
            const allGameIds = new Set();
            for (const developerId of this.selectedDeveloperIds) {
                const gameIds = this.developerGameMap[developerId] || [];
                gameIds.forEach(id => allGameIds.add(id));
            }
            return allGameIds.size;
        },

        /**
         * Get visible game IDs based on current filter
         */
        getVisibleGameIds() {
            if (this.selectedDeveloperIds.size === 0) {
                // All games - return all game IDs from gameRankMap
                return Object.keys(this.gameRankMap).map(Number);
            }

            // Get game IDs from selected developers
            const allGameIds = new Set();
            for (const developerId of this.selectedDeveloperIds) {
                const gameIds = this.developerGameMap[developerId] || [];
                gameIds.forEach(id => allGameIds.add(id));
            }
            return Array.from(allGameIds);
        },

        /**
         * Dispatch rank distribution update event for the SVG chart component
         * Uses 10 bins of 100 ranks each (same format as games list page)
         */
        dispatchRankDistribution() {
            const visibleGameIds = this.getVisibleGameIds();
            const bins = [];
            const binSize = 100;

            for (let i = 0; i < 10; i++) {
                const binStart = i * binSize + 1;
                const binEnd = (i + 1) * binSize;
                let count = 0;
                for (const gameId of visibleGameIds) {
                    const rank = this.gameRankMap[gameId];
                    if (rank && rank >= binStart && rank <= binEnd) {
                        count++;
                    }
                }
                bins.push({ binStart, binEnd, count });
            }

            window.dispatchEvent(new CustomEvent('rank-distribution-update', { detail: bins }));
        },

        /**
         * Get dynamic page title based on selected developers
         * Detects if there's a single "top-level" selection (a developer + all its descendants)
         */
        getDynamicTitle() {
            const count = this.selectedDeveloperIds.size;

            // Nothing selected - show root name
            if (count === 0) {
                return this.rootDeveloperName;
            }

            // Find the effective selection - the highest node that accounts for all selections
            const effectiveSelection = this.getEffectiveSelection();

            if (effectiveSelection !== null) {
                const name = this.developerNameMap[effectiveSelection] || this.rootDeveloperName;
                // If root (id 0) or name matches root, just show root name
                if (effectiveSelection === 0 || name === this.rootDeveloperName) {
                    return this.rootDeveloperName;
                }
                return `${name} (${this.rootDeveloperName})`;
            }

            // Multiple top-level selections - show count
            return `${this.rootDeveloperName} (${count} developers selected)`;
        },

        /**
         * Get the IGDB URL for the currently selected developer(s)
         * Returns URL if exactly one developer is effectively selected, null otherwise
         */
        getIgdbUrl() {
            // Nothing selected - show root developer's URL
            if (this.selectedDeveloperIds.size === 0) {
                return this.rootIgdbUrl || null;
            }

            // Find the effective selection
            const effectiveSelection = this.getEffectiveSelection();

            if (effectiveSelection !== null) {
                // If root (id 0), use root URL
                if (effectiveSelection === 0) {
                    return this.rootIgdbUrl || null;
                }
                // Otherwise, look up the URL for this developer
                return this.developerIgdbUrlMap[effectiveSelection] || null;
            }

            // Multiple selections - no single URL to show
            return null;
        },

        /**
         * Get the name of the developer for the IGDB link
         * Follows same logic as getDynamicTitle to determine which developer is selected
         */
        getIgdbDeveloperName() {
            // Nothing selected - show root developer's name
            if (this.selectedDeveloperIds.size === 0) {
                return this.rootDeveloperName;
            }

            // Find the effective selection (same logic as getDynamicTitle)
            const effectiveSelection = this.getEffectiveSelection();

            if (effectiveSelection !== null) {
                // If root (id 0), use root name
                if (effectiveSelection === 0) {
                    return this.rootDeveloperName;
                }
                // Otherwise, look up the name for this developer
                return this.developerNameMap[effectiveSelection] || this.rootDeveloperName;
            }

            // Multiple selections - no single developer
            return null;
        },

        /**
         * Find the single top-level selection if one exists
         * Returns the developer ID if exactly one developer + all its descendants are selected
         * Returns null if multiple independent selections exist or descendants are partially selected
         */
        getEffectiveSelection() {
            if (this.selectedDeveloperIds.size === 0) return null;

            // Find selected developers that have no selected ancestors (top-level selections)
            const topLevelSelections = [];

            for (const selectedId of this.selectedDeveloperIds) {
                let hasSelectedAncestor = false;

                // Check if any other selected developer is an ancestor of this one
                for (const otherId of this.selectedDeveloperIds) {
                    if (otherId !== selectedId && this.isAncestorOf(otherId, selectedId)) {
                        hasSelectedAncestor = true;
                        break;
                    }
                }

                if (!hasSelectedAncestor) {
                    topLevelSelections.push(selectedId);
                }
            }

            // If exactly one top-level selection, verify all its descendants are selected
            if (topLevelSelections.length === 1) {
                const topId = topLevelSelections[0];
                if (this.allDescendantsSelected(topId)) {
                    return topId;
                }
            }

            return null;
        },

        /**
         * Check if all descendants of a developer are selected
         */
        allDescendantsSelected(developerId) {
            const children = this.developerChildMap[developerId] || [];
            for (const childId of children) {
                if (!this.selectedDeveloperIds.has(childId)) {
                    return false;
                }
                if (!this.allDescendantsSelected(childId)) {
                    return false;
                }
            }
            return true;
        },

        /**
         * Check if ancestorId is an ancestor of descendantId
         */
        isAncestorOf(ancestorId, descendantId) {
            const children = this.developerChildMap[ancestorId] || [];
            if (children.includes(descendantId)) return true;

            // Check recursively
            for (const childId of children) {
                if (this.isAncestorOf(childId, descendantId)) return true;
            }
            return false;
        },

        /**
         * Sort games in the DOM based on current sortBy value and sortDirection
         */
        sortGames() {
            const container = document.getElementById('games-container');
            if (!container) return;

            const games = Array.from(container.children);
            const isDesc = this.sortDirection === 'desc';

            games.sort((a, b) => {
                if (this.sortBy === 'rank') {
                    const rankA = parseInt(a.dataset.rank) || 999999;
                    const rankB = parseInt(b.dataset.rank) || 999999;
                    const diff = rankA - rankB;
                    return isDesc ? -diff : diff;
                } else if (this.sortBy === 'year') {
                    const yearA = parseInt(a.dataset.year) || 0;
                    const yearB = parseInt(b.dataset.year) || 0;
                    const diff = yearA - yearB;
                    if (diff !== 0) return isDesc ? -diff : diff;
                    return parseInt(a.dataset.rank) - parseInt(b.dataset.rank);  // Secondary sort by rank
                } else if (this.sortBy === 'name') {
                    const nameA = a.dataset.name || '';
                    const nameB = b.dataset.name || '';
                    const diff = nameA.localeCompare(nameB);
                    return isDesc ? -diff : diff;
                } else if (this.sortBy === 'playtime') {
                    const gameA = this.gameMap.get(parseInt(a.dataset.gameId));
                    const gameB = this.gameMap.get(parseInt(b.dataset.gameId));

                    if (!gameA || !gameB) return 0;

                    const aTime = gameA.pt;  // Main story hours
                    const bTime = gameB.pt;

                    // Hide games without playtime data (sort to end)
                    if (aTime === null && bTime === null) return 0;
                    if (aTime === null) return 1;
                    if (bTime === null) return -1;

                    const diff = aTime - bTime;
                    return isDesc ? -diff : diff;
                }
                return 0;
            });

            // Re-append in sorted order
            games.forEach(game => container.appendChild(game));
        },

        /**
         * Toggle developer selection (with hierarchical child handling)
         */
        toggleDeveloper(developerId, childIds) {
            // Create a new Set to trigger Alpine reactivity
            const newSelection = new Set(this.selectedDeveloperIds);
            // Use shouldBeChecked to determine visual state (includes implicit selection)
            const isChecked = this.shouldBeChecked(developerId, childIds);
            const isIndeterminate = this.isIndeterminate(developerId, childIds);

            // Root developer (id: 0) stores root's direct games (not all games)
            // So ID 0 should be included in selection like any other developer

            if (isChecked) {
                // Checked → Unchecked: Uncheck developer + all children recursively
                newSelection.delete(developerId);
                this.uncheckChildrenInSet(newSelection, childIds);
            } else if (isIndeterminate) {
                // Indeterminate → Checked: Check developer + all children recursively
                newSelection.add(developerId);
                this.checkChildrenInSet(newSelection, childIds);
            } else {
                // Unchecked → Checked: Check developer + all children recursively
                newSelection.add(developerId);
                this.checkChildrenInSet(newSelection, childIds);
            }

            // Assign new Set to trigger reactivity
            this.selectedDeveloperIds = newSelection;
            this.updateURL();
            this.updateIndeterminateStates();
            this.dispatchRankDistribution();
        },

        /**
         * Recursively check all child developers in a Set
         */
        checkChildrenInSet(set, childIds) {
            childIds.forEach(childId => {
                set.add(childId);
                const grandchildIds = this.developerChildMap[childId] || [];
                this.checkChildrenInSet(set, grandchildIds);
            });
        },

        /**
         * Recursively uncheck all child developers in a Set
         */
        uncheckChildrenInSet(set, childIds) {
            childIds.forEach(childId => {
                set.delete(childId);
                const grandchildIds = this.developerChildMap[childId] || [];
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
                const grandchildIds = this.developerChildMap[id] || [];
                this.getAllDescendants(grandchildIds).forEach(d => descendants.add(d));
            });
            return descendants;
        },

        /**
         * Check if a developer should appear checked
         * Returns true if explicitly selected OR all children are checked (recursively)
         */
        shouldBeChecked(developerId, childIds) {
            // If explicitly selected, it's checked
            if (this.selectedDeveloperIds.has(developerId)) return true;

            // If no children, not checked (would need to be explicit)
            if (childIds.length === 0) return false;

            // Check if ALL direct children are checked (recursively)
            for (const childId of childIds) {
                const grandchildIds = this.developerChildMap[childId] || [];
                if (!this.shouldBeChecked(childId, grandchildIds)) {
                    return false;
                }
            }
            return true;
        },

        /**
         * Check if a developer should be in indeterminate state
         * Returns true if some (but not all) children are checked
         */
        isIndeterminate(developerId, childIds) {
            if (childIds.length === 0) return false;

            // Count how many direct children are checked (using recursive shouldBeChecked)
            let checkedCount = 0;
            for (const childId of childIds) {
                const grandchildIds = this.developerChildMap[childId] || [];
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
                    if (this.selectedDeveloperIds.has(id)) {
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
         * Scroll to and highlight a game element
         */
        scrollToGame(gameId) {
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
        },

        /**
         * Update URL hash with current selection
         */
        updateURL() {
            const ids = Array.from(this.selectedDeveloperIds).sort((a, b) => a - b);
            if (ids.length > 0) {
                window.location.hash = `developers=${ids.join(',')}`;
            } else {
                // Clear hash
                history.replaceState(null, '', window.location.pathname);
            }
        },

        /**
         * Cleanup method for memory leak prevention
         */
        destroy() {
            if (this._hashchangeListener) {
                window.removeEventListener('hashchange', this._hashchangeListener);
            }
        },

        /**
         * Initialize component - parse URL hash for deep linking
         */
        init() {
            // Load data from window globals (set by Django template)
            this.developerGameMap = window.DEVELOPER_GAME_MAP || {};
            this.developerChildMap = window.DEVELOPER_CHILD_MAP || {};
            this.developerNameMap = window.DEVELOPER_NAME_MAP || {};
            this.developerIgdbUrlMap = window.DEVELOPER_IGDB_URL_MAP || {};
            this.gameRankMap = window.GAME_RANK_MAP || {};
            this.rootDeveloperName = window.ROOT_DEVELOPER_NAME || '';
            this.rootIgdbUrl = window.ROOT_DEVELOPER_IGDB_URL || '';

            // Initialize game data map for playtime sorting
            const gameDataMap = window.GAME_DATA_MAP || {};
            this.gameMap = new Map(Object.entries(gameDataMap).map(([id, data]) => [parseInt(id), data]));

            // Parse URL hash for selection state
            const hash = window.location.hash;

            // New format: #developers=1,5,12
            if (hash.startsWith('#developers=')) {
                const ids = hash.slice(12).split(',').map(Number).filter(id => !isNaN(id));
                const newSelection = new Set(ids);
                this.selectedDeveloperIds = newSelection;
            }

            // Legacy format: #developer-123-game-456 or #developer-123
            else if (hash.match(/^#developer-(\d+)/)) {
                const match = hash.match(/^#developer-(\d+)(?:-game-(\d+))?$/);
                if (match) {
                    const developerId = parseInt(match[1]);
                    const gameId = match[2] ? parseInt(match[2]) : null;

                    // Select the developer and all its children (same as manual click)
                    const newSelection = new Set([developerId]);
                    const childIds = this.developerChildMap[developerId] || [];
                    this.checkChildrenInSet(newSelection, childIds);
                    this.selectedDeveloperIds = newSelection;

                    // If game ID is present, scroll to and highlight it
                    if (gameId) {
                        this.scrollToGame(gameId);
                    }
                }
            }

            // Game-only format: #game-123 (highlight without filtering)
            else if (hash.match(/^#game-(\d+)$/)) {
                const match = hash.match(/^#game-(\d+)$/);
                if (match) {
                    const gameId = parseInt(match[1]);
                    this.scrollToGame(gameId);
                }
            }

            // Listen for hash changes (browser back/forward)
            // Store reference for cleanup in destroy() to prevent memory leaks
            this._hashchangeListener = () => {
                // Re-parse hash when it changes
                const newHash = window.location.hash;
                if (newHash.startsWith('#developers=')) {
                    const ids = newHash.slice(12).split(',').map(Number).filter(id => !isNaN(id));
                    this.selectedDeveloperIds = new Set(ids);
                } else {
                    this.selectedDeveloperIds = new Set();
                }
                this.updateIndeterminateStates();
                this.dispatchRankDistribution();
            };
            window.addEventListener('hashchange', this._hashchangeListener);

            // Sort games on initial load and initialize chart
            this.$nextTick(() => {
                this.sortGames();
                this.updateIndeterminateStates();
                // Always dispatch rank distribution to ensure chart is in sync
                // (chart may have server-rendered data, but this ensures consistency)
                this.dispatchRankDistribution();
            });
        }
    };
}
