/**
 * Acclaimed Books - Client-Side Filter Engine
 *
 * Replicates server-side filtering logic for client-side filtering.
 * Supports text search, genre hierarchy, author filtering, year range, and sorting.
 */

/**
 * BookFilterEngine - Client-side book filtering
 *
 * Usage:
 *   const engine = new BookFilterEngine(bookData);
 *   const results = engine.filter({
 *     q: 'tolkien',
 *     genres: [1, 2],
 *     genreOption: 'any',
 *     authors: [5, 10],
 *     start: 1950,
 *     end: 2000,
 *     sort: 'rank'
 *   });
 */
class BookFilterEngine {
    /**
     * @param {Object} data - Book data from API
     * @param {Array} data.books - Book objects with id, n, s, r, y, au, g
     * @param {Object} data.authors - Author lookup by ID {n: name, pa: parentId, s: slug}
     * @param {Array} data.genres - Genre objects with id, n, s, p, l, d (descendants)
     */
    constructor(data) {
        this.books = data.books || [];
        this.authors = data.authors || {};
        this.genres = data.genres || [];

        // Lazy initialization flags - defer expensive index building
        this._genreMapBuilt = false;
        this._genreMap = null;
        this._genreDescendants = null;
    }

    /**
     * Lazily build genre lookup and descendant sets
     * @private
     */
    _ensureGenreMap() {
        if (this._genreMapBuilt) return;

        this._genreMap = new Map();
        this._genreDescendants = new Map();
        for (const genre of this.genres) {
            this._genreMap.set(genre.id, genre);
            // Store descendants as Set for O(1) lookup
            const descendantSet = new Set(genre.d || []);
            descendantSet.add(genre.id); // Include self for matching
            this._genreDescendants.set(genre.id, descendantSet);
        }
        this._genreMapBuilt = true;
    }

    /**
     * Filter books based on criteria
     *
     * @param {Object} filters - Filter criteria
     * @param {string} [filters.q] - Text search query (case-insensitive)
     * @param {Array<number>} [filters.genres] - Genre IDs to filter by
     * @param {string} [filters.genreOption] - 'any' or 'all' matching
     * @param {Array<number>} [filters.authors] - Author IDs to filter by
     * @param {number} [filters.start] - Minimum year
     * @param {number} [filters.end] - Maximum year
     * @param {string} [filters.sort] - Sort order: 'rank', 'year', 'name', 'pages'
     * @param {string} [filters.read] - 'yes', 'want', 'no', or '' for read status filter
     * @returns {Object} Result with filtered books and facet counts
     */
    filter(filters = {}) {
        // Ensure lazy indexes are built on first filter call
        this._ensureGenreMap();

        const {
            q = '',
            genres = [],
            genreOption = 'any',
            authors = [],
            start = null,
            end = null,
            sort = 'rank',
            sortDirection = 'asc',
            read = ''
        } = filters;

        const normalizedQuery = q.toLowerCase().trim();
        const genreIds = genres.map(id => parseInt(id, 10)).filter(id => !isNaN(id));
        const authorIds = authors.map(id => parseInt(id, 10)).filter(id => !isNaN(id));
        const authorSet = new Set(authorIds);
        const matchAll = genreOption !== 'any';

        // Pre-compute expanded genre sets for each selected genre
        const expandedGenreSets = genreIds.map(id => this._genreDescendants.get(id) || new Set([id]));

        let results = [];

        for (const book of this.books) {
            // Text search filter (searches name and author names)
            if (normalizedQuery) {
                const nameMatch = book.n.toLowerCase().includes(normalizedQuery);
                // Also search author names
                let authorMatch = false;
                if (book.au) {
                    for (const authorId of book.au) {
                        const author = this.authors[authorId];
                        if (author && author.n.toLowerCase().includes(normalizedQuery)) {
                            authorMatch = true;
                            break;
                        }
                    }
                }
                if (!nameMatch && !authorMatch) {
                    continue;
                }
            }

            // Year range filter
            if (start !== null && book.y !== null && book.y < start) {
                continue;
            }
            if (end !== null && book.y !== null && book.y > end) {
                continue;
            }

            // Author filter (any match)
            if (authorIds.length > 0) {
                const bookAuthors = book.au || [];
                const hasMatchingAuthor = bookAuthors.some(aid => authorSet.has(aid));
                if (!hasMatchingAuthor) {
                    continue;
                }
            }

            // Genre filter with hierarchy expansion
            if (genreIds.length > 0) {
                const bookGenreSet = new Set(book.g || []);

                if (matchAll) {
                    // Match All: book must have at least one genre from EACH expanded group
                    let matchesAll = true;
                    for (const expandedSet of expandedGenreSets) {
                        let hasMatch = false;
                        for (const gid of bookGenreSet) {
                            if (expandedSet.has(gid)) {
                                hasMatch = true;
                                break;
                            }
                        }
                        if (!hasMatch) {
                            matchesAll = false;
                            break;
                        }
                    }
                    if (!matchesAll) {
                        continue;
                    }
                } else {
                    // Match Any: book must have at least one genre from ANY expanded group
                    let hasAnyMatch = false;
                    for (const expandedSet of expandedGenreSets) {
                        for (const gid of bookGenreSet) {
                            if (expandedSet.has(gid)) {
                                hasAnyMatch = true;
                                break;
                            }
                        }
                        if (hasAnyMatch) break;
                    }
                    if (!hasAnyMatch) {
                        continue;
                    }
                }
            }

            // Read status filter (requires window.readBookIds, window.wantToReadBookIds, window.isAuthenticated)
            if (read && window.isAuthenticated && book.i) {
                const isBookRead = window.readBookIds && window.readBookIds.has(book.i);
                const isBookWantToRead = window.wantToReadBookIds && window.wantToReadBookIds.has(book.i);

                if (read === 'yes' && !isBookRead) {
                    continue;
                }
                if (read === 'want' && !isBookWantToRead) {
                    continue;
                }
                if (read === 'no' && (isBookRead || isBookWantToRead)) {
                    continue;
                }
            }

            results.push(book);
        }

        // Sort results
        results = this._sortBooks(results, sort, sortDirection);

        // Calculate faceted counts
        const facets = this._calculateFacets(filters);

        // Add rank distribution of filtered results
        facets.rankDistribution = this.getRankDistribution(results);

        return {
            books: results,
            total: results.length,
            facets
        };
    }

