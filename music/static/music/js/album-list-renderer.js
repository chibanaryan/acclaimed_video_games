/**
 * Acclaimed Albums - Client-Side Album List Renderer
 *
 * Renders album rows by cloning the <template> elements music/home.html
 * declares, which hold the same `_album_row.html` partial the server renders
 * rows with. That shared partial is the single source of truth for the
 * markup; this file only fills its data-slot hooks. Changing one without the
 * other is what the dual-rendering section of AGENTS.md warns about.
 *
 * Extends BaseMediaListRenderer from core, which owns paging, load-more,
 * highlight scrolling and the result summary.
 */
class AlbumListRenderer extends BaseMediaListRenderer {
    /**
     * @param {AlbumFilterEngine} filterEngine - Engine with reference data
     */
    constructor(filterEngine) {
        super(filterEngine);
    }

    /**
     * A path on the music site. Every URL here starts from the rankings
     * page's own address, which the page renders with {% url %} - music is
     * the root of its own host now, and was /music/ before that.
     * @protected
     */
    _musicPath(rest) {
        return (window.albumRankingsUrl || '/') + rest;
    }

    /**
     * Grab the row templates on first render.
     * @protected
     */
    _initTemplates() {
        if (this._templates) return;

        this._templates = {
            desktop: document.getElementById('desktop-row-template'),
            mobile: document.getElementById('mobile-row-template'),
            grid: document.getElementById('grid-card-template'),
            // Optional: absent when nobody is signed in, and the rows still
            // render without it.
            trackingButton: document.getElementById('tracking-button-template')
        };

        if (!this._templates.desktop || !this._templates.mobile) {
            // Nothing can be rendered without them. The caller leaves the
            // server-rendered rows alone when render() returns nothing.
            console.warn('Album row templates not found; keeping server-rendered rows');
            this._templates = null;
        }
    }

    /**
     * This album's listen status, from the Sets the page rendered.
     * @private
     */
    _albumStatus(albumId) {
        if (window.ownedAlbumIds && window.ownedAlbumIds.has(albumId)) {
            return 'own';
        }
        if (window.listenedAlbumIds && window.listenedAlbumIds.has(albumId)) {
            return 'listened';
        }
        if (window.wantToListenAlbumIds && window.wantToListenAlbumIds.has(albumId)) {
            return 'want';
        }
        return 'none';
    }

    /**
     * Build one listen button by cloning `_listen_button_template.html`.
     *
     * Returns null for an anonymous reader, which is also what the server
     * does - the caller then drops the whole column, so the row has the same
     * shape either way.
     *
     * Unlike games there is no string-building fallback: every row here is
     * cloned from a template, and `_initTemplates` already keeps the
     * server's rows when one is missing, so a second copy of this markup
     * would have no path that reached it.
     *
     * @private
     * @returns {Element|null}
     */
    _renderTrackingButtonDOM(album) {
        if (!window.isAuthenticated) return null;
        this._initTemplates();
        if (!this._templates || !this._templates.trackingButton) return null;

        const wrapper = this._templates.trackingButton.content
            .cloneNode(true).firstElementChild;
        if (!wrapper) return null;

        const status = this._albumStatus(album.id);
        const toggleUrl = this._musicPath(`${album.id}/toggle-listened/`);
        wrapper.dataset.itemId = String(album.id);
        wrapper.dataset.toggleUrl = toggleUrl;
        wrapper.dataset.status = status;

        const tips = {
            own: 'You have this album!',
            listened: 'You have heard this album!',
            want: 'You want this album!',
            none: "You aren't tracking this album."
        };
        const labels = {
            own: 'Have',
            listened: 'Heard',
            want: 'Want',
            none: 'Untracked'
        };
        const button = wrapper.querySelector('[data-slot="tracking-button"]');
        if (button) {
            button.setAttribute('data-tip', tips[status]);
            button.setAttribute('aria-label', `${labels[status]} - click to change`);
        }

        // Show the icon for the current state and hide the others.
        const icons = {
            own: 'owned-icon',
            listened: 'tracked-icon',
            want: 'wanted-icon',
            none: 'untracked-icon'
        };
        Object.keys(icons).forEach(key => {
            const icon = wrapper.querySelector(`[data-slot="${icons[key]}"]`);
            if (icon) icon.classList.toggle('hidden', key !== status);
        });

        // The server writes these URLs with {% url %}; the template cannot,
        // because it is rendered once with no album.
        const csrf = this._getCsrfToken();
        const targets = {
            'btn-owned': 'own',
            'btn-tracked': 'listened',
            'btn-wanted': 'want',
            'btn-untracked': 'none'
        };
        Object.keys(targets).forEach(slot => {
            const el = wrapper.querySelector(`[data-slot="${slot}"]`);
            if (!el) return;
            el.setAttribute(
                'hx-post',
                `${toggleUrl}?status=${targets[slot]}`
            );
            el.setAttribute('hx-headers', `{"X-CSRFToken": "${csrf}"}`);
        });

        // Offer only the states this album is not already in.
        const menus = {
            own: 'menu-owned',
            listened: 'menu-tracked',
            want: 'menu-wanted',
            none: 'menu-untracked'
        };
        Object.keys(menus).forEach(key => {
            const item = wrapper.querySelector(`[data-slot="${menus[key]}"]`);
            if (item) item.classList.toggle('hidden', key === status);
        });

        return wrapper;
    }

