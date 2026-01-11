/**
 * Acclaimed Games - Client-Side Game List Renderer
 *
 * Renders game rows by cloning HTML templates from the DOM.
 * Templates are defined in Django and included as <template> elements.
 * This ensures a single source of truth for HTML structure.
 *
 * Extends BaseMediaListRenderer from core.
 * Supports Load More pattern and game highlighting.
 */

/**
 * GameListRenderer - Renders game lists client-side using DOM template cloning
 *
 * Usage:
 *   const renderer = new GameListRenderer(filterEngine);
 *   renderer.render(games, container, { showRank: 'filtered' });
 */
class GameListRenderer extends BaseMediaListRenderer {
    /**
     * @param {GameFilterEngine} filterEngine - Engine with reference data
     */
    constructor(filterEngine) {
        super(filterEngine);
        // Cache static URLs (from Django template or fallback to hardcoded)
        this._staticUrls = window.staticUrls || {
            platformIcons: '/static/games/images/platform-icons.svg',
            placeholder: '/static/games/images/placeholder.webp',
            marioStar: '/static/games/images/mario-star.png',
            marioStar2x: '/static/games/images/mario-star@2x.png'
        };
    }

    /**
     * Platform family mappings (must match game_filters.py PLATFORM_FAMILIES)
     * @private
     */
    _platformFamilies = {
        // Nintendo
        'SW': 'nintendo', 'WiiU': 'nintendo', 'Wii': 'nintendo', 'GC': 'nintendo',
        'N64': 'nintendo', 'SNES': 'nintendo', 'NES': 'nintendo', 'GB': 'nintendo',
        'GBC': 'nintendo', 'GBA': 'nintendo', 'DS': 'nintendo', '3DS': 'nintendo', 'FDS': 'nintendo',
        // PlayStation
        'PS5': 'playstation', 'PS4': 'playstation', 'PS3': 'playstation',
        'PS2': 'playstation', 'PS': 'playstation', 'PSP': 'playstation',
        'PSV': 'playstation', 'PSVR': 'playstation',
        // Xbox
        'XBXS': 'xbox', 'XB1': 'xbox', 'X360': 'xbox', 'Xbox': 'xbox',
        // Sega
        'GEN': 'sega', 'DC': 'sega', 'SAT': 'sega', 'SMS': 'sega', 'GG': 'sega', 'SCD': 'sega',
        // PC
        'WIN': 'pc', 'DOS': 'pc', 'LIN': 'pc', 'MAC': 'pc',
        // Retro consoles
        'A26': 'retro', 'A52': 'retro', 'A78': 'retro', 'INTV': 'retro',
        'CV': 'retro', 'TG16': 'retro', '3DO': 'retro', 'NG': 'retro',
        'JAG': 'retro', 'LYNX': 'retro',
        // Microcomputers
        'C64': 'computers', 'AMI': 'computers', 'CD32': 'computers', 'MSX': 'computers',
        'CPC': 'computers', 'ZXS': 'computers', 'AST': 'computers', 'BBCM': 'computers',
        'PC88': 'computers', 'PC98': 'computers', 'FMT': 'computers', 'FM7': 'computers',
        'SX1': 'computers', 'T80': 'computers', 'TCC': 'computers', 'VC20': 'computers',
        'A8': 'computers', 'A2': 'computers', 'ARCH': 'computers', 'E60': 'computers',
        'HP21': 'computers', 'PDP': 'computers',
        // Arcade/Mobile/VR
        'ARC': 'arcade', 'AND': 'arcade', 'iOS': 'arcade', 'LMD': 'arcade',
        'VR': 'arcade', 'BR': 'arcade',
    };

    /**
     * Family display info (must match game_filters.py FAMILY_INFO)
     * @private
     */
    _familyInfo = {
        'nintendo': { icon: 'mdi-nintendo-switch', name: 'Nintendo', svg: null },
        'playstation': { icon: 'mdi-sony-playstation', name: 'PlayStation', svg: null },
        'xbox': { icon: 'mdi-microsoft-xbox', name: 'Xbox', svg: null },
        'pc': { icon: 'mdi-microsoft-windows', name: 'PC', svg: null },
        'sega': { icon: null, name: 'Sega', svg: 'platform-sega' },
        'retro': { icon: 'mdi-television-classic', name: 'Retro', svg: null },
        'computers': { icon: 'mdi-desktop-classic', name: 'Microcomputers', svg: null },
        'arcade': { icon: 'mdi-space-invaders', name: 'Arcade+', svg: null },
    };

    /**
     * Format playtime for display (must match game_filters.py format_playtime)
     * If less than 1 hour, shows minutes (e.g., "~30m").
     * If 1 hour or more, shows hours (e.g., "~10h").
     * @private
     * @param {number} hours - Playtime in hours
     * @returns {string} Formatted playtime string
     */
    _formatPlaytime(hours) {
        if (hours === null || hours === undefined) return '';
        if (hours < 1) {
            const minutes = Math.round(hours * 60);
            return `~${minutes}m`;
        }
        return `~${Math.round(hours)}h`;
    }

    /**
     * Sort key for platforms: (year_start, year_end, name).
     * Null values sort to end (9999).
     * @private
     */
    _platformSortKey(p) {
        return [
            p.year_start || 9999,
            p.year_end || 9999,
            p.name || ''
        ];
    }

    /**
     * Compare two platforms by sort key
     * @private
     */
    _comparePlatforms(a, b) {
        const keyA = this._platformSortKey(a);
        const keyB = this._platformSortKey(b);
        if (keyA[0] !== keyB[0]) return keyA[0] - keyB[0];
        if (keyA[1] !== keyB[1]) return keyA[1] - keyB[1];
        return keyA[2].localeCompare(keyB[2]);
    }

