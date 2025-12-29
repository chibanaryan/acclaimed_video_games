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
     * Generate square thumbnail URL for mobile
     * @private
     */
    _getThumbnailSquare(artworkId) {
        if (!artworkId) {
            return '/static/games/images/placeholder.webp';
        }
        return `https://images.igdb.com/igdb/image/upload/t_thumb/${artworkId}`;
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

        // Build developers HTML
        const developersHtml = expanded.developers.map((dev, i) => {
            const rootDev = this._getRootDeveloper(dev);
            const devSlug = rootDev?.slug;
            const separator = i < expanded.developers.length - 1 ? ', ' : '';

            if (devSlug) {
                // Only add hash when dev is not the root developer
                const hash = dev.id !== rootDev?.id ? `#developer-${dev.id}-game-${game.id}` : '';
                return `<a href="/developers/${devSlug}/${hash}" class="link link-hover text-base-content">${dev.name}</a>${separator}`;
            }
            return `<span class="text-base-content">${dev.name}</span>${separator}`;
        }).join('');

        const developerLabel = expanded.developers.length === 1 ? 'Developer' : 'Developers';

        // Build platforms HTML (limit to 6)
        const displayPlatforms = expanded.platforms.slice(0, 6);
        const extraPlatforms = expanded.platforms.length > 6 ? expanded.platforms.length - 6 : 0;

        const platformsHtml = displayPlatforms.map(p =>
            `<button type="button" class="badge badge-xs badge-outline hover:badge-primary cursor-pointer transition-colors" onclick="document.dispatchEvent(new CustomEvent('add-platform', {detail: {platformId: '${p.id}', gameId: '${game.id}'} }))" title="Filter by ${p.name}">${p.code}</button>`
        ).join('');
        const platformExtraHtml = extraPlatforms > 0 ? `<span class="text-xs text-base-content/50 ml-1">+${extraPlatforms}</span>` : '';
        const platformLabel = expanded.platforms.length === 1 ? 'Platform' : 'Platforms';

        // Build genres HTML (limit to 3)
        const displayGenres = expanded.genres.slice(0, 3);
        const extraGenres = expanded.genres.length > 3 ? expanded.genres.length - 3 : 0;

        const genresHtml = displayGenres.map(g =>
            `<button type="button" class="badge badge-xs badge-outline hover:badge-primary cursor-pointer transition-colors" onclick="document.dispatchEvent(new CustomEvent('add-genre', {detail: {genreId: '${g.id}', gameId: '${game.id}'} }))" title="Filter by ${g.name}">${g.name}</button>`
        ).join('');
        const genreExtraHtml = extraGenres > 0 ? `<span class="text-xs text-base-content/50 ml-1">+${extraGenres}</span>` : '';
        const genreLabel = expanded.genres.length === 1 ? 'Genre' : 'Genres';

        const globalRankHtml = showGlobalRank
            ? `<span class="game-row-global-rank text-sm text-base-content/60 shrink-0 font-medium">#${game.r}</span>`
            : '';

        return `
<div class="game-row desktop hidden lg:grid py-1.5 px-2 ${isHighlighted ? 'is-highlighted' : ''}" id="game-${game.id}" style="grid-template-columns: auto 1fr;">
    <div class="flex items-center gap-3 flex-shrink-0">
        ${showRank !== 'none' ? `<span class="text-2xl font-bold text-primary w-12 text-center">${displayRank}</span>` : ''}
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
                <a href="/game/${game.s}/" class="font-bold text-lg link link-hover">
                    ${this._escapeHtml(game.n)}
                </a>
                <a href="/games/?start=${game.y}&end=${game.y}&highlight=${game.id}" class="text-base-content/60 ml-1" data-year="${game.y}">
                    (${game.y || 'N/A'})
                </a>
            </div>
            ${globalRankHtml}
        </div>
        <div class="game-row-details text-sm mt-0.5">
            ${expanded.developers.length > 0 ? `<div class="text-base-content/70">${developerLabel}: ${developersHtml}</div>` : ''}
            ${expanded.platforms.length > 0 ? `<div class="flex items-center gap-1 text-base-content/70">${platformLabel}: ${platformsHtml}${platformExtraHtml}</div>` : ''}
            ${expanded.genres.length > 0 ? `<div class="flex items-center gap-1 text-base-content/70">${genreLabel}: ${genresHtml}${genreExtraHtml}</div>` : ''}
        </div>
    </div>
</div>`;
    }

    /**
     * Render a single game row (mobile version)
     * @private
     */
    _renderMobileRow(game, index, showRank) {
        const expanded = this.engine.expandGame(game);
        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const thumbnailSquare = this._getThumbnailSquare(game.a);

        const displayRank = showRank === 'filtered' ? index : game.r;

        // Build platforms HTML (limit to 4 for mobile)
        const displayPlatforms = expanded.platforms.slice(0, 4);
        const extraPlatforms = expanded.platforms.length > 4 ? expanded.platforms.length - 4 : 0;

        const platformsHtml = displayPlatforms.map(p =>
            `<button type="button" class="badge badge-xs badge-outline hover:badge-primary cursor-pointer transition-colors" onclick="event.stopPropagation(); event.preventDefault(); document.dispatchEvent(new CustomEvent('add-platform', {detail: {platformId: '${p.id}', gameId: '${game.id}'} }))" title="Filter by ${p.name}">${p.code}</button>`
        ).join('');
        const platformExtraHtml = extraPlatforms > 0 ? `<span class="text-xs text-base-content/50">+${extraPlatforms}</span>` : '';

        return `
<a href="/game/${game.s}/"
   class="game-row game-card-mobile lg:hidden flex items-center gap-3 p-3 bg-base-200 rounded-lg hover:bg-base-300 transition-colors mb-2 ${isHighlighted ? 'is-highlighted' : ''}"
   id="game-${game.id}-mobile">
    ${showRank !== 'none' ? `<div class="text-2xl font-bold text-primary w-10 text-center shrink-0">${displayRank}</div>` : ''}
    <div class="w-12 h-12 shrink-0 rounded-lg overflow-hidden bg-base-300">
        <img src="${thumbnailSquare}"
             alt="${this._escapeHtml(game.n)}"
             width="90" height="90"
             class="w-full h-full object-cover"
             loading="lazy"
             decoding="async">
    </div>
    <div class="flex-1 min-w-0">
        <h3 class="font-bold text-base">${this._escapeHtml(game.n)}</h3>
        <div class="flex items-center flex-wrap gap-1 text-sm text-base-content/60">
            <span class="mr-1" data-year="${game.y}">${game.y || 'N/A'}</span>
            ${platformsHtml}${platformExtraHtml}
        </div>
    </div>
    ${showRank === 'filtered'
        ? `<span class="text-sm text-base-content/60 shrink-0 font-medium">#${game.r}</span>`
        : `<svg class="w-5 h-5 text-base-content/30 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
    </svg>`}
</a>`;
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
            const isDesktop = window.matchMedia('(min-width: 1088px)').matches;
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
        return `<span id="loaded-count" class="loaded-count-value">${loaded.toLocaleString()}</span> of ${total.toLocaleString()} games`;
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
