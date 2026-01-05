/**
 * Acclaimed Books - Client-Side Book List Renderer
 *
 * Renders book rows by cloning HTML templates from the DOM.
 * Templates are defined in Django and included as <template> elements.
 * This ensures a single source of truth for HTML structure.
 *
 * Extends BaseMediaListRenderer from core.
 */

/**
 * BookListRenderer - Renders book lists client-side using DOM template cloning
 *
 * Usage:
 *   const renderer = new BookListRenderer(filterEngine);
 *   renderer.render(books, container, { showRank: 'filtered' });
 */
class BookListRenderer extends BaseMediaListRenderer {
    /**
     * @param {BookFilterEngine} filterEngine - Engine with reference data
     */
    constructor(filterEngine) {
        super(filterEngine);
    }

    /**
     * Format page count for display
     * @private
     * @param {number} pages - Page count
     * @returns {string} Formatted page count string
     */
    _formatPageCount(pages) {
        if (pages === null || pages === undefined) return '';
        return `${pages.toLocaleString()} pages`;
    }

    /**
     * Initialize templates from DOM
     * Called lazily on first render
     * @protected
     */
    _initTemplates() {
        if (this._templates) return;

        this._templates = {
            desktop: document.getElementById('desktop-row-template'),
            mobile: document.getElementById('mobile-row-template'),
            grid: document.getElementById('grid-card-template'),
            readButton: document.getElementById('read-button-template')
        };

        // Fallback check - if templates don't exist, we'll use string rendering
        if (!this._templates.desktop || !this._templates.mobile) {
            console.warn('Book row templates not found, falling back to string rendering');
            this._templates = null;
        }
    }

    /**
     * Check if a book is marked as read
     * @private
     */
    _isRead(goodreadsId) {
        return window.readBookIds && window.readBookIds.has(goodreadsId);
    }

    /**
     * Check if a book is marked as want to read
     * @private
     */
    _isWantToRead(goodreadsId) {
        return window.wantToReadBookIds && window.wantToReadBookIds.has(goodreadsId);
    }

    /**
     * Get book status: 'read', 'want', or 'none'
     * @private
     */
    _getBookStatus(goodreadsId) {
        if (this._isRead(goodreadsId)) return 'read';
        if (this._isWantToRead(goodreadsId)) return 'want';
        return 'none';
    }

    /**
     * Render the book status button by cloning template
     * Handles 3 states: read, want to read, untracked
     * @private
     * @returns {DocumentFragment|null}
     */
    _renderReadButtonDOM(book) {
        // Only render if authenticated and book has ID
        if (!window.isAuthenticated || !book.i) {
            return null;
        }

        const template = this._templates?.readButton;
        if (!template) {
            // Fallback to string-based button
            const html = this._renderReadButtonString(book);
            if (!html) return null;
            const div = document.createElement('div');
            div.innerHTML = html;
            return div.firstElementChild;
        }

        const fragment = template.content.cloneNode(true);
        const wrapper = fragment.querySelector('[data-slot="read-wrapper"]');
        if (!wrapper) return null;

        const status = this._getBookStatus(book.i);
        const bookSlug = book.s;

        // Update data attributes
        wrapper.setAttribute('data-book-slug', bookSlug);
        wrapper.setAttribute('data-book-id', book.i);

        // Get button elements
        const readBtn = wrapper.querySelector('[data-slot="read-btn"]');
        const wantBtn = wrapper.querySelector('[data-slot="want-btn"]');
        const trackBtn = wrapper.querySelector('[data-slot="track-btn"]');

        if (status === 'read') {
            // Show read state
            if (readBtn) {
                readBtn.classList.remove('hidden');
                readBtn.setAttribute('hx-delete', `/books/${bookSlug}/read/`);
            }
            if (wantBtn) wantBtn.classList.add('hidden');
            if (trackBtn) trackBtn.classList.add('hidden');
        } else if (status === 'want') {
            // Show want to read state
            if (readBtn) readBtn.classList.add('hidden');
            if (wantBtn) {
                wantBtn.classList.remove('hidden');
                wantBtn.setAttribute('hx-delete', `/books/${bookSlug}/want-to-read/`);
            }
            if (trackBtn) trackBtn.classList.add('hidden');
        } else {
            // Show untracked state (dropdown)
            if (readBtn) readBtn.classList.add('hidden');
            if (wantBtn) wantBtn.classList.add('hidden');
            if (trackBtn) {
                trackBtn.classList.remove('hidden');
                // Set up dropdown menu links
                const markReadLink = trackBtn.querySelector('[data-action="mark-read"]');
                const markWantLink = trackBtn.querySelector('[data-action="mark-want"]');
                if (markReadLink) {
                    markReadLink.setAttribute('hx-post', `/books/${bookSlug}/read/`);
                }
                if (markWantLink) {
                    markWantLink.setAttribute('hx-post', `/books/${bookSlug}/want-to-read/`);
                }
            }
        }

        return fragment;
    }

