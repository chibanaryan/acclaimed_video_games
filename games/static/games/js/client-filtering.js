/**
 * Acclaimed Games - Client-Side Filtering Integration
 *
 * Integrates GameDataCache, GameFilterEngine, and GameListRenderer
 * with the existing Alpine.js filter component.
 */

/**
 * ClientSideFiltering - Main integration class
 *
 * Usage:
 *   const csf = new ClientSideFiltering();
 *   await csf.init();
 *   csf.applyFilters(filters);
 */
class ClientSideFiltering {
    constructor() {
        this.cache = new GameDataCache();
        this.engine = null;
        this.renderer = null;
        this.isInitialized = false;
        this.isInitializing = false;
        this.initPromise = null;
        this.currentFilters = {};
        this.minYear = 1970;
        this.maxYear = new Date().getFullYear();
        this._hasRenderedUI = false;  // Track if CSF has taken over the UI
        this._viewMode = localStorage.getItem('gameViewMode') || 'list';
    }

    /**
     * Set the view mode (list or grid)
     * @param {string} mode - 'list' or 'grid'
     */
    setViewMode(mode) {
        this._viewMode = mode;
        localStorage.setItem('gameViewMode', mode);
    }

    /**
     * Get the current view mode
     * @returns {string} 'list' or 'grid'
     */
    getViewMode() {
        return this._viewMode;
    }

    /**
     * Initialize client-side filtering
     * Loads data from cache/server and sets up engine and renderer
     *
     * @param {Object} options
     * @param {Function} [options.onLoadStart] - Called when loading starts
     * @param {Function} [options.onLoadComplete] - Called when loading completes
     * @returns {Promise<boolean>} True if initialized successfully
     */
    async init(options = {}) {
        if (this.isInitialized) return true;
        if (this.initPromise) return this.initPromise;

        this.isInitializing = true;

        this.initPromise = (async () => {
            try {
                if (options.onLoadStart) options.onLoadStart();

                const data = await this.cache.getData({
                    onCacheHit: () => console.log('[CSF] Using cached data'),
                    onCacheMiss: () => console.log('[CSF] Fetching fresh data')
                });

                this.engine = new GameFilterEngine(data);
                this.renderer = new GameListRenderer(this.engine);

                // Get year bounds from data
                const bounds = this.engine.getYearBounds();
                this.minYear = bounds.min;
                this.maxYear = bounds.max;

                this.isInitialized = true;
                this.isInitializing = false;

                if (options.onLoadComplete) options.onLoadComplete();

                // Dispatch platform year ranges for filter display
                const platformYearRanges = this.engine.getPlatformYearRanges();
                window.dispatchEvent(new CustomEvent('platform-year-ranges-update', {
                    detail: platformYearRanges
                }));

                // Dispatch unfiltered year counts to reset heatmap baseline
                // This ensures the heatmap uses full data for intensity scaling,
                // even when the page loads with URL filters
                const unfilteredYearCounts = this.engine.getUnfilteredYearCounts();
                const yearCountsArray = [];
                for (let y = this.minYear; y <= this.maxYear; y++) {
                    yearCountsArray.push({ year: y, count: unfilteredYearCounts[y] || 0 });
                }
                window.dispatchEvent(new CustomEvent('year-original-counts-update', {
                    detail: yearCountsArray
                }));

                console.log(`[CSF] Initialized with ${data.games.length} games`);
                return true;
            } catch (e) {
                console.error('[CSF] Initialization failed:', e);
                this.isInitializing = false;
                return false;
            }
        })();

        return this.initPromise;
    }