    /**
     * Fill or drop a row's tracking column.
     *
     * @private
     * @returns {boolean} whether the column survived
     */
    _fillTrackingButton(row, album, slot) {
        const container = row.querySelector(`[data-slot="${slot}"]`);
        if (!container) return false;

        const button = this._renderTrackingButtonDOM(album);
        if (!button) {
            container.remove();
            return false;
        }
        container.appendChild(button);
        return true;
    }

    /**
     * Render one grid card, cloning the same `_album_card_grid.html` the
     * server renders cards with.
     * @protected
     * @returns {Element|null}
     */
    _renderGridCard(compactAlbum, index, showRank) {
        this._initTemplates();
        if (!this._templates || !this._templates.grid) return null;

        const card = this._templates.grid.content.cloneNode(true).firstElementChild;
        if (!card) return null;

        const album = this.engine.expandAlbum(compactAlbum);
        const url = this._musicPath(`${encodeURIComponent(album.slug)}/`);

        card.id = `music-${album.id}-grid`;
        if (this.highlightId && album.id === this.highlightId) {
            card.classList.add('is-highlighted');
        }

        // The grid badge carries a # that the row's rank column does not,
        // so the rank pair is filled here rather than through _fillRanks.
        const rank = card.querySelector('[data-slot="rank-grid"]');
        if (rank && showRank !== 'none') {
            rank.textContent = `#${showRank === 'filtered' ? index : album.rank}`;
        }
        const globalRank = card.querySelector('[data-slot="global-rank-grid"]');
        if (globalRank) {
            globalRank.textContent = `#${album.rank}`;
            globalRank.classList.toggle('hidden', showRank !== 'filtered');
        }

        this._fillCover(card, album, 'cover', 'cover-placeholder');
        const coverLink = card.querySelector('[data-slot="cover-link"]');
        if (coverLink) coverLink.href = url;

        this._fillSlot(card, 'name-grid', album.name);
        const titleLink = card.querySelector('[data-slot="title-link-grid"]');
        if (titleLink) titleLink.href = url;
        this._fillSlot(card, 'year-grid', album.year === null ? '' : album.year);

        this._fillSlot(card, 'creator', album.artistCredit || '');
        const genres = card.querySelector('[data-slot="genres-grid"]');
        if (genres) {
            genres.textContent = album.genres.map(genre => genre.n).join(' / ');
        }
        const listCount = card.querySelector('[data-slot="list-count-grid"]');
        if (listCount) {
            const label = album.listCount === 1 ? 'list' : 'lists';
            listCount.textContent = album.listCount
                ? `${album.listCount} ${label}`
                : '';
        }

        return card;
    }

    /**
     * Point the cover <img> at an album's art, or show the placeholder.
     *
     * Both elements are always in the row - see the comment in
     * `_album_row.html` - so this is a matter of filling one and hiding the
     * other, in whichever direction the album needs.
     * @private
     */
    _fillCover(row, album, imgSlot, placeholderSlot) {
        const img = row.querySelector(`[data-slot="${imgSlot}"]`);
        const placeholder = row.querySelector(`[data-slot="${placeholderSlot}"]`);

        if (img && album.thumbnail) {
            img.src = album.thumbnail;
            img.alt = album.name;
            img.classList.remove('hidden');
        } else if (img) {
            img.removeAttribute('src');
            img.classList.add('hidden');
        }

        if (placeholder) {
            placeholder.classList.toggle('hidden', Boolean(album.thumbnail));
        }
    }