    /**
     * Render read button as HTML string (fallback)
     * @private
     */
    _renderReadButtonString(book) {
        if (!window.isAuthenticated || !book.i) return '';

        const status = this._getBookStatus(book.i);
        const csrfToken = this._getCsrfToken();
        const bookSlug = book.s;

        if (status === 'read') {
            return `
                <button type="button"
                    class="btn btn-sm btn-success"
                    hx-delete="/books/${bookSlug}/read/"
                    hx-headers='{"X-CSRFToken": "${csrfToken}"}'
                    hx-swap="outerHTML"
                    title="Mark as unread">
                    <span class="mdi mdi-check"></span>
                    <span>Read</span>
                </button>
            `;
        } else if (status === 'want') {
            return `
                <button type="button"
                    class="btn btn-sm btn-info"
                    hx-delete="/books/${bookSlug}/want-to-read/"
                    hx-headers='{"X-CSRFToken": "${csrfToken}"}'
                    hx-swap="outerHTML"
                    title="Remove from Want to Read">
                    <span class="mdi mdi-bookmark"></span>
                    <span>Want to Read</span>
                </button>
            `;
        } else {
            return `
                <div class="dropdown dropdown-end">
                    <button type="button" tabindex="0" class="btn btn-sm btn-ghost">
                        <span class="mdi mdi-plus"></span>
                        <span>Track</span>
                    </button>
                    <ul tabindex="0" class="dropdown-content menu bg-base-100 rounded-box z-10 w-52 p-2 shadow">
                        <li>
                            <a hx-post="/books/${bookSlug}/read/"
                               hx-headers='{"X-CSRFToken": "${csrfToken}"}'
                               hx-swap="outerHTML"
                               hx-target="closest .dropdown">
                                <span class="mdi mdi-check"></span> Mark as Read
                            </a>
                        </li>
                        <li>
                            <a hx-post="/books/${bookSlug}/want-to-read/"
                               hx-headers='{"X-CSRFToken": "${csrfToken}"}'
                               hx-swap="outerHTML"
                               hx-target="closest .dropdown">
                                <span class="mdi mdi-bookmark-outline"></span> Want to Read
                            </a>
                        </li>
                    </ul>
                </div>
            `;
        }
    }