    /**
     * Group platforms by family for display.
     * Platforms within each family are sorted by (year_start, year_end, name).
     * Families are ordered by their first platform's sort position.
     * @private
     * @param {Array} platforms - Array of platform objects with id, code, name, year_start, year_end
     * @returns {Array} Array of family objects with icon, count, platformIds, tooltip
     */
    _groupPlatformsByFamily(platforms) {
        const families = {};

        // Group platforms by family
        for (const p of platforms) {
            const familyKey = this._platformFamilies[p.code];
            const familyInfo = this._familyInfo[familyKey];
            if (!familyInfo) continue;

            if (!families[familyKey]) {
                families[familyKey] = {
                    ...familyInfo,
                    key: familyKey,
                    _platformObjects: [],  // Keep originals for sorting
                };
            }
            families[familyKey]._platformObjects.push(p);
        }

        // Sort platforms within each family and build display data
        const result = Object.values(families).map(f => {
            // Sort platforms by (year_start, year_end, name)
            const sorted = f._platformObjects.slice().sort((a, b) => this._comparePlatforms(a, b));

            // Build display data from sorted platforms
            const platformIds = [];
            const platformNames = [];
            const platformCodes = [];
            const platformsData = [];

            for (const p of sorted) {
                platformIds.push(p.id);
                platformNames.push(p.name);
                platformCodes.push(p.code);
                platformsData.push({ code: p.code, id: p.id, name: p.name });
            }

            // Get first platform's sort key for family ordering
            const firstSortKey = sorted.length > 0 ? this._platformSortKey(sorted[0]) : [9999, 9999, ''];

            return {
                icon: f.icon,
                svg: f.svg,
                name: f.name,
                key: f.key,
                platformIds,
                platformNames,
                platformCodes,
                platforms: platformsData,
                count: platformNames.length,
                platformIdsStr: platformIds.join(','),
                tooltip: platformNames.join(', '),
                _firstSortKey: firstSortKey,
            };
        });

        // Sort families by their first platform's sort position
        result.sort((a, b) => {
            const keyA = a._firstSortKey;
            const keyB = b._firstSortKey;
            if (keyA[0] !== keyB[0]) return keyA[0] - keyB[0];
            if (keyA[1] !== keyB[1]) return keyA[1] - keyB[1];
            return keyA[2].localeCompare(keyB[2]);
        });

        // Clean up internal sort key
        for (const f of result) {
            delete f._firstSortKey;
        }

        return result;
    }

    /**
     * Initialize templates from DOM (game-specific templates)
     * Called lazily on first render
     * @protected
     * @override
     */
    _initTemplates() {
        if (this._templates) return;

        this._templates = {
            desktop: document.getElementById('desktop-row-template'),
            mobile: document.getElementById('mobile-row-template'),
            grid: document.getElementById('grid-card-template'),
            playedButton: document.getElementById('played-button-template')
        };

        // Fallback check - if templates don't exist, we'll use string rendering
        if (!this._templates.desktop || !this._templates.mobile) {
            console.warn('Game row templates not found, falling back to string rendering');
            this._templates = null;
        }
    }


    /**
     * Check if a game is marked as played
     * @private
     */
    _isPlayed(igdbId) {
        return window.playedGameIds && window.playedGameIds.has(igdbId);
    }

    /**
     * Check if a game is marked as want to play
     * @private
     */
    _isWantToPlay(igdbId) {
        return window.wantToPlayGameIds && window.wantToPlayGameIds.has(igdbId);
    }

    /**
     * Get game status: 'played', 'want', or 'none'
     * @private
     */
    _getGameStatus(igdbId) {
        if (this._isPlayed(igdbId)) return 'played';
        if (this._isWantToPlay(igdbId)) return 'want';
        return 'none';
    }


    /**
     * Render the game status dropdown button by cloning template
     * Handles 3 states: played, want to play, untracked
     * Shows dropdown with only non-current status options
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
        const status = this._getGameStatus(igdbId);
        const csrfToken = this._getCsrfToken();

        // Set tooltip based on status
        const tooltips = {
            'played': 'You have played this game!',
            'want': 'You want to play this game!',
            'none': "You aren't tracking this game."
        };
        const ariaLabels = {
            'played': 'Played - click to change',
            'want': 'Want to play - click to change',
            'none': 'Not tracked - click to change'
        };

        wrapper.dataset.igdbId = igdbId;
        wrapper.dataset.status = status;

        // Set tooltip and aria-label on the button
        const button = wrapper.querySelector('[data-slot="played-button"]');
        if (button) {
            button.dataset.tip = tooltips[status];
            button.setAttribute('aria-label', ariaLabels[status]);
        }

        // Show correct icon based on status
        const playedIcon = wrapper.querySelector('[data-slot="played-icon"]');
        const wantIcon = wrapper.querySelector('[data-slot="want-icon"]');
        const untrackedIcon = wrapper.querySelector('[data-slot="untracked-icon"]');

        // Hide all icons first
        if (playedIcon) playedIcon.classList.add('hidden');
        if (wantIcon) wantIcon.classList.add('hidden');
        if (untrackedIcon) untrackedIcon.classList.add('hidden');

        // Show the appropriate icon
        if (status === 'played' && playedIcon) {
            playedIcon.classList.remove('hidden');
        } else if (status === 'want' && wantIcon) {
            wantIcon.classList.remove('hidden');
        } else if (untrackedIcon) {
            untrackedIcon.classList.remove('hidden');
        }

        // Set up dropdown menu buttons with HTMX attributes
        const btnPlayed = wrapper.querySelector('[data-slot="btn-played"]');
        const btnWant = wrapper.querySelector('[data-slot="btn-want"]');
        const btnNone = wrapper.querySelector('[data-slot="btn-none"]');
        const menuPlayed = wrapper.querySelector('[data-slot="menu-played"]');
        const menuWant = wrapper.querySelector('[data-slot="menu-want"]');
        const menuNone = wrapper.querySelector('[data-slot="menu-none"]');

        // Set HTMX post URLs with status parameter
        if (btnPlayed) {
            btnPlayed.setAttribute('hx-post', `/game/${igdbId}/toggle-played/?status=played`);
            btnPlayed.setAttribute('hx-headers', `{"X-CSRFToken": "${csrfToken}"}`);
        }
        if (btnWant) {
            btnWant.setAttribute('hx-post', `/game/${igdbId}/toggle-played/?status=want`);
            btnWant.setAttribute('hx-headers', `{"X-CSRFToken": "${csrfToken}"}`);
        }
        if (btnNone) {
            btnNone.setAttribute('hx-post', `/game/${igdbId}/toggle-played/?status=none`);
            btnNone.setAttribute('hx-headers', `{"X-CSRFToken": "${csrfToken}"}`);
        }

        // Show/hide menu items based on current status (hide current status option)
        if (status === 'played' && menuPlayed) {
            menuPlayed.classList.add('hidden');
        }
        if (status === 'want' && menuWant) {
            menuWant.classList.add('hidden');
        }
        if (status === 'none' && menuNone) {
            menuNone.classList.add('hidden');
        }
        // Show "Untracked" option when currently tracking (played or want)
        if (status !== 'none' && menuNone) {
            menuNone.classList.remove('hidden');
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
            return this._staticUrls.placeholder;
        }
        return `https://images.igdb.com/igdb/image/upload/t_cover_small/${artworkId}`;
    }

    /**
     * Generate 2x thumbnail URL
     * @private
     */
    _getThumbnail2x(artworkId) {
        if (!artworkId) {
            return this._staticUrls.placeholder;
        }
        return `https://images.igdb.com/igdb/image/upload/t_cover_big/${artworkId}`;
    }

