/**
 * Acclaimed Games - Client-Side Game List Renderer
 *
 * Renders game rows matching the server-side _game_row.html template.
 * Supports Load More pattern and game highlighting.
 */

/**
 * GameListRenderer - Renders game lists client-side
 *
 * Usage:
 *   const renderer = new GameListRenderer(filterEngine);
 *   renderer.render(games, container, { showRank: 'filtered' });
 */
class GameListRenderer {
    /**
     * @param {GameFilterEngine} filterEngine - Engine with reference data
     */
    constructor(filterEngine) {
        this.engine = filterEngine;
        this.PAGE_SIZE = 100;
        this.currentPage = 1;
        this.currentGames = [];
        this.highlightId = null;
        this._csrfToken = null;
    }

    /**
     * Get CSRF token from cookie
     * @private
     */
    _getCsrfToken() {
        if (this._csrfToken) return this._csrfToken;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        this._csrfToken = match ? match[1] : '';
        return this._csrfToken;
    }

    /**
     * Check if a game is marked as played
     * @private
     */
    _isPlayed(igdbId) {
        return window.playedGameIds && window.playedGameIds.has(igdbId);
    }

    /**
     * Render the played button HTML
     * Matches server-side _played_button.html exactly
     * @private
     */
    _renderPlayedButton(game) {
        // Only render if authenticated and game has IGDB ID
        if (!window.isAuthenticated || !game.i) {
            return '';
        }

        const igdbId = game.i;
        const isPlayed = this._isPlayed(igdbId);
        const csrfToken = this._getCsrfToken();
        const title = isPlayed ? 'Unmark as played' : 'Mark as played';

        const innerHtml = isPlayed
            ? `<span class="w-8 h-8 desktop:w-6 desktop:h-6 flex items-center justify-center">
    <img src="/static/games/images/mario-star.png"
         srcset="/static/games/images/mario-star.png 1x, /static/games/images/mario-star@2x.png 2x"
         alt="Played" width="32" height="32"
         class="w-8 h-8 desktop:w-6 desktop:h-6 drop-shadow-[0_0_6px_rgba(250,204,21,0.9)]">
</span>`
            : `<span class="w-8 h-8 desktop:w-6 desktop:h-6 flex items-center justify-center">
    <span class="mdi mdi-star-outline text-4xl desktop:text-2xl text-base-content/30"></span>
</span>`;

        return `<button
    class="played-button flex items-center justify-center h-11 w-11 min-w-11 shrink-0 desktop:h-6 desktop:w-6 desktop:min-w-6 cursor-pointer overflow-hidden"
    data-igdb-id="${igdbId}"
    data-is-played="${isPlayed}"
    hx-post="/api/toggle-played-game/${igdbId}/"
    hx-swap="outerHTML"
    hx-headers='{"X-CSRFToken": "${csrfToken}"}'
    onclick="event.stopPropagation()"
    title="${title}">
    ${innerHtml}
</button>`;
    }

    /**
     * Generate thumbnail URL from artwork ID
     * Note: artwork IDs already include extensions (e.g., 'co1ir3.jpg')
     * @private
     */
    _getThumbnail(artworkId) {
        if (!artworkId) {
            return '/static/games/images/placeholder.webp';
        }
        return `https://images.igdb.com/igdb/image/upload/t_cover_small/${artworkId}`;
    }

    /**
     * Generate 2x thumbnail URL
     * @private
     */
    _getThumbnail2x(artworkId) {
        if (!artworkId) {
            return '/static/games/images/placeholder.webp';
        }
        return `https://images.igdb.com/igdb/image/upload/t_cover_big/${artworkId}`;
    }

    /**
     * Find the root developer (traverses parent hierarchy)
     * @private
     */
    _getRootDeveloper(developer) {
        if (!developer.root) return developer;
        return developer.root;
    }

