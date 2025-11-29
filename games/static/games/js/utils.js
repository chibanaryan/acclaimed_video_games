/**
 * Acclaimed Games - Shared Utility Functions
 *
 * This file contains pure utility functions used across templates.
 * Alpine.js component logic remains in templates following Alpine patterns.
 */

// ============================================================
// FETCH UTILITIES
// ============================================================

/**
 * Creates HTMX-compatible fetch headers
 * @param {string} targetId - The HTMX target element ID
 * @returns {Object} Headers object for fetch
 */
function createHtmxHeaders(targetId = 'content') {
    return {
        'X-Requested-With': 'XMLHttpRequest',
        'HX-Request': 'true',
        'HX-Target': targetId
    };
}

/**
 * Fetches HTML content with HTMX headers and AbortController support
 * @param {string} url - URL to fetch
 * @param {AbortSignal} signal - AbortController signal
 * @param {string} targetId - HTMX target ID
 * @returns {Promise<string>} HTML response text
 */
async function fetchHtml(url, signal, targetId = 'content') {
    const response = await fetch(url, {
        headers: createHtmxHeaders(targetId),
        signal: signal
    });
    return response.text();
}

/**
 * Parses HTML string and extracts elements by selector
 * @param {string} html - HTML string to parse
 * @param {Array<{selector: string, targetId: string}>} updates - Elements to extract
 * @returns {Object} Map of targetId to innerHTML
 */
function parseAndExtract(html, updates) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const result = {};

    updates.forEach(({ selector, targetId }) => {
        const element = doc.querySelector(selector);
        if (element) {
            result[targetId] = element.innerHTML;
        }
    });

    return result;
}

/**
 * Updates multiple DOM elements from parsed content
 * @param {Object} contentMap - Map of elementId to innerHTML
 */
function updateDomElements(contentMap) {
    Object.entries(contentMap).forEach(([elementId, innerHTML]) => {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = innerHTML;
        }
    });
}

// ============================================================
// TIMING UTILITIES
// ============================================================

/**
 * Creates a debounced function
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function with cancel method
 */
function debounce(fn, delay) {
    let timeoutId = null;

    const debounced = function(...args) {
        if (timeoutId) {
            clearTimeout(timeoutId);
        }
        timeoutId = setTimeout(() => {
            fn.apply(this, args);
            timeoutId = null;
        }, delay);
    };

    debounced.cancel = function() {
        if (timeoutId) {
            clearTimeout(timeoutId);
            timeoutId = null;
        }
    };

    return debounced;
}

/**
 * Creates a throttled function
 * @param {Function} fn - Function to throttle
 * @param {number} limit - Minimum time between calls in milliseconds
 * @returns {Function} Throttled function
 */
function throttle(fn, limit) {
    let lastCall = 0;

    return function(...args) {
        const now = Date.now();
        if (now - lastCall >= limit) {
            lastCall = now;
            return fn.apply(this, args);
        }
    };
}

/**
 * Creates a throttled function that can be force-called
 * @param {Function} fn - Function to throttle
 * @param {number} limit - Minimum time between calls
 * @returns {Object} Object with call() and force() methods
 */
function throttleWithForce(fn, limit) {
    let lastCall = 0;

    return {
        call(...args) {
            const now = Date.now();
            if (now - lastCall >= limit) {
                lastCall = now;
                return fn.apply(this, args);
            }
        },
        force(...args) {
            lastCall = 0;
            return fn.apply(this, args);
        }
    };
}

// ============================================================
// ABORT CONTROLLER MANAGER
// ============================================================

/**
 * Manages AbortController lifecycle for fetch requests
 * Ensures only one request is active at a time
 */
class FetchManager {
    constructor() {
        this.controller = null;
    }

    /**
     * Aborts any pending request and creates new controller
     * @returns {AbortSignal} Signal for the new request
     */
    newRequest() {
        if (this.controller) {
            this.controller.abort();
        }
        this.controller = new AbortController();
        return this.controller.signal;
    }

