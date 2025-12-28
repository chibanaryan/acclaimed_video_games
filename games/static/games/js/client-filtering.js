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
        const engineFilters = {
            q: filters.q || '',
            genres: (filters.genres || []).map(id => parseInt(id, 10)),
            genreOption: 'any',  // Single-select mode always uses 'any'
            platforms: (filters.platforms || []).map(id => parseInt(id, 10)),
            start: filters.start || null,
            end: filters.end || null,
            sort: filters.sort || 'rank'
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

        // Clear and render new results
        this.renderer.render(filterResult.games, gameListContainer, {
            showRank,
            highlightId
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
     * @returns {Object} Updated state
     */
    loadMore(gameListContainer) {
        if (!this.isInitialized) return null;

        return this.renderer.loadMore(gameListContainer, {
            showRank: 'filtered'
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
            showRank: 'filtered'
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
     * Initialize Load More button click handler
     * @private
     */
    _initLoadMoreButton(loadMoreContainer, gameListContainer, countContainer) {
        const button = loadMoreContainer.querySelector('.load-more-button');
        if (!button) return;

        button.addEventListener('click', () => {
            button.classList.add('loading');
            button.disabled = true;

            const state = this.loadMore(gameListContainer);

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