    /**
     * Render a single desktop row
     * @protected
     * @param {Object} book - Compact book object
     * @param {number} index - Position in list (1-based for display)
     * @param {string} showRank - 'alltime', 'filtered', or 'none'
     * @returns {Element} The rendered desktop row element
     */
    _renderDesktopRow(book, index, showRank) {
        this._initTemplates();

        if (!this._templates) {
            // Fallback to string rendering
            return this._renderDesktopRowString(book, index, showRank);
        }

        const template = this._templates.desktop;
        if (!template) return null;

        const row = template.content.cloneNode(true).firstElementChild;
        if (!row) return null;

        // Expand book data
        const expanded = this.engine.expandBook(book);

        // Set ID for highlighting
        row.id = 'book-' + book.id;

        // Highlight if needed
        if (this.highlightId && book.id === this.highlightId) {
            row.classList.add('highlight-row');
        }

        // Fill rank slots
        if (showRank === 'alltime' || showRank === 'filtered') {
            this._fillSlot(row, 'rank', showRank === 'alltime' ? book.r : index);
            const globalRankEl = this._fillSlot(row, 'global-rank', book.r);
            if (globalRankEl && showRank === 'alltime') {
                globalRankEl.classList.add('hidden');
            }
        }

        // Fill cover image
        const thumbEl = row.querySelector('[data-slot="thumbnail"]');
        if (thumbEl && book.c) {
            thumbEl.src = book.c;
            thumbEl.alt = expanded.name;
        }

        // Fill name and link
        this._fillSlot(row, 'name', expanded.name);
        const titleLink = row.querySelector('[data-slot="title-link"]');
        if (titleLink) {
            titleLink.href = '/books/' + expanded.slug + '/';
        }
        const thumbLink = row.querySelector('[data-slot="thumb-link"]');
        if (thumbLink) {
            thumbLink.href = '/books/' + expanded.slug + '/';
        }

        // Fill year
        if (expanded.year) {
            this._fillSlot(row, 'year', expanded.year);
            const yearLink = row.querySelector('[data-slot="year-link"]');
            if (yearLink) {
                yearLink.href = '/books/?year=' + expanded.year;
            }
        } else {
            const yearEl = row.querySelector('[data-slot="year"]');
            if (yearEl) yearEl.textContent = '';
        }

        // Fill page count
        if (expanded.pageCount) {
            this._fillSlot(row, 'page-count', this._formatPageCount(expanded.pageCount));
        }

        // Fill authors
        const authorsContainer = row.querySelector('[data-slot="authors"]');
        if (authorsContainer && expanded.authors.length > 0) {
            authorsContainer.innerHTML = '';
            expanded.authors.forEach((author, idx) => {
                if (idx > 0) {
                    authorsContainer.appendChild(document.createTextNode(', '));
                }
                const link = document.createElement('a');
                link.href = '/authors/' + (author.root?.slug || author.slug) + '/';
                link.className = 'link link-hover';
                link.textContent = author.name;
                authorsContainer.appendChild(link);
            });
        }

        // Fill genres
        const genresContainer = row.querySelector('[data-slot="genres"]');
        if (genresContainer && expanded.genres.length > 0) {
            genresContainer.innerHTML = '';
            expanded.genres.slice(0, 3).forEach((genre, idx) => {
                if (idx > 0) {
                    genresContainer.appendChild(document.createTextNode(', '));
                }
                const link = document.createElement('a');
                link.href = '/books/?genres=' + genre.id;
                link.className = 'link link-hover';
                link.textContent = genre.name;
                genresContainer.appendChild(link);
            });
            if (expanded.genres.length > 3) {
                genresContainer.appendChild(document.createTextNode(` +${expanded.genres.length - 3}`));
            }
        }

        // Fill read button
        const readButtonSlot = row.querySelector('[data-slot="read-button"]');
        if (readButtonSlot) {
            const buttonFragment = this._renderReadButtonDOM(book);
            if (buttonFragment) {
                readButtonSlot.innerHTML = '';
                readButtonSlot.appendChild(buttonFragment);
            }
        }

        return row;
    }