    /**
     * Aborts current request if any
     */
    abort() {
        if (this.controller) {
            this.controller.abort();
            this.controller = null;
        }
    }
}

// ============================================================
// URL UTILITIES
// ============================================================

/**
 * Builds URL parameters from filter object
 * @param {Object} filters - Filter values
 * @param {Object} options - Options for building params
 * @param {boolean} options.preservePage - Keep current page parameter
 * @returns {URLSearchParams} Built parameters
 */
function buildFilterParams(filters, options = {}) {
    const params = new URLSearchParams();

    if (options.preservePage) {
        const currentPage = new URLSearchParams(window.location.search).get('page');
        if (currentPage) {
            params.set('page', currentPage);
        }
    }

    if (filters.q) params.set('q', filters.q);
    if (filters.start) params.set('start', filters.start);
    if (filters.end) params.set('end', filters.end);
    if (filters.genres && filters.genres.length) {
        // Handle both object and string ID formats
        const genreIds = filters.genres.map(g =>
            (typeof g === 'object' && g !== null && g.id !== undefined) ? g.id : g
        ).filter(id => id !== null && id !== undefined);
        if (genreIds.length > 0) params.set('genres', genreIds.join(','));
    }
    if (filters.platforms && filters.platforms.length) {
        // Handle both object and string ID formats
        const platformIds = filters.platforms.map(p =>
            (typeof p === 'object' && p !== null && p.id !== undefined) ? p.id : p
        ).filter(id => id !== null && id !== undefined);
        if (platformIds.length > 0) params.set('platforms', platformIds.join(','));
    }
    if (filters.genre_option) params.set('genre_option', filters.genre_option);
    // rank_display is always filtered; no param needed

    return params;
}

/**
 * Normalizes URL string by decoding common URL-encoded characters
 * @param {string} url - URL string to normalize
 * @returns {string} Normalized URL
 */
function normalizeUrl(url) {
    return url.replace(/%2C/g, ',');
}

/**
 * Updates URL with filter parameter and navigates
 * @param {string} paramName - Parameter name
 * @param {string} value - Parameter value
 * @param {string} baseUrl - Base URL to navigate to
 */
function updateFilterAndNavigate(paramName, value, baseUrl) {
    const params = new URLSearchParams(window.location.search);
    params.delete('page');
    if (value) {
        params.set(paramName, value);
    } else {
        params.delete(paramName);
    }
    window.location.href = baseUrl + '?' + params.toString();
}

// ============================================================
// LOADING STATE UTILITIES
// ============================================================

/**
 * Adds loading class to element
 * @param {string} elementId - Element ID
 */
function setLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.add('is-loading');
    }
}

/**
 * Removes loading class from element
 * @param {string} elementId - Element ID
 */
function clearLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.remove('is-loading');
    }
}

// ============================================================
// MODAL UTILITIES
// ============================================================

/**
 * Opens a modal
 * @param {string} modalId - Modal element ID
 */
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('is-active');
        document.documentElement.classList.add('overflow-hidden');
    }
}

/**
 * Closes a modal
 * @param {string} modalId - Modal element ID
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('is-active');
        document.documentElement.classList.remove('overflow-hidden');
    }
}

// ============================================================
// SEARCH UTILITIES (for nav search)
// ============================================================

/**
 * Performs game search API call
 * @param {string} query - Search query
 * @param {number} limit - Max results
 * @param {string} apiUrl - API endpoint URL
 * @returns {Promise<Array>} Search results
 */
async function searchGames(query, limit, apiUrl) {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 2) {
        return [];
    }

    const response = await fetch(
        `${apiUrl}?q=${encodeURIComponent(trimmedQuery)}&limit=${limit}`
    );

    if (!response.ok) {
        throw new Error('API request failed');
    }

    const data = await response.json();
    return data.results || [];
}

