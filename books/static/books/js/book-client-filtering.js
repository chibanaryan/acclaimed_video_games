/**
 * Acclaimed Books - Client-Side Filtering Integration
 *
 * Integrates BookDataCache, BookFilterEngine, and BookListRenderer
 * with the existing Alpine.js filter component.
 */

/**
 * BookClientSideFiltering - Main integration class
 *
 * Usage:
 *   const csf = new BookClientSideFiltering();
 *   await csf.init();
 *   csf.applyFilters(filters);
 */
class BookClientSideFiltering {
    constructor() {
        this.cache = new BookDataCache();
        this.engine = null;
        this.renderer = null;
        this.isInitialized = false;
        this.isInitializing = false;
        this.initPromise = null;
        this.currentFilters = {};
        this.minYear = 1800;
        this.maxYear = new Date().getFullYear();
        this._hasRenderedUI = false;  // Track if CSF has taken over the UI
        this._viewMode = localStorage.getItem('bookViewMode') || 'list';
    }

    /**
     * Set the view mode (list or grid)
     * @param {string} mode - 'list' or 'grid'
     */
    setViewMode(mode) {
        this._viewMode = mode;
        localStorage.setItem('bookViewMode', mode);
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
                    onCacheHit: () => console.log('[BookCSF] Using cached data'),
                    onCacheMiss: () => console.log('[BookCSF] Fetching fresh data')
                });

                this.engine = new BookFilterEngine(data);
                this.renderer = new BookListRenderer(this.engine);

                // Get year bounds from data
                const bounds = this.engine.getYearBounds();
                this.minYear = bounds.min;
                this.maxYear = bounds.max;

                this.isInitialized = true;
                this.isInitializing = false;

                if (options.onLoadComplete) options.onLoadComplete();

                // Dispatch unfiltered year counts to reset heatmap baseline
                const unfilteredYearCounts = this.engine.getUnfilteredYearCounts();
                const yearCountsArray = [];
                for (let y = this.minYear; y <= this.maxYear; y++) {
                    yearCountsArray.push({ year: y, count: unfilteredYearCounts[y] || 0 });
                }
                window.dispatchEvent(new CustomEvent('year-original-counts-update', {
                    detail: yearCountsArray
                }));

                console.log(`[BookCSF] Initialized with ${data.books.length} books`);
                return true;
            } catch (e) {
                console.error('[BookCSF] Initialization failed:', e);
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
            console.warn('[BookCSF] Not initialized, cannot filter');
            return null;
        }

        this.currentFilters = filters;

        // Convert Alpine filter format to engine format
        const engineFilters = {
            q: filters.q || '',
            genres: (filters.genres || []).map(id => parseInt(id, 10)),
            genreOption: filters.genreOption || 'any',
            authors: (filters.authors || []).map(id => parseInt(id, 10)),
            start: filters.start || null,
            end: filters.end || null,
            sort: filters.sort || 'rank',
            sortDirection: filters.sortDirection || 'asc',
            read: filters.read || ''
        };

        // Apply filters
        const result = this.engine.filter(engineFilters);

        return result;
    }

    /**
     * Render filtered results to container
     *
     * @param {Object} filterResult - Result from applyFilters()
     * @param {HTMLElement} bookListContainer - Container for book rows
     * @param {Object} options
     * @returns {Object} Render state for Load More
     */
    renderResults(filterResult, bookListContainer, options = {}) {
        if (!this.isInitialized || !filterResult) return null;

        const {
            highlightId = null,
            showRank = 'filtered'
        } = options;

        // Mark that CSF has taken over UI rendering
        this._hasRenderedUI = true;

        // Clear and render new results with current view mode
        this.renderer.render(filterResult.books, bookListContainer, {
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
     * @param {HTMLElement} bookListContainer - Container for book rows
     * @param {Object} options - Options including showRank
     * @returns {Object} Updated state
     */
    loadMore(bookListContainer, options = {}) {
        if (!this.isInitialized) return null;

        const { showRank = 'filtered' } = options;

        return this.renderer.loadMore(bookListContainer, {
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
            bookListContainer,
            countContainer,
            loadMoreContainer,
            highlightId
        } = elements;

        const result = this.applyFilters(filters);
        if (!result) return null;

        const state = this.renderResults(result, bookListContainer, {
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
            this._initLoadMoreButton(loadMoreContainer, bookListContainer, countContainer);
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
        if (params.get('authors')) return 'filtered';
        if (params.get('read')) return 'filtered';

        // Check year/decade filters
        if (params.get('year') || params.get('decade')) return 'filtered';

        // Check start/end year bounds
        const bounds = this.getYearBounds();
        const start = params.get('start') ? parseInt(params.get('start')) : null;
        const end = params.get('end') ? parseInt(params.get('end')) : null;
        if (start && start > bounds.min) return 'filtered';
        if (end && end < bounds.max) return 'filtered';

        return 'alltime';
    }

    /**
     * Initialize Load More button click handler
     * @private
     */
    _initLoadMoreButton(loadMoreContainer, bookListContainer, countContainer) {
        const button = loadMoreContainer.querySelector('.load-more-button');
        if (!button) return;

        button.addEventListener('click', () => {
            button.classList.add('loading');
            button.disabled = true;

            // Compute showRank at click time based on current URL params
            const showRank = this._computeShowRank();
            const state = this.loadMore(bookListContainer, { showRank });

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
                this._initLoadMoreButton(loadMoreContainer, bookListContainer, countContainer);
            }
        });

        // Randomize icon on hover (book-themed icons)
        button.addEventListener('mouseenter', () => {
            const icons = ['mdi-book-open-page-variant', 'mdi-book', 'mdi-bookshelf', 'mdi-library', 'mdi-book-open', 'mdi-book-multiple'];
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
let _bookClientSideFiltering = null;

/**
 * Get or create the global BookClientSideFiltering instance
 * @returns {BookClientSideFiltering}
 */
function getBookClientSideFiltering() {
    if (!_bookClientSideFiltering) {
        _bookClientSideFiltering = new BookClientSideFiltering();
    }
    return _bookClientSideFiltering;
}

// Export for use in templates
if (typeof window !== 'undefined') {
    window.BookClientSideFiltering = BookClientSideFiltering;
    window.getBookClientSideFiltering = getBookClientSideFiltering;
}