    /**
     * Sort books by specified criteria
     * @private
     */
    _sortBooks(books, sort, direction = 'asc') {
        const sortedBooks = [...books];
        const isDesc = direction === 'desc';

        switch (sort) {
            case 'rank':
                sortedBooks.sort((a, b) => {
                    const diff = a.r - b.r;
                    return isDesc ? -diff : diff;
                });
                break;

            case 'year':
                sortedBooks.sort((a, b) => {
                    const yearDiff = (a.y || 0) - (b.y || 0);
                    if (yearDiff !== 0) return isDesc ? -yearDiff : yearDiff;
                    return a.r - b.r;  // Secondary sort by rank (always ascending)
                });
                break;

            case 'name':
                sortedBooks.sort((a, b) => {
                    const nameComp = a.n.localeCompare(b.n);
                    return isDesc ? -nameComp : nameComp;
                });
                break;

            case 'pages':
                // Filter out books without page count
                const booksWithPages = sortedBooks.filter(book => book.pc !== null && book.pc !== undefined);

                booksWithPages.sort((a, b) => {
                    const diff = a.pc - b.pc;
                    return isDesc ? -diff : diff;
                });

                return booksWithPages;

            default:
                sortedBooks.sort((a, b) => a.r - b.r);
                break;
        }

        return sortedBooks;
    }