/**
 * Removes a filter item and updates the page via fetch
 * Used by selectable tag list components
 * @param {Object} filters - Current filter state
 * @param {string} filterType - Type of filter ('genres' or 'platforms')
 * @param {number} index - Index of item to remove
 * @param {string} searchUrl - Base search URL
 * @param {Function} onUpdate - Callback after update (optional)
 */
async function removeFilterItem(filters, filterType, index, searchUrl, onUpdate) {
    filters[filterType] = filters[filterType].filter((_, i) => i !== index);

    const params = buildFilterParams(filters);
    const url = searchUrl + '?' + normalizeUrl(params.toString());

    try {
        const html = await fetchHtml(url, new AbortController().signal);
        const contentEl = document.getElementById('content');
        if (contentEl) {
            contentEl.innerHTML = html;
            window.history.pushState({}, '', url);
            if (typeof Alpine !== 'undefined') {
                Alpine.initTree(contentEl);
            }
        }
        if (onUpdate) onUpdate();
    } catch (err) {
        console.error('Error removing filter:', err);
    }
}

/**
 * Creates Alpine.js search component data
 * @param {string} apiUrl - API endpoint for search
 * @param {number} limit - Max results to return
 * @returns {Object} Alpine component data
 */
function createSearchData(apiUrl, limit = 5) {
    return {
        showMenu: false,
        q: '',
        results: [],
        loading: false,

        async loadResults() {
            const trimmedQ = this.q.trim();
            if (trimmedQ.length < 2) {
                this.results = [];
                this.loading = false;
                return;
            }
            this.loading = true;
            this.results = [];
            try {
                this.results = await searchGames(trimmedQ, limit, apiUrl);
            } catch (e) {
                console.error('Search error:', e);
                this.results = [];
            } finally {
                this.loading = false;
            }
        },

        reset() {
            this.showMenu = false;
            this.q = '';
            this.results = [];
            this.loading = false;
        }
    };
}

// ============================================================
// LOAD MORE UTILITIES
// ============================================================

/**
 * Initializes Load More functionality for game search
 * Called after page load and after filter updates
 */
function initLoadMore() {
    const container = document.getElementById('game-results-container');
    if (!container) return;

    const button = container.querySelector('.load-more-button');
    if (!button) return;

    // Remove existing listener to prevent duplicates after DOM updates
    const newButton = button.cloneNode(true);
    button.parentNode.replaceChild(newButton, button);
    newButton.addEventListener('click', handleLoadMore);
    // Randomize icon on each hover
    newButton.addEventListener('mouseenter', () => randomizeLoadMoreIcon(newButton));
}

// Gaming icons for hover effect (from MDI subset)
const LOAD_MORE_ICONS = [
    'mdi-gamepad-variant',
    'mdi-controller',
    'mdi-controller-classic',
    'mdi-pac-man',
    'mdi-space-invaders',
    'mdi-run-fast',
    'mdi-power'
];

/**
 * Handles Load More button click
 * @param {Event} event - Click event
 */