    /**
     * Render desktop row as HTML string (fallback)
     * @private
     */
    _renderDesktopRowString(book, index, showRank) {
        const expanded = this.engine.expandBook(book);
        const rankDisplay = showRank === 'alltime' ? book.r : index;

        const authorsHtml = expanded.authors.map(a =>
            `<a href="/authors/${a.root?.slug || a.slug}/" class="link link-hover">${this._escapeHtml(a.name)}</a>`
        ).join(', ');

        const genresHtml = expanded.genres.slice(0, 3).map(g =>
            `<a href="/books/?genres=${g.id}" class="link link-hover">${this._escapeHtml(g.name)}</a>`
        ).join(', ') + (expanded.genres.length > 3 ? ` +${expanded.genres.length - 3}` : '');

        const highlightClass = (this.highlightId && book.id === this.highlightId) ? 'highlight-row' : '';

        const html = `
            <tr id="book-${book.id}" class="media-row hidden md:table-row ${highlightClass}">
                <td class="text-center font-bold">${rankDisplay}</td>
                <td>
                    <div class="flex items-center gap-3">
                        <a href="/books/${expanded.slug}/">
                            <img src="${book.c || '/static/games/images/placeholder-book.png'}"
                                 alt="${this._escapeHtml(expanded.name)}"
                                 class="w-12 h-16 object-cover rounded">
                        </a>
                        <div>
                            <a href="/books/${expanded.slug}/" class="font-medium link link-hover">
                                ${this._escapeHtml(expanded.name)}
                            </a>
                            <div class="text-sm opacity-70">${authorsHtml}</div>
                        </div>
                    </div>
                </td>
                <td>${expanded.year || ''}</td>
                <td>${genresHtml}</td>
                <td>${expanded.pageCount ? this._formatPageCount(expanded.pageCount) : ''}</td>
                <td>${this._renderReadButtonString(book)}</td>
            </tr>
        `;

        const div = document.createElement('div');
        div.innerHTML = html.trim();
        return div.firstElementChild;
    }

    /**
     * Render a single mobile row
     * @protected
     * @param {Object} book - Compact book object
     * @param {number} index - Position in list (1-based for display)
     * @param {string} showRank - 'alltime', 'filtered', or 'none'
     * @returns {Element} The rendered mobile row element
     */
    _renderMobileRow(book, index, showRank) {
        this._initTemplates();

        if (!this._templates) {
            return this._renderMobileRowString(book, index, showRank);
        }

        const template = this._templates.mobile;
        if (!template) return null;

        const row = template.content.cloneNode(true).firstElementChild;
        if (!row) return null;

        // Expand book data
        const expanded = this.engine.expandBook(book);

        // Set ID for highlighting
        row.id = 'book-' + book.id + '-mobile';

        // Highlight if needed
        if (this.highlightId && book.id === this.highlightId) {
            row.classList.add('highlight-row');
        }

        // Fill rank
        if (showRank === 'alltime' || showRank === 'filtered') {
            this._fillSlot(row, 'rank', showRank === 'alltime' ? book.r : index);
        }

        // Fill cover image
        const thumbEl = row.querySelector('[data-slot="thumbnail"]');
        if (thumbEl && book.c) {
            thumbEl.src = book.c;
            thumbEl.alt = expanded.name;
        }

        // Fill name and link
        this._fillSlot(row, 'name', expanded.name);
        const titleLink = row.querySelector('[data-slot="title-link"]');
        if (titleLink) {
            titleLink.href = '/books/' + expanded.slug + '/';
        }

        // Fill year
        if (expanded.year) {
            this._fillSlot(row, 'year', expanded.year);
        }

        // Fill authors
        const authorsContainer = row.querySelector('[data-slot="authors"]');
        if (authorsContainer && expanded.authors.length > 0) {
            authorsContainer.innerHTML = '';
            expanded.authors.forEach((author, idx) => {
                if (idx > 0) {
                    authorsContainer.appendChild(document.createTextNode(', '));
                }
                const link = document.createElement('a');
                link.href = '/authors/' + (author.root?.slug || author.slug) + '/';
                link.className = 'link link-hover';
                link.textContent = author.name;
                authorsContainer.appendChild(link);
            });
        }

        // Fill read button
        const readButtonSlot = row.querySelector('[data-slot="read-button"]');
        if (readButtonSlot) {
            const buttonFragment = this._renderReadButtonDOM(book);
            if (buttonFragment) {
                readButtonSlot.innerHTML = '';
                readButtonSlot.appendChild(buttonFragment);
            }
        }

        return row;
    }

