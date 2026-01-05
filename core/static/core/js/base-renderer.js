/**
 * Base Media List Renderer - Client-Side Rendering Foundation
 *
 * Provides shared functionality for rendering media lists (games, books, etc.)
 * using DOM template cloning. Concrete renderers should extend this class.
 *
 * This ensures a single source of truth for HTML structure while allowing
 * media-specific customization.
 */

/**
 * BaseMediaListRenderer - Abstract base class for media list rendering
 *
 * Usage:
 *   class GameListRenderer extends BaseMediaListRenderer {
 *       constructor(filterEngine) {
 *           super(filterEngine);
 *           // Game-specific initialization
 *       }
 *   }
 */
class BaseMediaListRenderer {
    /**
     * @param {Object} filterEngine - Engine with reference data for expanding items
     */
    constructor(filterEngine) {
        this.engine = filterEngine;
        this.PAGE_SIZE = 100;
        this.currentPage = 1;
        this.currentItems = [];
        this.highlightId = null;
        this._csrfToken = null;
        this._templates = null;
    }

    /**
     * Get CSRF token from cookie
     * @protected
     */
    _getCsrfToken() {
        if (this._csrfToken) return this._csrfToken;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        this._csrfToken = match ? match[1] : '';
        return this._csrfToken;
    }

    /**
     * Fill a data slot with text content
     * @protected
     */
    _fillSlot(container, slotName, value) {
        const el = container.querySelector(`[data-slot="${slotName}"]`);
        if (!el) return null;
        if (value !== undefined && value !== null) {
            el.textContent = value;
        }
        return el;
    }

    /**
     * Escape HTML special characters
     * @protected
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    /**
     * Initialize templates from DOM - override in subclass
     * Called lazily on first render
     * @protected
     */
    _initTemplates() {
        if (this._templates) return;
        // Subclasses should override to initialize their specific templates
        this._templates = {};
    }

    /**
     * Render a single desktop row - override in subclass
     * @protected
     * @returns {Element} The rendered desktop row element
     */
    _renderDesktopRow(item, index, showRank) {
        throw new Error('Subclasses must implement _renderDesktopRow');
    }

    /**
     * Render a single mobile row - override in subclass
     * @protected
     * @returns {Element} The rendered mobile row element
     */
    _renderMobileRow(item, index, showRank) {
        throw new Error('Subclasses must implement _renderMobileRow');
    }

    /**
     * Render a single grid card - override in subclass
     * @protected
     * @returns {Element} The rendered grid card element
     */
    _renderGridCard(item, index, showRank) {
        throw new Error('Subclasses must implement _renderGridCard');
    }

    /**
     * Render items as DOM fragment
     * @protected
     * @param {string} viewMode - 'list' or 'grid'
     * @returns {DocumentFragment}
     */
    _renderItems(items, showRank, startIndex, viewMode = 'list') {
        const fragment = document.createDocumentFragment();

        if (viewMode === 'grid') {
            const gridContainer = document.createElement('div');
            gridContainer.className = 'media-grid';

            items.forEach((item, i) => {
                const index = startIndex + i;
                const card = this._renderGridCard(item, index, showRank);
                if (card) gridContainer.appendChild(card);
            });

            fragment.appendChild(gridContainer);
        } else {
            items.forEach((item, i) => {
                const index = startIndex + i;
                const desktopRow = this._renderDesktopRow(item, index, showRank);
                const mobileRow = this._renderMobileRow(item, index, showRank);
                if (desktopRow) fragment.appendChild(desktopRow);
                if (mobileRow) fragment.appendChild(mobileRow);
            });
        }

        return fragment;
    }

    /**
     * Render media list to container
     *
     * @param {Array} items - Items to render
     * @param {HTMLElement} container - Container element
     * @param {Object} options - Render options
     * @param {string} [options.showRank='alltime'] - 'alltime', 'filtered', or 'none'
     * @param {number} [options.highlightId] - Item ID to highlight
     * @param {boolean} [options.append=false] - Append to existing content
     * @param {string} [options.viewMode='list'] - 'list' or 'grid'
     */
    render(items, container, options = {}) {
        const {
            showRank = 'filtered',
            highlightId = null,
            append = false,
            viewMode = 'list'
        } = options;

        this.currentItems = items;
        this.highlightId = highlightId;
        this.currentPage = 1;
        this._currentViewMode = viewMode;
        this._currentShowRank = showRank;

        if (!append) {
            container.innerHTML = '';
        }

        // Render first page
        const pageItems = items.slice(0, this.PAGE_SIZE);
        const fragment = this._renderItems(pageItems, showRank, 1, viewMode);

        container.appendChild(fragment);

        // Reinitialize HTMX for dynamically rendered content
        if (typeof htmx !== 'undefined') {
            htmx.process(container);
        }

        // Handle highlighting
        if (highlightId) {
            this._scrollToHighlight(highlightId, viewMode);
        }
    }