    /**
     * Apply filters and render results
     *
     * @param {Object} filters - Filter criteria from Alpine.js component
     * @param {Object} options - Render options
     * @returns {Object} Result with total, facets, etc.
     */
    applyFilters(filters, options = {}) {
        if (!this.isInitialized) {
            console.warn('[CSF] Not initialized, cannot filter');
            return null;
        }

        this.currentFilters = filters;

        // Convert Alpine filter format to engine format (single-select, always use 'any')
        // Parse HLTB filters with default min=0 when max is set
        let hltb_min = filters.hltb_min !== undefined ? filters.hltb_min : null;
        let hltb_max = filters.hltb_max !== undefined ? filters.hltb_max : null;

        // Ensure non-negative values
        if (hltb_min !== null && hltb_min < 0) {
            hltb_min = 0;
        }
        if (hltb_max !== null && hltb_max < 0) {
            hltb_max = 0;
        }

        // If max is set but min is not, default min to 0
        if (hltb_max !== null && hltb_min === null) {
            hltb_min = 0;
        }

        // Ensure max >= min (if both are set)
        if (hltb_min !== null && hltb_max !== null) {
            if (hltb_max < hltb_min) {
                hltb_max = hltb_min;
            }
        }

        const engineFilters = {
            q: filters.q || '',
            genres: (filters.genres || []).map(id => parseInt(id, 10)),
            genreOption: 'any',  // Single-select mode always uses 'any'
            platforms: (filters.platforms || []).map(id => parseInt(id, 10)),
            series: (filters.series || []).map(id => parseInt(id, 10)),
            start: filters.start || null,
            end: filters.end || null,
            sort: filters.sort || 'rank',
            sortDirection: filters.sortDirection || 'asc',
            played: filters.played || '',
            hltb_mode: filters.hltb_mode || 'main',
            hltb_min: hltb_min,
            hltb_max: hltb_max
        };

        // Apply filters
        const result = this.engine.filter(engineFilters);

        return result;
    }

    /**
     * Render filtered results to container
     *
     * @param {Object} filterResult - Result from applyFilters()
     * @param {HTMLElement} gameListContainer - Container for game rows
     * @param {Object} options
     * @returns {Object} Render state for Load More
     */
    renderResults(filterResult, gameListContainer, options = {}) {
        if (!this.isInitialized || !filterResult) return null;

        const {
            highlightId = null,
            showRank = 'filtered'
        } = options;

        // Mark that CSF has taken over UI rendering
        this._hasRenderedUI = true;

        // Clear and render new results with current view mode
        this.renderer.render(filterResult.games, gameListContainer, {
            showRank,
            highlightId,
            viewMode: this._viewMode
        });

        const loaded = Math.min(100, filterResult.total);
        const hasMore = filterResult.total > loaded && loaded < 1000;

        return {
            total: filterResult.total,
            loaded,
            hasMore,
            remaining: Math.min(filterResult.total - loaded, 1000 - loaded),
            maxLoaded: loaded >= 1000,
            facets: filterResult.facets
        };
    }

    /**
     * Load more results
     *
     * @param {HTMLElement} gameListContainer - Container for game rows
     * @param {Object} options - Options including showRank
     * @returns {Object} Updated state
     */
    loadMore(gameListContainer, options = {}) {
        if (!this.isInitialized) return null;

        const { showRank = 'filtered' } = options;

        return this.renderer.loadMore(gameListContainer, {
            showRank
        });
    }

    /**
     * Update DOM with filter results
     * This is the main entry point called from Alpine.js
     *
     * @param {Object} filters - Filters from Alpine component
     * @param {Object} elements - DOM element references
     */
    updateUI(filters, elements) {
        const {
            gameListContainer,
            countContainer,
            loadMoreContainer,
            highlightId
        } = elements;

        const result = this.applyFilters(filters);
        if (!result) return null;

        const state = this.renderResults(result, gameListContainer, {
            highlightId,
            showRank: this._computeShowRank()
        });

        // Update count display
        if (countContainer) {
            countContainer.innerHTML = this.renderer.getResultSummaryHtml(state.loaded, state.total);
        }

        // Update Load More button
        if (loadMoreContainer) {
            loadMoreContainer.innerHTML = this.renderer.getLoadMoreHtml(state);
            this._initLoadMoreButton(loadMoreContainer, gameListContainer, countContainer);
        }

        return {
            total: state.total,
            facets: state.facets
        };
    }

