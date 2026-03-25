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
                // Use CSF load more if available (instant, no network requests)
                if (typeof getClientSideFiltering === 'function') {
                    const csf = getClientSideFiltering();
                    if (csf && csf.isReady()) {
                        handleLoadMoreCSF(csf);
                        return;
                    }
                }
                // Fallback to server-side load more
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
}

/**
 * Get current filters from URL parameters
 */
function getFiltersFromURL() {
    const params = new URLSearchParams(window.location.search);

    // Parse HLTB parameters
    const hltb_min_str = params.get('hltb_min');
    const hltb_max_str = params.get('hltb_max');
    const hltb_min = hltb_min_str ? parseInt(hltb_min_str) : null;
    const hltb_max = (hltb_max_str && hltb_max_str !== 'unlimited') ? parseInt(hltb_max_str) : null;

    return {
        q: params.get('q') || '',
        start: params.get('start') ? parseInt(params.get('start')) : null,
        end: params.get('end') ? parseInt(params.get('end')) : null,
        genres: params.get('genres') ? params.get('genres').split(',') : [],
        platforms: params.get('platforms') ? params.get('platforms').split(',') : [],
        series: params.get('series') ? params.get('series').split(',') : [],
        sort: params.get('sort') || 'rank',
        sortDirection: params.get('dir') || 'asc',
        played: params.get('played') || '',
        hltb_mode: params.get('hltb_mode') || 'main',
        hltb_min: hltb_min,
        hltb_max: hltb_max
    };
}

/**
 * Get the current game list state from the best available source
 * Priority: CSF renderer state > data attributes > DOM count
 * @returns {Object} { total, loaded, filters, showRank, csf }
 */
function getCurrentState() {
    const filters = getFiltersFromURL();
    let total = 0;
    let loaded = 0;
    let csf = null;

    // Try to get state from CSF (most authoritative when available)
    if (typeof getClientSideFiltering === 'function') {
        csf = getClientSideFiltering();
        if (csf && csf.isReady()) {
            const result = csf.applyFilters(filters);
            if (result) {
                total = result.total;
            }
            // Get loaded count from renderer if it has state
            if (csf.renderer && csf.renderer.currentItems && csf.renderer.currentItems.length > 0) {
                loaded = Math.min(
                    csf.renderer.currentPage * csf.renderer.PAGE_SIZE,
                    csf.renderer.currentItems.length
                );
            }
        }
    }

    // Fallback to data attributes if CSF doesn't have state
    if (loaded === 0) {
        const input = document.querySelector('.jump-to-rank-input');
        if (input) {
            loaded = parseInt(input.dataset.loaded) || 0;
            if (total === 0) {
                total = parseInt(input.dataset.total) || 0;
            }
        }
    }

    // Final fallback: count actual rendered rows
    const renderedRows = document.querySelectorAll('#game-list-container .game-row.desktop').length;
    if (renderedRows > loaded) {
        loaded = renderedRows;
    }

    const showRank = hasActiveFilters(filters, csf) ? 'filtered' : 'alltime';

    return { total, loaded, filters, showRank, csf };
}

/**
 * Check if any filters are active (should show filtered rank vs alltime rank)
 * @param {Object} filters - Filters from getFiltersFromURL()
 * @param {Object} csf - ClientSideFiltering instance (optional, for year bounds)
 * @returns {boolean}
 */
function hasActiveFilters(filters, csf) {
    // Check simple filters
    if (filters.q) return true;
    if (filters.genres && filters.genres.length > 0) return true;
    if (filters.platforms && filters.platforms.length > 0) return true;
    if (filters.series && filters.series.length > 0) return true;
    if (filters.played) return true;

    // Check sort - non-default sort or direction counts as filtered
    if (filters.sort && filters.sort !== 'rank') return true;
    if (filters.sortDirection && filters.sortDirection !== 'asc') return true;

    // Check year filter - only active if different from default bounds
    if (csf && csf.getYearBounds) {
        const bounds = csf.getYearBounds();
        if (filters.start && filters.start > bounds.min) return true;
        if (filters.end && filters.end < bounds.max) return true;
    } else {
        // Without CSF, any year value counts as filter
        if (filters.start) return true;
        if (filters.end) return true;
    }

    // Check HLTB filters (only if they narrow the range from defaults)
    // Default range is 0 to ∞, so only filter if min > 0 or max is explicitly set
    if (filters.hltb_min !== null && filters.hltb_min !== undefined && filters.hltb_min > 0) return true;
    if (filters.hltb_max !== null && filters.hltb_max !== undefined) return true;

    return false;
}