    /**
     * Calculate faceted counts for genres, authors, and years
     * @private
     */
    _calculateFacets(currentFilters) {
        const genreCounts = new Map();
        const authorCounts = new Map();
        const yearCounts = new Map();

        const { q, start, end, authors, genres, genreOption, read } = currentFilters;
        const matchAll = genreOption !== 'any';

        // Create base filter functions (without genre/author)
        const passesBaseFilters = (book) => {
            const normalizedQuery = (q || '').toLowerCase().trim();
            if (normalizedQuery) {
                const nameMatch = book.n.toLowerCase().includes(normalizedQuery);
                let authorMatch = false;
                if (book.au) {
                    for (const authorId of book.au) {
                        const author = this.authors[authorId];
                        if (author && author.n.toLowerCase().includes(normalizedQuery)) {
                            authorMatch = true;
                            break;
                        }
                    }
                }
                if (!nameMatch && !authorMatch) return false;
            }
            if (start !== null && book.y !== null && book.y < start) {
                return false;
            }
            if (end !== null && book.y !== null && book.y > end) {
                return false;
            }
            // Read status filter
            if (read && window.isAuthenticated && book.i) {
                const isBookRead = window.readBookIds && window.readBookIds.has(book.i);
                const isBookWantToRead = window.wantToReadBookIds && window.wantToReadBookIds.has(book.i);
                if (read === 'yes' && !isBookRead) return false;
                if (read === 'want' && !isBookWantToRead) return false;
                if (read === 'no' && (isBookRead || isBookWantToRead)) return false;
            }
            return true;
        };

        // Calculate genre facet counts (apply all filters except genre)
        const authorIds = (authors || []).map(id => parseInt(id, 10)).filter(id => !isNaN(id));
        const authorSet = new Set(authorIds);

        for (const book of this.books) {
            if (!passesBaseFilters(book)) continue;

            // Apply author filter
            if (authorSet.size > 0) {
                const bookAuthors = book.au || [];
                if (!bookAuthors.some(aid => authorSet.has(aid))) continue;
            }

            // For Match All mode with existing selections, only count genres on matching books
            if (matchAll && genres && genres.length > 0) {
                const genreIds = genres.map(id => parseInt(id, 10));
                const expandedGenreSets = genreIds.map(id => this._genreDescendants.get(id) || new Set([id]));
                const bookGenreSet = new Set(book.g || []);

                let matchesAll = true;
                for (const expandedSet of expandedGenreSets) {
                    let hasMatch = false;
                    for (const gid of bookGenreSet) {
                        if (expandedSet.has(gid)) {
                            hasMatch = true;
                            break;
                        }
                    }
                    if (!hasMatch) {
                        matchesAll = false;
                        break;
                    }
                }
                if (!matchesAll) continue;
            }

            // Count genres for this book
            const bookGenres = book.g || [];
            for (const gid of bookGenres) {
                genreCounts.set(gid, (genreCounts.get(gid) || 0) + 1);
            }
        }

        // Calculate author facet counts (apply all filters except author)
        const genreIds = (genres || []).map(id => parseInt(id, 10)).filter(id => !isNaN(id));
        const expandedGenreSets = genreIds.map(id => this._genreDescendants.get(id) || new Set([id]));

        for (const book of this.books) {
            if (!passesBaseFilters(book)) continue;

            // Apply genre filter
            if (genreIds.length > 0) {
                const bookGenreSet = new Set(book.g || []);
                if (matchAll) {
                    let matchesAll = true;
                    for (const expandedSet of expandedGenreSets) {
                        let hasMatch = false;
                        for (const gid of bookGenreSet) {
                            if (expandedSet.has(gid)) {
                                hasMatch = true;
                                break;
                            }
                        }
                        if (!hasMatch) {
                            matchesAll = false;
                            break;
                        }
                    }
                    if (!matchesAll) continue;
                } else {
                    let hasAnyMatch = false;
                    for (const expandedSet of expandedGenreSets) {
                        for (const gid of bookGenreSet) {
                            if (expandedSet.has(gid)) {
                                hasAnyMatch = true;
                                break;
                            }
                        }
                        if (hasAnyMatch) break;
                    }
                    if (!hasAnyMatch) continue;
                }
            }

            // Count authors for this book (author filter NOT applied)
            const bookAuthors = book.au || [];
            for (const aid of bookAuthors) {
                authorCounts.set(aid, (authorCounts.get(aid) || 0) + 1);
            }
        }

        // Calculate year counts (apply all filters EXCEPT year filters)
        for (const book of this.books) {
            // Apply search filter only (no year filter)
            const normalizedQuery = (q || '').toLowerCase().trim();
            if (normalizedQuery) {
                const nameMatch = book.n.toLowerCase().includes(normalizedQuery);
                let authorMatch = false;
                if (book.au) {
                    for (const authorId of book.au) {
                        const author = this.authors[authorId];
                        if (author && author.n.toLowerCase().includes(normalizedQuery)) {
                            authorMatch = true;
                            break;
                        }
                    }
                }
                if (!nameMatch && !authorMatch) continue;
            }

            // Apply author filter
            if (authorSet.size > 0) {
                const bookAuthors = book.au || [];
                if (!bookAuthors.some(aid => authorSet.has(aid))) continue;
            }

            // Apply genre filter
            if (genreIds.length > 0) {
                const bookGenreSet = new Set(book.g || []);
                if (matchAll) {
                    let matchesAll = true;
                    for (const expandedSet of expandedGenreSets) {
                        let hasMatch = false;
                        for (const gid of bookGenreSet) {
                            if (expandedSet.has(gid)) {
                                hasMatch = true;
                                break;
                            }
                        }
                        if (!hasMatch) {
                            matchesAll = false;
                            break;
                        }
                    }
                    if (!matchesAll) continue;
                } else {
                    let hasAnyMatch = false;
                    for (const expandedSet of expandedGenreSets) {
                        for (const gid of bookGenreSet) {
                            if (expandedSet.has(gid)) {
                                hasAnyMatch = true;
                                break;
                            }
                        }
                        if (hasAnyMatch) break;
                    }
                    if (!hasAnyMatch) continue;
                }
            }

            // Apply read status filter
            if (read && window.isAuthenticated && book.i) {
                const isBookRead = window.readBookIds && window.readBookIds.has(book.i);
                const isBookWantToRead = window.wantToReadBookIds && window.wantToReadBookIds.has(book.i);
                if (read === 'yes' && !isBookRead) continue;
                if (read === 'want' && !isBookWantToRead) continue;
                if (read === 'no' && (isBookRead || isBookWantToRead)) continue;
            }

            // Count this book's year
            if (book.y !== null) {
                yearCounts.set(book.y, (yearCounts.get(book.y) || 0) + 1);
            }
        }

        return {
            genres: Object.fromEntries(genreCounts),
            authors: Object.fromEntries(authorCounts),
            years: Object.fromEntries(yearCounts)
        };
    }

