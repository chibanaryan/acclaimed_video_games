/**
 * Acclaimed Games - Load More Utilities
 *
 * Utilities for progressive loading and "Jump to Rank" functionality.
 * Loaded only after initial page render to avoid blocking.
 */

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
 * Track if Load More has been initialized to prevent duplicate event listeners
 */
let loadMoreInitialized = false;

/**
 * Initializes Load More functionality for game search
 * Called after page load and after filter updates
 */
function initLoadMore() {
    const container = document.getElementById('game-results-container');
    if (!container) return;

    // Initialize event delegation once on the container (not the button)
    if (!loadMoreInitialized) {
        // Use event delegation on the container to handle clicks on load-more-button
        container.addEventListener('click', function(e) {
            const button = e.target.closest('.load-more-button');
            if (button && !button.classList.contains('is-loading')) {
                handleLoadMore({ currentTarget: button });
            }
        });

        // Use event delegation for hover (icon randomization)
        container.addEventListener('mouseenter', function(e) {
            const button = e.target.closest('.load-more-button');
            if (button) {
                randomizeLoadMoreIcon(button);
            }
        }, true); // Use capture phase to catch mouseenter on button

        loadMoreInitialized = true;
    }

    // Always reinitialize Jump to Rank (it handles its own listener management)
    initJumpToRank();
}

/**
 * Track if Jump to Rank has been initialized
 */
let jumpToRankInitialized = false;

/**
 * Initializes Jump to Rank functionality using event delegation
 */
function initJumpToRank() {
    if (jumpToRankInitialized) return;

    // Use event delegation on document for robustness
    document.addEventListener('click', function(e) {
        const button = e.target.closest('.jump-to-rank-btn');
        if (button) {
            e.preventDefault();
            // Find the associated input (sibling or nearby)
            const container = button.closest('.jump-to-rank-container') ||
                              button.parentElement;
            const input = container?.querySelector('.jump-to-rank-input');
            if (input) {
                handleJumpToRank(input);
            }
        }
    });

    document.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && e.target.classList.contains('jump-to-rank-input')) {
            e.preventDefault();
            handleJumpToRank(e.target);
        }
    });

    jumpToRankInitialized = true;
    console.log('[JumpToRank] Event delegation initialized');
}

/**
 * Get current filters from URL parameters
 */
function getFiltersFromURL() {
    const params = new URLSearchParams(window.location.search);
    return {
        q: params.get('q') || '',
        start: params.get('start') ? parseInt(params.get('start')) : null,
        end: params.get('end') ? parseInt(params.get('end')) : null,
        genres: params.get('genres') ? params.get('genres').split(',') : [],
        platforms: params.get('platforms') ? params.get('platforms').split(',') : [],
        series: params.get('series') ? params.get('series').split(',') : [],
        sort: params.get('sort') || 'rank'
    };
}

/**
 * Handles jumping to a specific rank
 * @param {HTMLInputElement} input - The rank input element
 */
async function handleJumpToRank(input) {
    const targetRank = parseInt(input.value);
    let total = parseInt(input.dataset.total);
    const loaded = parseInt(input.dataset.loaded);
    const perPage = parseInt(input.dataset.perPage);

    // Get actual filtered total from CSF if available
    if (typeof getClientSideFiltering === 'function') {
        const csf = getClientSideFiltering();
        if (csf && csf.isReady()) {
            const filters = getFiltersFromURL();
            const result = csf.applyFilters(filters);
            if (result && result.total) {
                total = result.total;
            }
        }
    }

    console.log('[JumpToRank] Target:', targetRank, 'Loaded:', loaded, 'Total:', total);

    // Validate input
    if (!targetRank || targetRank < 1 || targetRank > total) {
        input.classList.add('input-error');
        setTimeout(() => input.classList.remove('input-error'), 1000);
        console.log('[JumpToRank] Invalid input - target exceeds total');
        return;
    }

    // Check if target is already loaded
    if (targetRank <= loaded) {
        console.log('[JumpToRank] Already loaded, scrolling');
        scrollToAndHighlightRank(targetRank);
        return;
    }

    // Try to use client-side filtering (instant, no network requests)
    if (typeof getClientSideFiltering === 'function') {
        const csf = getClientSideFiltering();
        console.log('[JumpToRank] CSF available:', !!csf, 'Ready:', csf?.isReady?.());
        if (csf && csf.isReady()) {
            try {
                jumpToRankClientSide(csf, targetRank, loaded, perPage);
                input.value = '';
                return;
            } catch (err) {
                console.error('[JumpToRank] Client-side error:', err);
                // Fall through to server-side
            }
        }
    }

    // Fallback: fetch from server (parallel loading)
    console.log('[JumpToRank] Using server-side fallback');
    await jumpToRankServerSide(targetRank, loaded, perPage);
    input.value = '';
}