    /**
     * Generate larger cover URL for grid view
     * @private
     */
    _getCoverBig(artworkId) {
        if (!artworkId) {
            return this._staticUrls.placeholder;
        }
        return `https://images.igdb.com/igdb/image/upload/t_cover_big/${artworkId}`;
    }

    /**
     * Generate 2x cover URL for grid view
     * @private
     */
    _getCoverBig2x(artworkId) {
        if (!artworkId) {
            return this._staticUrls.placeholder;
        }
        return `https://images.igdb.com/igdb/image/upload/t_cover_big_2x/${artworkId}`;
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
     * Visually pleasing design with metadata always visible
     * @protected
     * @override
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

        // Fill global rank (under the main rank)
        const globalRankEl = row.querySelector('[data-slot="global-rank"]');
        if (globalRankEl) {
            if (showGlobalRank) {
                globalRankEl.textContent = `(#${game.r})`;
                globalRankEl.classList.remove('hidden');
            } else {
                globalRankEl.classList.add('hidden');
            }
        }

        // Fill meta row (developer, platforms, genres, playtime, list count - always visible)
        const metaRow = row.querySelector('[data-slot="meta-row"]');
        if (metaRow) {
            let metaHtml = '';

            // Developers
            if (expanded.developers.length > 0) {
                const devLinks = expanded.developers.map(dev => {
                    const rootDev = this._getRootDeveloper(dev);
                    const devSlug = rootDev?.slug;
                    if (devSlug) {
                        const anchor = (dev.id !== rootDev?.id)
                            ? `#developer-${dev.id}-game-${game.id}`
                            : `#game-${game.id}`;
                        return `<a href="/developers/${devSlug}/${anchor}" class="link link-hover">${this._escapeHtml(dev.name)}</a>`;
                    } else {
                        return this._escapeHtml(dev.name);
                    }
                });
                metaHtml += `<span class="whitespace-nowrap" data-slot="primary-developer">${devLinks.join(', ')}</span>`;
            }

            // Platforms - grouped by family, icons for 3+, text codes for < 3
            const platformFamilies = this._groupPlatformsByFamily(expanded.platforms);
            if (platformFamilies.length > 0) {
                const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
                const platformsHtml = platformFamilies.map((f, fi) => {
                    if (f.count >= 3) {
                        const iconHtml = f.svg
                            ? `<svg class="w-3.5 h-3.5" aria-hidden="true"><use href="${this._staticUrls.platformIcons}#${f.svg}"></use></svg>`
                            : `<span class="mdi ${f.icon} text-sm leading-none" aria-hidden="true"></span>`;
                        const countHtml = `<span class="tabular-nums font-bold leading-none" style="font-size: 8px; margin-left: 1px; margin-top: -2px;">${f.count}</span>`;
                        const comma = fi < platformFamilies.length - 1 ? ', ' : '';
                        return `<span class="tooltip tooltip-top inline-flex items-start hover:text-primary cursor-pointer transition-colors" data-tip="${this._escapeHtml(f.tooltip)}" onclick="event.stopPropagation(); document.dispatchEvent(new CustomEvent('add-platforms', {detail: {platformIds: '${f.platformIdsStr}', gameId: '${game.id}'} }))">${iconHtml}${countHtml}</span>${comma}`;
                    } else {
                        return f.platforms.map((p, pi) => {
                            const comma = (pi < f.platforms.length - 1) ? ', ' : (fi < platformFamilies.length - 1 ? ', ' : '');
                            return `<span class="tooltip tooltip-top hover:text-primary cursor-pointer transition-colors" data-tip="${this._escapeHtml(p.name)}" onclick="event.stopPropagation(); document.dispatchEvent(new CustomEvent('add-platforms', {detail: {platformIds: '${p.id}', gameId: '${game.id}'} }))">${p.code}</span>${comma}`;
                        }).join('');
                    }
                }).join('');
                metaHtml += ` <span class="whitespace-nowrap">${bullet}<span data-slot="platforms">${platformsHtml}</span></span>`;
            }

            // Genres
            if (expanded.genres.length > 0) {
                const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
                const genresHtml = expanded.genres.map((g, i) =>
                    `<button type="button" class="hover:text-primary cursor-pointer transition-colors" onclick="event.stopPropagation(); document.dispatchEvent(new CustomEvent('add-genre', {detail: {genreId: '${g.id}', gameId: '${game.id}'} }))" title="${this._escapeHtml(g.name)}">${this._escapeHtml(g.name)}</button>${i < expanded.genres.length - 1 ? '<span class="text-base-content/30"> / </span>' : ''}`
                ).join('');
                metaHtml += ` <span class="whitespace-nowrap">${bullet}<span data-slot="genres">${genresHtml}</span></span>`;
            }

            // Playtime (HLTB)
            const playtime = game.pt;
            if (playtime !== null && playtime !== undefined) {
                const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
                metaHtml += ` <span class="whitespace-nowrap">${bullet}<span class="tabular-nums" data-slot="playtime" title="HowLongToBeat playtime">${this._formatPlaytime(playtime)}</span></span>`;
            }

            // List count
            if (game.lc) {
                const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
                metaHtml += ` <span class="whitespace-nowrap">${bullet}<span class="tabular-nums" data-slot="list-count">${game.lc} lists</span></span>`;
            }

            metaRow.innerHTML = metaHtml;
        }

        return row;
    }