async function handleLoadMore(event) {
    const button = event.currentTarget;
    const nextPage = button.dataset.nextPage;

    if (!nextPage || button.classList.contains('is-loading')) return;

    // Set loading state
    button.classList.add('is-loading');
    button.disabled = true;

    // Build URL with current filters + next page + append flag
    const params = new URLSearchParams(window.location.search);
    params.set('page', nextPage);
    params.set('append', 'true');

    const url = window.location.pathname + '?' + params.toString();

    try {
        const response = await fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'HX-Request': 'true'
            }
        });

        if (!response.ok) throw new Error('Failed to load more');

        const html = await response.text();

        // Parse the response to separate game rows from metadata
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        // Extract metadata
        const metaScript = doc.getElementById('load-more-meta');
        const meta = metaScript ? JSON.parse(metaScript.textContent) : null;

        // Remove the metadata script from the parsed doc
        if (metaScript) metaScript.remove();

        // Append game rows with staggered cascade animation
        const gameList = document.getElementById('game-list-container');
        if (gameList) {
            // Only animate desktop rows for speed (mobile rows animate instantly)
            const newRows = doc.querySelectorAll('.game-row.desktop');
            const allRows = doc.querySelectorAll('.game-row');
            let desktopIndex = 0;
            allRows.forEach((row) => {
                if (row.classList.contains('desktop')) {
                    row.classList.add('game-row-enter');
                    row.style.animationDelay = `${desktopIndex * 8}ms`;
                    desktopIndex++;
                }
                gameList.appendChild(row);
            });
        }

        // Update result summary and button
        if (meta) {
            updateResultSummary(meta.loadedCount, meta.totalCount);
            updateLoadMoreButton(button, meta);
        }

    } catch (err) {
        console.error('Load more error:', err);
        button.classList.remove('is-loading');
        button.disabled = false;
    }
}

/**
 * Randomizes the Load More button icon on hover
 * @param {HTMLElement} button - The Load More button
 */
function randomizeLoadMoreIcon(button) {
    const iconSpan = button.querySelector('.mdi');
    if (iconSpan) {
        // Remove default and all gaming icon classes, then add a random one
        iconSpan.classList.remove('mdi-plus-circle-outline');
        LOAD_MORE_ICONS.forEach(cls => iconSpan.classList.remove(cls));
        const randomIcon = LOAD_MORE_ICONS[Math.floor(Math.random() * LOAD_MORE_ICONS.length)];
        iconSpan.classList.add(randomIcon);
    }
}

/**
 * Updates the result summary text
 * @param {number} loaded - Number of items currently loaded
 * @param {number} total - Total number of items
 */
function updateResultSummary(loaded, total) {
    const loadedCountEl = document.getElementById('loaded-count');
    if (loadedCountEl) {
        loadedCountEl.textContent = loaded.toLocaleString();
    }
}

/**
 * Updates the Load More button state based on server response
 * @param {HTMLElement} button - The Load More button
 * @param {Object} meta - Metadata from server response
 */
function updateLoadMoreButton(button, meta) {
    button.classList.remove('is-loading');

    if (!meta.hasMore || meta.maxLoaded) {
        const container = button.parentElement;
        if (meta.maxLoaded) {
            container.innerHTML = `
                <div class="notification is-dark">
                    <span class="mdi mdi-information-outline mr-2"></span>
                    Showing maximum of 1,000 results. Refine your filters to see more specific results.
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="text-text-muted text-center">
                    All ${meta.totalCount.toLocaleString()} results loaded
                </div>
            `;
        }
    } else {
        button.disabled = false;
        button.dataset.nextPage = meta.nextPage;
        button.dataset.loaded = meta.loadedCount;

        const textSpan = button.querySelector('.load-more-text');
        if (textSpan) {
            textSpan.textContent = `Load More (${meta.remainingCount.toLocaleString()} remaining)`;
        }
    }
}

// ============================================================
// YEAR PREVIEW UTILITIES
// ============================================================

/**
 * Initializes year preview highlighting during year grid drag selection
 * Called on page load for advanced search page
 */
function initYearPreview() {
    window.addEventListener('year-preview', handleYearPreview);
}

/**
 * Handles year preview event from year grid drag selection
 * @param {CustomEvent} event - Event with detail: { active, start, end }
 */
function handleYearPreview(event) {
    const { active, start, end } = event.detail;
    const gameYears = document.querySelectorAll('.game-year[data-year]');

    if (!active) {
        // Clear all previews
        gameYears.forEach(el => el.classList.remove('year-preview'));
        return;
    }

    // Apply preview to years in range
    gameYears.forEach(el => {
        const year = parseInt(el.dataset.year, 10);
        if (year >= start && year <= end) {
            el.classList.add('year-preview');
        } else {
            el.classList.remove('year-preview');
        }
    });
}