/**
 * Jump to rank using client-side rendering (instant, no network)
 */
function jumpToRankClientSide(csf, targetRank, loaded, perPage) {
    const gameListContainer = document.getElementById('game-list-container');
    const countContainer = document.querySelector('.result-count');
    const loadMoreContainer = document.querySelector('.load-more-container');

    console.log('[JumpToRank CSF] Container:', !!gameListContainer);
    if (!gameListContainer) {
        console.error('[JumpToRank CSF] No game list container found');
        return;
    }

    // Get current filters from URL
    const filters = getFiltersFromURL();
    console.log('[JumpToRank CSF] Filters:', filters);

    // Get filtered games from engine
    const result = csf.applyFilters(filters);
    console.log('[JumpToRank CSF] Filter result:', result?.total, 'games');
    if (!result || !result.games) {
        console.error('[JumpToRank CSF] No games returned from filter');
        return;
    }

    // Calculate which games to render (from loaded to targetRank)
    const gamesToRender = result.games.slice(loaded, targetRank);
    const total = result.total;
    const newLoaded = Math.min(targetRank, total);

    // Render games directly to container
    const renderer = csf.renderer;
    gamesToRender.forEach((game, i) => {
        const index = loaded + i + 1; // 1-based rank
        const html = renderer._renderDesktopRow(game, index, 'filtered') +
                     renderer._renderMobileRow(game, index, 'filtered');
        gameListContainer.insertAdjacentHTML('beforeend', html);
    });

    // Reinitialize HTMX for dynamically rendered content
    if (typeof htmx !== 'undefined') {
        htmx.process(gameListContainer);
    }

    // Update the renderer's state to match
    renderer.currentGames = result.games;
    renderer.currentPage = Math.ceil(newLoaded / perPage);

    // Update count display
    if (countContainer) {
        countContainer.innerHTML = renderer.getResultSummaryHtml(newLoaded, total);
    }

    // Update Load More button
    const hasMore = newLoaded < total && newLoaded < 1000;
    const remaining = Math.min(total - newLoaded, 1000 - newLoaded);
    if (loadMoreContainer) {
        loadMoreContainer.innerHTML = renderer.getLoadMoreHtml({
            hasMore,
            remaining,
            maxLoaded: newLoaded >= 1000
        });
        if (hasMore) {
            csf._initLoadMoreButton(loadMoreContainer, gameListContainer, countContainer);
        }
    }

    // Update jump-to-rank inputs
    document.querySelectorAll('.jump-to-rank-input').forEach(inp => {
        inp.dataset.loaded = newLoaded;
    });

    console.log('[JumpToRank CSF] Rendered', gamesToRender.length, 'games, now loaded:', newLoaded);

    // Scroll to and highlight the target rank
    setTimeout(() => {
        scrollToAndHighlightRank(targetRank);
    }, 50);
}

/**
 * Jump to rank using server-side fetching (fallback)
 */
async function jumpToRankServerSide(targetRank, loaded, perPage) {
    const targetPage = Math.ceil(targetRank / perPage);
    const currentPage = Math.ceil(loaded / perPage);

    // Show loading state on all instances
    const allButtons = document.querySelectorAll('.jump-to-rank-btn');
    const allInputs = document.querySelectorAll('.jump-to-rank-input');
    allButtons.forEach(btn => { btn.classList.add('loading'); btn.disabled = true; });
    allInputs.forEach(inp => { inp.disabled = true; });

    try {
        // Load all pages in parallel for speed
        const pagesToLoad = [];
        for (let page = currentPage + 1; page <= targetPage; page++) {
            pagesToLoad.push(page);
        }

        // Fetch all pages concurrently
        const pageResults = await Promise.all(
            pagesToLoad.map(page => fetchPage(page))
        );

        // Append pages in correct order (they may have arrived out of order)
        pageResults.sort((a, b) => a.page - b.page);
        for (const result of pageResults) {
            appendPageResults(result);
        }

        // Scroll to and highlight the target rank
        setTimeout(() => {
            scrollToAndHighlightRank(targetRank);
        }, 100);
    } catch (err) {
        console.error('Jump to rank error:', err);
    } finally {
        allButtons.forEach(btn => { btn.classList.remove('loading'); btn.disabled = false; });
        allInputs.forEach(inp => { inp.disabled = false; });
    }
}