    /**
     * Fallback: Render desktop row as string (legacy behavior)
     * Visually pleasing design with metadata always visible
     * @private
     */
    _renderDesktopRowString(game, index, showRank) {
        const expanded = this.engine.expandGame(game);
        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const thumbnail = this._getThumbnail(game.a);
        const thumbnail2x = this._getThumbnail2x(game.a);
        const displayRank = showRank === 'filtered' ? index : game.r;
        const showGlobalRank = showRank === 'filtered';

        // Build developers HTML (in meta row)
        let primaryDevHtml = '';
        if (expanded.developers.length > 0) {
            const devLinks = expanded.developers.map(dev => {
                const rootDev = this._getRootDeveloper(dev);
                const devSlug = rootDev?.slug;
                if (devSlug) {
                    const anchor = (dev.id !== rootDev?.id)
                        ? `#developer-${dev.id}-game-${game.id}`
                        : `#game-${game.id}`;
                    return `<a href="/developers/${devSlug}/${anchor}" class="link link-hover">${this._escapeHtml(dev.name)}</a>`;
                } else {
                    return this._escapeHtml(dev.name);
                }
            });
            primaryDevHtml = `<span class="whitespace-nowrap" data-slot="primary-developer">${devLinks.join(', ')}</span>`;
        }

        // Group platforms by family - icons for 3+, text codes for < 3
        const platformFamilies = this._groupPlatformsByFamily(expanded.platforms);
        const platformsHtml = platformFamilies.map((f, fi) => {
            if (f.count >= 3) {
                const iconHtml = f.svg
                    ? `<svg class="w-3.5 h-3.5" aria-hidden="true"><use href="${this._staticUrls.platformIcons}#${f.svg}"></use></svg>`
                    : `<span class="mdi ${f.icon} text-sm leading-none" aria-hidden="true"></span>`;
                const countHtml = `<span class="tabular-nums font-bold leading-none" style="font-size: 8px; margin-left: 1px; margin-top: -2px;">${f.count}</span>`;
                const comma = fi < platformFamilies.length - 1 ? ', ' : '';
                return `<span class="tooltip tooltip-top inline-flex items-start hover:text-primary cursor-pointer transition-colors" data-tip="${this._escapeHtml(f.tooltip)}" onclick="event.stopPropagation(); document.dispatchEvent(new CustomEvent('add-platforms', {detail: {platformIds: '${f.platformIdsStr}', gameId: '${game.id}'} }))">${iconHtml}${countHtml}</span>${comma}`;
            } else {
                return f.platforms.map((p, pi) => {
                    const comma = (pi < f.platforms.length - 1) ? ', ' : (fi < platformFamilies.length - 1 ? ', ' : '');
                    return `<span class="tooltip tooltip-top hover:text-primary cursor-pointer transition-colors" data-tip="${this._escapeHtml(p.name)}" onclick="event.stopPropagation(); document.dispatchEvent(new CustomEvent('add-platforms', {detail: {platformIds: '${p.id}', gameId: '${game.id}'} }))">${p.code}</span>${comma}`;
                }).join('');
            }
        }).join('');

        const genresHtml = expanded.genres.map((g, i) =>
            `<button type="button" class="hover:text-primary cursor-pointer transition-colors" onclick="event.stopPropagation(); document.dispatchEvent(new CustomEvent('add-genre', {detail: {genreId: '${g.id}', gameId: '${game.id}'} }))" title="${this._escapeHtml(g.name)}">${this._escapeHtml(g.name)}</button>${i < expanded.genres.length - 1 ? '<span class="text-base-content/30"> / </span>' : ''}`
        ).join('');

        const globalRankHtml = showGlobalRank ? `<span class="game-row-global-rank text-xs text-base-content/60 tabular-nums">(#${game.r})</span>` : '';
        const playedButtonHtml = this._renderPlayedButtonString(game);
        const playedContainerHtml = playedButtonHtml ? `<div class="w-12 min-w-12 max-w-12 shrink-0 flex items-center justify-center">${playedButtonHtml}</div>` : '';

        // Build meta row content (developer, platforms, genres, playtime, list count - always visible)
        let metaRowHtml = primaryDevHtml;
        if (platformFamilies.length > 0) {
            const bullet = metaRowHtml ? '<span class="text-base-content/30">|</span> ' : '';
            metaRowHtml += ` <span class="whitespace-nowrap">${bullet}<span data-slot="platforms">${platformsHtml}</span></span>`;
        }
        if (expanded.genres.length > 0) {
            const bullet = metaRowHtml ? '<span class="text-base-content/30">|</span> ' : '';
            metaRowHtml += ` <span class="whitespace-nowrap">${bullet}<span data-slot="genres">${genresHtml}</span></span>`;
        }
        const playtime = game.pt;
        if (playtime !== null && playtime !== undefined) {
            const bullet = metaRowHtml ? '<span class="text-base-content/30">|</span> ' : '';
            metaRowHtml += ` <span class="whitespace-nowrap">${bullet}<span class="tabular-nums" data-slot="playtime" title="HowLongToBeat playtime">${this._formatPlaytime(playtime)}</span></span>`;
        }
        if (game.lc) {
            const bullet = metaRowHtml ? '<span class="text-base-content/30">|</span> ' : '';
            metaRowHtml += ` <span class="whitespace-nowrap">${bullet}<span class="tabular-nums" data-slot="list-count">${game.lc} lists</span></span>`;
        }

        const div = document.createElement('div');
        div.innerHTML = `
<div class="game-row-wrapper hidden desktop:flex items-center" id="game-${game.id}">
    ${playedContainerHtml}
    <div class="game-row desktop flex-1 py-1.5 px-3 grid ${isHighlighted ? 'is-highlighted' : ''}" style="grid-template-columns: auto 1fr;">
        <div class="flex items-center gap-3 flex-shrink-0">
            ${showRank !== 'none' ? `<div class="w-14 text-center flex flex-col items-center justify-center"><span class="game-rank text-xl font-bold text-accent tabular-nums">${displayRank}</span>${globalRankHtml}</div>` : ''}
            <a href="/game/${game.s}/" class="game-thumb-link">
                <img src="${thumbnail}" srcset="${thumbnail} 1x, ${thumbnail2x} 2x" alt="${this._escapeHtml(game.n)}" width="90" height="128" loading="lazy" decoding="async" class="game-thumb">
            </a>
        </div>
        <div class="flex-1 min-w-0 px-4">
            <div class="truncate">
                <a href="/game/${game.s}/" class="game-title text-lg font-bold link link-hover">${this._escapeHtml(game.n)}</a>
                <a href="/games/?start=${game.y}&end=${game.y}&highlight=${game.id}" class="text-base-content/60 ml-1.5">(${game.y || 'N/A'})</a>
            </div>
            <div class="game-row-details text-base-content/80 text-sm ml-4" data-slot="meta-row">${metaRowHtml}</div>
        </div>
    </div>
</div>`;
        return div.firstElementChild;
    }