    /**
     * Render a single game row (desktop version)
     * Matches server-side _game_row.html template exactly
     * @private
     */
    _renderDesktopRow(game, index, showRank) {
        const expanded = this.engine.expandGame(game);
        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const thumbnail = this._getThumbnail(game.a);
        const thumbnail2x = this._getThumbnail2x(game.a);

        // Determine rank display
        const displayRank = showRank === 'filtered' ? index : game.r;
        const showGlobalRank = showRank === 'filtered';

        // Build developers HTML - matches Django template structure
        const developersHtml = expanded.developers.map((dev, i) => {
            const rootDev = this._getRootDeveloper(dev);
            const devSlug = rootDev?.slug;
            const separator = i < expanded.developers.length - 1 ? ', ' : '';

            if (devSlug) {
                // Hash logic: when dev is not root, use #developer-{dev.id}-game-{game.id}
                // when dev is root, use #game-{game.id}
                const hash = dev.id !== rootDev?.id
                    ? `#developer-${dev.id}-game-${game.id}`
                    : `#game-${game.id}`;
                return `<a href="/developers/${devSlug}/${hash}" class="link link-hover">${dev.name}</a>${separator}`;
            } else if (dev.slug) {
                return `<a href="/developers/${dev.slug}/#game-${game.id}" class="link link-hover">${dev.name}</a>${separator}`;
            }
            return `${dev.name}${separator}`;
        }).join('');

        const developerLabel = expanded.developers.length === 1 ? 'Developer' : 'Developers';

        // Build platforms HTML - all platforms, CSS handles overflow
        const platformsHtml = expanded.platforms.map(p =>
            `<button type="button" class="badge badge-xs badge-outline hover:badge-primary cursor-pointer transition-colors" onclick="document.dispatchEvent(new CustomEvent('add-platform', {detail: {platformId: '${p.id}', gameId: '${game.id}'} }))" title="Filter by ${p.name}">${p.code}</button>`
        ).join('');
        const platformLabel = expanded.platforms.length === 1 ? 'Platform' : 'Platforms';

        // Build genres HTML - all genres, CSS handles overflow
        const genresHtml = expanded.genres.map(g =>
            `<button type="button" class="badge badge-xs badge-outline hover:badge-primary cursor-pointer transition-colors max-w-36 truncate" onclick="document.dispatchEvent(new CustomEvent('add-genre', {detail: {genreId: '${g.id}', gameId: '${game.id}'} }))" title="${g.name}">${g.name}</button>`
        ).join('');
        const genreLabel = expanded.genres.length === 1 ? 'Genre' : 'Genres';

        const globalRankHtml = showGlobalRank
            ? `<span class="game-row-global-rank text-sm text-base-content/60 shrink-0 font-medium">#${game.r}</span>`
            : '';

        // Render played button
        const playedButtonHtml = this._renderPlayedButton(game);

        return `
<div class="game-row desktop hidden desktop:grid py-0.5 px-2 ${isHighlighted ? 'is-highlighted' : ''}" id="game-${game.id}" style="grid-template-columns: auto 1fr;">
    <div class="flex items-center gap-3 flex-shrink-0">
        <div class="w-6 min-w-6 max-w-6 shrink-0 flex items-center justify-center">
            ${playedButtonHtml}
        </div>
        ${showRank !== 'none' ? `<span class="game-rank text-2xl font-bold text-primary w-14 text-center">${displayRank}</span>` : ''}
        <a href="/game/${game.s}/" class="game-thumb-link">
            <img src="${thumbnail}"
                 srcset="${thumbnail} 1x, ${thumbnail2x} 2x"
                 alt="${this._escapeHtml(game.n)}" width="90" height="128" loading="lazy" decoding="async"
                 class="game-thumb">
        </a>
    </div>
    <div class="flex-1 min-w-0 px-4">
        <div class="flex items-center justify-between gap-4">
            <div class="truncate">
                <a href="/game/${game.s}/" class="game-title font-bold link link-hover">
                    ${this._escapeHtml(game.n)}
                </a>
                <a href="/games/?start=${game.y}&end=${game.y}&highlight=${game.id}" class="text-base-content/60 ml-1" data-year="${game.y}">
                    (${game.y || 'N/A'})
                </a>
            </div>
            ${globalRankHtml}
        </div>
        <div class="game-row-details text-sm ml-4">
            ${expanded.developers.length > 0 ? `<div class="truncate"><span class="text-base-content/70">${developerLabel}:</span> ${developersHtml}</div>` : ''}
            ${expanded.platforms.length > 0 ? `<div class="flex items-center gap-1"><span class="text-base-content/70 shrink-0">${platformLabel}:</span><span class="flex flex-wrap content-start gap-1 min-w-0" style="height: 1.125rem; overflow: hidden;">${platformsHtml}</span></div>` : ''}
            ${expanded.genres.length > 0 ? `<div class="flex items-center gap-1"><span class="text-base-content/70 shrink-0">${genreLabel}:</span><span class="flex flex-wrap content-start gap-1 min-w-0" style="height: 1.125rem; overflow: hidden;">${genresHtml}</span></div>` : ''}
        </div>
    </div>
</div>`;
    }