    /**
     * Get expanded book data with resolved references
     * @param {Object} book - Compact book object
     * @returns {Object} Expanded book with full author/genre info
     */
    expandBook(book) {
        // Ensure lazy indexes are built
        this._ensureGenreMap();

        // Resolve authors with parent info
        const authorList = (book.au || []).map(authorId => {
            const author = this.authors[authorId];
            if (!author) return null;

            // Find root author (for URL slug)
            let rootAuthor = author;
            let currentId = authorId;
            while (rootAuthor && rootAuthor.pa) {
                const parent = this.authors[rootAuthor.pa];
                if (!parent) break;
                rootAuthor = parent;
                currentId = rootAuthor.pa;
            }

            return {
                id: authorId,
                name: author.n,
                slug: author.s || null,
                parentId: author.pa || null,
                root: rootAuthor ? {
                    id: currentId,
                    name: rootAuthor.n,
                    slug: rootAuthor.s
                } : null
            };
        }).filter(Boolean);

        // Filter out ancestor authors
        const ancestorIds = new Set();
        for (const author of authorList) {
            let currentAuthor = this.authors[author.id];
            while (currentAuthor && currentAuthor.pa) {
                ancestorIds.add(currentAuthor.pa);
                currentAuthor = this.authors[currentAuthor.pa];
            }
        }
        const filteredAuthorList = authorList.filter(a => !ancestorIds.has(a.id));

        // Resolve genres
        const genreList = (book.g || []).map(gid => {
            const genre = this._genreMap.get(gid);
            return genre ? {
                id: gid,
                name: genre.n,
                slug: genre.s
            } : null;
        }).filter(Boolean);

        return {
            id: book.id,
            name: book.n,
            slug: book.s,
            rank: book.r,
            year: book.y,
            coverUrl: book.c,
            pageCount: book.pc,
            authors: filteredAuthorList,
            genres: genreList
        };
    }

    /**
     * Get year bounds from the dataset
     * @returns {Object} {min, max} year values
     */
    getYearBounds() {
        let min = Infinity;
        let max = -Infinity;

        for (const book of this.books) {
            if (book.y !== null) {
                if (book.y < min) min = book.y;
                if (book.y > max) max = book.y;
            }
        }

        return {
            min: min === Infinity ? 1800 : min,
            max: max === -Infinity ? new Date().getFullYear() : max
        };
    }

    /**
     * Get unfiltered year counts for all books
     * @returns {Object} Map of year -> count
     */
    getUnfilteredYearCounts() {
        const yearCounts = new Map();

        for (const book of this.books) {
            if (book.y !== null) {
                yearCounts.set(book.y, (yearCounts.get(book.y) || 0) + 1);
            }
        }

        return Object.fromEntries(yearCounts);
    }

    /**
     * Calculate rank distribution bins from an array of books
     * @param {Array} books - Array of book objects with rank (r) property
     * @param {number} binCount - Number of bins (default 10)
     * @returns {Array} Array of {binStart, binEnd, count} objects
     */
    getRankDistribution(books, binCount = 10) {
        const maxRank = 1000;
        const binSize = Math.ceil(maxRank / binCount);
        const bins = [];

        // Initialize bins
        for (let i = 0; i < binCount; i++) {
            bins.push({
                binStart: i * binSize + 1,
                binEnd: Math.min((i + 1) * binSize, maxRank),
                count: 0
            });
        }

        // Count books per bin
        for (const book of books) {
            if (book.r && book.r >= 1 && book.r <= maxRank) {
                const binIndex = Math.floor((book.r - 1) / binSize);
                if (binIndex >= 0 && binIndex < binCount) {
                    bins[binIndex].count++;
                }
            }
        }

        return bins;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.BookFilterEngine = BookFilterEngine;
}
