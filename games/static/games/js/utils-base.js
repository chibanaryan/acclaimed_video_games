/**
 * Acclaimed Games - Base Utilities
 *
 * Essential utilities that must be available before Alpine.js initializes.
 * Includes core functions and filter/search utilities.
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
        const genreIds = filters.genres.map(g =>
            (typeof g === 'object' && g !== null && g.id !== undefined) ? g.id : g
        ).filter(id => id !== null && id !== undefined);
        if (genreIds.length > 0) params.set('genres', genreIds.join(','));
    }
    if (filters.platforms && filters.platforms.length) {
        const platformIds = filters.platforms.map(p =>
            (typeof p === 'object' && p !== null && p.id !== undefined) ? p.id : p
        ).filter(id => id !== null && id !== undefined);
        if (platformIds.length > 0) params.set('platforms', platformIds.join(','));
    }
    if (filters.genre_option) params.set('genre_option', filters.genre_option);
    if (filters.sort && filters.sort !== 'rank') params.set('sort', filters.sort);

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
// SEARCH UTILITIES
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
// YEAR PREVIEW UTILITIES
// ============================================================

/**
 * Initializes year preview highlighting during year grid drag selection
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
        gameYears.forEach(el => el.classList.remove('year-preview'));
        return;
    }

    gameYears.forEach(el => {
        const year = parseInt(el.dataset.year, 10);
        if (year >= start && year <= end) {
            el.classList.add('year-preview');
        } else {
            el.classList.remove('year-preview');
        }
    });
}