    /**
     * Fallback: Render game status dropdown button as string
     * Handles 3 states: played, want to play, untracked
     * Shows dropdown with only non-current status options
     * @private
     */
    _renderPlayedButtonString(game) {
        if (!window.isAuthenticated || !game.i) return '';
        const igdbId = game.i;
        const status = this._getGameStatus(igdbId);
        const csrfToken = this._getCsrfToken();

        // Tooltip shows game status
        const tooltips = {
            'played': 'You have played this game!',
            'want': 'You want to play this game!',
            'none': "You aren't tracking this game."
        };
        const tooltipText = tooltips[status];

        // Icon based on status
        let innerHtml;
        if (status === 'played') {
            innerHtml = `<span class="flex items-center justify-center w-6 h-6"><img src="${this._staticUrls.marioStar}" srcset="${this._staticUrls.marioStar} 1x, ${this._staticUrls.marioStar2x} 2x" alt="Played" width="32" height="32" class="w-6 h-6 drop-shadow-[0_0_6px_rgba(250,204,21,0.9)]"></span>`;
        } else if (status === 'want') {
            innerHtml = `<span class="flex items-center justify-center w-6 h-6"><span class="mdi mdi-star-plus-outline text-2xl text-warning"></span></span>`;
        } else {
            innerHtml = `<span class="flex items-center justify-center w-6 h-6"><span class="mdi mdi-star-outline text-2xl text-base-content/30"></span></span>`;
        }

        const ariaLabels = {
            'played': 'Played - click to change',
            'want': 'Want to play - click to change',
            'none': 'Not tracked - click to change'
        };
        const ariaLabel = ariaLabels[status];

        // Build dropdown menu items (only show non-current status options)
        // Common button classes and HTMX attributes for dropdown items
        const btnClass = 'flex items-center gap-2 px-3 py-2 text-sm whitespace-nowrap';
        const hxAttrs = (targetStatus) =>
            `hx-post="/game/${igdbId}/toggle-played/?status=${targetStatus}" ` +
            `hx-target="closest .played-button-wrapper" hx-swap="outerHTML" ` +
            `hx-headers='{"X-CSRFToken": "${csrfToken}"}'`;

        let menuItems = '';
        if (status !== 'played') {
            menuItems += `<li><button type="button" class="${btnClass}" ${hxAttrs('played')}>` +
                `<span class="w-5 h-5 flex items-center justify-center">` +
                `<img src="${this._staticUrls.marioStar}" alt="" class="w-5 h-5"></span>` +
                `<span>Played</span></button></li>`;
        }
        if (status !== 'want') {
            menuItems += `<li><button type="button" class="${btnClass}" ${hxAttrs('want')}>` +
                `<span class="w-5 h-5 flex items-center justify-center">` +
                `<span class="mdi mdi-star-plus-outline text-xl text-warning"></span></span>` +
                `<span>Want to Play</span></button></li>`;
        }
        if (status !== 'none') {
            menuItems += `<li><button type="button" class="${btnClass}" ${hxAttrs('none')}>` +
                `<span class="w-5 h-5 flex items-center justify-center">` +
                `<span class="mdi mdi-star-outline text-xl text-base-content/30"></span></span>` +
                `<span>Untracked</span></button></li>`;
        }

        // Use x-data for Alpine.js dropdown toggle with z-index management
        // Dropdown positioned above button (bottom-full) for list rows
        return `<div class="played-button-wrapper relative" ` +
            `x-data="{ open: false, zHigh: false }" ` +
            `x-effect="if (open) { zHigh = true } else { setTimeout(() => zHigh = false, 100) }" ` +
            `:class="{ 'z-[9999]': zHigh, 'z-10': !zHigh }" ` +
            `@click.away="open = false" ` +
            `@open-played-dropdown.window="if ($event.detail !== $el) open = false" ` +
            `data-igdb-id="${igdbId}" data-status="${status}" onclick="event.stopPropagation()">` +
            `<button @click="$dispatch('open-played-dropdown', $el.closest('.played-button-wrapper')); open = !open" ` +
            `class="played-button desktop:tooltip desktop:tooltip-top flex items-center justify-center shrink-0 cursor-pointer h-8 w-8 min-w-8" ` +
            `data-tip="${tooltipText}" aria-label="${ariaLabel}" aria-haspopup="true" :aria-expanded="open">` +
            `${innerHtml}</button>` +
            `<ul x-show="open" x-cloak ` +
            `x-transition:enter="transition ease-out duration-100" ` +
            `x-transition:enter-start="opacity-0 scale-95" ` +
            `x-transition:enter-end="opacity-100 scale-100" ` +
            `x-transition:leave="transition ease-in duration-75" ` +
            `x-transition:leave-start="opacity-100 scale-100" ` +
            `x-transition:leave-end="opacity-0 scale-95" ` +
            `class="absolute bottom-full mb-1 left-0 menu bg-base-100 rounded-box shadow-lg p-1 min-w-max">` +
            `${menuItems}</ul></div>`;
    }

