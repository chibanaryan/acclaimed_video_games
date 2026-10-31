/**
 * Acclaimed Albums - Client-Side Filtering Integration
 *
 * Takes over the album rankings page's filter form once the whole corpus is
 * in the browser: 1000 albums, about 95 KB gzipped, so filtering a 100-row
 * page costs nothing locally where every change was an HTMX round trip.
 *
 * Progressive enhancement, deliberately. The page is server-rendered and its
 * HTMX form filters server-side on its own; this file suppresses those
 * requests only once it has data and a renderer, so a slow or failed bundle
 * leaves a page that still works. There is no Alpine component and no
 * IndexedDB layer: the sidebar is a plain GET form whose fields are already
 * the engine's inputs, and the payload is small enough to refetch per
 * session.
 */
class AlbumClientSideFiltering {
    constructor() {
        this.engine = null;
        this.renderer = null;
        this.isInitialized = false;
        this.initPromise = null;
        this.currentFilters = {};
        this.viewMode = 'list';
        this.form = null;
    }

    /**
     * Adopt the sidebar form and the state the server rendered with.
     *
     * Nothing is re-rendered on load - the server already rendered this
     * filter state - so without this the instance would hold no filters at
     * all, and the first Load More or view switch would read fields off
     * nothing.
     */
    attach(form) {
        this.form = form;
        this.currentFilters = this.readFilters(form);
    }

    /**
     * Point the renderer at the current result set without re-rendering.
     *
     * Load More and jump-to-rank continue a list the server rendered, so the
     * renderer has to know what the whole list is and how much of it is
     * already on the page before it can append the next slice.
     * @private
     */
    _syncRendererWithPage() {
        if (!this.isInitialized) return;
        if (this.renderer.currentItems && this.renderer.currentItems.length) return;

        const filters = this.form ? this.readFilters(this.form) : this.currentFilters;
        this.currentFilters = filters;
        const { albums } = this.engine.apply(filters);
        this.renderer.adopt(albums, loadedAlbumCount());
        this.renderer._currentViewMode = this.viewMode;
        this.renderer._currentShowRank = this._isFiltered(filters)
            ? 'filtered'
            : 'alltime';
    }

    /**
     * Re-announce the year and genre counts for the form's current state.
     *
     * For sidebar components created after the last update - the mobile
     * sheet builds its filters on first open, and a desktop sidebar skipped
     * on a narrow first load is initialised when the window widens - which
     * would otherwise show the counts they were rendered with.
     * @returns {boolean} Whether there was an engine to count with
     */
    republishFacets() {
        if (!this.isInitialized) return false;
        const filters = this.form ? this.readFilters(this.form) : this.currentFilters;
        this._dispatchFacetCounts(this.engine.facets(filters));
        return true;
    }

    /** Announce year and genre counts to the sidebar's components. @private */
    _dispatchFacetCounts(facets) {
        window.dispatchEvent(
            new CustomEvent('year-counts-update', { detail: facets.years })
        );
        window.dispatchEvent(
            new CustomEvent('genre-counts-update', { detail: facets.genres })
        );
    }

    /** Whether the engine and renderer are ready to take the page over. */
    isReady() {
        return this.isInitialized;
    }

    /** Switch between list and grid, re-rendering if we own the list. */
    setViewMode(mode) {
        this.viewMode = mode === 'grid' ? 'grid' : 'list';
        if (!this.isInitialized) return;

        if (this.renderer.currentItems && this.renderer.currentItems.length) {
            this.applyFilters(this.currentFilters);
        } else {
            // Still showing the server's rows and cards, which the view
            // class switches between on its own.
            this.renderer._currentViewMode = this.viewMode;
        }
    }

    /** The sessionStorage key, versioned so stale data is never read. */
    static storageKey(version) {
        return `albumData:${version}`;
    }

    /**
     * The view the list/grid toggle was last left in. The same key
     * core/js/media-list-controls.js writes.
     * @private
     */
    _storedViewMode() {
        try {
            return localStorage.getItem('albumViewMode') === 'grid'
                ? 'grid'
                : 'list';
        } catch (e) {
            return 'list';
        }
    }