    /**
     * Load more items (for Load More button)
     *
     * @param {HTMLElement} container - Container element
     * @param {Object} options - Options
     * @returns {Object} { loaded, total, hasMore }
     */
    loadMore(container, options = {}) {
        const { showRank = 'filtered' } = options;
        const viewMode = this._currentViewMode || 'list';

        this.currentPage++;
        const start = (this.currentPage - 1) * this.PAGE_SIZE;
        const end = start + this.PAGE_SIZE;
        const pageItems = this.currentItems.slice(start, end);

        if (pageItems.length === 0) {
            return {
                loaded: Math.min((this.currentPage - 1) * this.PAGE_SIZE, this.currentItems.length),
                total: this.currentItems.length,
                hasMore: false
            };
        }

        if (viewMode === 'grid') {
            let gridContainer = container.querySelector('.media-grid');
            if (!gridContainer) {
                gridContainer = document.createElement('div');
                gridContainer.className = 'media-grid';
                container.appendChild(gridContainer);
            }

            pageItems.forEach((item, i) => {
                const index = start + 1 + i;
                const card = this._renderGridCard(item, index, showRank);
                if (card) gridContainer.appendChild(card);
            });
        } else {
            const fragment = this._renderItems(pageItems, showRank, start + 1, viewMode);
            container.appendChild(fragment);
        }

        // Reinitialize HTMX
        if (typeof htmx !== 'undefined') {
            htmx.process(container);
        }

        const loaded = Math.min(this.currentPage * this.PAGE_SIZE, this.currentItems.length);
        const hasMore = loaded < this.currentItems.length && loaded < 1000;

        return {
            loaded,
            total: this.currentItems.length,
            hasMore,
            remaining: Math.min(this.currentItems.length - loaded, 1000 - loaded)
        };
    }

    /**
     * Reset pagination
     */
    reset() {
        this.currentPage = 1;
        this.currentItems = [];
        this.highlightId = null;
    }

    /**
     * Scroll to and highlight an item
     * @protected
     * @param {number} itemId - Item ID to highlight
     * @param {string} viewMode - 'list' or 'grid'
     */
    _scrollToHighlight(itemId, viewMode = 'list') {
        // Subclasses should override with their specific ID patterns
        setTimeout(() => {
            let elementToScroll = null;
            let elementsToHighlight = [];

            if (viewMode === 'grid') {
                const gridElement = document.getElementById('item-' + itemId + '-grid');
                if (gridElement) {
                    elementToScroll = gridElement;
                    elementsToHighlight = [gridElement];
                }
            } else {
                const desktopElement = document.getElementById('item-' + itemId);
                const mobileElement = document.getElementById('item-' + itemId + '-mobile');
                const isDesktop = window.matchMedia('(min-width: 962px)').matches;
                elementToScroll = isDesktop ? desktopElement : mobileElement;

                if (desktopElement) elementsToHighlight.push(desktopElement);
                if (mobileElement) elementsToHighlight.push(mobileElement);
            }

            if (elementToScroll) {
                elementToScroll.scrollIntoView({ behavior: 'smooth', block: 'start' });

                // Fade out highlight after 4 seconds
                const fadeTimeout = setTimeout(() => {
                    elementsToHighlight.forEach(el => el.classList.add('fade-out'));
                }, 4000);

                // Fade out on hover of other items
                const selector = viewMode === 'grid' ? '.media-card-grid' : '.media-row';
                const items = document.querySelectorAll(selector);
                items.forEach((item) => {
                    if (!elementsToHighlight.includes(item)) {
                        item.addEventListener('mouseenter', () => {
                            clearTimeout(fadeTimeout);
                            elementsToHighlight.forEach(el => el.classList.add('fade-out'));
                        }, { once: true });
                    }
                });
            }
        }, 300);
    }

    /**
     * Generate result summary HTML
     * @param {number} loaded - Number loaded
     * @param {number} total - Total count
     * @returns {string} HTML string
     */
    getResultSummaryHtml(loaded, total) {
        return 'Showing <span id="loaded-count" class="loaded-count-value">' + loaded.toLocaleString() + '</span> of ' + total.toLocaleString();
    }

    /**
     * Generate load more button HTML
     * @param {Object} state - { hasMore, remaining, maxLoaded }
     * @returns {string} HTML string
     */
    getLoadMoreHtml(state) {
        const { hasMore, remaining, maxLoaded } = state;

        if (maxLoaded) {
            return '<div class="alert alert-info"><span class="mdi mdi-information-outline"></span><span>Showing maximum of 1,000 results. Refine your filters to see more specific results.</span></div>';
        }

        if (!hasMore) {
            return '<div class="text-base-content/60 text-center">All results loaded</div>';
        }

        return '<button type="button" class="btn btn-ghost load-more-button"><span class="mdi mdi-plus-circle-outline"></span><span class="load-more-text">Load More (' + remaining.toLocaleString() + ' remaining)</span></button>';
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.BaseMediaListRenderer = BaseMediaListRenderer;
}