/**
 * Handles jumping to a specific rank
 * @param {HTMLInputElement} input - The rank input element
 */
async function handleJumpToRank(input) {
    const targetRank = parseInt(input.value);
    const perPage = parseInt(input.dataset.perPage) || 100;

    // Get authoritative state
    const state = getCurrentState();
    const { total, loaded, csf } = state;

    // Validate input
    if (!targetRank || targetRank < 1 || targetRank > total) {
        input.classList.add('input-error');
        setTimeout(() => input.classList.remove('input-error'), 1000);
        return;
    }

    // Check if target is already loaded
    if (targetRank <= loaded) {
        scrollToAndHighlightRank(targetRank);
        input.value = '';
        return;
    }

    // Try to use client-side filtering (instant, no network requests)
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

    // Fallback: fetch from server (parallel loading)
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

    if (!gameListContainer) {
        console.error('[JumpToRank CSF] No game list container found');
        return;
    }

    // Get authoritative state (filters, showRank already computed)
    const currentState = getCurrentState();
    const { filters, showRank } = currentState;

    // Determine view mode from CSF or container class
    const viewMode = csf.getViewMode ? csf.getViewMode() :
                     (gameListContainer.classList.contains('view-grid') ? 'grid' : 'list');

    // Get filtered games from engine
    const result = csf.applyFilters(filters);
    if (!result || !result.games) {
        console.error('[JumpToRank CSF] No games returned from filter');
        return;
    }

    // Round up to the next page boundary so "Load More" continues smoothly
    // e.g., if targetRank=750 and perPage=100, load up to 800
    const total = result.total;
    const pageBoundary = Math.ceil(targetRank / perPage) * perPage;
    const loadUpTo = Math.min(pageBoundary, total);
    const gamesToRender = result.games.slice(loaded, loadUpTo);
    const newLoaded = loadUpTo;

    // Render games directly to container
    const renderer = csf.renderer;

    if (viewMode === 'grid') {
        // For grid view, append cards to existing grid container
        let gridContainer = gameListContainer.querySelector('.game-grid');
        if (!gridContainer) {
            gridContainer = document.createElement('div');
            gridContainer.className = 'game-grid';
            gameListContainer.appendChild(gridContainer);
        }
        gamesToRender.forEach((game, i) => {
            const index = loaded + i + 1; // 1-based rank
            const card = renderer._renderGridCard(game, index, showRank);
            if (card) gridContainer.appendChild(card);
        });
    } else {
        // List view: render desktop + mobile rows
        gamesToRender.forEach((game, i) => {
            const index = loaded + i + 1; // 1-based rank
            const desktopRow = renderer._renderDesktopRow(game, index, showRank);
            const mobileRow = renderer._renderMobileRow(game, index, showRank);
            if (desktopRow) gameListContainer.appendChild(desktopRow);
            if (mobileRow) gameListContainer.appendChild(mobileRow);
        });
    }

    // Reinitialize HTMX for dynamically rendered content
    if (typeof htmx !== 'undefined') {
        htmx.process(gameListContainer);
    }

    // Update the renderer's state to match
    renderer.currentItems = result.games;
    renderer.currentPage = Math.ceil(newLoaded / perPage);

    // Update count display
    if (countContainer) {
        countContainer.innerHTML = renderer.getResultSummaryHtml(newLoaded, total);
    }

    // Update Load More button
    const hasMore = newLoaded < total;
    const remaining = total - newLoaded;
    if (loadMoreContainer) {
        loadMoreContainer.innerHTML = renderer.getLoadMoreHtml({
            hasMore,
            remaining,
            maxLoaded: newLoaded >= total,
            total
        });
        if (hasMore) {
            csf._initLoadMoreButton(loadMoreContainer, gameListContainer, countContainer);
        }
    }

    // Update jump-to-rank inputs
    document.querySelectorAll('.jump-to-rank-input').forEach(inp => {
        inp.dataset.loaded = newLoaded;
    });


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

    // Get all game rows (select top-level wrappers, not inner .game-row divs,
    // so desktop rows include the played button container)
    const rows = doc.querySelectorAll('.game-row-wrapper, .game-card-mobile');

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
    // Detect view mode from container
    const gameListContainer = document.getElementById('game-list-container');
    const isGridView = gameListContainer && gameListContainer.classList.contains('view-grid');

    // Position is 1-based, arrays are 0-based
    const index = position - 1;

    let elementToScroll = null;
    let elementsToHighlight = [];

    if (isGridView) {
        // Grid view: get grid cards
        const gridCards = document.querySelectorAll('.game-card-grid');
        const gridCard = gridCards[index];
        if (gridCard) {
            elementToScroll = gridCard;
            elementsToHighlight = [gridCard];
        }
    } else {
        // List view: get desktop and mobile rows
        const desktopRows = document.querySelectorAll('.game-row.desktop');
        const mobileRows = document.querySelectorAll('.game-row.game-card-mobile');

        const desktopRow = desktopRows[index];
        const mobileRow = mobileRows[index];

        if (desktopRow || mobileRow) {
            // Find the visible row (desktop rows are hidden on mobile and vice versa)
            elementToScroll = (desktopRow && desktopRow.offsetParent !== null) ? desktopRow :
                              (mobileRow && mobileRow.offsetParent !== null) ? mobileRow :
                              desktopRow || mobileRow;

            if (desktopRow) elementsToHighlight.push(desktopRow);
            if (mobileRow) elementsToHighlight.push(mobileRow);
        }
    }

    if (!elementToScroll) {
        console.warn('Could not find position:', position);
        return;
    }

    // Scroll to the element with smooth scrolling
    elementToScroll.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Add temporary highlight
    elementsToHighlight.forEach(el => el.classList.add('is-highlighted'));
    setTimeout(() => {
        elementsToHighlight.forEach(el => el.classList.remove('is-highlighted'));
    }, 3000); // Remove highlight after 3 seconds
}

