/**
 * Acclaimed Games - Client-Side Filter Engine
 *
 * Replicates server-side filtering logic for client-side filtering.
 * Supports text search, genre hierarchy, platform filtering, year range, and sorting.
 */

/**
 * Platform hierarchy for deduplicated group counting
 * Maps manufacturer/form factor keys to platform codes
 */
const PLATFORM_HIERARCHY = {
    nintendo: {
        name: 'Nintendo',
        codes: ['NES', 'SNES', 'N64', 'GC', 'Wii', 'WiiU', 'DS', '3DS', 'SW', 'GB', 'GBA', 'GBC', 'FDS'],
        formFactors: {
            home: { name: 'Home Consoles', codes: ['NES', 'FDS', 'SNES', 'N64', 'GC', 'Wii', 'WiiU', 'SW'] },
            handheld: { name: 'Handhelds', codes: ['GB', 'GBC', 'GBA', 'DS', '3DS'] }
        }
    },
    playstation: {
        name: 'PlayStation',
        codes: ['PS', 'PS2', 'PS3', 'PS4', 'PS5', 'PSP', 'PSV', 'PSVR'],
        formFactors: {
            home: { name: 'Home Consoles', codes: ['PS', 'PS2', 'PS3', 'PS4', 'PS5', 'PSVR'] },
            handheld: { name: 'Handhelds', codes: ['PSP', 'PSV'] }
        }
    },
    xbox: {
        name: 'Xbox',
        codes: ['Xbox', 'X360', 'XB1', 'XBXS']
    },
    sega: {
        name: 'Sega',
        codes: ['GEN', 'SMS', 'DC', 'SAT', 'GG', 'SCD'],
        formFactors: {
            home: { name: 'Home Consoles', codes: ['SMS', 'GEN', 'SCD', 'SAT', 'DC'] },
            handheld: { name: 'Handhelds', codes: ['GG'] }
        }
    },
    pc: {
        name: 'PC',
        codes: ['WIN', 'DOS', 'LIN', 'MAC']
    },
    arcadePlus: {
        name: 'Arcade+',
        codes: ['ARC', 'AND', 'iOS', 'LMD', 'VR', 'BR']
    },
    retro: {
        name: 'Retro Consoles',
        codes: ['A26', 'A52', 'A78', 'INTV', 'CV', 'TG16', '3DO', 'NG', 'JAG', 'LYNX', 'NGP', 'WS']
    },
    computers: {
        name: 'Microcomputers',
        codes: ['C64', 'AMI', 'CD32', 'MSX', 'CPC', 'ZXS', 'AST', 'BBCM', 'PC88', 'PC98', 'FMT', 'FM7', 'SX1', 'T80', 'TCC', 'VC20', 'A8', 'A2']
    }
};

/**
 * GameFilterEngine - Client-side game filtering
 *
 * Usage:
 *   const engine = new GameFilterEngine(gameData);
 *   const results = engine.filter({
 *     q: 'zelda',
 *     genres: [1, 2],
 *     genreOption: 'any',
 *     platforms: [5, 10],
 *     start: 1990,
 *     end: 2000,
 *     sort: 'rank'
 *   });
 */
class GameFilterEngine {
    /**
     * @param {Object} data - Game data from API
     * @param {Array} data.games - Game objects with id, n, s, r, y, a, st, p, g
     * @param {Object} data.studios - Studio lookup by ID {n: name, c: companyId}
     * @param {Object} data.companies - Company lookup by ID {n: name, s: slug}
     * @param {Object} data.platforms - Platform lookup by ID {n: name, c: code}
     * @param {Array} data.genres - Genre objects with id, n, s, p, l, d (descendants)
     */
    constructor(data) {
        this.games = data.games || [];
        this.studios = data.studios || {};
        this.companies = data.companies || {};
        this.platforms = data.platforms || {};
        this.genres = data.genres || [];

        // Build genre lookup and descendant sets for fast filtering
        this._genreMap = new Map();
        this._genreDescendants = new Map();
        for (const genre of this.genres) {
            this._genreMap.set(genre.id, genre);
            // Store descendants as Set for O(1) lookup
            const descendantSet = new Set(genre.d || []);
            descendantSet.add(genre.id); // Include self for matching
            this._genreDescendants.set(genre.id, descendantSet);
        }

        // Build platform ID to group mapping for deduplicated group counts
        // Maps platform ID -> { manufacturer: 'nintendo', formFactor: 'home' }
        this._platformToGroups = new Map();
        this._buildPlatformGroupMapping();
    }