    /**
     * Load the bulk payload: this session's copy if it matches the version
     * the page was rendered with, otherwise the network.
     *
     * sessionStorage rather than IndexedDB or localStorage: a tab-scoped copy
     * is the shortest lifetime that still avoids refetching on every
     * navigation.
     * @private
     */
    async _loadData() {
        const version = window.albumDataVersion || '';
        const key = AlbumClientSideFiltering.storageKey(version);

        if (version) {
            try {
                const stored = sessionStorage.getItem(key);
                if (stored) return JSON.parse(stored);
            } catch (e) {
                // Private mode, blocked storage, or a truncated entry.
            }
        }

        const response = await fetch(window.albumDataUrl || '/api/all/', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        if (!response.ok) {
            throw new Error(`album data request failed: ${response.status}`);
        }
        const data = await response.json();

        if (version && data.version === version) {
            try {
                sessionStorage.setItem(key, JSON.stringify(data));
            } catch (e) {
                // Over quota: filtering still works, it just refetches.
            }
        }
        return data;
    }

    /**
     * Fetch the data and build the engine and renderer.
     * @returns {Promise<boolean>} Whether client-side filtering is usable
     */
    async init() {
        if (this.isInitialized) return true;
        if (this.initPromise) return this.initPromise;

        this.initPromise = (async () => {
            try {
                const data = await this._loadData();
                this.engine = new AlbumFilterEngine(data);
                this.renderer = new AlbumListRenderer(this.engine);
                this.viewMode = this._storedViewMode();
                this.isInitialized = true;
                return true;
            } catch (e) {
                console.warn('[albums] client-side filtering unavailable:', e);
                return false;
            }
        })();

        return this.initPromise;
    }

    /**
     * Read the current filter state off the sidebar form.
     *
     * Through FormData so that the client and the server read one
     * vocabulary: these are the same field names `AlbumHomePageView` parses.
     * @param {HTMLFormElement} form
     * @returns {Object}
     */
    readFilters(form) {
        const data = new FormData(form);
        const text = name => (data.get(name) || '').toString().trim();
        const number = name => {
            const parsed = parseInt(text(name), 10);
            return Number.isFinite(parsed) ? parsed : undefined;
        };
        const ids = name =>
            text(name)
                .split(',')
                .map(part => parseInt(part.trim(), 10))
                .filter(Number.isFinite);

        // The status values are words, not ids, so they get their own
        // reader rather than going through `ids`.
        const words = name =>
            text(name)
                .split(',')
                .map(part => part.trim())
                .filter(Boolean);

        return {
            q: text('q'),
            start: number('start'),
            end: number('end'),
            // Slugs: the page never carries an artist pk.
            artists: words('artists'),
            genres: ids('genres'),
            listened: words('listened'),
            sort: text('sort') || 'rank',
            dir: text('dir') || 'asc'
        };
    }

    /**
     * Whether any filter is set, which is what decides between showing
     * all-time ranks and positions within the filtered set. Mirrors
     * `is_filtered` in the view: sort and direction do not count.
     * @private
     */
    _isFiltered(filters) {
        const current = filters || {};
        return Boolean(
            current.q ||
            current.start !== undefined ||
            current.end !== undefined ||
            (current.artists && current.artists.length) ||
            (current.genres && current.genres.length) ||
            (current.listened && current.listened.length)
        );
    }

    /**
     * Filter, render, and update the count and the load-more button.
     * @param {Object} filters
     * @param {Object} [options]
     * @param {number} [options.highlightId]
     */
    applyFilters(filters, options = {}) {
        if (!this.isInitialized) return null;

        this.currentFilters = filters;
        const { albums, total } = this.engine.apply(filters);
        const showRank = this._isFiltered(filters) ? 'filtered' : 'alltime';

        const container = document.getElementById('album-list-container');
        if (!container) return null;

        this.renderer.reset();
        if (total === 0) {
            container.innerHTML =
                '<div class="text-base-content/85 py-8 text-center">' +
                'No albums match your filters.</div>';
        } else {
            this.renderer.render(albums, container, {
                showRank,
                highlightId: options.highlightId || null,
                viewMode: this.viewMode
            });
        }

        this._updatePaging();
        this._publishFacets(filters, albums);
        return { total };
    }

    /**
     * Redraw everything that describes the renderer's window: both
     * result-count lines (the controls partial renders one for desktop and a
     * compact one for mobile), Load Previous, and Load More.
     * @private
     */
    _updatePaging() {
        const state = this.renderer.windowState();

        document.querySelectorAll(
            '#album-results-container [data-result-count]'
        ).forEach(line => {
            line.innerHTML = this.renderer.getResultSummaryHtml(state.loaded, state.total, {
                start: state.start,
                compact: line.dataset.resultCount === 'mobile'
            });
        });

        const previous = document.querySelector(
            '#album-results-container .load-previous-container'
        );
        if (previous) {
            previous.innerHTML = this.renderer.getLoadPreviousHtml(state);
        }

        this._updateLoadMore(state);
    }

    /**
     * Re-publish the sidebar's facet counts from the engine.
     *
     * The server sends these with each render; once filtering happens in the
     * browser nothing asks the server again, so the year grid and the genre
     * tree would keep showing the counts from the last page load.
     * @private
     */
    _publishFacets(filters, albums) {
        this._dispatchFacetCounts(this.engine.facets(filters));
        window.dispatchEvent(
            new CustomEvent('rank-distribution-update', {
                detail: this.engine.rankDistribution(albums)
            })
        );
    }

    /**
     * Replace the server's HTMX load-more button with one this class drives.
     * @private
     */
    _updateLoadMore(state) {
        const existing = document.querySelector(
            '#album-results-container .load-more-container'
        );

        if (!state.hasMore) {
            if (existing) existing.remove();
            return;
        }

        const html = this.renderer.getLoadMoreHtml(state);
        const container = existing || document.createElement('div');
        container.id = 'load-more-container';
        container.className = 'load-more-container text-center my-6';
        container.innerHTML = html;
        if (!existing) {
            document.getElementById('album-results-container').appendChild(container);
        }
    }

    /** The rank column to show for the current filters. @private */
    _showRank() {
        return this._isFiltered(this.currentFilters) ? 'filtered' : 'alltime';
    }

    /** Append the next page and refresh the count and buttons. */
    loadMore() {
        const container = document.getElementById('album-list-container');
        if (!container || !this.isInitialized) return;

        this._syncRendererWithPage();
        this.renderer.loadMore(container, { showRank: this._showRank() });
        this._updatePaging();
    }

    /**
     * Prepend the page above a jumped-to window, keeping the reader on the
     * row they were looking at.
     */
    loadPrevious() {
        const container = document.getElementById('album-list-container');
        if (!container || !this.isInitialized) return;

        this._syncRendererWithPage();
        const restoreScroll = this.renderer.captureScrollAnchor(container);
        this.renderer.loadPrevious(container, { showRank: this._showRank() });
        // The button can disappear as well, so keep the place after both
        this._updatePaging();
        restoreScroll();
    }

    /**
     * Bring `position` (1-based, in the current result set) onto the page.
     *
     * Only the target and JUMP_RADIUS rows either side are rendered, not
     * everything above it; one already on the page is left as it is, and one
     * near the rendered rows extends them. See BaseMediaListRenderer.planJump.
     * @param {number} position
     */
    jumpTo(position) {
        const container = document.getElementById('album-list-container');
        if (!container || !this.isInitialized) return;

        this._syncRendererWithPage();
        const plan = this.renderer.planJump(position - 1);
        if (plan.mode === 'scroll') return;

        this.renderer.showRange(container, plan.start, plan.end, {
            showRank: this._showRank(),
            viewMode: this.viewMode
        });
        this._updatePaging();
    }

    /**
     * Mirror the filter state into the URL, as `hx-push-url` did.
     * @private
     */
    pushUrl(filters, { replace = false } = {}) {
        const params = new URLSearchParams();
        if (filters.q) params.set('q', filters.q);
        if (filters.start !== undefined) params.set('start', filters.start);
        if (filters.end !== undefined) params.set('end', filters.end);
        if (filters.artists.length) params.set('artists', filters.artists.join(','));
        if (filters.genres.length) params.set('genres', filters.genres.join(','));
        if (filters.listened.length) {
            params.set('listened', filters.listened.join(','));
        }
        if (filters.sort && filters.sort !== 'rank') params.set('sort', filters.sort);
        if (filters.dir && filters.dir !== 'asc') params.set('dir', filters.dir);

        // Always onto the rankings URL, never relative to the current path:
        // on a landing page such as /genres/rock/, a relative push
        // kept the path - and with it the path's own genre - so clearing
        // the genre and reloading brought rock straight back.
        const query = params.toString();
        const base = window.albumRankingsUrl || window.location.pathname;
        window.history[replace ? 'replaceState' : 'pushState'](
            {}, '', query ? `${base}?${query}` : base
        );
    }
}

/**
 * The filter params the current URL stands for.
 *
 * A landing page's own path implies its filters with no query string, and
 * Back can return to that bare path, so on it an empty query means the
 * page's params (`window.albumLandingSearch`) rather than no filters.
 */
function albumUrlParams() {
    if (
        !window.location.search &&
        window.albumLandingPath &&
        window.location.pathname === window.albumLandingPath
    ) {
        return new URLSearchParams(window.albumLandingSearch || '');
    }
    return new URLSearchParams(window.location.search);
}

/**
 * Scroll to the Nth row currently on the page and flash it.
 *
 * Positional, like the games page's equivalent: the box takes a position in
 * the current result set, which is only the album's own rank when nothing is
 * filtered.
 */
function scrollToAlbumPosition(position) {
    const container = document.getElementById('album-list-container');
    const isGrid = container && container.classList.contains('view-grid');
    // After a jump the first rendered row is at windowStart, not the top.
    const csf = getAlbumClientSideFiltering();
    const offset = csf.isReady() && csf.renderer.currentItems.length
        ? csf.renderer.windowStart
        : 0;
    const index = position - 1 - offset;

    let target = null;
    const highlight = [];

    if (isGrid) {
        const card = document.querySelectorAll('.media-card-grid')[index];
        if (card) {
            target = card;
            highlight.push(card);
        }
    } else {
        const desktop = document.querySelectorAll('.media-row.desktop')[index];
        const mobile = document.querySelectorAll('.media-row.media-card-mobile')[index];
        // Each half is display:none at the other's breakpoint, so the one
        // with a layout box is the one the reader can see.
        target =
            (desktop && desktop.offsetParent !== null && desktop) ||
            (mobile && mobile.offsetParent !== null && mobile) ||
            desktop ||
            mobile ||
            null;
        if (desktop) highlight.push(desktop);
        if (mobile) highlight.push(mobile);
    }

    if (!target) return;

    flashHighlight(target, highlight);
}

/**
 * Scroll to an album's row or card by id and flash it.
 *
 * What a `?highlight=` link from album detail lands on, as the games
 * rankings page does: the highlight fades after a couple of seconds, or as
 * soon as the reader hovers another row.
 * @param {number} albumId
 * @param {string} [viewMode] - see loadedAlbumCount
 * @returns {boolean} Whether the album is on the page
 */
function scrollToAlbumById(albumId, viewMode) {
    const isGrid = albumViewIsGrid(viewMode);

    let target = null;
    const highlight = [];

    if (isGrid) {
        const card = document.getElementById(`music-${albumId}-grid`);
        if (card) {
            target = card;
            highlight.push(card);
        }
    } else {
        const desktop = document.getElementById(`music-${albumId}`);
        const mobile = document.getElementById(`music-${albumId}-mobile`);
        // As in scrollToAlbumPosition: the half with a layout box is the
        // one the reader can see.
        target =
            (desktop && desktop.offsetParent !== null && desktop) ||
            (mobile && mobile.offsetParent !== null && mobile) ||
            desktop ||
            mobile ||
            null;
        if (desktop) highlight.push(desktop);
        if (mobile) highlight.push(mobile);
    }

    if (!target) return false;

    flashHighlight(target, highlight);
    return true;
}

/**
 * Whether the list is in grid view: `viewMode` if given, otherwise the
 * container's class. The class is Alpine's `:class`, which on a fresh load
 * may not be applied yet when the engine is ready, so a caller that knows
 * the mode passes it.
 */
function albumViewIsGrid(viewMode) {
    if (viewMode) return viewMode === 'grid';
    const container = document.getElementById('album-list-container');
    return Boolean(container && container.classList.contains('view-grid'));
}

/**
 * How many rows are on the page now, in whichever view is showing.
 * @param {string} [viewMode] - 'list' or 'grid'; read off the container if omitted
 */
function loadedAlbumCount(viewMode) {
    const container = document.getElementById('album-list-container');
    if (!container) return 0;
    const selector = albumViewIsGrid(viewMode)
        ? '.media-card-grid'
        : '.media-row.desktop';
    return container.querySelectorAll(selector).length;
}

/**
 * Page until at least `count` rows are on the page, or there are no more.
 *
 * With the engine ready this pages through the data in memory; without it the
 * page's own HTMX load-more is clicked instead, which is slower but keeps
 * working if the bundle's data never arrives.
 */
async function loadAlbumsThrough(csf, count) {
    // The engine's mode is the one its loadMore appends in.
    const loaded = () => loadedAlbumCount(csf.isReady() ? csf.viewMode : undefined);
    while (loaded() < count) {
        const before = loaded();
        if (csf.isReady()) {
            csf.loadMore();
        } else {
            const button = document.querySelector(
                '#load-more-container .load-more-button'
            );
            if (!button) break;
            button.click();
            // Give HTMX a moment to swap the next page in.
            await new Promise(resolve => setTimeout(resolve, 400));
        }
        if (loaded() === before) break;
    }
}

/**
 * Wire the jump-to-rank boxes in the results header.
 *
 * The controls partial renders a pair of them, one for each breakpoint, so
 * the handlers are delegated from the document rather than bound per input.
 */
function initAlbumJumpToRank(csf) {
    const jump = async input => {
        const target = parseInt(input.value, 10);
        // The renderer holds the current result set once it has rendered
        // one; before that the server's own count is on the input.
        const rendered = csf.isReady() ? csf.renderer.currentItems.length : 0;
        const total = rendered || parseInt(input.dataset.total, 10) || 0;

        if (!Number.isFinite(target) || target < 1 || (total && target > total)) {
            input.classList.add('input-error');
            setTimeout(() => input.classList.remove('input-error'), 1000);
            return;
        }

        if (csf.isReady()) {
            csf.jumpTo(target);
        } else {
            // Without the data, page down through the server's HTMX button
            await loadAlbumsThrough(csf, target);
        }
        scrollToAlbumPosition(target);
        input.value = '';
    };

    document.addEventListener('click', event => {
        const button = event.target.closest('.jump-to-rank-btn');
        if (!button) return;
        const input = button
            .closest('div')
            .querySelector('.jump-to-rank-input');
        if (input) jump(input);
    });

    document.addEventListener('keydown', event => {
        if (event.key !== 'Enter') return;
        if (!event.target.classList.contains('jump-to-rank-input')) return;
        event.preventDefault();
        jump(event.target);
    });
}

let _albumClientSideFiltering = null;

/** The page's single instance. */
function getAlbumClientSideFiltering() {
    if (!_albumClientSideFiltering) {
        _albumClientSideFiltering = new AlbumClientSideFiltering();
    }
    return _albumClientSideFiltering;
}

/**
 * Wire the sidebar up to the client-side engine.
 *
 * Until `init()` resolves, nothing is intercepted and HTMX keeps serving
 * filter changes from the server. From then on every request the sidebar
 * would make is suppressed - the form, the decade chips and the load-more
 * button alike. Leaving any of them to HTMX would let a server-rendered swap
 * interleave with client-rendered rows.
 */
function initAlbumFiltering() {
    const form = document.getElementById('album-filters');
    const results = document.getElementById('album-results-container');
    if (!form || !results) return;

    const csf = getAlbumClientSideFiltering();
    let ready = false;

    // Stop the server round-trip for anything the engine can answer itself,
    // once it can. Only GETs: these listeners sit on the form and on the
    // results container, so every HTMX request raised by anything *inside*
    // the results bubbles through them - including a row's listen-status
    // POST, which has to reach the server and which cancelling here would
    // silently swallow the moment the bundle finished loading.
    const suppressHtmx = event => {
        if (!ready) return;
        const detail = event.detail || {};
        const verb = (detail.requestConfig && detail.requestConfig.verb) || 'get';
        if (verb.toLowerCase() !== 'get') return;
        event.preventDefault();
    };
    form.addEventListener('htmx:beforeRequest', suppressHtmx);
    results.addEventListener('htmx:beforeRequest', suppressHtmx);

    const currentHighlight = () => {
        const highlight = new URLSearchParams(window.location.search).get('highlight');
        const parsed = parseInt(highlight, 10);
        return Number.isFinite(parsed) ? parsed : null;
    };

    const rerender = ({ push = true, highlightId = null, replace = false } = {}) => {
        const filters = csf.readFilters(form);
        csf.applyFilters(filters, { highlightId });
        if (push) csf.pushUrl(filters, { replace });
    };

    // A genre clicked in a row filters by it, as it does on the games
    // rankings page. Bound before init resolves so the click works either
    // way: the select is the filter's single source of truth, and a plain
    // change event is what both HTMX and the engine below listen for.
    document.addEventListener('add-genre', event => {
        const select = form.querySelector('[name="genres"]');
        const genreId = event.detail && event.detail.genreId;
        if (!select || !genreId) return;
        select.value = String(genreId);
        // `filters` lives on the Alpine controls component, and the heading
        // and the sidebar's genre tree are both built from it. Setting the
        // select alone left them showing the previous selection.
        window.dispatchEvent(new CustomEvent('genres-selected', {
            detail: { genres: [String(genreId)] },
        }));

        if (!ready) {
            select.dispatchEvent(new Event('change', { bubbles: true }));
            return;
        }
        const highlight = parseInt(event.detail.itemId, 10);
        rerender({ highlightId: Number.isFinite(highlight) ? highlight : null });
    });

    // A toggle can change whether a row still belongs in the results.
    // media-tracking.js has already updated the Sets the engine reads by the
    // time this fires, so re-filtering is all that is needed.
    window.addEventListener('album-status-changed', () => {
        if (!ready) return;
        const filters = csf.readFilters(form);
        if (!filters.listened.length) return;
        rerender({ push: false, highlightId: currentHighlight() });
    });

    // A `?highlight=` link from album detail lands on the album, as it does
    // on the games rankings page. If the server rendered its row, scroll now
    // - after a beat, so Alpine has laid out the heading and sidebar above
    // it - without waiting on the data. Otherwise it is further down the
    // result set, and finding it waits for the engine below.
    const highlightOnLoad = currentHighlight();
    const viewModeOnLoad = csf._storedViewMode();
    let highlightPending = false;
    if (highlightOnLoad !== null) {
        const onPage =
            document.getElementById(`music-${highlightOnLoad}`) ||
            document.getElementById(`music-${highlightOnLoad}-grid`);
        if (onPage) {
            setTimeout(() => scrollToAlbumById(highlightOnLoad, viewModeOnLoad), 300);
        } else {
            highlightPending = true;
        }
    }

    csf.init().then(async ok => {
        if (!ok) return;
        ready = true;
        csf.attach(form);

        // The server rendered its own Load More button, whose HTMX request
        // is suppressed from here on, so paging is driven by the engine
        // instead. Delegated, because every later page rewrites the button.
        document.addEventListener('click', event => {
            const button = event.target.closest('.load-more-button');
            if (!button) return;
            event.preventDefault();
            csf.loadMore();
        });
        // Load Previous is only ever drawn by the engine, after a jump.
        document.addEventListener('click', event => {
            if (!event.target.closest('.load-previous-button')) return;
            event.preventDefault();
            csf.loadPrevious();
        });

        // The controls mark a burst's trailing commit, which the user
        // experiences as the same change: one history entry, not two.
        form.addEventListener('change', event => rerender({
            replace: Boolean(event.detail && event.detail.historyReplace)
        }));
        form.addEventListener('submit', event => {
            event.preventDefault();
            rerender();
        });

        let typingTimer = null;
        const search = form.querySelector('input[name="q"]');
        if (search) {
            search.addEventListener('input', () => {
                clearTimeout(typingTimer);
                typingTimer = setTimeout(() => rerender(), 350);
            });
        }

        // The list/grid toggle lives in the results header, outside this
        // form, and announces itself rather than reaching in here.
        window.addEventListener('media-view-mode', event => {
            csf.setViewMode(event.detail && event.detail.mode);
        });

        initAlbumJumpToRank(csf);

        window.addEventListener('popstate', () => {
            // The URL moved under us; re-read it into the form and re-render.
            const params = albumUrlParams();
            [
                'q', 'start', 'end', 'artists', 'genres', 'listened', 'sort', 'dir'
            ].forEach(name => {
                const field = form.querySelector(`[name="${name}"]`);
                if (field) field.value = params.get(name) || '';
            });
            rerender({ push: false, highlightId: currentHighlight() });
        });

        // Nothing is re-rendered on load: the server already rendered this
        // exact filter state, and re-rendering would only make the page
        // flicker. The engine takes over from the next interaction - except
        // to page down to a highlighted album the server did not render.
        if (highlightPending) {
            csf._syncRendererWithPage();
            const position = csf.renderer.currentItems.findIndex(
                album => album.id === highlightOnLoad
            ) + 1;
            // Not in this result set at all: nothing to land on.
            if (position > 0) {
                csf.jumpTo(position);
                scrollToAlbumById(highlightOnLoad, csf.viewMode);
            }
        }
    });
}

if (typeof window !== 'undefined') {
    window.AlbumClientSideFiltering = AlbumClientSideFiltering;
    window.getAlbumClientSideFiltering = getAlbumClientSideFiltering;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAlbumFiltering);
    } else {
        initAlbumFiltering();
    }
}