    /**
     * Fill the rank pair, matching the server's show_rank handling.
     * @private
     */
    _fillRanks(row, album, index, showRank, slot, globalSlot) {
        if (showRank === 'none') return;

        this._fillSlot(row, slot, showRank === 'filtered' ? index : album.rank);

        if (!globalSlot) return;
        const globalRank = row.querySelector(`[data-slot="${globalSlot}"]`);
        if (!globalRank) return;
        // The all-time rank in parentheses only means something when the
        // visible rank is a position within the filtered set.
        globalRank.textContent = `(#${album.rank})`;
        globalRank.classList.toggle('hidden', showRank !== 'filtered');
    }

    /**
     * The credit line as links, in credit order: "A", "A & B", "A, B & C".
     *
     * Mirrors the `artist_links` template tag and
     * `music.services.credits.credit_separator`. Each credit shows the name
     * the album is credited under and links to the artist's page, titled
     * with the artist's own name when the two differ. A various-artists
     * credit ends in "Various Artists", unlinked - after the names on a
     * soundtrack, alone on a compilation. With no credits at all the
     * album's credit text is shown; an artist without a slug is plain text.
     * @private
     * @returns {string} HTML
     */
    _artistCreditHtml(album) {
        const artists = album.artists || [];
        if (!artists.length) {
            return this._escapeHtml(album.artistCredit || '');
        }
        const parts = artists.map(artist => {
            const name = this._escapeHtml(artist.n);
            if (!artist.s) return name;
            // `_escapeHtml` leaves quotes alone, which an attribute cannot:
            // Bonnie "Prince" Billy would end the title early.
            const title = artist.a && artist.a !== artist.n
                ? ` title="${this._escapeHtml(artist.a).replace(/"/g, '&quot;')}"`
                : '';
            return `<a href="${this._musicPath(`artists/${encodeURIComponent(artist.s)}/`)}" ` +
                `class="link link-hover"${title}>${name}</a>`;
        });
        if (album.variousArtists) {
            parts.push(AlbumListRenderer.VARIOUS_ARTISTS);
        }
        return parts
            .map((part, index) => {
                let separator = '';
                if (index === parts.length - 1 && index > 0) {
                    separator = ' & ';
                } else if (index > 0) {
                    separator = ', ';
                }
                const prefix = separator
                    ? `<span class="text-base-content/30">${this._escapeHtml(separator)}</span>`
                    : '';
                return prefix + part;
            })
            .join('');
    }

    /**
     * Build the metadata line's inner HTML.
     *
     * The separators between the parts are conditional server-side, so the
     * line is assembled here rather than slotted piece by piece - the same
     * approach `game-list-renderer.js` takes for its details row.
     * @private
     * @returns {string} HTML
     */
    _metaHtml(album, { withGenres, withCredit = true }) {
        const divider = '<span class="text-base-content/30">|</span> ';
        const parts = [];

        if (withCredit && album.artistCredit) {
            parts.push(
                '<span class="whitespace-nowrap font-medium text-base-content"' +
                ` data-slot="artist-credit">${this._artistCreditHtml(album)}</span>`
            );
        }

        if (withGenres && album.genres.length) {
            // Clickable, as the game row's genres are: each one adds itself
            // to the filter rather than only naming itself.
            const names = album.genres
                .map(genre => {
                    const label = this._escapeHtml(genre.n);
                    return (
                        '<button type="button" class="hover:text-primary ' +
                        'cursor-pointer transition-colors" ' +
                        `data-add-genre="${genre.id}" data-item="${album.id}" ` +
                        `title="${label}">${label}</button>`
                    );
                })
                .join('<span class="text-base-content/30"> / </span>');
            parts.push(
                `<span class="whitespace-nowrap">${parts.length ? divider : ''}` +
                `<span data-slot="genres">${names}</span></span>`
            );
        }

        if (album.listCount) {
            const label = album.listCount === 1 ? 'list' : 'lists';
            parts.push(
                `<span class="whitespace-nowrap">${parts.length ? divider : ''}` +
                `<span class="tabular-nums" data-slot="list-count">` +
                `${album.listCount} ${label}</span></span>`
            );
        }

        return parts.join('\n');
    }