/**
 * Fetches a specific page and returns parsed results (without appending to DOM)
 * @param {number} page - The page number to load
 * @returns {Promise<{page: number, rows: NodeList, meta: Object}>}
 */
async function fetchPage(page) {
    const params = new URLSearchParams(window.location.search);
    params.set('page', page);
    params.set('append', 'true');

    const url = window.location.pathname + '?' + params.toString();

    const response = await fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'HX-Request': 'true'
        }
    });

    if (!response.ok) throw new Error('Failed to load page ' + page);

    const html = await response.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    // Extract metadata
    const metaScript = doc.getElementById('load-more-meta');
    const meta = metaScript ? JSON.parse(metaScript.textContent) : null;

    // Get all game rows
    const rows = doc.querySelectorAll('.game-row');

    return { page, rows, meta };
}

/**
 * Appends fetched page results to the DOM
 * @param {{page: number, rows: NodeList, meta: Object}} result - Fetched page data
 */
function appendPageResults(result) {
    const { rows, meta } = result;

    // Append game rows
    const gameList = document.getElementById('game-list-container');
    if (gameList) {
        rows.forEach((row) => {
            gameList.appendChild(row);
        });

        // Reinitialize HTMX for dynamically appended content
        if (typeof htmx !== 'undefined') {
            htmx.process(gameList);
        }
    }

    // Update metadata (last page's meta will have final counts)
    if (meta) {
        updateResultSummary(meta.loadedCount, meta.totalCount);

        // Update all jump to rank inputs data
        document.querySelectorAll('.jump-to-rank-input').forEach(input => {
            input.dataset.loaded = meta.loadedCount;
        });

        // Update or remove load more button
        const loadMoreButton = document.querySelector('.load-more-button');
        if (loadMoreButton) {
            updateLoadMoreButton(loadMoreButton, meta);
        }
    }
}

/**
 * Loads a specific page and appends to the list (used by Load More button)
 * @param {number} page - The page number to load
 * @returns {Promise<void>}
 */
async function loadPage(page) {
    const result = await fetchPage(page);
    appendPageResults(result);
}

/**
 * Scrolls to and highlights a specific position in the list
 * @param {number} position - The 1-based position to scroll to (e.g., 50 = 50th game in list)
 */
function scrollToAndHighlightRank(position) {
    // Get all game rows - desktop and mobile versions are separate elements
    // Desktop rows have class 'desktop', mobile rows have class 'game-card-mobile'
    const desktopRows = document.querySelectorAll('.game-row.desktop');
    const mobileRows = document.querySelectorAll('.game-row.game-card-mobile');

    // Position is 1-based, arrays are 0-based
    const index = position - 1;

    const desktopRow = desktopRows[index];
    const mobileRow = mobileRows[index];

    if (!desktopRow && !mobileRow) {
        console.warn('Could not find position:', position);
        return;
    }

    // Find the visible row (desktop rows are hidden on mobile and vice versa)
    const visibleRow = (desktopRow && desktopRow.offsetParent !== null) ? desktopRow :
                       (mobileRow && mobileRow.offsetParent !== null) ? mobileRow :
                       desktopRow || mobileRow;

    // Scroll to the row with smooth scrolling
    visibleRow.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Add temporary highlight to both rows (desktop and mobile)
    if (desktopRow) desktopRow.classList.add('is-highlighted');
    if (mobileRow) mobileRow.classList.add('is-highlighted');
    setTimeout(() => {
        if (desktopRow) desktopRow.classList.remove('is-highlighted');
        if (mobileRow) mobileRow.classList.remove('is-highlighted');
    }, 3000); // Remove highlight after 3 seconds
}

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

        // Append game rows without animation (instant load)
        const gameList = document.getElementById('game-list-container');
        if (gameList) {
            const allRows = doc.querySelectorAll('.game-row');
            allRows.forEach((row) => {
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
    const iconSpan = button.querySelector('.icon .mdi');
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
    // Update all loaded count elements (supports multiple instances for responsive layouts)
    document.querySelectorAll('.loaded-count-value, #loaded-count').forEach(el => {
        el.textContent = loaded.toLocaleString();
    });
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
                    <span class="icon is-small mr-2">
                        <span class="mdi mdi-information-outline"></span>
                    </span>
                    Showing maximum of 1,000 results. Refine your filters to see more specific results.
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="has-text-grey-light has-text-centered">
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

// Auto-initialize when script loads
(function() {
    console.log('[LoadMore] Script loaded, initializing...');
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLoadMore);
    } else {
        // DOM already loaded
        initLoadMore();
    }
})();