    /**
     * Build mapping from platform IDs to their manufacturer/form factor groups
     * @private
     */
    _buildPlatformGroupMapping() {
        // Build code -> ID lookup from platforms
        const codeToId = new Map();
        for (const [id, platform] of Object.entries(this.platforms)) {
            if (platform.c) {
                codeToId.set(platform.c, parseInt(id, 10));
            }
        }

        // Map each platform ID to its groups
        for (const [mfrKey, mfrData] of Object.entries(PLATFORM_HIERARCHY)) {
            // Map manufacturer-level platforms
            for (const code of mfrData.codes) {
                const platformId = codeToId.get(code);
                if (platformId !== undefined) {
                    if (!this._platformToGroups.has(platformId)) {
                        this._platformToGroups.set(platformId, { manufacturer: mfrKey });
                    }
                }
            }

            // Map form factor-level platforms
            if (mfrData.formFactors) {
                for (const [ffKey, ffData] of Object.entries(mfrData.formFactors)) {
                    for (const code of ffData.codes) {
                        const platformId = codeToId.get(code);
                        if (platformId !== undefined) {
                            const existing = this._platformToGroups.get(platformId) || {};
                            this._platformToGroups.set(platformId, {
                                ...existing,
                                manufacturer: mfrKey,
                                formFactor: ffKey
                            });
                        }
                    }
                }
            }
        }
    }