    /** @private */
    _fillMeta(row, album, slot, options) {
        const container = row.querySelector(`[data-slot="${slot}"]`);
        if (container) {
            container.innerHTML = this._metaHtml(album, options);
        }
    }

    /**
     * Render one desktop row.
     * @protected
     * @returns {Element|null}
     */
    _renderDesktopRow(compactAlbum, index, showRank) {
        this._initTemplates();
        if (!this._templates) return null;

        const row = this._templates.desktop.content.cloneNode(true).firstElementChild;
        if (!row) return null;

        const album = this.engine.expandAlbum(compactAlbum);
        const url = this._musicPath(`${encodeURIComponent(album.slug)}/`);

        // The server renders `music-<id>` here (media_type + id, from the
        // shared row template), and `?highlight=` deep links and the
        // scroll-to-highlight both look rows up by that id.
        row.id = `music-${album.id}`;
        if (this.highlightId && album.id === this.highlightId) {
            const inner = row.querySelector('[data-slot="media-row"]');
            if (inner) inner.classList.add('is-highlighted');
        }

        this._fillRanks(row, album, index, showRank, 'rank', 'global-rank');
        this._fillCover(row, album, 'thumbnail', 'thumbnail-placeholder');

        this._fillSlot(row, 'name', album.name);
        const titleLink = row.querySelector('[data-slot="title-link"]');
        if (titleLink) titleLink.href = url;
        const thumbLink = row.querySelector('[data-slot="thumb-link"]');
        if (thumbLink) thumbLink.href = url;

        const credit = row.querySelector('[data-slot="artist-credit-inline"]');
        if (credit) credit.innerHTML = this._artistCreditHtml(album);

        this._fillSlot(row, 'year', album.year === null ? '' : album.year);
        const yearLink = row.querySelector('[data-slot="year-link"]');
        if (yearLink && album.year !== null) {
            yearLink.href =
                this._musicPath(`?start=${album.year}&end=${album.year}`) +
                `&highlight=${album.id}`;
        } else if (yearLink) {
            yearLink.removeAttribute('href');
        }
        this._fillMeta(row, album, 'meta-row', {
            withGenres: true,
            withCredit: false
        });

        this._fillTrackingButton(row, album, 'tracking-column');

        return row;
    }

    /**
     * Render one mobile row.
     *
     * The mobile row shows the raw published credit and no genres, as
     * `_album_row.html`'s mobile_metadata block does.
     * @protected
     * @returns {Element|null}
     */
    _renderMobileRow(compactAlbum, index, showRank) {
        this._initTemplates();
        if (!this._templates) return null;

        const row = this._templates.mobile.content.cloneNode(true).firstElementChild;
        if (!row) return null;

        const album = this.engine.expandAlbum(compactAlbum);
        const url = this._musicPath(`${encodeURIComponent(album.slug)}/`);

        row.id = `music-${album.id}-mobile`;
        // Navigated by base.html's [data-href] listener: an onclick string
        // is inline script, which the CSP forbids
        row.dataset.href = url;
        if (this.highlightId && album.id === this.highlightId) {
            row.classList.add('is-highlighted');
        }

        if (showRank !== 'none') {
            const rank = showRank === 'filtered' ? index : album.rank;
            this._fillSlot(row, 'rank-mobile', `#${rank}`);
        }
        this._fillCover(row, album, 'thumbnail-mobile', 'thumbnail-mobile-placeholder');

        // The title sits as a bare text node between the rank and the year,
        // so it is written directly rather than through a slot of its own.
        const title = row.querySelector('[data-slot="title-mobile"]');
        const yearEl = row.querySelector('[data-slot="year-mobile"]');
        if (yearEl) {
            yearEl.textContent = album.year === null ? '' : `(${album.year})`;
        }
        if (title && yearEl) {
            title.insertBefore(document.createTextNode(` ${album.name} `), yearEl);
        }

        // Mobile credit is the published text, not links.
        const mobileAlbum = Object.assign({}, album, { artists: [] });
        this._fillMeta(row, mobileAlbum, 'meta-mobile', { withGenres: false });

        // The template always reserves the button's column, because it is
        // rendered with no user. Narrow it back when there is no button, as
        // games' renderer does.
        const hasButton = this._fillTrackingButton(
            row, album, 'tracking-column-mobile'
        );
        row.style.gridTemplateColumns = hasButton ? 'auto auto 1fr' : 'auto 1fr';

        return row;
    }

