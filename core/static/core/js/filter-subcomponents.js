/**
 * Shared filter sidebar components.
 *
 * The year heatmap grid and the hierarchical genre tree, as Alpine
 * components. They started life in games/js/filter-subcomponents.js and were
 * moved here unchanged when the album rankings page adopted them: a copy
 * would have drifted, and the album page previously made do with a row of
 * decade chips and a flat <select> that could not tell a root genre from one
 * of its styles.
 *
 * Neither component knows what it is counting. Each takes:
 *   filters  - the page's filter state, with .start/.end or .genres
 *   genres   - [{id, name, level, parent_id, item_count|game_count,
 *                filtered_count}]
 *   minYear / maxYear, and callbacks for requesting an update
 * and reads live counts from `year-counts-update` / `genre-counts-update`
 * events, so facet counts shrink as other filters narrow the results.
 *
 * Registered as `yearGridComponent`, `genreFilterComponent` and their mobile
 * equivalents. Load this before games/js/filter-subcomponents.js, which
 * registers the components that are genuinely about games - platforms,
 * series and playtime.
 */
(function () {
    "use strict";

    function readIconMap(elementId) {
        var el = elementId && document.getElementById(elementId);
        if (!el) {
            return null;
        }
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            return null;
        }
    }

    /**
     * The shape of a genre list, built once: position by id, child positions
     * by parent id, the roots, and each genre's descendant ids. A genre tree
     * never changes after the page renders - only its counts do - so none of
     * this needs to be reactive.
     *
     * Every lookup used to scan the page's reactive array (`genres.find`,
     * `genres.filter`, a recursive getChildren for descendants). A year
     * change re-evaluates every row's bindings, and each of those scans read
     * every genre through Alpine's proxy and subscribed to all of them, so a
     * single filter change cost hundreds of full scans. Reading `genres[i]`
     * through these positions tracks just the genre a binding shows.
     */
    function buildGenreIndex(genres) {
        var byId = indexBy(genres, function (g) {
            return String(g.id);
        });
        var childPositions = {};
        var rootPositions = [];
        (genres || []).forEach(function (g, i) {
            var parent = String(g.parent_id);
            (childPositions[parent] = childPositions[parent] || []).push(i);
            if (g.level === 0) {
                rootPositions.push(i);
            }
        });
        var descendants = {};
        function descendantIds(id, seen) {
            id = String(id);
            if (descendants[id]) {
                return descendants[id];
            }
            seen = seen || {};
            seen[id] = true;
            var ids = [];
            (childPositions[id] || []).forEach(function (i) {
                var childId = String(genres[i].id);
                if (seen[childId]) {
                    return; // a cycle in bad data; the scan it replaces would have recursed forever
                }
                ids.push(childId);
                ids = ids.concat(descendantIds(childId, seen));
            });
            descendants[id] = ids;
            return ids;
        }
        return {
            byId: byId,
            childPositions: childPositions,
            rootPositions: rootPositions,
            descendantIds: descendantIds,
        };
    }

    function createGenreFilterComponent(config) {
        var filters = config.filters;
        var genres = config.genres;
        var index = buildGenreIndex(genres);

        function genreById(genreId) {
            var i = index.byId[String(genreId)];
            return i === undefined ? undefined : genres[i];
        }

        function childrenOf(parentId) {
            return (index.childPositions[String(parentId)] || []).map(function (i) {
                return genres[i];
            });
        }
        // Each section's taxonomy has its own icons; the games ones are the
        // default because this component started there. The map arrives in a
        // JSON block rather than in the x-data attribute, whose double
        // quotes JSON would close.
        var categoryIcons = config.categoryIcons || readIconMap(config.categoryIconsElementId);
        var defaultIcon = config.defaultCategoryIcon || "mdi-gamepad-variant";
        // Whether a genre's count already covers its descendants. When it
        // does, adding the children's counts to a root's counts albums
        // tagged with both the root and one of its styles twice.
        var countsIncludeDescendants = Boolean(config.countsIncludeDescendants);

        return {
            _genreCountsHandler: null,
            countsReady: false,
            expandedCategories: {},
            categoryIcons: categoryIcons || {
                Shooter: "mdi-crosshairs",
                Action: "mdi-run-fast",
                Adventure: "mdi-image-filter-hdr",
                "Role-Playing": "mdi-wizard-hat",
                Strategy: "mdi-chess-knight",
                Simulation: "mdi-cog",
                "Racing & Sports": "mdi-car-sports",
                "Puzzle & Casual": "mdi-puzzle",
                Other: "mdi-layers",
            },

            init: function () {
                var self = this;
                this._genreCountsHandler = function (event) {
                    self.updateFilteredCounts(event.detail);
                    self.countsReady = true;
                };
                window.addEventListener("genre-counts-update", this._genreCountsHandler);
                this.loadExpandedState();
            },

            destroy: function () {
                if (this._genreCountsHandler) {
                    window.removeEventListener("genre-counts-update", this._genreCountsHandler);
                }
            },

            loadExpandedState: function () {
                try {
                    var saved = localStorage.getItem("genreCategoriesExpanded");
                    if (saved) {
                        this.expandedCategories = JSON.parse(saved);
                    }
                } catch (e) {
                    this.expandedCategories = {};
                }
            },

            saveExpandedState: function () {
                localStorage.setItem("genreCategoriesExpanded", JSON.stringify(this.expandedCategories));
            },

            toggleCategoryExpanded: function (categoryId) {
                this.expandedCategories[categoryId] = !this.expandedCategories[categoryId];
                this.saveExpandedState();
            },

            isCategoryExpanded: function (categoryId) {
                if (this.expandedCategories[categoryId] === undefined) {
                    return this.hasCategoryOrChildrenSelected(categoryId);
                }
                return this.expandedCategories[categoryId];
            },

            updateFilteredCounts: function (countMap) {
                genres.forEach(function (g) {
                    g.filtered_count = countMap[String(g.id)] || 0;
                });
            },

            get rootCategories() {
                var self = this;
                return index.rootPositions
                    .map(function (i) {
                        return genres[i];
                    })
                    .sort(function (a, b) {
                        return self.getCategoryTotalGameCount(b.id) - self.getCategoryTotalGameCount(a.id);
                    });
            },

            getCategoryTotalGameCount: function (categoryId) {
                var category = genreById(categoryId);
                var categoryCount = category ? this.getEffectiveCount(category) : 0;
                if (countsIncludeDescendants) {
                    return categoryCount;
                }
                var children = childrenOf(categoryId);
                var self = this;
                var childrenCount = children.reduce(function (sum, c) {
                    return sum + self.getEffectiveCount(c);
                }, 0);
                return categoryCount + childrenCount;
            },

            getChildren: function (parentId) {
                var self = this;
                return childrenOf(parentId).sort(function (a, b) {
                    return self.getEffectiveCount(b) - self.getEffectiveCount(a);
                });
            },

            getDescendantIds: function (genreId) {
                return index.descendantIds(genreId).slice();
            },

            isGenreAvailable: function (genreId) {
                var genre = genreById(genreId);
                if (!genre) {
                    return false;
                }
                var count = this.getEffectiveCount(genre);
                return count > 0 || this.isGenreSelected(genreId);
            },

            hasZeroResults: function (genreId) {
                var genre = genreById(genreId);
                if (!genre) {
                    return false;
                }
                var count = this.getEffectiveCount(genre);
                return count === 0 && this.isGenreSelected(genreId);
            },

            getEffectiveCount: function (genre) {
                if (genre.filtered_count !== undefined) {
                    return genre.filtered_count;
                }
                // `game_count` is what the games payload calls it; anything
                // else counts something other than games.
                return genre.item_count !== undefined ? genre.item_count : genre.game_count;
            },

            getCategoryTotalCount: function (categoryId) {
                var category = genreById(categoryId);
                var categoryCount = category ? this.getEffectiveCount(category) : 0;
                if (countsIncludeDescendants) {
                    return categoryCount;
                }
                var children = this.getChildren(categoryId);
                var self = this;
                var childrenCount = children.reduce(function (sum, c) {
                    return sum + self.getEffectiveCount(c);
                }, 0);
                return categoryCount + childrenCount;
            },

            isCategoryAvailable: function (categoryId) {
                var category = genreById(categoryId);
                if (category && this.getEffectiveCount(category) > 0) {
                    return true;
                }
                var children = this.getChildren(categoryId);
                var self = this;
                return children.some(function (c) {
                    return self.isGenreAvailable(c.id);
                });
            },

            isGenreSelected: function (genreId) {
                return filters.genres.includes(String(genreId));
            },

            isCategorySelected: function (categoryId) {
                return filters.genres.includes(String(categoryId));
            },

            hasSelectedChildren: function (categoryId) {
                var childIds = this.getDescendantIds(categoryId);
                return childIds.some(function (id) {
                    return filters.genres.includes(id);
                });
            },

            hasCategoryOrChildrenSelected: function (categoryId) {
                return this.isCategorySelected(categoryId) || this.hasSelectedChildren(categoryId);
            },

            allChildrenSelected: function (categoryId) {
                var self = this;
                var children = this.getChildren(categoryId).filter(function (c) {
                    return self.isGenreAvailable(c.id);
                });
                if (children.length === 0) {
                    return false;
                }
                return children.every(function (c) {
                    return filters.genres.includes(String(c.id));
                });
            },

            findGenreParent: function (genreId) {
                var genre = genreById(genreId);
                if (!genre || !genre.parent_id) {
                    return null;
                }
                return genreById(genre.parent_id);
            },

            toggleGenre: function (genreId) {
                var id = String(genreId);
                var genre = genreById(id);
                if (genre && genre.parent_id) {
                    var parentId = String(genre.parent_id);
                    if (filters.genres.includes(parentId)) {
                        filters.genres = filters.genres.filter(function (gid) {
                            return gid !== parentId;
                        });
                        if (!filters.genres.includes(id)) {
                            filters.genres.push(id);
                        }
                        this.dispatchFilterChange();
                        return;
                    }
                    if (this.allChildrenSelected(parentId)) {
                        var siblingIds = this.getChildren(parentId).map(function (c) {
                            return String(c.id);
                        });
                        filters.genres = filters.genres.filter(function (gid) {
                            return !siblingIds.includes(gid);
                        });
                        filters.genres.push(id);
                        this.dispatchFilterChange();
                        return;
                    }
                }
                var idx = filters.genres.indexOf(id);
                if (idx > -1) {
                    filters.genres.splice(idx, 1);
                } else {
                    filters.genres.push(id);
                }
                this.dispatchFilterChange();
            },

            toggleCategorySelection: function (categoryId) {
                var id = String(categoryId);
                if (this.expandedCategories[id] === undefined) {
                    this.expandedCategories[id] = this.hasCategoryOrChildrenSelected(id);
                }
                var idx = filters.genres.indexOf(id);
                if (idx > -1) {
                    filters.genres.splice(idx, 1);
                } else {
                    var descendantIds = this.getDescendantIds(categoryId);
                    filters.genres = filters.genres.filter(function (gid) {
                        return !descendantIds.includes(gid);
                    });
                    filters.genres.push(id);
                }
                this.dispatchFilterChange();
            },

            dispatchFilterChange: function () {
                var selectedItems = genres.filter(function (g) {
                    return filters.genres.includes(String(g.id));
                });
                this.$dispatch("filter-changed", { type: "genres", items: selectedItems });
            },

            getSelectedCount: function () {
                return filters.genres.length;
            },

            getCategoryIcon: function (name) {
                return this.categoryIcons[name] || defaultIcon;
            },

            handleReset: function () {
                this.expandedCategories = {};
                localStorage.removeItem("genreCategoriesExpanded");
            },

            areAllExpanded: function () {
                var categories = this.rootCategories;
                for (var i = 0; i < categories.length; i++) {
                    if (!this.expandedCategories[categories[i].id]) {
                        return false;
                    }
                }
                return true;
            },

            toggleAllExpanded: function () {
                var shouldExpand = !this.areAllExpanded();
                var categories = this.rootCategories;
                for (var i = 0; i < categories.length; i++) {
                    this.expandedCategories[categories[i].id] = shouldExpand;
                }
                this.saveExpandedState();
            },
        };
    }

    function createYearGridComponent(config) {
        var filters = config.filters;
        var minYear = config.minYear;
        var maxYear = config.maxYear;
        var requestFilterUpdate =
            typeof config.requestFilterUpdate === "function" ? config.requestFilterUpdate : function () {};
        var isApplyingSavedFilter =
            typeof config.isApplyingSavedFilter === "function" ? config.isApplyingSavedFilter : function () { return false; };

        return {
            yearCounts: [],
            originalYearCounts: [],
            maxCount: 0,
            originalMaxCount: 0,
            decades: [],
            dragStart: null,
            dragAnchorEnd: null,
            dragEnd: null,
            isDragging: false,
            isDraggingDecade: false,
            isDraggingToDecade: false,
            lastClicked: null,
            wasAlreadySelected: false,
            _yearCountsHandler: null,
            _yearOriginalCountsHandler: null,
            _yearSet: null,
            _minCount: 0,
            _decadeStructure: null,
            // The grid's one tab stop (a roving tabindex): a row (decade) and
            // a column, 0 for the decade label and 1-10 for its years. Until
            // the grid is focused it is the first decade's label.
            focusRow: 0,
            focusCol: 0,

            init: function () {
                var self = this;
                var dataEl = document.getElementById("year-counts-data");
                if (dataEl) {
                    this.yearCounts = JSON.parse(dataEl.textContent);
                    // The colour scale: the whole corpus when the page sends
                    // it, else the counts it rendered with - which, on a
                    // page loaded filtered, would scale every later count
                    // to that filter's.
                    var baselineEl = document.getElementById("year-baseline-counts-data");
                    this.originalYearCounts = baselineEl
                        ? JSON.parse(baselineEl.textContent)
                        : this.yearCounts.slice();
                    this._rebuildCaches();
                    this.maxCount = Math.max.apply(
                        null,
                        this.originalYearCounts.map(function (y) {
                            return y.count;
                        }).concat([1])
                    );
                    this.originalMaxCount = this.maxCount;
                    this.buildDecades();
                }

                var setupListeners = function () {
                    self._yearOriginalCountsHandler = function (event) {
                        if (!Array.isArray(event.detail) || event.detail.length === 0) {
                            return;
                        }
                        self.originalYearCounts = event.detail;
                        self._rebuildCaches();
                        self.originalMaxCount = Math.max.apply(
                            null,
                            event.detail.map(function (y) {
                                return y.count;
                            }).concat([1])
                        );
                        self.maxCount = self.originalMaxCount;
                    };
                    window.addEventListener("year-original-counts-update", self._yearOriginalCountsHandler);

                    self._yearCountsHandler = function (event) {
                        if (!Array.isArray(event.detail) || event.detail.length === 0) {
                            return;
                        }
                        if (event.detail.length !== self.originalYearCounts.length) {
                            var newCountMap = {};
                            event.detail.forEach(function (yc) {
                                if (yc && typeof yc.year === "number") {
                                    newCountMap[yc.year] = yc.count || 0;
                                }
                            });
                            self.yearCounts = self.originalYearCounts.map(function (yc) {
                                return {
                                    year: yc.year,
                                    count: newCountMap[yc.year] !== undefined ? newCountMap[yc.year] : 0,
                                };
                            });
                        } else {
                            self.yearCounts = event.detail;
                        }
                        self.maxCount = self.originalMaxCount;
                        self.buildDecades();
                    };
                    window.addEventListener("year-counts-update", self._yearCountsHandler);
                };

                // At once, not at idle time: adding two listeners costs
                // nothing, and a grid created late (the mobile sheet on first
                // open, a sidebar initialised when the window widens) is sent
                // its counts in the same tick and would miss them.
                setupListeners();
            },

            destroy: function () {
                if (this._yearCountsHandler) {
                    window.removeEventListener("year-counts-update", this._yearCountsHandler);
                }
                if (this._yearOriginalCountsHandler) {
                    window.removeEventListener("year-original-counts-update", this._yearOriginalCountsHandler);
                }
            },

            handleReset: function () {
                this.lastClicked = null;
            },

            _rebuildCaches: function () {
                var nonZero = this.originalYearCounts.filter(function (yc) {
                    return yc.count > 0;
                });
                this._minCount =
                    nonZero.length > 0
                        ? Math.min.apply(
                              null,
                              nonZero.map(function (yc) {
                                  return yc.count;
                              })
                          )
                        : 0;
                this._decadeStructure = null;
            },

            getMinCount: function () {
                return this._minCount;
            },

            buildDecades: function () {
                var self = this;
                var currentCountMap = {};
                this.yearCounts.forEach(function (yc) {
                    currentCountMap[yc.year] = yc.count;
                });

                if (this._decadeStructure) {
                    this.decades = this._decadeStructure.map(function (decade) {
                        return {
                            start: decade.start,
                            label: decade.label,
                            cells: decade.cells.map(function (cell) {
                                if (!cell.year) {
                                    return cell;
                                }
                                var currentCount = currentCountMap[cell.year] || 0;
                                return {
                                    year: cell.year,
                                    count: currentCount,
                                    originalCount: cell.originalCount,
                                    available: currentCount > 0,
                                };
                            }),
                        };
                    });
                    return;
                }

                var originalCountMap = {};
                this.originalYearCounts.forEach(function (yc) {
                    originalCountMap[yc.year] = yc.count;
                });

                var decadeMap = {};
                this.originalYearCounts.forEach(function (yc) {
                    var decadeStart = Math.floor(yc.year / 10) * 10;
                    if (!decadeMap[decadeStart]) {
                        decadeMap[decadeStart] = { maxOriginalPos: 0 };
                    }
                    var position = yc.year % 10;
                    decadeMap[decadeStart][position] = {
                        year: yc.year,
                        originalCount: yc.count || 0,
                    };
                    if (position > decadeMap[decadeStart].maxOriginalPos) {
                        decadeMap[decadeStart].maxOriginalPos = position;
                    }
                });

                var decadeStarts = Object.keys(decadeMap)
                    .map(Number)
                    .sort(function (a, b) {
                        return b - a;
                    });

                // Every year with a cell, so the zero-count years filled in
                // below too: a neighbouring tile bridges the gap to them
                var yearSet = new Set();
                this._decadeStructure = decadeStarts.map(function (ds) {
                    var maxPos = decadeMap[ds].maxOriginalPos || 0;
                    var cells = [];
                    for (var i = 0; i < 10; i++) {
                        if (i > maxPos) {
                            cells.push({ hidden: true });
                            continue;
                        }
                        yearSet.add(ds + i);
                        if (decadeMap[ds][i]) {
                            cells.push({
                                year: decadeMap[ds][i].year,
                                originalCount: decadeMap[ds][i].originalCount,
                            });
                        } else {
                            cells.push({
                                year: ds + i,
                                originalCount: 0,
                            });
                        }
                    }
                    return { start: ds, label: ds + "s", cells: cells };
                });

                this._yearSet = yearSet;

                this.decades = this._decadeStructure.map(function (decade) {
                    return {
                        start: decade.start,
                        label: decade.label,
                        cells: decade.cells.map(function (cell) {
                            if (!cell.year) {
                                return cell;
                            }
                            var currentCount = currentCountMap[cell.year] || 0;
                            return {
                                year: cell.year,
                                count: currentCount,
                                originalCount: cell.originalCount,
                                available: currentCount > 0,
                            };
                        }),
                    };
                });
            },

            isYearAvailable: function (year) {
                var yearData = this.yearCounts.find(function (yc) {
                    return yc.year === year;
                });
                return yearData && yearData.count > 0;
            },

            getOpacity: function (count) {
                if (count === 0) {
                    return "5%";
                }
                // Capped: a count above a stale baseline would otherwise give
                // an opacity over 100%, which the CSS rejects, drawing nothing.
                var normalized = Math.min(1, count / this.maxCount);
                var opacity = 0.2 + normalized * 0.8;
                return Math.round(opacity * 100) + "%";
            },

            getYearLabel: function (year) {
                return String(year).slice(-2);
            },

            isInRange: function (year) {
                if (this.isDragging) {
                    var min = Math.min(this.dragStart, this.dragAnchorEnd, this.dragEnd);
                    var max = Math.max(this.dragStart, this.dragAnchorEnd, this.dragEnd);
                    return year >= min && year <= max;
                }
                if (isApplyingSavedFilter()) {
                    return false;
                }
                if (filters.start === minYear && filters.end === maxYear) {
                    return false;
                }
                return year >= filters.start && year <= filters.end;
            },

            isDecadeSelected: function (decadeStart) {
                if (this.isDragging) {
                    return false;
                }
                if (isApplyingSavedFilter()) {
                    return false;
                }
                if (filters.start === minYear && filters.end === maxYear) {
                    return false;
                }
                var isDecadeAligned = filters.start % 10 === 0 && filters.end % 10 === 9;
                if (!isDecadeAligned) {
                    return false;
                }
                return decadeStart >= filters.start && decadeStart + 9 <= filters.end;
            },

            isDecadeInDragRange: function (decadeStart) {
                if (!this.isDragging || !this.isDraggingDecade) {
                    return false;
                }
                if (!this.isDraggingToDecade) {
                    return decadeStart === this.dragStart;
                }
                var min = Math.min(this.dragStart, this.dragEnd);
                var max = Math.max(this.dragStart, this.dragEnd);
                return decadeStart >= min && decadeStart <= max;
            },

            selectDecade: function (decadeStart, event) {
                if (event && event.shiftKey && this.lastClicked !== null) {
                    filters.start = Math.min(this.lastClicked, decadeStart);
                    filters.end = Math.max(this.lastClicked, decadeStart + 9);
                    requestFilterUpdate();
                } else if (this.wasAlreadySelected) {
                    filters.start = minYear;
                    filters.end = maxYear;
                    this.lastClicked = null;
                    this.wasAlreadySelected = false;
                    requestFilterUpdate();
                } else {
                    this.lastClicked = decadeStart;
                }
            },

            startDragDecade: function (decadeStart, event) {
                event.preventDefault();
                this.isDragging = true;
                this.isDraggingDecade = true;
                this.isDraggingToDecade = true;
                this.dragStart = decadeStart;
                this.dragAnchorEnd = decadeStart + 9;
                this.dragEnd = decadeStart + 9;
                this.wasAlreadySelected = filters.start === decadeStart && filters.end === decadeStart + 9;
                this.dispatchPreview();
            },

            updateDragDecade: function (decadeStart) {
                if (this.isDragging) {
                    this.isDraggingToDecade = true;
                    this.dragEnd = decadeStart < this.dragStart ? decadeStart : decadeStart + 9;
                    this.dispatchPreview();
                }
            },

            selectYear: function (year, event) {
                if (event && event.shiftKey && this.lastClicked !== null) {
                    filters.start = Math.min(this.lastClicked, year);
                    filters.end = Math.max(this.lastClicked, year);
                    requestFilterUpdate();
                } else if (this.wasAlreadySelected) {
                    filters.start = minYear;
                    filters.end = maxYear;
                    this.lastClicked = null;
                    this.wasAlreadySelected = false;
                    requestFilterUpdate();
                } else {
                    this.lastClicked = year;
                }
            },

            isTabStop: function (row, col) {
                return row === this.focusRow && col === this.focusCol;
            },

            /**
             * Keyboard use of the grid, which was mouse-only: arrows and
             * Home/End move between the decade labels and the years that
             * exist, Enter or Space selects, and Shift with either extends
             * the range from the last pick, as Shift+click does.
             */
            onGridKeydown: function (event) {
                var cell = event.target.closest("[data-col]");
                if (!cell) return;
                var row = parseInt(cell.dataset.row, 10);
                var col = parseInt(cell.dataset.col, 10);
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    var decade = this.decades[row];
                    if (col === 0) {
                        this.keySelectRange(decade.start, decade.start + 9, event);
                    } else {
                        var year = decade.cells[col - 1].year;
                        this.keySelectRange(year, year, event);
                    }
                    return;
                }
                var grid = event.currentTarget;
                var target = null;
                if (event.key === "Home" || event.key === "End") {
                    // Home: the row's decade label. End: its last year that
                    // exists, walking back past empty cells (the 2020s row
                    // stops at the current year)
                    event.preventDefault();
                    for (var c = event.key === "Home" ? 0 : 10; c >= 0 && !target; c--) {
                        target = grid.querySelector('[data-row="' + row + '"][data-col="' + c + '"]');
                    }
                    if (target) target.focus();
                    return;
                }
                var moves = {
                    ArrowLeft: [0, -1], ArrowRight: [0, 1],
                    ArrowUp: [-1, 0], ArrowDown: [1, 0]
                };
                var move = moves[event.key];
                if (!move) return;
                event.preventDefault();
                target = this._nextFocusable(grid, row, col, move[0], move[1]);
                if (target) target.focus();
            },

            /** The nearest focusable cell from (row, col) in a direction. */
            _nextFocusable: function (grid, row, col, rowStep, colStep) {
                var r = row + rowStep;
                var c = Math.max(0, Math.min(10, col + colStep));
                if (colStep !== 0 && rowStep === 0) {
                    // Along a row: walk on past empty cells
                    var step = colStep > 0 ? 1 : -1;
                    for (; c >= 0 && c <= 10; c += step) {
                        var found = grid.querySelector('[data-row="' + row + '"][data-col="' + c + '"]');
                        if (found) return found;
                    }
                    return null;
                }
                // Up or down: the same column, else that row's decade label
                for (; r >= 0 && r < this.decades.length; r += rowStep) {
                    var same = grid.querySelector('[data-row="' + r + '"][data-col="' + c + '"]');
                    if (same) return same;
                    var label = grid.querySelector('[data-row="' + r + '"][data-col="0"]');
                    if (label) return label;
                }
                return null;
            },

            /**
             * Select a year or decade from the keyboard. A mouse selection
             * is set by the drag (endDrag) and the click only settles it, so
             * the keyboard sets the range itself: picking the range that is
             * already the whole selection clears it, as a second click does.
             */
            keySelectRange: function (start, end, event) {
                if (event.shiftKey && this.lastClicked !== null) {
                    filters.start = Math.min(this.lastClicked, start);
                    filters.end = Math.max(this.lastClicked, end);
                } else if (filters.start === start && filters.end === end) {
                    filters.start = minYear;
                    filters.end = maxYear;
                    this.lastClicked = null;
                } else {
                    filters.start = start;
                    filters.end = end;
                    this.lastClicked = start;
                }
                requestFilterUpdate();
            },

            startDrag: function (year, event) {
                event.preventDefault();
                this.isDragging = true;
                this.dragStart = year;
                this.dragAnchorEnd = year;
                this.dragEnd = year;
                this.wasAlreadySelected = filters.start === year && filters.end === year;
                this.dispatchPreview();
            },

            updateDrag: function (year) {
                if (this.isDragging) {
                    this.isDraggingToDecade = false;
                    this.dragEnd = year;
                    this.dispatchPreview();
                }
            },

            endDrag: function () {
                if (this.isDragging) {
                    filters.start = Math.min(this.dragStart, this.dragAnchorEnd, this.dragEnd);
                    filters.end = Math.max(this.dragStart, this.dragAnchorEnd, this.dragEnd);
                    requestFilterUpdate();
                }
                this.isDragging = false;
                this.isDraggingDecade = false;
                this.isDraggingToDecade = false;
                this.dragStart = null;
                this.dragAnchorEnd = null;
                this.dragEnd = null;
                window.dispatchEvent(new CustomEvent("year-preview", { detail: { active: false } }));
            },

            cancelDrag: function () {
                this.isDragging = false;
                this.isDraggingDecade = false;
                this.isDraggingToDecade = false;
                this.dragStart = null;
                this.dragAnchorEnd = null;
                this.dragEnd = null;
                window.dispatchEvent(new CustomEvent("year-preview", { detail: { active: false } }));
            },

            dispatchPreview: function () {
                if (this.isDragging) {
                    var min = Math.min(this.dragStart, this.dragAnchorEnd, this.dragEnd);
                    var max = Math.max(this.dragStart, this.dragAnchorEnd, this.dragEnd);
                    window.dispatchEvent(
                        new CustomEvent("year-preview", { detail: { active: true, start: min, end: max } })
                    );
                }
            },

            getDecadeCount: function (decade) {
                return decade.cells
                    .filter(function (c) {
                        return c && c.year && !c.hidden;
                    })
                    .reduce(function (sum, c) {
                        return sum + (c.count || 0);
                    }, 0);
            },

            yearExists: function (year) {
                return this._yearSet && this._yearSet.has(year);
            },

            hasSelectedAbove: function (year) {
                var aboveYear = year + 10;
                return this.yearExists(aboveYear) && this.isInRange(aboveYear);
            },

            hasSelectedBelow: function (year) {
                var belowYear = year - 10;
                return this.yearExists(belowYear) && this.isInRange(belowYear);
            },

            hasSelectedRight: function (year) {
                var position = year % 10;
                if (position === 9) {
                    return false;
                }
                return this.yearExists(year + 1) && this.isInRange(year + 1);
            },

            hasSelectedLeft: function (year) {
                var position = year % 10;
                if (position === 0) {
                    var decadeStart = Math.floor(year / 10) * 10;
                    return this.isDecadeSelected(decadeStart) || this.isDecadeInDragRange(decadeStart);
                }
                return this.isInRange(year - 1);
            },

            decadeHasSelectedAbove: function (decadeStart) {
                var aboveDecade = decadeStart + 10;
                return this.isDecadeSelected(aboveDecade) || this.isDecadeInDragRange(aboveDecade);
            },

            decadeHasSelectedBelow: function (decadeStart) {
                var belowDecade = decadeStart - 10;
                return this.isDecadeSelected(belowDecade) || this.isDecadeInDragRange(belowDecade);
            },

            decadeHasSelectedRight: function (decadeStart) {
                return this.isInRange(decadeStart);
            },

            hasSelectedDiagonalBR: function (year) {
                var diagYear = year + 1 - 10;
                var position = year % 10;
                if (position === 9) {
                    return false;
                }
                return this.yearExists(diagYear) && this.isInRange(diagYear);
            },
        };
    }

    function createMobileGenreFilterComponent(config) {
        var filters = config.filters;
        var component = createGenreFilterComponent(config || {});
        if (!Array.isArray(filters.genres)) {
            filters.genres = [];
        }

        component.expanded = JSON.parse(localStorage.getItem("mobileFilterExpanded_genre") || "true");
        component.expandedCategories = {};
        component.countsReady = false;

        component.init = function () {
            var self = this;
            this.$watch("expanded", function (val) {
                localStorage.setItem("mobileFilterExpanded_genre", JSON.stringify(val));
            });
            this._genreCountsHandler = function (event) {
                self.updateFilteredCounts(event.detail);
                self.countsReady = true;
            };
            window.addEventListener("genre-counts-update", this._genreCountsHandler);
        };

        component.destroy = function () {
            if (this._genreCountsHandler) {
                window.removeEventListener("genre-counts-update", this._genreCountsHandler);
            }
        };

        component.selectedCount = function () {
            return filters.genres.length;
        };

        component.clearGenres = function () {
            filters.genres = [];
        };

        component.isCategoryExpanded = function (categoryId) {
            return this.expandedCategories[categoryId] === true;
        };

        component.toggleCategoryExpansion = function (categoryId) {
            this.expandedCategories[categoryId] = !this.isCategoryExpanded(categoryId);
        };

        component.resetExpanded = function () {
            this.expandedCategories = {};
        };

        component.toggleAllExpanded = function () {
            var shouldExpand = !this.areAllExpanded();
            var categories = this.rootCategories;
            for (var i = 0; i < categories.length; i++) {
                this.expandedCategories[categories[i].id] = shouldExpand;
            }
        };

        return component;
    }

    /**
     * The decade buttons the mobile sheet offers, spanning the data.
     *
     * This was a hardcoded 1970s-2020s, which is the games range. Albums go
     * back to the 1950s, and a section whose earliest decades are missing
     * from the sheet cannot be filtered to them on a phone at all.
     */
    function buildDecades(minYear, maxYear) {
        if (!isFinite(minYear) || !isFinite(maxYear) || maxYear < minYear) {
            return [];
        }
        var decades = [];
        var first = Math.floor(minYear / 10) * 10;
        var last = Math.floor(maxYear / 10) * 10;
        for (var decade = first; decade <= last; decade += 10) {
            decades.push({ label: decade + "s", start: decade, end: decade + 9 });
        }
        return decades;
    }

    function createMobileTimeFilterComponent(config) {
        var filters = config.filters;
        var minYear = config.minYear;
        var maxYear = config.maxYear;

        return {
            expanded: JSON.parse(localStorage.getItem("mobileFilterExpanded_time") || "true"),
            mode: "decade",
            decades: buildDecades(minYear, maxYear),

            isDecadeSelected: function (decade) {
                return Number(filters.start) === decade.start && Number(filters.end) === decade.end;
            },

            toggleDecade: function (decade) {
                if (this.isDecadeSelected(decade)) {
                    filters.start = minYear;
                    filters.end = maxYear;
                } else {
                    filters.start = decade.start;
                    filters.end = decade.end;
                }
            },

            selectDecade: function (decade) {
                filters.start = decade.start;
                filters.end = decade.end;
            },

            hasYearFilter: function () {
                return filters.start !== minYear || filters.end !== maxYear;
            },

            clearYears: function () {
                filters.start = minYear;
                filters.end = maxYear;
            },

            syncRangeSelects: function () {
                var self = this;
                setTimeout(function () {
                    if (self.$refs.startYear) {
                        self.$refs.startYear.value = filters.start;
                    }
                    if (self.$refs.endYear) {
                        self.$refs.endYear.value = filters.end;
                    }
                }, 50);
            },

            init: function () {
                var self = this;
                this.$watch("expanded", function (val) {
                    localStorage.setItem("mobileFilterExpanded_time", JSON.stringify(val));
                });
                this.$watch("mode", function (val) {
                    if (val === "range") {
                        self.syncRangeSelects();
                    }
                });
            },
        };
    }

    /**
     * The rankings pages' mobile filter sheet: open state, and whether it
     * has ever been opened. The sheet's filters render only once it has
     * (`<template x-if="hasOpenedBefore">`), so Alpine does not build them
     * for the many visits that never open it; the first open then asks for
     * the facet counts those late components missed.
     */
    function createMobileFilterSheet() {
        return {
            filterOpen: false,
            hasOpenedBefore: false,
            init: function () {
                var self = this;
                this.$watch("filterOpen", function (open) {
                    if (open && !self.hasOpenedBefore) {
                        self.hasOpenedBefore = true;
                        // After the template has rendered its components.
                        setTimeout(function () {
                            window.dispatchEvent(new CustomEvent("mobile-filter-opened"));
                        }, 50);
                    }
                });
            },
        };
    }

    function registerFactories() {
        Alpine.data("genreFilterComponent", function (config) {
            return createGenreFilterComponent(config || {});
        });
        Alpine.data("yearGridComponent", function (config) {
            return createYearGridComponent(config || {});
        });
        Alpine.data("mobileGenreFilterComponent", function (config) {
            return createMobileGenreFilterComponent(config || {});
        });
        Alpine.data("mobileFilterSheet", createMobileFilterSheet);
        Alpine.data("mobileTimeFilterComponent", function (config) {
            return createMobileTimeFilterComponent(config || {});
        });
    }

    document.addEventListener("alpine:init", registerFactories);
})();