/**
 * Handles Load More using client-side filtering (instant, no network)
 * @param {ClientSideFiltering} csf - The CSF instance
 */
function handleLoadMoreCSF(csf) {
    const gameListContainer = document.getElementById('game-list-container');
    const countContainer = document.querySelector('.result-count');
    const loadMoreContainer = document.querySelector('.load-more-container');

    if (!gameListContainer) return;

    // Get authoritative state
    const currentState = getCurrentState();
    const { filters, showRank, loaded } = currentState;

    // Determine view mode from CSF or container class
    const viewMode = csf.getViewMode ? csf.getViewMode() :
                     (gameListContainer.classList.contains('view-grid') ? 'grid' : 'list');

    // Initialize renderer state if not already done (taking over from server-rendered content)
    const renderer = csf.renderer;
    if (!renderer.currentItems || renderer.currentItems.length === 0) {
        // Get the filtered games from the engine
        const result = csf.applyFilters(filters);
        if (!result || !result.games) return;

        // Set the renderer's state based on what's already loaded
        renderer.currentItems = result.games;
        renderer.currentPage = Math.ceil(loaded / renderer.PAGE_SIZE);
    }

    // Ensure renderer knows the current view mode
    renderer._currentViewMode = viewMode;

    // Use CSF's loadMore method
    const state = csf.loadMore(gameListContainer, { showRank });
    if (!state) return;

    // Mark that CSF has taken over
    csf._hasRenderedUI = true;

    // Reinitialize HTMX for dynamically rendered content
    if (typeof htmx !== 'undefined') {
        htmx.process(gameListContainer);
    }

    // Update count display
    if (countContainer) {
        countContainer.innerHTML = csf.renderer.getResultSummaryHtml(state.loaded, state.total);
    }

    // Update Load More button
    if (loadMoreContainer) {
        loadMoreContainer.innerHTML = csf.renderer.getLoadMoreHtml({
            hasMore: state.hasMore,
            remaining: state.remaining,
            maxLoaded: state.loaded >= state.total,
            total: state.total
        });
    }

    // Update jump-to-rank inputs
    document.querySelectorAll('.jump-to-rank-input').forEach(inp => {
        inp.dataset.loaded = state.loaded;
    });
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
            const allRows = doc.querySelectorAll('.game-row-wrapper, .game-card-mobile');
            allRows.forEach((row) => {
                gameList.appendChild(row);
            });

            // Reinitialize HTMX for dynamically appended content
            if (typeof htmx !== 'undefined') {
                htmx.process(gameList);
            }
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
        container.innerHTML = `
            <div class="text-base-content/50 text-sm">
                <span class="mdi mdi-check-circle-outline"></span>
                <span>All ${meta.totalCount.toLocaleString()} results loaded</span>
            </div>
        `;
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

/**
 * Jump to a highlighted game by ID using client-side filtering
 * Used when navigating from game detail page with ?highlight=<game_id>
 * @param {number} gameId - The game ID to find and scroll to
 */
function jumpToHighlightedGame(gameId) {
    // Check if game is already loaded in DOM
    var desktopEl = document.getElementById('game-' + gameId);
    var mobileEl = document.getElementById('game-' + gameId + '-mobile');

    if (desktopEl || mobileEl) {
        // Game already loaded - just scroll and highlight
        scrollToAndHighlightGameById(gameId);
        return;
    }

    // Game not loaded - wait for CSF, find position, use jumpToRankClientSide
    var checkCSF = function() {
        if (typeof getClientSideFiltering !== 'function') {
            setTimeout(checkCSF, 100);
            return;
        }

        var csf = getClientSideFiltering();
        if (!csf || !csf.isReady()) {
            setTimeout(checkCSF, 100);
            return;
        }

        // Apply current filters and find the game's position
        var filters = getFiltersFromURL();
        var result = csf.applyFilters(filters);
        if (!result || !result.games) {
            console.warn('[JumpToHighlight] No games in filtered results');
            return;
        }

        // Find the game's position in filtered results (1-based)
        var position = result.games.findIndex(function(g) {
            return g.id === gameId;
        }) + 1;

        if (position <= 0) {
            console.warn('[JumpToHighlight] Game not found in filtered results:', gameId);
            return;
        }

        // Get current loaded count
        var state = getCurrentState();
        var loaded = state.loaded;
        var perPage = 100;

        // Use jumpToRankClientSide directly (same as Jump to Rank)
        jumpToRankClientSide(csf, position, loaded, perPage);

        // After loading, scroll to the specific game by ID
        setTimeout(function() {
            scrollToAndHighlightGameById(gameId);
        }, 100);
    };

    checkCSF();
}

/**
 * Scroll to and highlight a game by its ID
 * @param {number} gameId - The game ID
 */
function scrollToAndHighlightGameById(gameId) {
    // Detect view mode from container
    var gameListContainer = document.getElementById('game-list-container');
    var isGridView = gameListContainer && gameListContainer.classList.contains('view-grid');

    var elementToScroll = null;
    var elementsToHighlight = [];

    if (isGridView) {
        // Grid view: look for grid card
        var gridEl = document.getElementById('game-' + gameId + '-grid');
        if (gridEl) {
            elementToScroll = gridEl;
            elementsToHighlight = [gridEl];
        }
    } else {
        // List view: look for desktop and mobile rows
        var desktopEl = document.getElementById('game-' + gameId);
        var mobileEl = document.getElementById('game-' + gameId + '-mobile');

        var isDesktop = window.matchMedia('(min-width: 962px)').matches;
        elementToScroll = isDesktop ? desktopEl : mobileEl;

        if (desktopEl) elementsToHighlight.push(desktopEl);
        if (mobileEl) elementsToHighlight.push(mobileEl);
    }

    if (elementToScroll) {
        elementToScroll.scrollIntoView({ behavior: 'smooth', block: 'start' });
        elementsToHighlight.forEach(function(el) { el.classList.add('is-highlighted'); });
        setTimeout(function() {
            elementsToHighlight.forEach(function(el) { el.classList.remove('is-highlighted'); });
        }, 3000);
    }
}

// Export for use in templates
window.jumpToHighlightedGame = jumpToHighlightedGame;

// Auto-initialize when script loads
(function() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLoadMore);
    } else {
        // DOM already loaded
        initLoadMore();
    }
})();