    /**
     * Render a single game row (mobile version)
     * Matches server-side _game_row.html template exactly
     * @private
     */
    _renderMobileRow(game, index, showRank) {
        const expanded = this.engine.expandGame(game);
        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const thumbnail = this._getThumbnail(game.a);

        const displayRank = showRank === 'filtered' ? index : game.r;
        const showRankColumn = showRank !== 'none';

        // Build platforms text (limit to 3, comma-separated codes)
        const displayPlatforms = expanded.platforms.slice(0, 3);
        const platformsText = displayPlatforms.map(p => p.code).join(', ');

        // Get first genre name
        const firstGenre = expanded.genres.length > 0 ? expanded.genres[0].name : '';

        // Build metadata text: "platforms • genre"
        let metaText = '';
        if (platformsText) metaText += platformsText;
        if (platformsText && firstGenre) metaText += ' • ';
        if (firstGenre) metaText += firstGenre;

        // Grid template columns: star [rank] thumbnail content
        const gridCols = showRankColumn ? 'auto auto auto 1fr' : 'auto auto 1fr';

        // Render played button
        const playedButtonHtml = this._renderPlayedButton(game);

        // End element: global rank or chevron (inside content div)
        const endElementHtml = showRank === 'filtered'
            ? `<span class="text-sm text-base-content/60 font-medium shrink-0 ml-2">#${game.r}</span>`
            : `<svg class="w-5 h-5 text-base-content/30 shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
        </svg>`;

        return `
<div class="game-row game-card-mobile desktop:hidden grid items-center gap-2 p-2 bg-base-200 rounded-lg hover:bg-base-300 transition-colors mb-2 cursor-pointer ${isHighlighted ? 'is-highlighted' : ''}"
   id="game-${game.id}-mobile"
   onclick="window.location.href='/game/${game.s}/'"
   style="grid-template-columns: ${gridCols};">
    <div class="w-11 h-11 min-w-11 max-w-11 shrink-0 flex items-center justify-center">
        ${playedButtonHtml}
    </div>
    ${showRankColumn ? `<div class="text-2xl font-bold text-primary w-10 text-center">${displayRank}</div>` : ''}
    <div class="w-10 mx-1 rounded overflow-hidden bg-base-300" style="aspect-ratio: 90/128;">
        <img src="${thumbnail}" alt="${this._escapeHtml(game.n)}" width="90" height="128"
             class="w-full h-full object-cover" loading="lazy" decoding="async">
    </div>
    <div class="min-w-0 flex items-center justify-between">
        <div class="min-w-0">
            <div class="font-bold text-base leading-tight line-clamp-2">${this._escapeHtml(game.n)} <span class="font-normal text-base-content/60">(${game.y || 'N/A'})</span></div>
            <div class="text-xs text-base-content/60 truncate">${metaText}</div>
        </div>
        ${endElementHtml}
    </div>
</div>`;
    }

    /**
     * Escape HTML special characters
     * @private
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    /**
     * Render game list to container
     *
     * @param {Array} games - Games to render
     * @param {HTMLElement} container - Container element
     * @param {Object} options - Render options
     * @param {string} [options.showRank='alltime'] - 'alltime', 'filtered', or 'none'
     * @param {number} [options.highlightId] - Game ID to highlight
     * @param {boolean} [options.append=false] - Append to existing content
     */
    render(games, container, options = {}) {
        const {
            showRank = 'filtered',
            highlightId = null,
            append = false
        } = options;

        this.currentGames = games;
        this.highlightId = highlightId;
        this.currentPage = 1;

        if (!append) {
            container.innerHTML = '';
        }

        // Render first page
        const pageGames = games.slice(0, this.PAGE_SIZE);
        const html = this._renderGames(pageGames, showRank, 1);

        if (append) {
            container.insertAdjacentHTML('beforeend', html);
        } else {
            container.innerHTML = html;
        }

        // Reinitialize HTMX for dynamically rendered content
        if (typeof htmx !== 'undefined') {
            htmx.process(container);
        }

        // Handle highlighting
        if (highlightId) {
            this._scrollToHighlight(highlightId);
        }
    }