    /**
     * Compute whether to show filtered or alltime rank based on URL params
     * @private
     * @returns {string} 'filtered' or 'alltime'
     */
    _computeShowRank() {
        const params = new URLSearchParams(window.location.search);

        // Check simple filters
        if (params.get('q')) return 'filtered';
        if (params.get('genres')) return 'filtered';
        if (params.get('platforms')) return 'filtered';
        if (params.get('series')) return 'filtered';
        if (params.get('played')) return 'filtered';
        // Note: sort and sortDirection are intentionally NOT checked here
        // Sorting changes the order but doesn't filter games, so it shouldn't
        // affect whether we show the rank distribution

        // Check year/decade filters
        if (params.get('year') || params.get('decade')) return 'filtered';

        // Check start/end year bounds
        const bounds = this.getYearBounds();
        const start = params.get('start') ? parseInt(params.get('start')) : null;
        const end = params.get('end') ? parseInt(params.get('end')) : null;
        if (start && start > bounds.min) return 'filtered';
        if (end && end < bounds.max) return 'filtered';

        // Check HLTB filters (only if they narrow the range from defaults)
        // Default range is 0 to ∞, so only filter if min > 0 or max is explicitly set
        const hltb_min_str = params.get('hltb_min');
        const hltb_max_str = params.get('hltb_max');
        const hltb_min = hltb_min_str ? parseInt(hltb_min_str) : null;
        const hltb_max = (hltb_max_str && hltb_max_str !== 'unlimited') ? parseInt(hltb_max_str) : null;
        if (hltb_min && hltb_min > 0) return 'filtered';
        if (hltb_max !== null && !isNaN(hltb_max)) return 'filtered';

        return 'alltime';
    }

    /**
     * Initialize Load More button click handler
     * @private
     */
    _initLoadMoreButton(loadMoreContainer, gameListContainer, countContainer) {
        const button = loadMoreContainer.querySelector('.load-more-button');
        if (!button) return;

        button.addEventListener('click', () => {
            button.classList.add('loading');
            button.disabled = true;

            // Compute showRank at click time based on current URL params
            const showRank = this._computeShowRank();
            const state = this.loadMore(gameListContainer, { showRank });

            // Update count
            if (countContainer) {
                countContainer.innerHTML = this.renderer.getResultSummaryHtml(state.loaded, state.total);
            }

            // Update or replace Load More button
            loadMoreContainer.innerHTML = this.renderer.getLoadMoreHtml({
                hasMore: state.hasMore,
                remaining: state.remaining,
                maxLoaded: state.loaded >= 1000
            });

            if (state.hasMore) {
                this._initLoadMoreButton(loadMoreContainer, gameListContainer, countContainer);
            }
        });

        // Randomize icon on hover
        button.addEventListener('mouseenter', () => {
            const icons = ['mdi-gamepad-variant', 'mdi-controller', 'mdi-controller-classic', 'mdi-pac-man', 'mdi-space-invaders', 'mdi-run-fast', 'mdi-power'];
            const iconSpan = button.querySelector('.icon .mdi');
            if (iconSpan) {
                iconSpan.classList.remove('mdi-plus-circle-outline');
                icons.forEach(cls => iconSpan.classList.remove(cls));
                const randomIcon = icons[Math.floor(Math.random() * icons.length)];
                iconSpan.classList.add(randomIcon);
            }
        });
    }

    /**
     * Get year bounds from loaded data
     * @returns {Object} {min, max}
     */
    getYearBounds() {
        return {
            min: this.minYear,
            max: this.maxYear
        };
    }

    /**
     * Check if client-side filtering is available
     * @returns {boolean}
     */
    isReady() {
        return this.isInitialized;
    }

    /**
     * Check if CSF has taken over UI rendering
     * (i.e., CSF has actively rendered the page, not just loaded data)
     * @returns {boolean}
     */
    hasRenderedUI() {
        return this._hasRenderedUI;
    }

    /**
     * Force refresh from server
     */
    async refresh() {
        this.isInitialized = false;
        this.initPromise = null;
        await this.cache.clearCache();
        return this.init();
    }
}

// Global instance
let _clientSideFiltering = null;

/**
 * Get or create the global ClientSideFiltering instance
 * @returns {ClientSideFiltering}
 */
function getClientSideFiltering() {
    if (!_clientSideFiltering) {
        _clientSideFiltering = new ClientSideFiltering();
    }
    return _clientSideFiltering;
}

// Export for use in templates
if (typeof window !== 'undefined') {
    window.ClientSideFiltering = ClientSideFiltering;
    window.getClientSideFiltering = getClientSideFiltering;
}
