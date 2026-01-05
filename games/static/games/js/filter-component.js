/**
 * Acclaimed Games - Filter Component
 *
 * Alpine.js data component for the advanced filters sidebar.
 * Extracted from inline x-data to enable browser caching and reduce main-thread parsing.
 *
 * Usage in template:
 *   <div x-data="filterComponent({ minYear: 1970, maxYear: 2025 })">
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('filterComponent', (config) => ({
        // Configuration passed from template
        minYear: config.minYear,
        maxYear: config.maxYear,

        // Data loaded from JSON script tags
        filters: JSON.parse(document.getElementById('filters-data').textContent),
        genres: JSON.parse(document.getElementById('genres-data').textContent),
        platforms: JSON.parse(document.getElementById('platforms-data').textContent),
        seriesList: JSON.parse(document.getElementById('series-data').textContent),

        // Component state
        platformGroupCounts: {},
        initialized: false,
        isLoading: false,
        yearExpanded: localStorage.getItem('yearExpanded') !== 'false',
        genresExpanded: localStorage.getItem('genresExpanded') !== 'false',
        platformsExpanded: localStorage.getItem('platformsExpanded') !== 'false',
        seriesExpanded: localStorage.getItem('seriesExpanded') !== 'false',
        hltbExpanded: localStorage.getItem('hltbExpanded') !== 'false',
        viewMode: localStorage.getItem('gameViewMode') || 'list',
        fetchManager: new FetchManager(),
        _debouncedUpdate: null,
        _throttledSlider: null,
        _debouncedFilter: null,
        _debouncedDisplay: null,
        clientFilterReady: false,
        _csf: null,

        // Saved filters state
        savedFiltersOpen: false,
        savedFiltersLoading: false,
        savedFilters: [],
        savedFiltersLoaded: false,
        saveFilterModalOpen: false,
        saveFilterName: '',
        saveFilterError: '',
        saveFilterSaving: false,
        applyingSavedFilter: false,
        renameFilterModalOpen: false,
        renameFilterName: '',
        renameFilterError: '',
        renameFilterSaving: false,
        renameFilterTarget: null,
        deleteFilterModalOpen: false,
        deleteFilterTarget: null,
        deleteFilterDeleting: false,

        _getCsrfToken() {
            const name = 'csrftoken';
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        },

        init() {
            if (!this.filters.sort || this.filters.sort === '') {
                this.filters.sort = 'rank';
            }
            if (!this.filters.sortDirection || this.filters.sortDirection === '') {
                this.filters.sortDirection = 'asc';
            }

            const urlParams = new URLSearchParams(window.location.search);
            const highlightParam = urlParams.get('highlight');
            if (highlightParam) {
                this.filters.highlight = highlightParam;
            }
            const dirParam = urlParams.get('dir');
            if (dirParam && (dirParam === 'asc' || dirParam === 'desc')) {
                this.filters.sortDirection = dirParam;
            }

            setTimeout(() => { this.initialized = true; }, 100);

            this._debouncedUpdate = debounce(() => this.performUpdate({
                partial: true, historyMethod: 'pushState'
            }), 300);

            this._throttledSlider = throttleWithForce(() => this.performUpdate({
                partial: true, historyMethod: 'replaceState'
            }), 150);

            this._debouncedFilter = debounce(() => this.performUpdate({
                partial: true, historyMethod: 'pushState'
            }), 150);

            this._debouncedDisplay = debounce(() => this.performUpdate({
                partial: true, historyMethod: 'pushState', preservePage: true
            }), 150);

            const savedScrollPos = sessionStorage.getItem('gameListScrollPos');
            if (savedScrollPos) {
                setTimeout(() => {
                    window.scrollTo(0, parseInt(savedScrollPos));
                    sessionStorage.removeItem('gameListScrollPos');
                }, 100);
            }

            const saveScrollPosition = () => {
                sessionStorage.setItem('gameListScrollPos', window.scrollY.toString());
            };

            document.addEventListener('click', (e) => {
                const link = e.target.closest("a[href*='/game/']");
                if (link) {
                    saveScrollPosition();
                }
            });

            window.addEventListener('popstate', (event) => {
                const params = new URLSearchParams(window.location.search);
                this.filters.q = params.get('q') || '';
                this.filters.start = params.get('start') ? parseInt(params.get('start')) : this.minYear;
                this.filters.end = params.get('end') ? parseInt(params.get('end')) : this.maxYear;
                this.filters.sort = params.get('sort') || 'rank';
                this.filters.sortDirection = params.get('dir') || 'asc';
                this.filters.played = params.get('played') || '';
                const genresParam = params.get('genres');
                this.filters.genres = genresParam ? genresParam.split(',').filter(id => id) : [];
                const platformsParam = params.get('platforms');
                this.filters.platforms = platformsParam ? platformsParam.split(',').filter(id => id) : [];
                const seriesParam = params.get('series');
                this.filters.series = seriesParam ? seriesParam.split(',').filter(id => id) : [];
                this.filters.hltb_mode = params.get('hltb_mode') || 'main';
                this.filters.hltb_min = params.get('hltb_min') ? parseInt(params.get('hltb_min')) : null;
                this.filters.hltb_max = params.get('hltb_max') ? parseInt(params.get('hltb_max')) : null;
                this.filters.hltb_preset = this.calculateHltbPreset(this.filters.hltb_min, this.filters.hltb_max);
                if (this.clientFilterReady) {
                    this.performClientUpdate();
                } else {
                    setLoading('game-results-container');
                }
            });

            this.$watch('filters.q', val => {
                if (!this.initialized) return;
                this.updateResults();
            });

            setTimeout(() => { if (typeof initLoadMore === 'function') initLoadMore(); }, 150);
            if (typeof initYearPreview === 'function') initYearPreview();

            this.$watch('filters', () => {
                this.$dispatch('filters-updated');
            }, { deep: true });

            document.addEventListener('add-platform', (e) => this.addPlatform(e.detail));
            document.addEventListener('add-platforms', (e) => this.addPlatforms(e.detail));
            document.addEventListener('add-genre', (e) => this.addGenre(e.detail));
            document.addEventListener('add-genres', (e) => this.addGenres(e.detail));

            window.addEventListener('game-status-changed', (event) => {
                if (this.filters.played && this.clientFilterReady) {
                    this.performClientUpdate({ historyMethod: 'replaceState' });
                }
            });

            window.addEventListener('mobile-filter-opened', () => {
                if (this.clientFilterReady) {
                    this.updateFacetCounts();
                } else {
                    this.dispatchInitialCounts();
                }
            });

            this.initClientFiltering();
        },

        hasActiveFilters() {
            return this.filters.q ||
                   this.filters.genres.length > 0 ||
                   this.filters.platforms.length > 0 ||
                   (this.filters.series && this.filters.series.length > 0) ||
                   this.filters.start !== this.minYear ||
                   this.filters.end !== this.maxYear ||
                   this.filters.played ||
                   this.filters.hltb_min !== null ||
                   this.filters.hltb_max !== null;
        },

        async initClientFiltering() {
            let retries = 0;
            const maxRetries = 30;
            const self = this;

            const doInit = async () => {
                self._csf = getClientSideFiltering();
                try {
                    await self._csf.init({
                        onLoadStart: () => console.log('[CSF] Loading game data...'),
                        onLoadComplete: () => {
                            console.log('[CSF] Game data loaded, client filtering ready');
                            self.clientFilterReady = true;
                            self._csf.setViewMode(self.viewMode);
                            if (self.hasActiveFilters()) {
                                self.performClientUpdate({ historyMethod: 'replaceState' });
                            } else {
                                self.updateFacetCounts();
                            }
                        }
                    });
                } catch (e) {
                    console.error('[CSF] Failed to initialize:', e);
                    self.dispatchInitialCounts();
                }
            };

            const tryInit = () => {
                if (typeof getClientSideFiltering !== 'function') {
                    retries++;
                    if (retries < maxRetries) {
                        setTimeout(tryInit, 100);
                        return;
                    }
                    console.log('[CSF] Client-side filtering not available after retries');
                    self.dispatchInitialCounts();
                    return;
                }

                if ('requestIdleCallback' in window) {
                    requestIdleCallback(doInit);
                } else {
                    setTimeout(doInit, 50);
                }
            };

            tryInit();
        },

        async loadSavedFilters() {
            if (this.savedFiltersLoading) return;
            this.savedFiltersOpen = true;
            if (this.savedFiltersLoaded) return;

            this.savedFiltersLoading = true;
            try {
                const response = await fetch('/api/saved-filters/');
                if (response.ok) {
                    const data = await response.json();
                    this.savedFilters = data.filter_sets || [];
                    this.savedFiltersLoaded = true;
                }
            } catch (e) {
                console.error('[SavedFilters] Failed to load:', e);
            } finally {
                this.savedFiltersLoading = false;
            }
        },

        applySavedFilter(filter) {
            this.applyingSavedFilter = true;
            const f = filter.filters;
            this.filters.q = f.q || '';
            this.filters.start = f.start || this.minYear;
            this.filters.end = f.end || this.maxYear;
            this.filters.genres = f.genres || [];
            this.filters.platforms = f.platforms || [];
            this.filters.series = f.series || [];
            this.filters.sort = f.sort || 'rank';
            this.filters.played = f.played || '';
            this.filters.hltb_mode = f.hltb_mode || 'main';
            this.filters.hltb_min = f.hltb_min || null;
            this.filters.hltb_max = f.hltb_max || null;
            this.filters.hltb_preset = this.calculateHltbPreset(this.filters.hltb_min, this.filters.hltb_max);
            this.savedFiltersOpen = false;
            this.debouncedFilterUpdate();

            const resetFlag = () => {
                this.applyingSavedFilter = false;
                document.removeEventListener('htmx:afterSwap', resetFlag);
            };
            document.addEventListener('htmx:afterSwap', resetFlag, { once: true });
            setTimeout(() => { this.applyingSavedFilter = false; }, 500);
        },

        saveCurrentFilters() {
            this.saveFilterName = this._buildDynamicTitle();
            this.saveFilterError = '';
            this.saveFilterSaving = false;
            this.saveFilterModalOpen = true;
            this.savedFiltersOpen = false;
            this.$nextTick(() => {
                const input = document.getElementById('save-filter-name-input');
                if (input) {
                    input.focus();
                    input.select();
                }
            });
        },

        async submitSaveFilter() {
            const name = this.saveFilterName.trim();
            if (!name) {
                this.saveFilterError = 'Filter name is required';
                return;
            }
            if (name.length > 255) {
                this.saveFilterError = 'Filter name must be 255 characters or less';
                return;
            }

            this.saveFilterSaving = true;
            this.saveFilterError = '';

            const csrfToken = this._getCsrfToken();
            try {
                const response = await fetch('/api/saved-filters/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({
                        name: name,
                        filters: {
                            q: this.filters.q,
                            start: this.filters.start,
                            end: this.filters.end,
                            genres: this.filters.genres,
                            platforms: this.filters.platforms,
                            series: this.filters.series,
                            sort: this.filters.sort,
                            sortDirection: this.filters.sortDirection,
                            played: this.filters.played,
                            hltb_mode: this.filters.hltb_mode,
                            hltb_min: this.filters.hltb_min,
                            hltb_max: this.filters.hltb_max,
                        },
                    }),
                });

                if (response.ok) {
                    const newFilter = await response.json();
                    this.savedFilters.unshift(newFilter);
                    this.saveFilterModalOpen = false;
                } else {
                    let errorMsg = 'Failed to save filter';
                    try {
                        const error = await response.json();
                        errorMsg = error.error || errorMsg;
                    } catch (e) {
                        errorMsg = 'Error ' + response.status + ': ' + response.statusText;
                    }
                    this.saveFilterError = errorMsg;
                }
            } catch (e) {
                console.error('[SavedFilters] Failed to save:', e);
                this.saveFilterError = 'Network error - please try again';
            } finally {
                this.saveFilterSaving = false;
            }
        },

        renameSavedFilter(filter) {
            this.renameFilterTarget = filter;
            this.renameFilterName = filter.name;
            this.renameFilterError = '';
            this.renameFilterSaving = false;
            this.renameFilterModalOpen = true;
            this.savedFiltersOpen = false;
            this.$nextTick(() => {
                const input = document.getElementById('rename-filter-name-input');
                if (input) {
                    input.focus();
                    input.select();
                }
            });
        },

        async submitRenameFilter() {
            const name = this.renameFilterName.trim();
            if (!name) {
                this.renameFilterError = 'Filter name is required';
                return;
            }
            if (name === this.renameFilterTarget.name) {
                this.renameFilterModalOpen = false;
                return;
            }

            this.renameFilterSaving = true;
            this.renameFilterError = '';

            const csrfToken = this._getCsrfToken();
            try {
                const response = await fetch('/api/saved-filters/' + this.renameFilterTarget.id + '/', {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({ name: name }),
                });

                if (response.ok) {
                    this.renameFilterTarget.name = name;
                    this.renameFilterModalOpen = false;
                } else {
                    let errorMsg = 'Failed to rename filter';
                    try {
                        const error = await response.json();
                        errorMsg = error.error || errorMsg;
                    } catch (e) {
                        errorMsg = 'Error ' + response.status + ': ' + response.statusText;
                    }
                    this.renameFilterError = errorMsg;
                }
            } catch (e) {
                console.error('[SavedFilters] Failed to rename:', e);
                this.renameFilterError = 'Network error - please try again';
            } finally {
                this.renameFilterSaving = false;
            }
        },

        deleteSavedFilter(filter) {
            this.deleteFilterTarget = filter;
            this.deleteFilterDeleting = false;
            this.deleteFilterModalOpen = true;
            this.savedFiltersOpen = false;
        },

        async confirmDeleteFilter() {
            this.deleteFilterDeleting = true;
            const csrfToken = this._getCsrfToken();
            try {
                const response = await fetch('/api/saved-filters/' + this.deleteFilterTarget.id + '/', {
                    method: 'DELETE',
                    headers: { 'X-CSRFToken': csrfToken },
                });

                if (response.ok) {
                    const index = this.savedFilters.indexOf(this.deleteFilterTarget);
                    if (index > -1) this.savedFilters.splice(index, 1);
                    this.deleteFilterModalOpen = false;
                }
            } catch (e) {
                console.error('[SavedFilters] Failed to delete:', e);
            } finally {
                this.deleteFilterDeleting = false;
            }
        },

        _buildDynamicTitle() {
            const timeWindow = this._buildTimeWindow();
            const platformLabel = this._buildPlatformSegment();
            let genreLabel = '';
            let seriesLabel = '';
            if (this.filters.genres && this.filters.genres.length > 0) {
                const genreNames = this.filters.genres
                    .map(gid => this.genres.find(g => String(g.id) === String(gid)))
                    .filter(g => g)
                    .map(g => g.name);
                if (genreNames.length > 0) {
                    genreLabel = ' ' + this._joinNames(genreNames);
                }
            }

            if (this.filters.series && this.filters.series.length === 1) {
                const series = this.seriesList.find(s => String(s.id) === String(this.filters.series[0]));
                if (series) {
                    seriesLabel = series.name;
                }
            }

            let hltbLabel = '';
            if (this.filters.hltb_min !== null || this.filters.hltb_max !== null) {
                let timeDesc = '';
                const mode = this.filters.hltb_mode || 'main';
                const modeSuffix = mode === 'completionist' ? ' (100%)' : '';
                const min = this.filters.hltb_min;
                const max = this.filters.hltb_max;

                if (min === 0 && max === 10) {
                    timeDesc = 'Short (<10 Hour)';
                } else if (min === 10 && max === 30) {
                    timeDesc = 'Medium (10-30 Hour)';
                } else if (min === 30 && max === null) {
                    timeDesc = 'Long (30+ Hour)';
                } else if (min === 0 && max !== null) {
                    timeDesc = '<' + max + ' Hour';
                } else if (min !== null && max !== null) {
                    if (min === max) {
                        timeDesc = '~' + min + ' Hour';
                    } else {
                        timeDesc = min + '-' + max + ' Hour';
                    }
                } else if (min !== null) {
                    timeDesc = min + '+ Hour';
                } else if (max !== null) {
                    timeDesc = '<' + max + ' Hour';
                }

                if (timeDesc) {
                    hltbLabel = ' ' + timeDesc + modeSuffix;
                }
            }

            const timeSuffix = timeWindow ? ' of ' + timeWindow : '';
            let platform = platformLabel;

            if ((genreLabel || seriesLabel || hltbLabel) && platform === 'Video') {
                platform = '';
            }

            let titleParts = 'Most Acclaimed';
            if (hltbLabel) titleParts += hltbLabel;
            if (platform) titleParts += ' ' + platform;
            if (genreLabel) titleParts += genreLabel;
            if (seriesLabel) titleParts += ' ' + seriesLabel;
            titleParts += ' Games' + timeSuffix;

            if (this.filters.played === 'yes') {
                titleParts += ': Played';
            } else if (this.filters.played === 'want') {
                titleParts += ': Want to Play';
            } else if (this.filters.played === 'no') {
                titleParts += ': Untracked';
            }

            return titleParts;
        },

        _buildTimeWindow() {
            const start = this.filters.start;
            const end = this.filters.end;
            if (!start || !end) return '';
            if (start <= this.minYear && end >= this.maxYear) return 'All Time';
            if (start === end) return String(start);
            if (start % 10 === 0 && end === start + 9) return 'the ' + start + 's';
            return start + '-' + end;
        },

        _buildPlatformSegment() {
            return buildPlatformSegment(this.platforms, this.filters.platforms);
        },

        _joinNames(names) {
            if (!names || names.length === 0) return '';
            if (names.length === 1) return names[0];
            if (names.length === 2) return names.join(' and ');
            return names.slice(0, -1).join(', ') + ', and ' + names[names.length - 1];
        },

        handleFilterChange(type, data) {
            if (type === 'hltb') {
                this.filters.hltb_mode = data.mode;
                this.filters.hltb_min = data.min;
                this.filters.hltb_max = data.max;
                this.filters.hltb_preset = this.calculateHltbPreset(data.min, data.max);
            } else {
                const itemIds = data.map(item => {
                    if (typeof item === 'object' && item !== null && item.id !== undefined) {
                        return String(item.id);
                    }
                    return String(item);
                });
                if (type === 'genres') {
                    this.filters.genres = itemIds;
                } else if (type === 'platforms') {
                    this.filters.platforms = itemIds;
                } else if (type === 'series') {
                    this.filters.series = itemIds;
                }
            }
            if (this.initialized) {
                this.debouncedFilterUpdate();
            }
        },

        resetSearch() {
            this.filters.q = '';
            if (this.initialized) this.updateResults();
        },

        resetYears() {
            this.filters.start = this.minYear;
            this.filters.end = this.maxYear;
            this.$dispatch('year-reset');
            if (this.initialized) this.debouncedFilterUpdate();
        },

        resetPlatforms() {
            this.filters.platforms = [];
            this.$dispatch('platforms-reset');
            if (this.initialized) this.debouncedFilterUpdate();
        },

        resetGenres() {
            this.filters.genres = [];
            this.$dispatch('genres-reset');
            if (this.initialized) this.debouncedFilterUpdate();
        },

        resetSeries() {
            this.filters.series = [];
            this.$dispatch('series-reset');
            if (this.initialized) this.debouncedFilterUpdate();
        },

        calculateHltbPreset(min, max) {
            if (min === null && max === null) return '';
            if (min === 0 && max === 10) return 'short';
            if (min === 10 && max === 30) return 'medium';
            if (min === 30 && max === null) return 'long';
            return 'custom';
        },

        resetHltb() {
            this.filters.hltb_mode = 'main';
            this.filters.hltb_preset = '';
            this.filters.hltb_min = null;
            this.filters.hltb_max = null;
            window.dispatchEvent(new CustomEvent('hltb-reset'));
            if (this.initialized) this.debouncedFilterUpdate();
        },

        resetPlayed() {
            this.filters.played = '';
            if (this.initialized) this.debouncedFilterUpdate();
        },

        resetAllFilters() {
            this.filters.q = '';
            this.filters.start = this.minYear;
            this.filters.end = this.maxYear;
            this.filters.genres = [];
            this.filters.platforms = [];
            this.filters.series = [];
            this.filters.played = '';
            this.filters.sort = 'rank';
            this.filters.hltb_mode = 'main';
            this.filters.hltb_preset = '';
            this.filters.hltb_min = null;
            this.filters.hltb_max = null;
            this.$dispatch('platforms-reset');
            this.$dispatch('genres-reset');
            this.$dispatch('series-reset');
            this.$dispatch('year-reset');
            window.dispatchEvent(new CustomEvent('hltb-reset'));
            if (this.initialized) this.debouncedFilterUpdate();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        addPlatform(data) {
            const { platformId, gameId } = data;
            const id = String(platformId);
            this.filters.q = '';
            this.filters.start = this.minYear;
            this.filters.end = this.maxYear;
            this.filters.genres = [];
            this.filters.platforms = [id];
            this.$dispatch('genres-reset');
            this.$dispatch('year-reset');
            if (this.initialized) this.debouncedFilterUpdate();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        addPlatforms(data) {
            const { platformIds, gameId } = data;
            const ids = platformIds.split(',').filter(id => id);
            this.filters.q = '';
            this.filters.start = this.minYear;
            this.filters.end = this.maxYear;
            this.filters.genres = [];
            this.filters.platforms = ids;
            this.$dispatch('genres-reset');
            this.$dispatch('year-reset');
            if (this.initialized) this.debouncedFilterUpdate();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        addGenre(data) {
            const { genreId, gameId } = data;
            const id = String(genreId);
            this.filters.q = '';
            this.filters.start = this.minYear;
            this.filters.end = this.maxYear;
            this.filters.genres = [id];
            this.filters.platforms = [];
            this.$dispatch('platforms-reset');
            this.$dispatch('year-reset');
            if (this.initialized) this.debouncedFilterUpdate();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        addGenres(data) {
            const { genreIds, gameId } = data;
            const ids = genreIds.split(',').filter(id => id);
            this.filters.q = '';
            this.filters.start = this.minYear;
            this.filters.end = this.maxYear;
            this.filters.genres = ids;
            this.filters.platforms = [];
            this.$dispatch('platforms-reset');
            this.$dispatch('year-reset');
            if (this.initialized) this.debouncedFilterUpdate();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        async performUpdate(options = {}) {
            const { partial = false, historyMethod = 'pushState', preservePage = false } = options;

            if (this.clientFilterReady) {
                return this.performClientUpdate({ historyMethod });
            }

            if (partial) {
                this.isLoading = true;
                setLoading('game-results-container');
                return;
            }

            const signal = this.fetchManager.newRequest();
            this.isLoading = true;
            setLoading('game-results-container');

            const params = buildFilterParams(this.filters, { preservePage });
            const url = '/games/?' + normalizeUrl(params.toString());

            try {
                const html = await fetchHtml(url, signal);

                if (partial) {
                    const content = parseAndExtract(html, [
                        { selector: '#search-heading', targetId: 'search-heading' },
                        { selector: '#game-results-container', targetId: 'game-results-container' }
                    ]);
                    updateDomElements(content);
                    if (typeof initLoadMore === 'function') initLoadMore();

                    const urlParams = new URLSearchParams(params.toString());
                    const highlightId = urlParams.get('highlight');
                    if (highlightId) {
                        setTimeout(() => {
                            const desktopElement = document.getElementById('game-' + highlightId);
                            const mobileElement = document.getElementById('game-' + highlightId + '-mobile');
                            const isDesktop = window.matchMedia('(min-width: 962px)').matches;
                            const element = isDesktop ? desktopElement : mobileElement;

                            if (element) {
                                element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                const fadeTimeout = setTimeout(() => {
                                    if (desktopElement) desktopElement.classList.add('fade-out');
                                    if (mobileElement) mobileElement.classList.add('fade-out');
                                }, 4000);

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

                    const yearCountsEl = document.getElementById('year-counts-update');
                    if (yearCountsEl) {
                        try {
                            const yearCounts = JSON.parse(yearCountsEl.textContent);
                            window.dispatchEvent(new CustomEvent('year-counts-update', { detail: yearCounts }));
                        } catch (e) {
                            console.error('Error parsing year counts:', e);
                        }
                    }

                    const genreCountsEl = document.getElementById('genre-counts-update');
                    if (genreCountsEl) {
                        try {
                            const genreCounts = JSON.parse(genreCountsEl.textContent);
                            window.dispatchEvent(new CustomEvent('genre-counts-update', { detail: genreCounts }));
                        } catch (e) {
                            console.error('Error parsing genre counts:', e);
                        }
                    }

                    const platformCountsEl = document.getElementById('platform-counts-update');
                    if (platformCountsEl) {
                        try {
                            const platformCounts = JSON.parse(platformCountsEl.textContent);
                            window.dispatchEvent(new CustomEvent('platform-counts-update', { detail: platformCounts }));
                        } catch (e) {
                            console.error('Error parsing platform counts:', e);
                        }
                    }

                    const rankDistEl = document.getElementById('rank-distribution-update');
                    if (rankDistEl) {
                        try {
                            const rankDist = JSON.parse(rankDistEl.textContent);
                            window.dispatchEvent(new CustomEvent('rank-distribution-update', { detail: rankDist }));
                        } catch (e) {
                            console.error('Error parsing rank distribution:', e);
                        }
                    }
                } else {
                    const contentEl = document.getElementById('content');
                    if (contentEl) {
                        contentEl.innerHTML = html;
                    }
                }

                window.history[historyMethod]({}, '', url);
            } catch (err) {
                if (err.name !== 'AbortError') {
                    console.error('Error fetching results:', err);
                }
            } finally {
                this.isLoading = false;
                clearLoading('game-results-container');
                if (this.filters.highlight) {
                    delete this.filters.highlight;
                }
            }
        },

        performClientUpdate(options = {}) {
            const { historyMethod = 'pushState' } = options;

            this.isLoading = true;

            const highlightId = this.filters.highlight ? parseInt(this.filters.highlight) : null;

            const gameListContainer = document.getElementById('game-list-container');
            const countContainer = document.querySelector('.result-count');
            const loadMoreContainer = document.querySelector('.load-more-container');

            if (!gameListContainer) {
                console.error('[CSF] game-list-container not found');
                this.updateFacetCounts();
                this.isLoading = false;
                return;
            }

            const result = this._csf.applyFilters(this.filters);
            if (!result) {
                this.isLoading = false;
                return;
            }

            const state = this._csf.renderResults(result, gameListContainer, {
                highlightId,
                showRank: this.hasActiveFilters() ? 'filtered' : 'alltime'
            });

            if (countContainer) {
                countContainer.innerHTML = this._csf.renderer.getResultSummaryHtml(state.loaded, state.total);
            }

            if (loadMoreContainer) {
                loadMoreContainer.innerHTML = this._csf.renderer.getLoadMoreHtml(state);
                this._initClientLoadMore(loadMoreContainer, gameListContainer, countContainer);
            }

            const searchTitle = document.getElementById('search-title');
            if (searchTitle) {
                searchTitle.textContent = this._buildDynamicTitle();
            }

            if (state.facets) {
                const yearCountsArray = [];
                const yearFacets = state.facets.years || {};
                for (let y = this.minYear; y <= this.maxYear; y++) {
                    yearCountsArray.push({ year: y, count: yearFacets[y] || 0 });
                }
                window.dispatchEvent(new CustomEvent('year-counts-update', { detail: yearCountsArray }));

                window.dispatchEvent(new CustomEvent('genre-counts-update', { detail: state.facets.genres }));
                window.dispatchEvent(new CustomEvent('platform-counts-update', { detail: state.facets.platforms }));

                if (state.facets.platformGroups) {
                    this.platformGroupCounts = state.facets.platformGroups;
                    window.dispatchEvent(new CustomEvent('platform-group-counts-update', { detail: state.facets.platformGroups }));
                }

                if (state.facets.series) {
                    window.dispatchEvent(new CustomEvent('series-counts-update', { detail: state.facets.series }));
                }

                if (state.facets.rankDistribution) {
                    window.dispatchEvent(new CustomEvent('rank-distribution-update', { detail: state.facets.rankDistribution }));
                }
            }

            const params = buildFilterParams(this.filters);
            const url = '/games/?' + normalizeUrl(params.toString());
            window.history[historyMethod]({}, '', url);

            this.isLoading = false;

            if (this.filters.highlight) {
                delete this.filters.highlight;
            }
        },

        updateFacetCounts() {
            const result = this._csf.applyFilters(this.filters);
            if (!result || !result.facets) return;

            const yearCountsArray = [];
            const yearFacets = result.facets.years || {};
            for (let y = this.minYear; y <= this.maxYear; y++) {
                yearCountsArray.push({ year: y, count: yearFacets[y] || 0 });
            }
            window.dispatchEvent(new CustomEvent('year-counts-update', { detail: yearCountsArray }));

            window.dispatchEvent(new CustomEvent('genre-counts-update', { detail: result.facets.genres || {} }));
            window.dispatchEvent(new CustomEvent('platform-counts-update', { detail: result.facets.platforms || {} }));

            if (result.facets.platformGroups) {
                this.platformGroupCounts = result.facets.platformGroups;
                window.dispatchEvent(new CustomEvent('platform-group-counts-update', { detail: result.facets.platformGroups }));
            }

            if (result.facets.series) {
                window.dispatchEvent(new CustomEvent('series-counts-update', { detail: result.facets.series }));
            }

            if (result.facets.rankDistribution) {
                window.dispatchEvent(new CustomEvent('rank-distribution-update', { detail: result.facets.rankDistribution }));
            }
        },

        dispatchInitialCounts() {
            console.log('[CSF] Dispatching initial counts from server-rendered data');

            const yearCountsEl = document.getElementById('year-counts-update');
            if (yearCountsEl) {
                try {
                    const yearCounts = JSON.parse(yearCountsEl.textContent);
                    window.dispatchEvent(new CustomEvent('year-counts-update', { detail: yearCounts }));
                } catch (e) {
                    console.error('Error parsing year counts:', e);
                }
            }

            const genreCountsEl = document.getElementById('genre-counts-update');
            if (genreCountsEl) {
                try {
                    const genreCounts = JSON.parse(genreCountsEl.textContent);
                    window.dispatchEvent(new CustomEvent('genre-counts-update', { detail: genreCounts }));
                } catch (e) {
                    console.error('Error parsing genre counts:', e);
                }
            }

            const platformCountsEl = document.getElementById('platform-counts-update');
            if (platformCountsEl) {
                try {
                    const platformCounts = JSON.parse(platformCountsEl.textContent);
                    window.dispatchEvent(new CustomEvent('platform-counts-update', { detail: platformCounts }));
                } catch (e) {
                    console.error('Error parsing platform counts:', e);
                }
            }

            const seriesCountsEl = document.getElementById('series-counts-update');
            if (seriesCountsEl) {
                try {
                    const seriesCounts = JSON.parse(seriesCountsEl.textContent);
                    window.dispatchEvent(new CustomEvent('series-counts-update', { detail: seriesCounts }));
                } catch (e) {
                    console.error('Error parsing series counts:', e);
                }
            }
        },

        _initClientLoadMore(loadMoreContainer, gameListContainer, countContainer) {
            const button = loadMoreContainer.querySelector('.load-more-button');
            if (!button) return;

            button.addEventListener('click', () => {
                button.classList.add('loading');
                button.disabled = true;

                const state = this._csf.loadMore(gameListContainer);

                if (countContainer) {
                    countContainer.innerHTML = this._csf.renderer.getResultSummaryHtml(state.loaded, state.total);
                }

                loadMoreContainer.innerHTML = this._csf.renderer.getLoadMoreHtml({
                    hasMore: state.hasMore,
                    remaining: state.remaining,
                    maxLoaded: state.loaded >= 1000
                });

                if (state.hasMore) {
                    this._initClientLoadMore(loadMoreContainer, gameListContainer, countContainer);
                }
            });
        },

        updateResults() {
            if (!this.initialized) return;
            this._debouncedUpdate();
        },

        updateUrlAndResults() {
            if (!this.initialized) return;
            if (this._debouncedUpdate) this._debouncedUpdate.cancel();
            this.performUpdate({ partial: false, historyMethod: 'pushState' });
        },

        throttledSliderUpdate() {
            this._throttledSlider.call();
        },

        forceSliderUpdate() {
            this._throttledSlider.force();
        },

        debouncedFilterUpdate() {
            this._debouncedFilter();
        },

        updateUrl() {
            this.debouncedFilterUpdate();
        },

        updateSort(newSort) {
            this.filters.sort = newSort;
            if (this.initialized) {
                this.debouncedFilterUpdate();
            }
        },

        toggleSortDirection() {
            this.filters.sortDirection = this.filters.sortDirection === 'asc' ? 'desc' : 'asc';
            if (this.initialized) {
                this.debouncedFilterUpdate();
            }
        },

        setViewMode(mode) {
            this.viewMode = mode;
            localStorage.setItem('gameViewMode', mode);
            if (this._csf) {
                this._csf.setViewMode(mode);
            }
            if (this.clientFilterReady && this._csf) {
                this.performClientUpdate({ historyMethod: 'replaceState' });
            }
        },

        updateDisplayOnly() {
            if (!this.initialized) return;
            this._debouncedDisplay();
        }
    }));
});
