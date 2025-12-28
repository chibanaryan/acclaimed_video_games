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
 * Initializes Jump to Rank functionality
 */
function initJumpToRank() {
    const input = document.getElementById('jump-to-rank-input');
    const button = document.getElementById('jump-to-rank-btn');

    if (!input || !button) return;

    // Clone button to remove existing listeners (prevents duplicates after DOM updates)
    const newButton = button.cloneNode(true);
    button.parentNode.replaceChild(newButton, button);

    // Clone input to remove existing listeners
    const newInput = input.cloneNode(true);
    input.parentNode.replaceChild(newInput, input);

    // Handle button click
    newButton.addEventListener('click', () => handleJumpToRank(newInput));

    // Handle Enter key in input
    newInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleJumpToRank(newInput);
        }
    });
}

/**
 * Handles jumping to a specific rank
 * @param {HTMLInputElement} input - The rank input element
 */
async function handleJumpToRank(input) {
    const targetRank = parseInt(input.value);
    const total = parseInt(input.dataset.total);
    const loaded = parseInt(input.dataset.loaded);
    const perPage = parseInt(input.dataset.perPage);

    // Validate input
    if (!targetRank || targetRank < 1 || targetRank > total) {
        input.classList.add('input-error');
        setTimeout(() => input.classList.remove('input-error'), 1000);
        return;
    }

    // Check if target is already loaded
    if (targetRank <= loaded) {
        scrollToAndHighlightRank(targetRank);
        return;
    }

    // Calculate target page and load pages progressively
    const targetPage = Math.ceil(targetRank / perPage);
    const currentPage = Math.ceil(loaded / perPage);

    // Show loading state
    const button = document.getElementById('jump-to-rank-btn');
    button.classList.add('loading');
    button.disabled = true;
    input.disabled = true;

    try {
        // Load pages progressively to reach target
        for (let page = currentPage + 1; page <= targetPage; page++) {
            await loadPage(page);
        }

        // Scroll to and highlight the target rank
        setTimeout(() => {
            scrollToAndHighlightRank(targetRank);
        }, 300); // Wait for animations to settle
    } catch (err) {
        console.error('Jump to rank error:', err);
    } finally {
        button.classList.remove('loading');
        button.disabled = false;
        input.disabled = false;
        input.value = ''; // Clear input
    }
}

/**
 * Loads a specific page and appends to the list
 * @param {number} page - The page number to load
 * @returns {Promise<void>}
 */
async function loadPage(page) {
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

    if (!response.ok) throw new Error('Failed to load page');

    const html = await response.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    // Extract metadata
    const metaScript = doc.getElementById('load-more-meta');
    const meta = metaScript ? JSON.parse(metaScript.textContent) : null;
    if (metaScript) metaScript.remove();

    // Append game rows (without animation for jump)
    const gameList = document.getElementById('game-list-container');
    if (gameList) {
        const allRows = doc.querySelectorAll('.game-row');
        allRows.forEach((row) => {
            gameList.appendChild(row);
        });
    }

    // Update metadata
    if (meta) {
        updateResultSummary(meta.loadedCount, meta.totalCount);

        // Update jump to rank input data
        const input = document.getElementById('jump-to-rank-input');
        if (input) {
            input.dataset.loaded = meta.loadedCount;
        }

        // Update or remove load more button
        const loadMoreButton = document.querySelector('.load-more-button');
        if (loadMoreButton && meta) {
            updateLoadMoreButton(loadMoreButton, meta);
        }
    }
}

/**
 * Scrolls to and highlights a specific rank
 * @param {number} rank - The rank number to scroll to
 */
function scrollToAndHighlightRank(rank) {
    // Find the game row by rank
    const gameRows = document.querySelectorAll('.game-row');
    let targetRow = null;

    for (const row of gameRows) {
        const rankSpan = row.querySelector('.text-2xl.font-bold.text-primary');
        if (rankSpan && parseInt(rankSpan.textContent.trim()) === rank) {
            targetRow = row;
            break;
        }
    }

    if (!targetRow) {
        console.warn('Could not find rank:', rank);
        return;
    }

    // Scroll to the row with smooth scrolling
    targetRow.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Add temporary highlight
    targetRow.classList.add('is-highlighted');
    setTimeout(() => {
        targetRow.classList.remove('is-highlighted');
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