    /**
     * Render mobile row as HTML string (fallback)
     * @private
     */
    _renderMobileRowString(book, index, showRank) {
        const expanded = this.engine.expandBook(book);
        const rankDisplay = showRank === 'alltime' ? book.r : index;

        const authorsHtml = expanded.authors.map(a =>
            `<a href="/authors/${a.root?.slug || a.slug}/" class="link link-hover">${this._escapeHtml(a.name)}</a>`
        ).join(', ');

        const highlightClass = (this.highlightId && book.id === this.highlightId) ? 'highlight-row' : '';

        const html = `
            <div id="book-${book.id}-mobile" class="media-row md:hidden p-3 border-b ${highlightClass}">
                <div class="flex gap-3">
                    <div class="flex-shrink-0 w-8 text-center font-bold">${rankDisplay}</div>
                    <a href="/books/${expanded.slug}/">
                        <img src="${book.c || '/static/games/images/placeholder-book.png'}"
                             alt="${this._escapeHtml(expanded.name)}"
                             class="w-12 h-16 object-cover rounded">
                    </a>
                    <div class="flex-1 min-w-0">
                        <a href="/books/${expanded.slug}/" class="font-medium link link-hover block truncate">
                            ${this._escapeHtml(expanded.name)}
                        </a>
                        <div class="text-sm opacity-70">${authorsHtml}</div>
                        <div class="text-sm opacity-50">${expanded.year || ''}</div>
                    </div>
                    <div class="flex-shrink-0">
                        ${this._renderReadButtonString(book)}
                    </div>
                </div>
            </div>
        `;

        const div = document.createElement('div');
        div.innerHTML = html.trim();
        return div.firstElementChild;
    }

    /**
     * Render a single grid card
     * @protected
     * @param {Object} book - Compact book object
     * @param {number} index - Position in list (1-based for display)
     * @param {string} showRank - 'alltime', 'filtered', or 'none'
     * @returns {Element} The rendered grid card element
     */
    _renderGridCard(book, index, showRank) {
        this._initTemplates();

        if (!this._templates || !this._templates.grid) {
            return this._renderGridCardString(book, index, showRank);
        }

        const template = this._templates.grid;
        const card = template.content.cloneNode(true).firstElementChild;
        if (!card) return null;

        // Expand book data
        const expanded = this.engine.expandBook(book);

        // Set ID for highlighting
        card.id = 'book-' + book.id + '-grid';

        // Highlight if needed
        if (this.highlightId && book.id === this.highlightId) {
            card.classList.add('highlight-row');
        }

        // Fill rank
        if (showRank === 'alltime' || showRank === 'filtered') {
            this._fillSlot(card, 'rank', showRank === 'alltime' ? book.r : index);
        }

        // Fill cover image
        const thumbEl = card.querySelector('[data-slot="thumbnail"]');
        if (thumbEl && book.c) {
            thumbEl.src = book.c;
            thumbEl.alt = expanded.name;
        }

        // Fill name and link
        this._fillSlot(card, 'name', expanded.name);
        const titleLink = card.querySelector('[data-slot="title-link"]');
        if (titleLink) {
            titleLink.href = '/books/' + expanded.slug + '/';
        }

        // Fill year
        if (expanded.year) {
            this._fillSlot(card, 'year', expanded.year);
        }

        // Fill authors (primary author only for grid)
        if (expanded.authors.length > 0) {
            const primaryAuthor = expanded.authors[0];
            this._fillSlot(card, 'primary-author', primaryAuthor.name);
            const authorLink = card.querySelector('[data-slot="author-link"]');
            if (authorLink) {
                authorLink.href = '/authors/' + (primaryAuthor.root?.slug || primaryAuthor.slug) + '/';
            }
        }

        // Fill read button
        const readButtonSlot = card.querySelector('[data-slot="read-button"]');
        if (readButtonSlot) {
            const buttonFragment = this._renderReadButtonDOM(book);
            if (buttonFragment) {
                readButtonSlot.innerHTML = '';
                readButtonSlot.appendChild(buttonFragment);
            }
        }

        return card;
    }