    /**
     * Filter games based on criteria
     *
     * @param {Object} filters - Filter criteria
     * @param {string} [filters.q] - Text search query (case-insensitive)
     * @param {Array<number>} [filters.genres] - Genre IDs to filter by
     * @param {string} [filters.genreOption] - 'any' or 'all' matching
     * @param {Array<number>} [filters.platforms] - Platform IDs to filter by
     * @param {number} [filters.start] - Minimum year
     * @param {number} [filters.end] - Maximum year
     * @param {string} [filters.sort] - Sort order: 'rank', 'year', 'name'
     * @returns {Object} Result with filtered games and facet counts
     */
    filter(filters = {}) {
        const {
            q = '',
            genres = [],
            genreOption = 'any',
            platforms = [],
            start = null,
            end = null,
            sort = 'rank'
        } = filters;

        const normalizedQuery = q.toLowerCase().trim();
        const genreIds = genres.map(id => parseInt(id, 10)).filter(id => !isNaN(id));
        const platformIds = platforms.map(id => parseInt(id, 10)).filter(id => !isNaN(id));
        const platformSet = new Set(platformIds);
        const matchAll = genreOption !== 'any';

        // Pre-compute expanded genre sets for each selected genre
        const expandedGenreSets = genreIds.map(id => this._genreDescendants.get(id) || new Set([id]));

        let results = [];

        for (const game of this.games) {
            // Text search filter
            if (normalizedQuery && !game.n.toLowerCase().includes(normalizedQuery)) {
                continue;
            }

            // Year range filter
            if (start !== null && game.y !== null && game.y < start) {
                continue;
            }
            if (end !== null && game.y !== null && game.y > end) {
                continue;
            }

            // Platform filter (any match)
            if (platformIds.length > 0) {
                const hasMatchingPlatform = game.p.some(pid => platformSet.has(pid));
                if (!hasMatchingPlatform) {
                    continue;
                }
            }

            // Genre filter with hierarchy expansion
            if (genreIds.length > 0) {
                const gameGenreSet = new Set(game.g);

                if (matchAll) {
                    // Match All: game must have at least one genre from EACH expanded group
                    let matchesAll = true;
                    for (const expandedSet of expandedGenreSets) {
                        let hasMatch = false;
                        for (const gid of gameGenreSet) {
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
                    // Match Any: game must have at least one genre from ANY expanded group
                    let hasAnyMatch = false;
                    for (const expandedSet of expandedGenreSets) {
                        for (const gid of gameGenreSet) {
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

            results.push(game);
        }

        // Sort results
        results = this._sortGames(results, sort);

        // Calculate faceted counts
        const facets = this._calculateFacets(filters);

        return {
            games: results,
            total: results.length,
            facets
        };
    }

    /**
     * Sort games by specified criteria
     * @private
     */
    _sortGames(games, sort) {
        const sortedGames = [...games];

        switch (sort) {
            case 'year':
                sortedGames.sort((a, b) => {
                    // Sort by year ascending, then by rank
                    const yearDiff = (a.y || 0) - (b.y || 0);
                    if (yearDiff !== 0) return yearDiff;
                    return a.r - b.r;
                });
                break;
            case 'name':
                sortedGames.sort((a, b) => a.n.localeCompare(b.n));
                break;
            case 'rank':
            default:
                sortedGames.sort((a, b) => a.r - b.r);
                break;
        }

        return sortedGames;
    }

    /**
     * Calculate faceted counts for genres, platforms, and years
     * @private
     */
    _calculateFacets(currentFilters) {
        const genreCounts = new Map();
        const platformCounts = new Map();
        const yearCounts = new Map();

        // For genre facets, we need to calculate counts based on filters EXCLUDING genres
        // For platform facets, calculate counts based on filters EXCLUDING platforms
        // This is standard faceted search behavior

        const { q, start, end, platforms, genres, genreOption } = currentFilters;
        const matchAll = genreOption !== 'any';

        // Create base filter functions (without genre/platform)
        const passesBaseFilters = (game) => {
            const normalizedQuery = (q || '').toLowerCase().trim();
            if (normalizedQuery && !game.n.toLowerCase().includes(normalizedQuery)) {
                return false;
            }
            if (start !== null && game.y !== null && game.y < start) {
                return false;
            }
            if (end !== null && game.y !== null && game.y > end) {
                return false;
            }
            return true;
        };

        // Calculate genre facet counts (apply all filters except genre)
        const platformSet = new Set((platforms || []).map(id => parseInt(id, 10)));
        for (const game of this.games) {
            if (!passesBaseFilters(game)) continue;

            // Apply platform filter
            if (platformSet.size > 0) {
                if (!game.p.some(pid => platformSet.has(pid))) continue;
            }

            // For Match All mode with existing selections, only count genres on matching games
            if (matchAll && genres && genres.length > 0) {
                const genreIds = genres.map(id => parseInt(id, 10));
                const expandedGenreSets = genreIds.map(id => this._genreDescendants.get(id) || new Set([id]));
                const gameGenreSet = new Set(game.g);

                let matchesAll = true;
                for (const expandedSet of expandedGenreSets) {
                    let hasMatch = false;
                    for (const gid of gameGenreSet) {
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

            // Count genres for this game
            for (const gid of game.g) {
                genreCounts.set(gid, (genreCounts.get(gid) || 0) + 1);
            }
        }

        // Calculate platform facet counts (apply all filters except platform)
        const genreIds = (genres || []).map(id => parseInt(id, 10)).filter(id => !isNaN(id));
        const expandedGenreSets = genreIds.map(id => this._genreDescendants.get(id) || new Set([id]));

        // Track unique games per manufacturer and form factor for deduplicated counts
        const manufacturerGameSets = new Map();  // mfrKey -> Set of game IDs
        const formFactorGameSets = new Map();     // 'mfrKey_ffKey' -> Set of game IDs

        for (const game of this.games) {
            if (!passesBaseFilters(game)) continue;

            // Apply genre filter
            if (genreIds.length > 0) {
                const gameGenreSet = new Set(game.g);
                if (matchAll) {
                    let matchesAll = true;
                    for (const expandedSet of expandedGenreSets) {
                        let hasMatch = false;
                        for (const gid of gameGenreSet) {
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
                        for (const gid of gameGenreSet) {
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

            // Count platforms for this game and track group membership
            for (const pid of game.p) {
                platformCounts.set(pid, (platformCounts.get(pid) || 0) + 1);

                // Track game for manufacturer/form factor group counts
                const groupInfo = this._platformToGroups.get(pid);
                if (groupInfo) {
                    // Add to manufacturer set
                    if (!manufacturerGameSets.has(groupInfo.manufacturer)) {
                        manufacturerGameSets.set(groupInfo.manufacturer, new Set());
                    }
                    manufacturerGameSets.get(groupInfo.manufacturer).add(game.id);

                    // Add to form factor set if applicable
                    if (groupInfo.formFactor) {
                        const ffKey = `${groupInfo.manufacturer}_${groupInfo.formFactor}`;
                        if (!formFactorGameSets.has(ffKey)) {
                            formFactorGameSets.set(ffKey, new Set());
                        }
                        formFactorGameSets.get(ffKey).add(game.id);
                    }
                }
            }
        }

        // Build platform group counts from the sets
        const platformGroupCounts = {};
        for (const [mfrKey, gameSet] of manufacturerGameSets) {
            platformGroupCounts[mfrKey] = {
                count: gameSet.size,
                formFactors: {}
            };
        }
        for (const [ffFullKey, gameSet] of formFactorGameSets) {
            const [mfrKey, ffKey] = ffFullKey.split('_');
            if (platformGroupCounts[mfrKey]) {
                platformGroupCounts[mfrKey].formFactors[ffKey] = gameSet.size;
            }
        }

        // Calculate year counts (apply all filters EXCEPT year filters)
        // This allows the heatmap to show which years have games given other filters
        for (const game of this.games) {
            // Apply search filter only (no year filter)
            const normalizedQuery = (q || '').toLowerCase().trim();
            if (normalizedQuery && !game.n.toLowerCase().includes(normalizedQuery)) {
                continue;
            }

            // Apply platform filter
            if (platformSet.size > 0) {
                if (!game.p.some(pid => platformSet.has(pid))) continue;
            }

            // Apply genre filter
            if (genreIds.length > 0) {
                const gameGenreSet = new Set(game.g);
                if (matchAll) {
                    let matchesAll = true;
                    for (const expandedSet of expandedGenreSets) {
                        let hasMatch = false;
                        for (const gid of gameGenreSet) {
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
                        for (const gid of gameGenreSet) {
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

            // Count this game's year
            if (game.y !== null) {
                yearCounts.set(game.y, (yearCounts.get(game.y) || 0) + 1);
            }
        }

        return {
            genres: Object.fromEntries(genreCounts),
            platforms: Object.fromEntries(platformCounts),
            platformGroups: platformGroupCounts,
            years: Object.fromEntries(yearCounts)
        };
    }

    /**
     * Get expanded game data with resolved references
     * @param {Object} game - Compact game object
     * @returns {Object} Expanded game with full studio/platform/genre info
     */
    expandGame(game) {
        // Resolve studios with company info
        const studios = game.st.map(sid => {
            const studio = this.studios[sid];
            if (!studio) return null;
            const company = studio.c ? this.companies[studio.c] : null;
            return {
                id: sid,
                name: studio.n,
                company: company ? {
                    id: studio.c,
                    name: company.n,
                    slug: company.s
                } : null
            };
        }).filter(Boolean);

        // Resolve platforms
        const platformList = game.p.map(pid => {
            const platform = this.platforms[pid];
            return platform ? {
                id: pid,
                name: platform.n,
                code: platform.c
            } : null;
        }).filter(Boolean);

        // Resolve genres
        const genreList = game.g.map(gid => {
            const genre = this._genreMap.get(gid);
            return genre ? {
                id: gid,
                name: genre.n,
                slug: genre.s
            } : null;
        }).filter(Boolean);

        return {
            id: game.id,
            name: game.n,
            slug: game.s,
            rank: game.r,
            year: game.y,
            artworkId: game.a,
            studios,
            platforms: platformList,
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

        for (const game of this.games) {
            if (game.y !== null) {
                if (game.y < min) min = game.y;
                if (game.y > max) max = game.y;
            }
        }

        return {
            min: min === Infinity ? 1970 : min,
            max: max === -Infinity ? new Date().getFullYear() : max
        };
    }

    /**
     * Get year ranges for each platform based on actual game data
     * @returns {Object} Map of platformId -> { start: minYear, end: maxYear }
     */
    getPlatformYearRanges() {
        const ranges = {};

        for (const game of this.games) {
            if (game.y === null) continue;

            for (const pid of game.p) {
                if (!ranges[pid]) {
                    ranges[pid] = { start: game.y, end: game.y };
                } else {
                    if (game.y < ranges[pid].start) ranges[pid].start = game.y;
                    if (game.y > ranges[pid].end) ranges[pid].end = game.y;
                }
            }
        }

        return ranges;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.GameFilterEngine = GameFilterEngine;
}