    /**
     * Render a single game row (mobile version) using DOM template cloning
     * @protected
     * @override
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
        const showRankInline = showRank !== 'none';

        // Build unified meta row: Developer, Platforms, Genres, Playtime, List count
        const platformFamilies = this._groupPlatformsByFamily(expanded.platforms);
        let metaHtml = '';

        // Developers (full list)
        if (expanded.developers.length > 0) {
            const devNames = expanded.developers.map(d => this._escapeHtml(d.name)).join(', ');
            metaHtml += `<span class="whitespace-nowrap" data-slot="primary-developer">${devNames}</span>`;
        }

        // Platforms
        if (platformFamilies.length > 0) {
            const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
            const platformsHtml = platformFamilies.map((f, fi) => {
                if (f.count >= 3) {
                    const iconHtml = f.svg
                        ? `<svg class="w-3 h-3" aria-hidden="true"><use href="${this._staticUrls.platformIcons}#${f.svg}"></use></svg>`
                        : `<span class="mdi ${f.icon}" aria-hidden="true"></span>`;
                    const countHtml = `<span class="tabular-nums font-bold" style="font-size: 8px; margin-left: 1px;">${f.count}</span>`;
                    const comma = fi < platformFamilies.length - 1 ? ', ' : '';
                    return `<span class="inline-flex items-center" title="${this._escapeHtml(f.tooltip)}">${iconHtml}${countHtml}</span>${comma}`;
                } else {
                    return f.platforms.map((p, pi) => {
                        const comma = (pi < f.platforms.length - 1) ? ', ' : (fi < platformFamilies.length - 1 ? ', ' : '');
                        return `<span title="${this._escapeHtml(p.name)}">${p.code}</span>${comma}`;
                    }).join('');
                }
            }).join('');
            metaHtml += ` <span class="whitespace-nowrap">${bullet}<span data-slot="platforms">${platformsHtml}</span></span>`;
        }

        // Genres (all)
        if (expanded.genres.length > 0) {
            const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
            const genresHtml = expanded.genres.map((g, i) =>
                `${this._escapeHtml(g.name)}${i < expanded.genres.length - 1 ? '<span class="text-base-content/30"> / </span>' : ''}`
            ).join('');
            metaHtml += ` <span class="whitespace-nowrap">${bullet}<span data-slot="genres">${genresHtml}</span></span>`;
        }

        // Playtime
        const playtime = game.pt;
        if (playtime !== null && playtime !== undefined) {
            const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
            metaHtml += ` <span class="whitespace-nowrap">${bullet}<span class="tabular-nums" data-slot="playtime" title="Playtime">${this._formatPlaytime(playtime)}</span></span>`;
        }

        // List count
        if (game.lc) {
            const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
            metaHtml += ` <span class="whitespace-nowrap">${bullet}<span class="tabular-nums" data-slot="list-count">${game.lc} lists</span></span>`;
        }

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

        // Update grid columns (no more rank column - rank is inline with title)
        row.style.gridTemplateColumns = hasPlayedButton ? 'auto auto 1fr' : 'auto 1fr';

        // Fill thumbnail
        const thumbImg = row.querySelector('[data-slot="thumbnail"]');
        if (thumbImg) {
            thumbImg.src = thumbnail;
            thumbImg.alt = game.n;
        }

        // Fill rank inline with title
        const rankEl = row.querySelector('[data-slot="rank"]');
        if (rankEl) {
            if (showRankInline) {
                rankEl.textContent = `#${displayRank}`;
            } else {
                rankEl.style.display = 'none';
            }
        }

        // Fill title (rank is now inline, so we just add name and year after rank slot)
        const titleEl = row.querySelector('[data-slot="title"]');
        if (titleEl) {
            // Build title HTML: rank (handled above) + name + year + global rank
            const globalRankHtml = showRank === 'filtered'
                ? `<span class="font-normal text-xs text-base-content/60 tabular-nums" data-slot="global-rank"> (#${game.r})</span>`
                : '';
            const rankHtml = showRankInline ? `<span class="text-accent tabular-nums text-lg" data-slot="rank">#${displayRank}</span> ` : '';
            titleEl.innerHTML = `${rankHtml}${this._escapeHtml(game.n)} <span class="font-normal text-sm text-base-content/70">(${game.y || 'N/A'})</span>${globalRankHtml}`;
        }

        // Fill meta (unified row: developer, platforms, genres, playtime, list count)
        const metaEl = row.querySelector('[data-slot="meta"]');
        if (metaEl) {
            metaEl.innerHTML = metaHtml;
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
        const showRankInline = showRank !== 'none';

        // Build unified meta row: Developer, Platforms, Genres, Playtime, List count
        const platformFamilies = this._groupPlatformsByFamily(expanded.platforms);
        let metaHtml = '';

        // Developers (full list)
        if (expanded.developers.length > 0) {
            const devNames = expanded.developers.map(d => this._escapeHtml(d.name)).join(', ');
            metaHtml += `<span class="whitespace-nowrap" data-slot="primary-developer">${devNames}</span>`;
        }

        // Platforms
        if (platformFamilies.length > 0) {
            const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
            const platformsHtml = platformFamilies.map((f, fi) => {
                if (f.count >= 3) {
                    const iconHtml = f.svg
                        ? `<svg class="w-3 h-3" aria-hidden="true"><use href="${this._staticUrls.platformIcons}#${f.svg}"></use></svg>`
                        : `<span class="mdi ${f.icon}" aria-hidden="true"></span>`;
                    const countHtml = `<span class="tabular-nums font-bold" style="font-size: 8px; margin-left: 1px;">${f.count}</span>`;
                    const comma = fi < platformFamilies.length - 1 ? ', ' : '';
                    return `<span class="inline-flex items-center" title="${this._escapeHtml(f.tooltip)}">${iconHtml}${countHtml}</span>${comma}`;
                } else {
                    return f.platforms.map((p, pi) => {
                        const comma = (pi < f.platforms.length - 1) ? ', ' : (fi < platformFamilies.length - 1 ? ', ' : '');
                        return `<span title="${this._escapeHtml(p.name)}">${p.code}</span>${comma}`;
                    }).join('');
                }
            }).join('');
            metaHtml += ` <span class="whitespace-nowrap">${bullet}<span data-slot="platforms">${platformsHtml}</span></span>`;
        }

        // Genres (all)
        if (expanded.genres.length > 0) {
            const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
            const genresHtml = expanded.genres.map((g, i) =>
                `${this._escapeHtml(g.name)}${i < expanded.genres.length - 1 ? '<span class="text-base-content/30"> / </span>' : ''}`
            ).join('');
            metaHtml += ` <span class="whitespace-nowrap">${bullet}<span data-slot="genres">${genresHtml}</span></span>`;
        }

        // Playtime
        const playtime = game.pt;
        if (playtime !== null && playtime !== undefined) {
            const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
            metaHtml += ` <span class="whitespace-nowrap">${bullet}<span class="tabular-nums" data-slot="playtime" title="Playtime">${this._formatPlaytime(playtime)}</span></span>`;
        }

        // List count
        if (game.lc) {
            const bullet = metaHtml ? '<span class="text-base-content/30">|</span> ' : '';
            metaHtml += ` <span class="whitespace-nowrap">${bullet}<span class="tabular-nums" data-slot="list-count">${game.lc} lists</span></span>`;
        }

        const playedButtonHtml = this._renderPlayedButtonString(game);
        // Only include container if authenticated (button exists)
        const playedContainerHtml = playedButtonHtml ? `<div class="w-8 h-8 min-w-8 max-w-8 shrink-0 flex items-center justify-center">${playedButtonHtml}</div>` : '';
        // Grid columns: no more rank column (rank is inline with title)
        const hasPlayedButton = !!playedButtonHtml;
        const gridCols = hasPlayedButton ? 'auto auto 1fr' : 'auto 1fr';
        // Inline rank and global rank in title
        const rankHtml = showRankInline ? `<span class="text-accent tabular-nums text-lg">#${displayRank}</span> ` : '';
        const globalRankHtml = showRank === 'filtered' ? `<span class="font-normal text-xs text-base-content/60 tabular-nums"> (#${game.r})</span>` : '';

        const div = document.createElement('div');
        div.innerHTML = `
<div class="game-row game-card-mobile desktop:hidden grid items-center gap-3 p-2 bg-base-200 rounded-lg mb-2 cursor-pointer ${isHighlighted ? 'is-highlighted' : ''}" id="game-${game.id}-mobile" onclick="window.location.href='/game/${game.s}/'" style="grid-template-columns: ${gridCols};">
    ${playedContainerHtml}
    <div class="w-12 rounded overflow-hidden bg-base-100" style="aspect-ratio: 90/128;"><img src="${thumbnail}" alt="${this._escapeHtml(game.n)}" width="90" height="128" class="w-full h-full object-cover" loading="lazy" decoding="async"></div>
    <div class="min-w-0 flex items-center justify-between">
        <div class="min-w-0">
            <div class="font-bold text-base leading-tight line-clamp-2" data-slot="title">${rankHtml}${this._escapeHtml(game.n)} <span class="font-normal text-sm text-base-content/70">(${game.y || 'N/A'})</span>${globalRankHtml}</div>
            <div class="text-xs text-base-content/65" data-slot="meta">${metaHtml}</div>
        </div>
    </div>
</div>`;
        return div.firstElementChild;
    }


    /**
     * Render a single grid card using DOM template cloning
     * @protected
     * @override
     * @returns {Element} The rendered grid card element
     */
    _renderGridCard(game, index, showRank) {
        this._initTemplates();

        const template = this._templates?.grid;
        if (!template) {
            return this._renderGridCardString(game, index, showRank);
        }

        const fragment = template.content.cloneNode(true);
        const card = fragment.querySelector('[data-slot="root"]');
        if (!card) return this._renderGridCardString(game, index, showRank);

        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const coverUrl = this._getCoverBig(game.a);
        const coverUrl2x = this._getCoverBig2x(game.a);
        const displayRank = showRank === 'filtered' ? index : game.r;

        // Set root attributes
        card.id = `game-${game.id}-grid`;
        if (isHighlighted) card.classList.add('is-highlighted');

        // Fill rank badge
        const rankEl = card.querySelector('[data-slot="rank"]');
        if (rankEl) {
            if (showRank !== 'none') {
                rankEl.textContent = `#${displayRank}`;
            } else {
                const rankContainer = card.querySelector('[data-slot="rank-container"]');
                if (rankContainer) rankContainer.remove();
            }
        }

        // Fill global rank (shown when filtered)
        const globalRankEl = card.querySelector('[data-slot="global-rank"]');
        if (globalRankEl) {
            if (showRank === 'filtered') {
                globalRankEl.textContent = `#${game.r}`;
                globalRankEl.classList.remove('hidden');
            } else {
                globalRankEl.classList.add('hidden');
            }
        }

        // Fill cover image
        const coverImg = card.querySelector('[data-slot="cover"]');
        if (coverImg) {
            coverImg.src = coverUrl;
            coverImg.srcset = `${coverUrl} 1x, ${coverUrl2x} 2x`;
            coverImg.alt = game.n;
        }

        // Fill links
        const coverLink = card.querySelector('[data-slot="cover-link"]');
        if (coverLink) coverLink.href = `/game/${game.s}/`;

        const titleLink = card.querySelector('[data-slot="title-link"]');
        if (titleLink) titleLink.href = `/game/${game.s}/`;

        // Fill title and year
        this._fillSlot(card, 'name', game.n);
        this._fillSlot(card, 'year', game.y || 'N/A');

        // Fill overlay with game details
        const expanded = this.engine.expandGame(game);

        // Developer
        const devEl = card.querySelector('[data-slot="developer"]');
        if (devEl) {
            if (expanded.developers.length > 0) {
                devEl.textContent = expanded.developers.map(d => d.name).join(', ');
            } else {
                devEl.remove();
            }
        }

        // Platforms
        const platEl = card.querySelector('[data-slot="platforms"]');
        if (platEl) {
            if (expanded.platforms.length > 0) {
                platEl.textContent = expanded.platforms.map(p => p.code).join(', ');
            } else {
                platEl.remove();
            }
        }

        // Genres
        const genreEl = card.querySelector('[data-slot="genres"]');
        if (genreEl) {
            if (expanded.genres.length > 0) {
                genreEl.textContent = expanded.genres.map(g => g.name).join(' / ');
            } else {
                genreEl.remove();
            }
        }

        // Playtime (HLTB)
        const playtimeEl = card.querySelector('[data-slot="playtime"]');
        if (playtimeEl) {
            if (game.pt !== null && game.pt !== undefined) {
                playtimeEl.textContent = this._formatPlaytime(game.pt);
                playtimeEl.title = 'HowLongToBeat playtime';
            } else {
                playtimeEl.remove();
            }
        }

        // List count
        const listEl = card.querySelector('[data-slot="list-count"]');
        if (listEl) {
            if (game.lc) {
                listEl.textContent = `${game.lc} lists`;
            } else {
                listEl.remove();
            }
        }

        return card;
    }