    /**
     * Render grid card as HTML string (fallback)
     * @private
     */
    _renderGridCardString(book, index, showRank) {
        const expanded = this.engine.expandBook(book);
        const rankDisplay = showRank === 'alltime' ? book.r : index;
        const primaryAuthor = expanded.authors[0];

        const highlightClass = (this.highlightId && book.id === this.highlightId) ? 'highlight-row' : '';

        const html = `
            <div id="book-${book.id}-grid" class="media-card-grid card bg-base-100 shadow-md ${highlightClass}">
                <figure class="relative">
                    <div class="absolute top-2 left-2 badge badge-primary font-bold">#${rankDisplay}</div>
                    <a href="/books/${expanded.slug}/">
                        <img src="${book.c || '/static/games/images/placeholder-book.png'}"
                             alt="${this._escapeHtml(expanded.name)}"
                             class="w-full h-48 object-cover">
                    </a>
                </figure>
                <div class="card-body p-3">
                    <a href="/books/${expanded.slug}/" class="card-title text-sm link link-hover line-clamp-2">
                        ${this._escapeHtml(expanded.name)}
                    </a>
                    ${primaryAuthor ? `
                        <a href="/authors/${primaryAuthor.root?.slug || primaryAuthor.slug}/"
                           class="text-xs opacity-70 link link-hover">
                            ${this._escapeHtml(primaryAuthor.name)}
                        </a>
                    ` : ''}
                    <div class="text-xs opacity-50">${expanded.year || ''}</div>
                    <div class="card-actions justify-end mt-2">
                        ${this._renderReadButtonString(book)}
                    </div>
                </div>
            </div>
        `;

        const div = document.createElement('div');
        div.innerHTML = html.trim();
        return div.firstElementChild;
    }

    /**
     * Override scroll to highlight for book-specific IDs
     * @protected
     */
    _scrollToHighlight(bookId, viewMode = 'list') {
        setTimeout(() => {
            let elementToScroll = null;
            let elementsToHighlight = [];

            if (viewMode === 'grid') {
                const gridElement = document.getElementById('book-' + bookId + '-grid');
                if (gridElement) {
                    elementToScroll = gridElement;
                    elementsToHighlight = [gridElement];
                }
            } else {
                const desktopElement = document.getElementById('book-' + bookId);
                const mobileElement = document.getElementById('book-' + bookId + '-mobile');
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

                // Fade out on hover of other items
                const selector = viewMode === 'grid' ? '.media-card-grid' : '.media-row';
                const items = document.querySelectorAll(selector);
                items.forEach((item) => {
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
     * Generate load more button HTML with book-themed icons
     * @param {Object} state - { hasMore, remaining, maxLoaded }
     * @returns {string} HTML string
     */
    getLoadMoreHtml(state) {
        const { hasMore, remaining, maxLoaded } = state;

        if (maxLoaded) {
            return '<div class="alert alert-info"><span class="mdi mdi-information-outline"></span><span>Showing maximum of 1,000 results. Refine your filters to see more specific results.</span></div>';
        }

        if (!hasMore) {
            return '<div class="text-base-content/70 text-center">All results loaded</div>';
        }

        return '<button type="button" class="btn btn-ghost load-more-button"><span class="icon"><span class="mdi mdi-plus-circle-outline"></span></span><span class="load-more-text">Load More (' + remaining.toLocaleString() + ' remaining)</span></button>';
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.BookListRenderer = BookListRenderer;
}