    /**
     * Render games HTML
     * @private
     */
    _renderGames(games, showRank, startIndex) {
        return games.map((game, i) => {
            const index = startIndex + i;
            return this._renderDesktopRow(game, index, showRank) +
                   this._renderMobileRow(game, index, showRank);
        }).join('');
    }

    /**
     * Load more games (for Load More button)
     *
     * @param {HTMLElement} container - Container element
     * @param {Object} options - Options
     * @returns {Object} { loaded, total, hasMore }
     */
    loadMore(container, options = {}) {
        const { showRank = 'filtered' } = options;

        this.currentPage++;
        const start = (this.currentPage - 1) * this.PAGE_SIZE;
        const end = start + this.PAGE_SIZE;
        const pageGames = this.currentGames.slice(start, end);

        if (pageGames.length === 0) {
            return {
                loaded: Math.min((this.currentPage - 1) * this.PAGE_SIZE, this.currentGames.length),
                total: this.currentGames.length,
                hasMore: false
            };
        }

        const html = this._renderGames(pageGames, showRank, start + 1);
        container.insertAdjacentHTML('beforeend', html);

        // Reinitialize HTMX for dynamically rendered content
        if (typeof htmx !== 'undefined') {
            htmx.process(container);
        }

        const loaded = Math.min(this.currentPage * this.PAGE_SIZE, this.currentGames.length);
        const hasMore = loaded < this.currentGames.length && loaded < 1000; // Max 1000

        return {
            loaded,
            total: this.currentGames.length,
            hasMore,
            remaining: Math.min(this.currentGames.length - loaded, 1000 - loaded)
        };
    }

    /**
     * Reset pagination
     */
    reset() {
        this.currentPage = 1;
        this.currentGames = [];
        this.highlightId = null;
    }

    /**
     * Scroll to and highlight a game
     * @private
     */
    _scrollToHighlight(gameId) {
        setTimeout(() => {
            const desktopElement = document.getElementById(`game-${gameId}`);
            const mobileElement = document.getElementById(`game-${gameId}-mobile`);
            const isDesktop = window.matchMedia('(min-width: 962px)').matches;
            const element = isDesktop ? desktopElement : mobileElement;

            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'start' });

                // Fade out highlight after 4 seconds
                const fadeTimeout = setTimeout(() => {
                    if (desktopElement) desktopElement.classList.add('fade-out');
                    if (mobileElement) mobileElement.classList.add('fade-out');
                }, 4000);

                // Fade out on hover of other rows
                const gameRows = document.querySelectorAll('.game-row');
                gameRows.forEach((row) => {
                    if (row !== desktopElement && row !== mobileElement) {
                        row.addEventListener('mouseenter', () => {
                            clearTimeout(fadeTimeout);
                            if (desktopElement) desktopElement.classList.add('fade-out');
                            if (mobileElement) mobileElement.classList.add('fade-out');
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
        return `Showing <span id="loaded-count" class="loaded-count-value">${loaded.toLocaleString()}</span> of ${total.toLocaleString()}`;
    }

    /**
     * Generate load more button HTML
     * @param {Object} state - { hasMore, remaining, maxLoaded }
     * @returns {string} HTML string
     */
    getLoadMoreHtml(state) {
        const { hasMore, remaining, maxLoaded } = state;

        if (maxLoaded) {
            return `
                <div class="alert alert-info">
                    <span class="mdi mdi-information-outline"></span>
                    <span>Showing maximum of 1,000 results. Refine your filters to see more specific results.</span>
                </div>
            `;
        }

        if (!hasMore) {
            return `
                <div class="text-base-content/60 text-center">
                    All results loaded
                </div>
            `;
        }

        return `
            <button type="button" class="btn btn-ghost load-more-button">
                <span class="mdi mdi-space-invaders"></span>
                <span class="load-more-text">Load More (${remaining.toLocaleString()} remaining)</span>
            </button>
        `;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.GameListRenderer = GameListRenderer;
}