    /**
     * Fallback: Render grid card as string (legacy behavior)
     * @private
     */
    _renderGridCardString(game, index, showRank) {
        const isHighlighted = this.highlightId && game.id === this.highlightId;
        const coverUrl = this._getCoverBig(game.a);
        const coverUrl2x = this._getCoverBig2x(game.a);
        const displayRank = showRank === 'filtered' ? index : game.r;
        const showRankBadge = showRank !== 'none';
        const showGlobalRank = showRank === 'filtered';

        const globalRankHtml = showGlobalRank ? `<span class="game-card-global-rank">#${game.r}</span>` : '';
        const rankHtml = showRankBadge
            ? `<div class="game-card-rank"><span class="badge">#${displayRank}</span></div>`
            : '';

        // Build overlay content
        const expanded = this.engine.expandGame(game);
        let overlayContent = '';
        if (expanded.developers.length > 0) {
            overlayContent += `<div class="game-card-dev">${this._escapeHtml(expanded.developers.map(d => d.name).join(', '))}</div>`;
        }
        if (expanded.platforms.length > 0) {
            overlayContent += `<div class="game-card-platforms">${this._escapeHtml(expanded.platforms.map(p => p.code).join(', '))}</div>`;
        }
        if (expanded.genres.length > 0) {
            overlayContent += `<div class="game-card-genres">${this._escapeHtml(expanded.genres.map(g => g.name).join(' / '))}</div>`;
        }
        if (game.pt !== null && game.pt !== undefined) {
            overlayContent += `<div class="game-card-playtime" title="HowLongToBeat playtime">${this._formatPlaytime(game.pt)}</div>`;
        }
        if (game.lc) {
            overlayContent += `<div class="game-card-lists">${game.lc} lists</div>`;
        }

        const div = document.createElement('div');
        div.innerHTML = `
<div class="game-card-grid ${isHighlighted ? 'is-highlighted' : ''}" id="game-${game.id}-grid">
    <div class="game-card-cover relative">
        ${rankHtml}
        ${globalRankHtml}
        <a href="/game/${game.s}/" class="block w-full h-full">
            <img src="${coverUrl}" srcset="${coverUrl} 1x, ${coverUrl2x} 2x" alt="${this._escapeHtml(game.n)}" width="264" height="374" loading="lazy" decoding="async" class="w-full h-full object-cover">
        </a>
        <div class="game-card-overlay">
            <div class="game-card-overlay-content">${overlayContent}</div>
        </div>
    </div>
    <div class="game-card-info">
        <a href="/game/${game.s}/" class="link link-hover">
            <span class="game-card-name">${this._escapeHtml(game.n)}</span>
        </a>
        <span class="game-card-year">${game.y || 'N/A'}</span>
    </div>
</div>`;
        return div.firstElementChild;
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
     * @param {string} [options.viewMode='list'] - 'list' or 'grid'
     */
    render(games, container, options = {}) {
        const {
            showRank = 'filtered',
            highlightId = null,
            append = false,
            viewMode = 'list'
        } = options;

        this.currentItems = games;
        this.highlightId = highlightId;
        this.currentPage = 1;
        this._currentViewMode = viewMode;
        this._currentShowRank = showRank;

        if (!append) {
            container.innerHTML = '';
        }

        // Render first page
        const pageGames = games.slice(0, this.PAGE_SIZE);
        const fragment = this._renderGames(pageGames, showRank, 1, viewMode);

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
     * Render games as DOM fragment
     * @private
     * @param {string} viewMode - 'list' or 'grid'
     * @returns {DocumentFragment}
     */
    _renderGames(games, showRank, startIndex, viewMode = 'list') {
        const fragment = document.createDocumentFragment();

        if (viewMode === 'grid') {
            // Grid view: render cards inside a grid container
            const gridContainer = document.createElement('div');
            gridContainer.className = 'game-grid';

            games.forEach((game, i) => {
                const index = startIndex + i;
                const card = this._renderGridCard(game, index, showRank);
                if (card) gridContainer.appendChild(card);
            });

            fragment.appendChild(gridContainer);
        } else {
            // List view: render desktop + mobile rows
            games.forEach((game, i) => {
                const index = startIndex + i;
                const desktopRow = this._renderDesktopRow(game, index, showRank);
                const mobileRow = this._renderMobileRow(game, index, showRank);
                if (desktopRow) fragment.appendChild(desktopRow);
                if (mobileRow) fragment.appendChild(mobileRow);
            });
        }

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
        const viewMode = this._currentViewMode || 'list';

        this.currentPage++;
        const start = (this.currentPage - 1) * this.PAGE_SIZE;
        const end = start + this.PAGE_SIZE;
        const pageGames = this.currentItems.slice(start, end);

        if (pageGames.length === 0) {
            return {
                loaded: Math.min((this.currentPage - 1) * this.PAGE_SIZE, this.currentItems.length),
                total: this.currentItems.length,
                hasMore: false
            };
        }

        if (viewMode === 'grid') {
            // For grid view, append cards to existing grid container
            let gridContainer = container.querySelector('.game-grid');
            if (!gridContainer) {
                gridContainer = document.createElement('div');
                gridContainer.className = 'game-grid';
                container.appendChild(gridContainer);
            }

            pageGames.forEach((game, i) => {
                const index = start + 1 + i;
                const card = this._renderGridCard(game, index, showRank);
                if (card) gridContainer.appendChild(card);
            });
        } else {
            const fragment = this._renderGames(pageGames, showRank, start + 1, viewMode);
            container.appendChild(fragment);
        }

        // Reinitialize HTMX for dynamically rendered content
        if (typeof htmx !== 'undefined') {
            htmx.process(container);
        }

        const loaded = Math.min(this.currentPage * this.PAGE_SIZE, this.currentItems.length);
        const hasMore = loaded < this.currentItems.length && loaded < 1000; // Max 1000

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
     * Scroll to and highlight a game
     * @private
     * @param {number} gameId - Game ID to highlight
     * @param {string} viewMode - 'list' or 'grid'
     */
    _scrollToHighlight(gameId, viewMode = 'list') {
        setTimeout(() => {
            let elementToScroll = null;
            let elementsToHighlight = [];

            if (viewMode === 'grid') {
                // Grid view has a single element per game
                const gridElement = document.getElementById(`game-${gameId}-grid`);
                if (gridElement) {
                    elementToScroll = gridElement;
                    elementsToHighlight = [gridElement];
                }
            } else {
                // List view has separate desktop/mobile elements
                const desktopElement = document.getElementById(`game-${gameId}`);
                const mobileElement = document.getElementById(`game-${gameId}-mobile`);
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

                // Fade out on hover of other rows/cards
                const selector = viewMode === 'grid' ? '.game-card-grid' : '.game-row';
                const gameItems = document.querySelectorAll(selector);
                gameItems.forEach((item) => {
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
                <div class="text-base-content/70 text-center">
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
