/**
 * Alpine.js component for developer filtering on developer detail pages
 * Provides client-side filtering with hierarchical checkbox selection
 */
function developerFilter() {
    return {
        // State
        selectedDeveloperIds: new Set(),
        sortBy: 'year', // 'year', 'rank', or 'name'
        showMobileFilters: false, // Controls mobile filter modal

        // Data loaded from Django context via window globals
        developerGameMap: {},
        developerChildMap: {},
        developerNameMap: {},
        gameRankMap: {},
        rootDeveloperName: '',

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
         * Calculate rank distribution for currently visible games
         * Returns { top_100: n, top_500: n, top_1000: n, beyond: n, top_100_pct: n, ... }
         * Percentages use TOTAL games (not filtered) as denominator for consistent scale
         */
        getRankDistribution() {
            const visibleGameIds = this.getVisibleGameIds();
            const dist = { top_100: 0, top_500: 0, top_1000: 0, beyond: 0 };

            for (const gameId of visibleGameIds) {
                const rank = this.gameRankMap[gameId];
                if (rank && rank <= 100) {
                    dist.top_100++;
                } else if (rank && rank <= 500) {
                    dist.top_500++;
                } else if (rank && rank <= 1000) {
                    dist.top_1000++;
                } else if (rank) {
                    dist.beyond++;
                }
            }

            // Use TOTAL games (not filtered) as denominator for consistent bar scale
            // This means bars shrink when filtering, showing absolute reduction
            const totalGames = Object.keys(this.gameRankMap).length || 1;
            dist.top_100_pct = Math.round(dist.top_100 / totalGames * 100);
            dist.top_500_pct = Math.round(dist.top_500 / totalGames * 100);
            dist.top_1000_pct = Math.round(dist.top_1000 / totalGames * 100);
            dist.beyond_pct = Math.round(dist.beyond / totalGames * 100);

            return dist;
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
         * Initialize component - parse URL hash for deep linking
         */
        init() {
            // Load data from window globals (set by Django template)
            this.developerGameMap = window.DEVELOPER_GAME_MAP || {};
            this.developerChildMap = window.DEVELOPER_CHILD_MAP || {};
            this.developerNameMap = window.DEVELOPER_NAME_MAP || {};
            this.gameRankMap = window.GAME_RANK_MAP || {};
            this.rootDeveloperName = window.ROOT_DEVELOPER_NAME || '';

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
            window.addEventListener('hashchange', () => {
                // Re-parse hash when it changes
                const newHash = window.location.hash;
                if (newHash.startsWith('#developers=')) {
                    const ids = newHash.slice(12).split(',').map(Number).filter(id => !isNaN(id));
                    this.selectedDeveloperIds = new Set(ids);
                } else {
                    this.selectedDeveloperIds = new Set();
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
