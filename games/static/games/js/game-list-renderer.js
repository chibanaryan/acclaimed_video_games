/**
 * Acclaimed Games - Client-Side Game List Renderer
 *
 * Renders game rows by cloning HTML templates from the DOM.
 * Templates are defined in Django and included as <template> elements.
 * This ensures a single source of truth for HTML structure.
 *
 * Supports Load More pattern and game highlighting.
 */

/**
 * GameListRenderer - Renders game lists client-side using DOM template cloning
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
        this._templates = null;
    }

    /**
     * Initialize templates from DOM
     * Called lazily on first render
     * @private
     */
    _initTemplates() {
        if (this._templates) return;

        this._templates = {
            desktop: document.getElementById('desktop-row-template'),
            mobile: document.getElementById('mobile-row-template'),
            playedButton: document.getElementById('played-button-template')
        };

        // Fallback check - if templates don't exist, we'll use string rendering
        if (!this._templates.desktop || !this._templates.mobile) {
            console.warn('Game row templates not found, falling back to string rendering');
            this._templates = null;
        }
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
     * Fill a data slot with text content
     * @private
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
     * Render the played button by cloning template
     * @private
     * @returns {DocumentFragment|null}
     */
    _renderPlayedButtonDOM(game) {
        // Only render if authenticated and game has IGDB ID
        if (!window.isAuthenticated || !game.i) {
            return null;
        }

        const template = this._templates?.playedButton;
        if (!template) {
            // Fallback to string-based button
            const html = this._renderPlayedButtonString(game);
            if (!html) return null;
            const div = document.createElement('div');
            div.innerHTML = html;
            return div.firstElementChild;
        }

        const fragment = template.content.cloneNode(true);
        const wrapper = fragment.querySelector('[data-slot="played-wrapper"]');
        if (!wrapper) return null;

        const igdbId = game.i;
        const isPlayed = this._isPlayed(igdbId);
        const csrfToken = this._getCsrfToken();

        // Set attributes
        wrapper.dataset.tip = isPlayed ? 'You have played this game!' : 'You have not played this game.';
        wrapper.dataset.igdbId = igdbId;
        wrapper.dataset.isPlayed = isPlayed;
        wrapper.setAttribute('hx-post', `/game/${igdbId}/toggle-played/`);
        wrapper.setAttribute('hx-headers', `{"X-CSRFToken": "${csrfToken}"}`);

        // Show correct icon based on played state
        const playedIcon = wrapper.querySelector('[data-slot="played-icon"]');
        const unplayedIcon = wrapper.querySelector('[data-slot="unplayed-icon"]');

        if (isPlayed) {
            if (playedIcon) playedIcon.classList.remove('hidden');
            if (unplayedIcon) unplayedIcon.classList.add('hidden');
        } else {
            if (playedIcon) playedIcon.classList.add('hidden');
            if (unplayedIcon) unplayedIcon.classList.remove('hidden');
        }

        return fragment;
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
     * Render a single game row (desktop version) using DOM template cloning
     * @private
     * @returns {Element} The rendered desktop row element
     */
    _renderDesktopRow(game, index, showRank) {
        this._initTemplates();

        const template = this._templates?.desktop;
        if (!template) {
            // Fallback: create element from string (legacy behavior)
            return this._renderDesktopRowString(game, index, showRank);
        }

        const fragment = template.content.cloneNode(true);
        const row = fragment.querySelector('[data-slot="root"]');
        if (!row) return this._renderDesktopRowString(game, index, showRank);

        const expanded = this.engine.expandGame(game);
        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const thumbnail = this._getThumbnail(game.a);
        const thumbnail2x = this._getThumbnail2x(game.a);
        const displayRank = showRank === 'filtered' ? index : game.r;
        const showGlobalRank = showRank === 'filtered';

        // Set root element attributes
        row.id = `game-${game.id}`;

        // Add highlight to inner game-row element (not wrapper)
        const gameRowEl = row.querySelector('[data-slot="game-row"]') || row;
        if (isHighlighted) gameRowEl.classList.add('is-highlighted');

        // Fill played button (or remove container if not authenticated)
        const playedContainer = row.querySelector('[data-slot="played-button"]');
        if (playedContainer) {
            const playedButton = this._renderPlayedButtonDOM(game);
            if (playedButton) {
                playedContainer.appendChild(playedButton);
            } else {
                // Remove container to save space when not authenticated
                playedContainer.remove();
            }
        }

        // Fill rank
        const rankEl = row.querySelector('[data-slot="rank"]');
        if (rankEl) {
            if (showRank !== 'none') {
                rankEl.textContent = displayRank;
                rankEl.classList.remove('hidden');
            } else {
                rankEl.classList.add('hidden');
            }
        }

        // Fill thumbnail
        const thumbImg = row.querySelector('[data-slot="thumbnail"]');
        if (thumbImg) {
            thumbImg.src = thumbnail;
            thumbImg.srcset = `${thumbnail} 1x, ${thumbnail2x} 2x`;
            thumbImg.alt = game.n;
        }

        // Fill links
        const thumbLink = row.querySelector('[data-slot="thumb-link"]');
        if (thumbLink) thumbLink.href = `/game/${game.s}/`;

        const titleLink = row.querySelector('[data-slot="title-link"]');
        if (titleLink) titleLink.href = `/game/${game.s}/`;

        // Fill title and year
        this._fillSlot(row, 'name', game.n);
        this._fillSlot(row, 'year', game.y || 'N/A');

        const yearLink = row.querySelector('[data-slot="year-link"]');
        if (yearLink) yearLink.href = `/games/?start=${game.y}&end=${game.y}&highlight=${game.id}`;

        // Fill global rank (now under the main rank)
        const globalRankEl = row.querySelector('[data-slot="global-rank"]');
        if (globalRankEl) {
            if (showGlobalRank) {
                globalRankEl.textContent = `(#${game.r})`;
                globalRankEl.classList.remove('hidden');
            } else {
                globalRankEl.classList.add('hidden');
            }
        }

        // Fill developers
        const devsRow = row.querySelector('[data-slot="developers-row"]');
        const devsContainer = row.querySelector('[data-slot="developers"]');
        const devLabel = row.querySelector('[data-slot="developer-label"]');
        if (devsContainer && expanded.developers.length > 0) {
            if (devLabel) devLabel.textContent = expanded.developers.length === 1 ? 'Developer:' : 'Developers:';
            devsContainer.innerHTML = expanded.developers.map((dev, i) => {
                const rootDev = this._getRootDeveloper(dev);
                const devSlug = rootDev?.slug;
                const separator = i < expanded.developers.length - 1 ? ', ' : '';
                if (devSlug) {
                    const hash = dev.id !== rootDev?.id
                        ? `#developer-${dev.id}-game-${game.id}`
                        : `#game-${game.id}`;
                    return `<a href="/developers/${devSlug}/${hash}" class="link link-hover">${this._escapeHtml(dev.name)}</a>${separator}`;
                } else if (dev.slug) {
                    return `<a href="/developers/${dev.slug}/#game-${game.id}" class="link link-hover">${this._escapeHtml(dev.name)}</a>${separator}`;
                }
                return `${this._escapeHtml(dev.name)}${separator}`;
            }).join('');
        } else if (devsRow) {
            devsRow.classList.add('hidden');
        }

        // Fill platforms
        const platsRow = row.querySelector('[data-slot="platforms-row"]');
        const platsContainer = row.querySelector('[data-slot="platforms"]');
        const platLabel = row.querySelector('[data-slot="platform-label"]');
        if (platsContainer && expanded.platforms.length > 0) {
            if (platLabel) platLabel.textContent = expanded.platforms.length === 1 ? 'Platform:' : 'Platforms:';
            platsContainer.innerHTML = expanded.platforms.map(p =>
                `<button type="button" class="badge badge-xs badge-outline opacity-70 hover:opacity-100 hover:badge-primary cursor-pointer transition-colors" onclick="document.dispatchEvent(new CustomEvent('add-platform', {detail: {platformId: '${p.id}', gameId: '${game.id}'} }))" title="Filter by ${this._escapeHtml(p.name)}">${this._escapeHtml(p.code)}</button>`
            ).join('');
            if (platsRow) platsRow.classList.remove('hidden');
        } else if (platsRow) {
            platsRow.classList.add('hidden');
        }

        // Fill genres
        const genresRow = row.querySelector('[data-slot="genres-row"]');
        const genresContainer = row.querySelector('[data-slot="genres"]');
        const genreLabel = row.querySelector('[data-slot="genre-label"]');
        if (genresContainer && expanded.genres.length > 0) {
            if (genreLabel) genreLabel.textContent = expanded.genres.length === 1 ? 'Genre:' : 'Genres:';
            genresContainer.innerHTML = expanded.genres.map(g =>
                `<button type="button" class="badge badge-xs badge-outline opacity-70 hover:opacity-100 hover:badge-primary cursor-pointer transition-colors max-w-36 truncate" onclick="document.dispatchEvent(new CustomEvent('add-genre', {detail: {genreId: '${g.id}', gameId: '${game.id}'} }))" title="${this._escapeHtml(g.name)}">${this._escapeHtml(g.name)}</button>`
            ).join('');
            if (genresRow) genresRow.classList.remove('hidden');
        } else if (genresRow) {
            genresRow.classList.add('hidden');
        }

        return row;
    }

    /**
     * Fallback: Render desktop row as string (legacy behavior)
     * @private
     */
    _renderDesktopRowString(game, index, showRank) {
        const expanded = this.engine.expandGame(game);
        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const thumbnail = this._getThumbnail(game.a);
        const thumbnail2x = this._getThumbnail2x(game.a);
        const displayRank = showRank === 'filtered' ? index : game.r;
        const showGlobalRank = showRank === 'filtered';

        const developersHtml = expanded.developers.map((dev, i) => {
            const rootDev = this._getRootDeveloper(dev);
            const devSlug = rootDev?.slug;
            const separator = i < expanded.developers.length - 1 ? ', ' : '';
            if (devSlug) {
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
        const platformsHtml = expanded.platforms.map(p =>
            `<button type="button" class="badge badge-xs badge-outline opacity-70 hover:opacity-100 hover:badge-primary cursor-pointer transition-colors" onclick="document.dispatchEvent(new CustomEvent('add-platform', {detail: {platformId: '${p.id}', gameId: '${game.id}'} }))" title="Filter by ${p.name}">${p.code}</button>`
        ).join('');
        const platformLabel = expanded.platforms.length === 1 ? 'Platform' : 'Platforms';
        const genresHtml = expanded.genres.map(g =>
            `<button type="button" class="badge badge-xs badge-outline opacity-70 hover:opacity-100 hover:badge-primary cursor-pointer transition-colors max-w-36 truncate" onclick="document.dispatchEvent(new CustomEvent('add-genre', {detail: {genreId: '${g.id}', gameId: '${game.id}'} }))" title="${g.name}">${g.name}</button>`
        ).join('');
        const genreLabel = expanded.genres.length === 1 ? 'Genre' : 'Genres';
        const globalRankHtml = showGlobalRank ? `<span class="game-row-global-rank text-xs text-base-content/50">(#${game.r})</span>` : '';
        const playedButtonHtml = this._renderPlayedButtonString(game);
        // Only include container if authenticated (button exists)
        const playedContainerHtml = playedButtonHtml ? `<div class="w-10 min-w-10 max-w-10 shrink-0 flex items-center justify-center">${playedButtonHtml}</div>` : '';

        const div = document.createElement('div');
        div.innerHTML = `
<div class="game-row-wrapper hidden desktop:flex items-center" id="game-${game.id}">
    ${playedContainerHtml}
    <div class="game-row desktop flex-1 py-0.5 px-2 grid ${isHighlighted ? 'is-highlighted' : ''}" style="grid-template-columns: auto 1fr;">
        <div class="flex items-center gap-3 flex-shrink-0">
            ${showRank !== 'none' ? `<div class="w-14 text-center flex flex-col items-center justify-center"><span class="game-rank text-2xl font-bold text-primary">${displayRank}</span>${globalRankHtml}</div>` : ''}
            <a href="/game/${game.s}/" class="game-thumb-link">
                <img src="${thumbnail}" srcset="${thumbnail} 1x, ${thumbnail2x} 2x" alt="${this._escapeHtml(game.n)}" width="90" height="128" loading="lazy" decoding="async" class="game-thumb">
            </a>
        </div>
        <div class="flex-1 min-w-0 px-4">
            <div class="flex items-center justify-between gap-4">
                <div class="truncate">
                    <a href="/game/${game.s}/" class="game-title font-bold link link-hover">${this._escapeHtml(game.n)}</a>
                    <a href="/games/?start=${game.y}&end=${game.y}&highlight=${game.id}" class="text-base-content/60 ml-1" data-year="${game.y}">(${game.y || 'N/A'})</a>
                </div>
            </div>
            <div class="game-row-details text-sm ml-4">
                ${expanded.developers.length > 0 ? `<div class="truncate"><span class="text-base-content/70">${developerLabel}:</span> ${developersHtml}</div>` : ''}
                ${expanded.platforms.length > 0 ? `<div class="flex items-center gap-1"><span class="text-base-content/70 shrink-0">${platformLabel}:</span><span class="flex flex-wrap content-start gap-1 min-w-0" style="height: 1.125rem; overflow: hidden;">${platformsHtml}</span></div>` : ''}
                ${expanded.genres.length > 0 ? `<div class="flex items-center gap-1"><span class="text-base-content/70 shrink-0">${genreLabel}:</span><span class="flex flex-wrap content-start gap-1 min-w-0" style="height: 1.125rem; overflow: hidden;">${genresHtml}</span></div>` : ''}
            </div>
        </div>
    </div>
</div>`;
        return div.firstElementChild;
    }

    /**
     * Fallback: Render played button as string (legacy behavior)
     * @private
     */
    _renderPlayedButtonString(game) {
        if (!window.isAuthenticated || !game.i) return '';
        const igdbId = game.i;
        const isPlayed = this._isPlayed(igdbId);
        const csrfToken = this._getCsrfToken();
        const tooltipText = isPlayed ? 'You have played this game!' : 'You have not played this game.';
        const innerHtml = isPlayed
            ? `<span class="w-6 h-6 flex items-center justify-center"><img src="/static/games/images/mario-star.png" srcset="/static/games/images/mario-star.png 1x, /static/games/images/mario-star@2x.png 2x" alt="Played" width="32" height="32" class="w-6 h-6 drop-shadow-[0_0_6px_rgba(250,204,21,0.9)]"></span>`
            : `<span class="w-6 h-6 flex items-center justify-center"><span class="mdi mdi-star-outline text-2xl text-base-content/30"></span></span>`;
        return `<div class="desktop:tooltip desktop:tooltip-top played-button-wrapper cursor-pointer" data-tip="${tooltipText}" data-igdb-id="${igdbId}" data-is-played="${isPlayed}" hx-post="/game/${igdbId}/toggle-played/" hx-trigger="click" hx-swap="outerHTML" hx-headers='{"X-CSRFToken": "${csrfToken}"}' onclick="event.stopPropagation()"><button class="played-button flex items-center justify-center h-8 w-8 min-w-8 shrink-0 pointer-events-none">${innerHtml}</button></div>`;
    }

    /**
     * Render a single game row (mobile version) using DOM template cloning
     * @private
     * @returns {Element} The rendered mobile row element
     */
    _renderMobileRow(game, index, showRank) {
        this._initTemplates();

        const template = this._templates?.mobile;
        if (!template) {
            return this._renderMobileRowString(game, index, showRank);
        }

        const fragment = template.content.cloneNode(true);
        const row = fragment.querySelector('[data-slot="root"]');
        if (!row) return this._renderMobileRowString(game, index, showRank);

        const expanded = this.engine.expandGame(game);
        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const thumbnail = this._getThumbnail(game.a);
        const displayRank = showRank === 'filtered' ? index : game.r;
        const showRankColumn = showRank !== 'none';

        // Build metadata text
        const displayPlatforms = expanded.platforms.slice(0, 3);
        const platformsText = displayPlatforms.map(p => p.code).join(', ');
        const firstGenre = expanded.genres.length > 0 ? expanded.genres[0].name : '';
        let metaText = '';
        if (platformsText) metaText += platformsText;
        if (platformsText && firstGenre) metaText += ' \u2022 ';
        if (firstGenre) metaText += firstGenre;

        // Set root element attributes
        row.id = `game-${game.id}-mobile`;
        row.onclick = () => { window.location.href = `/game/${game.s}/`; };
        if (isHighlighted) row.classList.add('is-highlighted');

        // Fill played button (or remove container if not authenticated)
        const playedContainer = row.querySelector('[data-slot="played-button"]');
        let hasPlayedButton = false;
        if (playedContainer) {
            const playedButton = this._renderPlayedButtonDOM(game);
            if (playedButton) {
                playedContainer.appendChild(playedButton);
                hasPlayedButton = true;
            } else {
                // Remove container to save space when not authenticated
                playedContainer.remove();
            }
        }

        // Update grid columns based on played button and rank visibility
        if (hasPlayedButton) {
            row.style.gridTemplateColumns = showRankColumn ? 'auto auto auto 1fr' : 'auto auto 1fr';
        } else {
            row.style.gridTemplateColumns = showRankColumn ? 'auto auto 1fr' : 'auto 1fr';
        }

        // Fill rank (now just the inner span, parent div controls visibility)
        const rankEl = row.querySelector('[data-slot="rank"]');
        const rankParent = rankEl?.parentElement;
        if (rankEl) {
            rankEl.textContent = displayRank;
        }
        if (rankParent) {
            if (!showRankColumn) {
                rankParent.style.display = 'none';
            }
        }

        // Fill thumbnail
        const thumbImg = row.querySelector('[data-slot="thumbnail"]');
        if (thumbImg) {
            thumbImg.src = thumbnail;
            thumbImg.alt = game.n;
        }

        // Fill title (includes year span)
        const titleEl = row.querySelector('[data-slot="title"]');
        if (titleEl) {
            titleEl.innerHTML = `${this._escapeHtml(game.n)} <span class="font-normal text-base-content/60">(${game.y || 'N/A'})</span>`;
        }

        // Fill meta
        this._fillSlot(row, 'meta', metaText);

        // Show/hide global rank (now under the main rank) based on mode
        const globalRankEl = row.querySelector('[data-slot="global-rank"]');

        if (showRank === 'filtered') {
            if (globalRankEl) {
                globalRankEl.textContent = `(#${game.r})`;
                globalRankEl.classList.remove('hidden');
            }
        } else {
            if (globalRankEl) globalRankEl.classList.add('hidden');
        }

        return row;
    }

    /**
     * Fallback: Render mobile row as string (legacy behavior)
     * @private
     */
    _renderMobileRowString(game, index, showRank) {
        const expanded = this.engine.expandGame(game);
        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const thumbnail = this._getThumbnail(game.a);
        const displayRank = showRank === 'filtered' ? index : game.r;
        const showRankColumn = showRank !== 'none';

        const displayPlatforms = expanded.platforms.slice(0, 3);
        const platformsText = displayPlatforms.map(p => p.code).join(', ');
        const firstGenre = expanded.genres.length > 0 ? expanded.genres[0].name : '';
        let metaText = '';
        if (platformsText) metaText += platformsText;
        if (platformsText && firstGenre) metaText += ' \u2022 ';
        if (firstGenre) metaText += firstGenre;

        const playedButtonHtml = this._renderPlayedButtonString(game);
        // Only include container if authenticated (button exists)
        const playedContainerHtml = playedButtonHtml ? `<div class="w-8 h-8 min-w-8 max-w-8 shrink-0 flex items-center justify-center">${playedButtonHtml}</div>` : '';
        // Grid columns depend on whether played button and rank are shown
        const hasPlayedButton = !!playedButtonHtml;
        const gridCols = hasPlayedButton
            ? (showRankColumn ? 'auto auto auto 1fr' : 'auto auto 1fr')
            : (showRankColumn ? 'auto auto 1fr' : 'auto 1fr');
        const globalRankHtml = showRank === 'filtered' ? `<span class="text-xs text-base-content/50">(#${game.r})</span>` : '';

        const div = document.createElement('div');
        div.innerHTML = `
<div class="game-row game-card-mobile desktop:hidden grid items-center gap-1.5 p-2 bg-base-200 rounded-lg hover:bg-base-300 transition-colors mb-2 cursor-pointer ${isHighlighted ? 'is-highlighted' : ''}" id="game-${game.id}-mobile" onclick="window.location.href='/game/${game.s}/'" style="grid-template-columns: ${gridCols};">
    ${playedContainerHtml}
    ${showRankColumn ? `<div class="w-10 text-center flex flex-col items-center justify-center"><div class="text-2xl font-bold text-primary">${displayRank}</div>${globalRankHtml}</div>` : ''}
    <div class="w-10 mx-1 rounded overflow-hidden bg-base-300" style="aspect-ratio: 90/128;"><img src="${thumbnail}" alt="${this._escapeHtml(game.n)}" width="90" height="128" class="w-full h-full object-cover" loading="lazy" decoding="async"></div>
    <div class="min-w-0 flex items-center justify-between">
        <div class="min-w-0">
            <div class="font-bold text-base leading-tight line-clamp-2">${this._escapeHtml(game.n)} <span class="font-normal text-base-content/60">(${game.y || 'N/A'})</span></div>
            <div class="text-xs text-base-content/60 truncate">${metaText}</div>
        </div>
    </div>
</div>`;
        return div.firstElementChild;
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
        const fragment = this._renderGames(pageGames, showRank, 1);

        container.appendChild(fragment);

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
     * Render games as DOM fragment
     * @private
     * @returns {DocumentFragment}
     */
    _renderGames(games, showRank, startIndex) {
        const fragment = document.createDocumentFragment();
        games.forEach((game, i) => {
            const index = startIndex + i;
            const desktopRow = this._renderDesktopRow(game, index, showRank);
            const mobileRow = this._renderMobileRow(game, index, showRank);
            if (desktopRow) fragment.appendChild(desktopRow);
            if (mobileRow) fragment.appendChild(mobileRow);
        });
        return fragment;
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

        const fragment = this._renderGames(pageGames, showRank, start + 1);
        container.appendChild(fragment);

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