    /**
     * Scroll to a highlighted album.
     *
     * Overridden only to use this section's row ids; the base class looks for
     * `item-<id>`.
     * @protected
     */
    _scrollToHighlight(albumId) {
        const desktop = document.getElementById(`music-${albumId}`);
        const mobile = document.getElementById(`music-${albumId}-mobile`);
        const target = window.matchMedia('(min-width: 962px)').matches
            ? desktop || mobile
            : mobile || desktop;
        if (!target) return;

        setTimeout(() => {
            flashHighlight(target, [desktop, mobile]);
            // Marked once: rows rendered later should not come back lit
            this.highlightId = null;
        }, 300);
    }

    /**
     * Result summary, worded exactly as the shared controls partial words it
     * server-side - which is also how the games rankings page words it. The
     * base class does the wording, the compact mobile form and the range a
     * jump leaves; an empty result set shows nothing, as the partial does.
     * @returns {string} HTML
     */
    getResultSummaryHtml(loaded, total, options = {}) {
        if (!total) return '';
        return super.getResultSummaryHtml(loaded, total, options);
    }

    /**
     * Load-more button, matching `_album_load_more.html` - and so the games
     * load-more - in both wording and classes.
     * @returns {string} HTML
     */
    getLoadMoreHtml(state) {
        const { hasMore, remaining } = state;
        if (!hasMore) return '';
        return (
            '<button type="button" class="btn btn-ghost load-more-button">' +
            '<span class="mdi mdi-album"></span>' +
            '<span class="load-more-text">Load More (' +
            remaining.toLocaleString() + ' remaining)</span></button>'
        );
    }
}

// The tail of a various-artists credit: `music.config.VARIOUS_ARTISTS`.
AlbumListRenderer.VARIOUS_ARTISTS = 'Various Artists';

/**
 * The data-slot hooks this renderer fills in a cloned row, declared rather
 * than left implicit so music/tests/test_visual_regression.py can check that
 * `_album_row.html` still emits every one of them - in the empty rendering
 * as well as a filled one.
 *
 * `artist-credit`, `genres` and `list-count` are deliberately absent: those
 * live inside the metadata line, which is written as innerHTML because its
 * separators are conditional, so they exist only in a row that has them.
 */
AlbumListRenderer.SLOTS = [
    'root',
    'media-row',
    'artist-credit-inline',
    'rank',
    'global-rank',
    'thumb-link',
    'thumbnail',
    'thumbnail-placeholder',
    'title-link',
    'name',
    'year',
    'meta-row',
    'tracking-column',
    'root-mobile',
    'rank-mobile',
    'thumbnail-mobile',
    'thumbnail-mobile-placeholder',
    'title-mobile',
    'year-mobile',
    'meta-mobile',
    'tracking-column-mobile'
];

/**
 * The slots inside the tracking button, checked against its own template.
 *
 * Separate from SLOTS because these live in
 * `_listen_button_template.html`, not in the row: a slot listed in SLOTS
 * has to be emitted by `_album_row.html`, which this one is not.
 */
AlbumListRenderer.TRACKING_SLOTS = [
    'tracking-wrapper',
    'tracking-button',
    'owned-icon',
    'tracked-icon',
    'wanted-icon',
    'untracked-icon',
    'dropdown-menu',
    'menu-owned',
    'menu-tracked',
    'menu-wanted',
    'menu-untracked',
    'btn-owned',
    'btn-tracked',
    'btn-wanted',
    'btn-untracked'
];

/** The slots the grid card renderer fills, checked the same way. */
AlbumListRenderer.GRID_SLOTS = [
    'root-grid',
    'rank-container',
    'rank-grid',
    'global-rank-grid',
    'cover-link',
    'cover',
    'cover-placeholder',
    'overlay',
    'creator',
    'genres-grid',
    'list-count-grid',
    'title-link-grid',
    'name-grid',
    'year-grid'
];

if (typeof window !== 'undefined') {
    window.AlbumListRenderer = AlbumListRenderer;
}
