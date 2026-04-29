(function () {
    "use strict";

    var SHARED_PLATFORM_HIERARCHY_UI = {
        nintendo: {
            name: "Nintendo",
            icon: "mdi-nintendo-switch",
            formFactors: {
                home: {
                    name: "Home Consoles",
                    platforms: ["NES", "FDS", "SNES", "N64", "GC", "Wii", "WiiU", "SW", "SW2"],
                },
                handheld: {
                    name: "Handhelds",
                    platforms: ["GW", "GB", "GBC", "GBA", "DS", "3DS"],
                },
            },
        },
        playstation: {
            name: "PlayStation",
            icon: "mdi-sony-playstation",
            formFactors: {
                home: {
                    name: "Home Consoles",
                    platforms: ["PS", "PS2", "PS3", "PS4", "PS5", "PSVR"],
                },
                handheld: {
                    name: "Handhelds",
                    platforms: ["PSP", "PSV"],
                },
            },
        },
        xbox: {
            name: "Xbox",
            icon: "mdi-microsoft-xbox",
            platforms: ["Xbox", "X360", "XB1", "XBXS"],
        },
        sega: {
            name: "Sega",
            svgIcon: "platform-sega",
            formFactors: {
                home: {
                    name: "Home Consoles",
                    platforms: ["SMS", "GEN", "SCD", "SAT", "DC"],
                },
                handheld: {
                    name: "Handhelds",
                    platforms: ["GG"],
                },
            },
        },
        pc: {
            name: "PC",
            icon: "mdi-microsoft-windows",
            platforms: ["WIN", "DOS", "LIN", "MAC"],
        },
        arcadePlus: {
            name: "Arcade, Mobile, & VR",
            icon: "mdi-space-invaders",
            platforms: ["ARC", "AND", "iOS", "LMD", "VR", "BR"],
        },
        retro: {
            name: "Retro Consoles",
            icon: "mdi-pac-man",
            platforms: ["A26", "A52", "A78", "INTV", "CV", "TG16", "3DO", "NG", "JAG", "LYNX", "VECT"],
        },
        computers: {
            name: "Microcomputers",
            icon: "mdi-desktop-classic",
            formFactors: {
                commodore: { name: "Commodore", platforms: ["VC20", "C64", "AMI", "CD32"] },
                uk: { name: "UK", platforms: ["ZXS", "CPC", "BBCM", "ARCH", "D32"] },
                japan: { name: "Japan", platforms: ["PC88", "PC98", "FM7", "FMT", "SX1", "MSX", "TT"] },
                atari: { name: "Atari", platforms: ["A8", "AST"] },
                other: { name: "Other", platforms: ["A2", "T80", "TCC", "PDP", "HP21", "E60", "MIC"] },
            },
        },
    };

    function createEnginePlatformHierarchy(uiHierarchy) {
        var result = {};
        Object.keys(uiHierarchy).forEach(function (mfrKey) {
            var mfr = uiHierarchy[mfrKey];
            var allCodes = [];
            var mapped = {
                name: mfr.name,
            };

            if (mfr.formFactors) {
                mapped.formFactors = {};
                Object.keys(mfr.formFactors).forEach(function (ffKey) {
                    var ff = mfr.formFactors[ffKey];
                    var ffCodes = (ff.platforms || []).slice();
                    mapped.formFactors[ffKey] = {
                        name: ff.name,
                        codes: ffCodes,
                    };
                    allCodes = allCodes.concat(ffCodes);
                });
            }

            if (mfr.platforms) {
                allCodes = allCodes.concat(mfr.platforms.slice());
            }

            mapped.codes = Array.from(new Set(allCodes));
            result[mfrKey] = mapped;
        });
        return result;
    }

    if (typeof window !== "undefined" && !window.AV_PLATFORM_HIERARCHY) {
        window.AV_PLATFORM_HIERARCHY = createEnginePlatformHierarchy(SHARED_PLATFORM_HIERARCHY_UI);
    }

    function createPlatformHierarchy() {
        return JSON.parse(JSON.stringify(SHARED_PLATFORM_HIERARCHY_UI));
    }

    function defineComputed(target, key, getter) {
        Object.defineProperty(target, key, {
            configurable: true,
            enumerable: true,
            get: getter,
        });
    }

    function createPlatformFilterComponent(config) {
        var filters = config.filters;
        var platforms = config.platforms;

        return {
            _platformCountsHandler: null,
            _platformGroupCountsHandler: null,
            countsReady: false,
            groupCounts: {},
            expandedManufacturers: {},
            expandedFormFactors: {},
            platformHierarchy: createPlatformHierarchy(),

            init: function () {
                var self = this;
                this._platformCountsHandler = function (event) {
                    self.updateFilteredCounts(event.detail);
                    self.countsReady = true;
                };
                window.addEventListener("platform-counts-update", this._platformCountsHandler);

                this._platformGroupCountsHandler = function (event) {
                    self.groupCounts = event.detail;
                    self.countsReady = true;
                };
                window.addEventListener("platform-group-counts-update", this._platformGroupCountsHandler);
                this.loadExpandedState();
            },

            destroy: function () {
                if (this._platformCountsHandler) {
                    window.removeEventListener("platform-counts-update", this._platformCountsHandler);
                }
                if (this._platformGroupCountsHandler) {
                    window.removeEventListener("platform-group-counts-update", this._platformGroupCountsHandler);
                }
            },

            loadExpandedState: function () {
                try {
                    var savedMfr = localStorage.getItem("platformManufacturersExpanded");
                    var savedFF = localStorage.getItem("platformFormFactorsExpanded");
                    if (savedMfr) {
                        this.expandedManufacturers = JSON.parse(savedMfr);
                    }
                    if (savedFF) {
                        this.expandedFormFactors = JSON.parse(savedFF);
                    }
                } catch (e) {
                    this.expandedManufacturers = {};
                    this.expandedFormFactors = {};
                }
            },

            saveExpandedState: function () {
                localStorage.setItem("platformManufacturersExpanded", JSON.stringify(this.expandedManufacturers));
                localStorage.setItem("platformFormFactorsExpanded", JSON.stringify(this.expandedFormFactors));
            },

            toggleManufacturerExpanded: function (mfrKey) {
                var self = this;
                var newState = !this.expandedManufacturers[mfrKey];
                this.expandedManufacturers[mfrKey] = newState;
                var mfr = this.platformHierarchy[mfrKey];
                if (mfr && mfr.formFactors) {
                    Object.keys(mfr.formFactors).forEach(function (ffKey) {
                        var key = mfrKey + "_" + ffKey;
                        self.expandedFormFactors[key] = newState;
                    });
                }
                this.saveExpandedState();
            },

            isManufacturerExpanded: function (mfrKey) {
                if (this.expandedManufacturers[mfrKey] === undefined) {
                    return this.hasManufacturerOrChildrenSelected(mfrKey);
                }
                return this.expandedManufacturers[mfrKey];
            },

            toggleFormFactorExpanded: function (mfrKey, ffKey) {
                var key = mfrKey + "_" + ffKey;
                this.expandedFormFactors[key] = !this.expandedFormFactors[key];
                this.saveExpandedState();
            },

            isFormFactorExpanded: function (mfrKey, ffKey) {
                var key = mfrKey + "_" + ffKey;
                if (this.expandedFormFactors[key] === undefined) {
                    return this.hasFormFactorSelection(mfrKey, ffKey);
                }
                return this.expandedFormFactors[key];
            },

            updateFilteredCounts: function (countMap) {
                platforms.forEach(function (p) {
                    p.filtered_count = countMap[String(p.id)] || 0;
                });
            },

            getPlatformByCode: function (code) {
                return platforms.find(function (p) {
                    return p.code === code;
                });
            },

            getEffectiveCount: function (platform) {
                if (!platform) {
                    return 0;
                }
                return platform.filtered_count !== undefined
                    ? platform.filtered_count
                    : platform.game_count || 0;
            },

            formatPlatformYears: function (platform) {
                if (!platform || !platform.year_start) {
                    return "";
                }
                var startAbbr = "'" + String(platform.year_start).slice(-2);
                var endAbbr = platform.year_end ? "'" + String(platform.year_end).slice(-2) : "now";
                return "(" + startAbbr + "-" + endAbbr + ")";
            },

            formatPlatformName: function (platform) {
                if (!platform) {
                    return "";
                }
                if (!platform.year_start) {
                    return platform.name;
                }
                var endYear = platform.year_end ? platform.year_end : "now";
                return platform.name + " (" + platform.year_start + "-" + endYear + ")";
            },

            get sortedManufacturerKeys() {
                var self = this;
                return Object.keys(this.platformHierarchy).sort(function (a, b) {
                    return self.getManufacturerTotalCount(b) - self.getManufacturerTotalCount(a);
                });
            },

            getSortedFormFactorKeys: function (mfrKey) {
                var self = this;
                var mfr = this.platformHierarchy[mfrKey];
                if (!mfr || !mfr.formFactors) {
                    return [];
                }
                return Object.keys(mfr.formFactors).sort(function (a, b) {
                    return self.getFormFactorTotalCount(mfrKey, b) - self.getFormFactorTotalCount(mfrKey, a);
                });
            },

            getAllCodesForManufacturer: function (mfrKey) {
                var mfr = this.platformHierarchy[mfrKey];
                if (!mfr) {
                    return [];
                }
                if (mfr.formFactors) {
                    return Object.values(mfr.formFactors).flatMap(function (ff) {
                        return ff.platforms;
                    });
                }
                return mfr.platforms || [];
            },

            getManufacturerTotalCount: function (mfrKey) {
                var self = this;
                if (this.groupCounts && this.groupCounts[mfrKey]) {
                    return this.groupCounts[mfrKey].count || 0;
                }
                var codes = this.getAllCodesForManufacturer(mfrKey);
                return codes.reduce(function (sum, code) {
                    var p = self.getPlatformByCode(code);
                    return sum + self.getEffectiveCount(p);
                }, 0);
            },

            getFormFactorTotalCount: function (mfrKey, ffKey) {
                var self = this;
                if (this.groupCounts && this.groupCounts[mfrKey] && this.groupCounts[mfrKey].formFactors) {
                    return this.groupCounts[mfrKey].formFactors[ffKey] || 0;
                }
                var mfr = this.platformHierarchy[mfrKey];
                if (!mfr || !mfr.formFactors || !mfr.formFactors[ffKey]) {
                    return 0;
                }
                return mfr.formFactors[ffKey].platforms.reduce(function (sum, code) {
                    var p = self.getPlatformByCode(code);
                    return sum + self.getEffectiveCount(p);
                }, 0);
            },

            getFormFactorPlatforms: function (mfrKey, ffKey) {
                var self = this;
                var mfr = this.platformHierarchy[mfrKey];
                if (!mfr || !mfr.formFactors || !mfr.formFactors[ffKey]) {
                    return [];
                }
                return mfr.formFactors[ffKey].platforms
                    .map(function (code) {
                        return self.getPlatformByCode(code);
                    })
                    .filter(function (p) {
                        return p;
                    })
                    .sort(function (a, b) {
                        var startA = a.year_start || 9999;
                        var startB = b.year_start || 9999;
                        if (startA !== startB) {
                            return startA - startB;
                        }
                        var endA = a.year_end || 9999;
                        var endB = b.year_end || 9999;
                        if (endA !== endB) {
                            return endA - endB;
                        }
                        return (a.name || "").localeCompare(b.name || "");
                    });
            },

            getFlatPlatforms: function (mfrKey) {
                var self = this;
                var mfr = this.platformHierarchy[mfrKey];
                if (!mfr || !mfr.platforms) {
                    return [];
                }
                return mfr.platforms
                    .map(function (code) {
                        return self.getPlatformByCode(code);
                    })
                    .filter(function (p) {
                        return p;
                    })
                    .sort(function (a, b) {
                        var startA = a.year_start || 9999;
                        var startB = b.year_start || 9999;
                        if (startA !== startB) {
                            return startA - startB;
                        }
                        var endA = a.year_end || 9999;
                        var endB = b.year_end || 9999;
                        if (endA !== endB) {
                            return endA - endB;
                        }
                        return (a.name || "").localeCompare(b.name || "");
                    });
            },

            isPlatformAvailable: function (platformId) {
                var platform = platforms.find(function (p) {
                    return String(p.id) === String(platformId);
                });
                if (!platform) {
                    return false;
                }
                var count = this.getEffectiveCount(platform);
                return count > 0 || this.isPlatformInFilter(platformId);
            },

            hasZeroResults: function (platformId) {
                var platform = platforms.find(function (p) {
                    return String(p.id) === String(platformId);
                });
                if (!platform) {
                    return false;
                }
                var count = this.getEffectiveCount(platform);
                return count === 0 && this.isPlatformInFilter(platformId);
            },

            isManufacturerAvailable: function (mfrKey) {
                var self = this;
                var codes = this.getAllCodesForManufacturer(mfrKey);
                return codes.some(function (code) {
                    var p = self.getPlatformByCode(code);
                    return p && self.isPlatformAvailable(p.id);
                });
            },

            isFormFactorAvailable: function (mfrKey, ffKey) {
                var self = this;
                var mfr = this.platformHierarchy[mfrKey];
                if (!mfr || !mfr.formFactors || !mfr.formFactors[ffKey]) {
                    return false;
                }
                return mfr.formFactors[ffKey].platforms.some(function (code) {
                    var p = self.getPlatformByCode(code);
                    return p && self.isPlatformAvailable(p.id);
                });
            },

            isPlatformInFilter: function (platformId) {
                return filters.platforms.includes(String(platformId));
            },

            findPlatformParent: function (platformId) {
                var id = String(platformId);
                for (var _i = 0, _arr = Object.keys(this.platformHierarchy); _i < _arr.length; _i++) {
                    var mfrKey = _arr[_i];
                    var mfr = this.platformHierarchy[mfrKey];
                    if (mfr.formFactors) {
                        for (var _j = 0, _entries = Object.entries(mfr.formFactors); _j < _entries.length; _j++) {
                            var entry = _entries[_j];
                            var ffKey = entry[0];
                            var ff = entry[1];
                            var platformIds = ff.platforms
                                .map(this.getPlatformByCode.bind(this))
                                .filter(Boolean)
                                .map(function (p) {
                                    return String(p.id);
                                });
                            if (platformIds.includes(id)) {
                                return { mfrKey: mfrKey, ffKey: ffKey };
                            }
                        }
                    } else if (mfr.platforms) {
                        var flatIds = mfr.platforms
                            .map(this.getPlatformByCode.bind(this))
                            .filter(Boolean)
                            .map(function (p) {
                                return String(p.id);
                            });
                        if (flatIds.includes(id)) {
                            return { mfrKey: mfrKey, ffKey: null };
                        }
                    }
                }
                return null;
            },

            _isFormFactorFullySelected: function (mfrKey, ffKey) {
                var platformIds = this.getAllPlatformIdsForFormFactor(mfrKey, ffKey);
                if (platformIds.length === 0) {
                    return false;
                }
                return platformIds.every(function (id) {
                    return filters.platforms.includes(id);
                });
            },

            isPlatformSelected: function (platformId) {
                if (!filters.platforms.includes(String(platformId))) {
                    return false;
                }
                var parentInfo = this.findPlatformParent(platformId);
                if (!parentInfo) {
                    return true;
                }
                if (this.isManufacturerSelected(parentInfo.mfrKey)) {
                    return false;
                }
                if (
                    parentInfo.ffKey &&
                    this._isFormFactorFullySelected(parentInfo.mfrKey, parentInfo.ffKey)
                ) {
                    return false;
                }
                return true;
            },

            togglePlatform: function (platformId) {
                var id = String(platformId);
                var parentInfo = this.findPlatformParent(platformId);
                if (parentInfo) {
                    if (this.isManufacturerSelected(parentInfo.mfrKey)) {
                        var mfrPlatformIds = this.getAllPlatformIdsForManufacturer(parentInfo.mfrKey);
                        filters.platforms = filters.platforms.filter(function (pid) {
                            return !mfrPlatformIds.includes(pid);
                        });
                        filters.platforms.push(id);
                        return;
                    }
                    if (parentInfo.ffKey && this._isFormFactorFullySelected(parentInfo.mfrKey, parentInfo.ffKey)) {
                        var ffPlatformIds = this.getAllPlatformIdsForFormFactor(parentInfo.mfrKey, parentInfo.ffKey);
                        filters.platforms = filters.platforms.filter(function (pid) {
                            return !ffPlatformIds.includes(pid);
                        });
                        filters.platforms.push(id);
                        return;
                    }
                }
                var idx = filters.platforms.indexOf(id);
                if (idx > -1) {
                    filters.platforms.splice(idx, 1);
                } else {
                    filters.platforms.push(id);
                }
            },

            getAllPlatformIdsForManufacturer: function (mfrKey) {
                return this.getAllCodesForManufacturer(mfrKey)
                    .map(this.getPlatformByCode.bind(this))
                    .filter(Boolean)
                    .map(function (p) {
                        return String(p.id);
                    });
            },

            getAllPlatformIdsForFormFactor: function (mfrKey, ffKey) {
                var mfr = this.platformHierarchy[mfrKey];
                if (!mfr || !mfr.formFactors || !mfr.formFactors[ffKey]) {
                    return [];
                }
                return mfr.formFactors[ffKey].platforms
                    .map(this.getPlatformByCode.bind(this))
                    .filter(Boolean)
                    .map(function (p) {
                        return String(p.id);
                    });
            },

            hasManufacturerOrChildrenSelected: function (mfrKey) {
                var platformIds = this.getAllPlatformIdsForManufacturer(mfrKey);
                return platformIds.some(function (id) {
                    return filters.platforms.includes(id);
                });
            },

            hasFormFactorSelection: function (mfrKey, ffKey) {
                var platformIds = this.getAllPlatformIdsForFormFactor(mfrKey, ffKey);
                return platformIds.some(function (id) {
                    return filters.platforms.includes(id);
                });
            },

            isManufacturerSelected: function (mfrKey) {
                var platformIds = this.getAllPlatformIdsForManufacturer(mfrKey);
                if (platformIds.length === 0) {
                    return false;
                }
                return platformIds.every(function (id) {
                    return filters.platforms.includes(id);
                });
            },

            isFormFactorSelected: function (mfrKey, ffKey) {
                if (this.isManufacturerSelected(mfrKey)) {
                    return false;
                }
                var platformIds = this.getAllPlatformIdsForFormFactor(mfrKey, ffKey);
                if (platformIds.length === 0) {
                    return false;
                }
                return platformIds.every(function (id) {
                    return filters.platforms.includes(id);
                });
            },

            toggleManufacturerSelection: function (mfrKey) {
                if (this.expandedManufacturers[mfrKey] === undefined) {
                    this.expandedManufacturers[mfrKey] = this.hasManufacturerOrChildrenSelected(mfrKey);
                }
                var platformIds = this.getAllPlatformIdsForManufacturer(mfrKey);
                if (this.isManufacturerSelected(mfrKey)) {
                    filters.platforms = filters.platforms.filter(function (id) {
                        return !platformIds.includes(id);
                    });
                } else {
                    var newIds = platformIds.filter(function (id) {
                        return !filters.platforms.includes(id);
                    });
                    filters.platforms = filters.platforms.concat(newIds);
                }
            },

            toggleFormFactorSelection: function (mfrKey, ffKey) {
                var key = mfrKey + "_" + ffKey;
                if (this.expandedFormFactors[key] === undefined) {
                    this.expandedFormFactors[key] = this.hasFormFactorSelection(mfrKey, ffKey);
                }
                var platformIds = this.getAllPlatformIdsForFormFactor(mfrKey, ffKey);
                if (this.isManufacturerSelected(mfrKey)) {
                    var mfrPlatformIds = this.getAllPlatformIdsForManufacturer(mfrKey);
                    filters.platforms = filters.platforms.filter(function (id) {
                        return !mfrPlatformIds.includes(id);
                    });
                    filters.platforms = filters.platforms.concat(platformIds);
                    return;
                }
                if (this._isFormFactorFullySelected(mfrKey, ffKey)) {
                    filters.platforms = filters.platforms.filter(function (id) {
                        return !platformIds.includes(id);
                    });
                } else {
                    var newIds = platformIds.filter(function (id) {
                        return !filters.platforms.includes(id);
                    });
                    filters.platforms = filters.platforms.concat(newIds);
                }
            },

            getSelectedCount: function () {
                return filters.platforms.length;
            },

            handleReset: function () {
                this.expandedManufacturers = {};
                this.expandedFormFactors = {};
                localStorage.removeItem("platformManufacturersExpanded");
                localStorage.removeItem("platformFormFactorsExpanded");
            },

            areAllExpanded: function () {
                for (var _i2 = 0, _arr2 = Object.keys(this.platformHierarchy); _i2 < _arr2.length; _i2++) {
                    var mfrKey = _arr2[_i2];
                    if (!this.expandedManufacturers[mfrKey]) {
                        return false;
                    }
                    var mfr = this.platformHierarchy[mfrKey];
                    if (mfr.formFactors) {
                        for (var _j2 = 0, _arr3 = Object.keys(mfr.formFactors); _j2 < _arr3.length; _j2++) {
                            var ffKey = _arr3[_j2];
                            var key = mfrKey + "_" + ffKey;
                            if (!this.expandedFormFactors[key]) {
                                return false;
                            }
                        }
                    }
                }
                return true;
            },

            toggleAllExpanded: function () {
                var shouldExpand = !this.areAllExpanded();
                for (var _i3 = 0, _arr4 = Object.keys(this.platformHierarchy); _i3 < _arr4.length; _i3++) {
                    var mfrKey = _arr4[_i3];
                    this.expandedManufacturers[mfrKey] = shouldExpand;
                    var mfr = this.platformHierarchy[mfrKey];
                    if (mfr.formFactors) {
                        for (var _j3 = 0, _arr5 = Object.keys(mfr.formFactors); _j3 < _arr5.length; _j3++) {
                            var ffKey = _arr5[_j3];
                            this.expandedFormFactors[mfrKey + "_" + ffKey] = shouldExpand;
                        }
                    }
                }
                this.saveExpandedState();
            },
        };
    }

    function createGenreFilterComponent(config) {
        var filters = config.filters;
        var genres = config.genres;

        return {
            _genreCountsHandler: null,
            countsReady: false,
            expandedCategories: {},
            categoryIcons: {
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
                return genres
                    .filter(function (g) {
                        return g.level === 0;
                    })
                    .sort(function (a, b) {
                        return self.getCategoryTotalGameCount(b.id) - self.getCategoryTotalGameCount(a.id);
                    });
            },

            getCategoryTotalGameCount: function (categoryId) {
                var category = genres.find(function (g) {
                    return String(g.id) === String(categoryId);
                });
                var categoryCount = category ? this.getEffectiveCount(category) : 0;
                var children = genres.filter(function (g) {
                    return String(g.parent_id) === String(categoryId);
                });
                var self = this;
                var childrenCount = children.reduce(function (sum, c) {
                    return sum + self.getEffectiveCount(c);
                }, 0);
                return categoryCount + childrenCount;
            },

            getChildren: function (parentId) {
                var self = this;
                return genres
                    .filter(function (g) {
                        return String(g.parent_id) === String(parentId);
                    })
                    .sort(function (a, b) {
                        return self.getEffectiveCount(b) - self.getEffectiveCount(a);
                    });
            },

            getDescendantIds: function (genreId) {
                var children = this.getChildren(genreId);
                var ids = children.map(function (c) {
                    return String(c.id);
                });
                for (var i = 0; i < children.length; i++) {
                    ids = ids.concat(this.getDescendantIds(children[i].id));
                }
                return ids;
            },

            isGenreAvailable: function (genreId) {
                var genre = genres.find(function (g) {
                    return String(g.id) === String(genreId);
                });
                if (!genre) {
                    return false;
                }
                var count = this.getEffectiveCount(genre);
                return count > 0 || this.isGenreSelected(genreId);
            },

            hasZeroResults: function (genreId) {
                var genre = genres.find(function (g) {
                    return String(g.id) === String(genreId);
                });
                if (!genre) {
                    return false;
                }
                var count = this.getEffectiveCount(genre);
                return count === 0 && this.isGenreSelected(genreId);
            },

            getEffectiveCount: function (genre) {
                return genre.filtered_count !== undefined ? genre.filtered_count : genre.game_count;
            },

            getCategoryTotalCount: function (categoryId) {
                var category = genres.find(function (g) {
                    return String(g.id) === String(categoryId);
                });
                var categoryCount = category ? this.getEffectiveCount(category) : 0;
                var children = this.getChildren(categoryId);
                var self = this;
                var childrenCount = children.reduce(function (sum, c) {
                    return sum + self.getEffectiveCount(c);
                }, 0);
                return categoryCount + childrenCount;
            },

            isCategoryAvailable: function (categoryId) {
                var category = genres.find(function (g) {
                    return String(g.id) === String(categoryId);
                });
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
                var genre = genres.find(function (g) {
                    return String(g.id) === String(genreId);
                });
                if (!genre || !genre.parent_id) {
                    return null;
                }
                return genres.find(function (g) {
                    return String(g.id) === String(genre.parent_id);
                });
            },

            toggleGenre: function (genreId) {
                var id = String(genreId);
                var genre = genres.find(function (g) {
                    return String(g.id) === id;
                });
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
                return this.categoryIcons[name] || "mdi-gamepad-variant";
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

            init: function () {
                var self = this;
                var dataEl = document.getElementById("year-counts-data");
                if (dataEl) {
                    this.yearCounts = JSON.parse(dataEl.textContent);
                    this.originalYearCounts = this.yearCounts.slice();
                    this._rebuildCaches();
                    this.maxCount = Math.max.apply(
                        null,
                        this.yearCounts.map(function (y) {
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

                if ("requestIdleCallback" in window) {
                    requestIdleCallback(setupListeners, { timeout: 200 });
                } else {
                    setTimeout(setupListeners, 50);
                }
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
                this._yearSet = new Set(
                    this.originalYearCounts.map(function (yc) {
                        return yc.year;
                    })
                );
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

                this._decadeStructure = decadeStarts.map(function (ds) {
                    var maxPos = decadeMap[ds].maxOriginalPos || 0;
                    var cells = [];
                    for (var i = 0; i < 10; i++) {
                        if (i > maxPos) {
                            cells.push({ hidden: true });
                        } else if (decadeMap[ds][i]) {
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
                var normalized = count / this.maxCount;
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

            hasSelectedDiagonalBL: function (year) {
                var diagYear = year - 1 - 10;
                var position = year % 10;
                if (position === 0) {
                    return false;
                }
                return this.yearExists(diagYear) && this.isInRange(diagYear);
            },

            hasSelectedDiagonalTR: function (year) {
                var diagYear = year + 1 + 10;
                var position = year % 10;
                if (position === 9) {
                    return false;
                }
                return this.yearExists(diagYear) && this.isInRange(diagYear);
            },

            hasSelectedDiagonalTL: function (year) {
                var diagYear = year - 1 + 10;
                var position = year % 10;
                if (position === 0) {
                    return false;
                }
                return this.yearExists(diagYear) && this.isInRange(diagYear);
            },
        };
    }

    function createSeriesFilterComponent(config) {
        var filters = config.filters;
        var seriesList = config.seriesList;

        return {
            _seriesResetHandler: null,
            _seriesCountsHandler: null,
            searchQuery: "",
            countsReady: false,
            selectedSeries: [],

            init: function () {
                var self = this;
                this.selectedSeries = filters.series || [];
                this._seriesResetHandler = function () {
                    self.handleReset();
                };
                window.addEventListener("series-reset", this._seriesResetHandler);
                this.$watch("filters.series", function (value) {
                    self.selectedSeries = value || [];
                });
                this._seriesCountsHandler = function (event) {
                    self.updateFilteredCounts(event.detail);
                };
                window.addEventListener("series-counts-update", this._seriesCountsHandler);
                setTimeout(function () {
                    self.countsReady = true;
                }, 150);
            },

            destroy: function () {
                if (this._seriesResetHandler) {
                    window.removeEventListener("series-reset", this._seriesResetHandler);
                }
                if (this._seriesCountsHandler) {
                    window.removeEventListener("series-counts-update", this._seriesCountsHandler);
                }
            },

            handleReset: function () {
                this.selectedSeries = [];
                this.searchQuery = "";
            },

            updateFilteredCounts: function (countMap) {
                seriesList.forEach(function (s) {
                    s.filtered_count = countMap[String(s.id)] || 0;
                });
            },

            getEffectiveCount: function (series) {
                return series.filtered_count !== undefined ? series.filtered_count : series.game_count;
            },

            isSeriesAvailable: function (seriesId) {
                var series = seriesList.find(function (s) {
                    return String(s.id) === String(seriesId);
                });
                if (!series) {
                    return false;
                }
                var count = this.getEffectiveCount(series);
                return count > 0 || this.isSelected(seriesId);
            },

            hasZeroResults: function (seriesId) {
                var series = seriesList.find(function (s) {
                    return String(s.id) === String(seriesId);
                });
                if (!series) {
                    return false;
                }
                var count = this.getEffectiveCount(series);
                return count === 0 && this.isSelected(seriesId);
            },

            normalizeSearchText: function (value) {
                var lower = String(value || "").toLowerCase();
                if (typeof lower.normalize !== "function") {
                    return lower;
                }
                return lower.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
            },

            get filteredSeries() {
                var self = this;
                var list = seriesList;
                if (this.searchQuery) {
                    var query = this.normalizeSearchText(this.searchQuery);
                    list = list.filter(function (s) {
                        return self.normalizeSearchText(s.name).includes(query);
                    });
                }
                list = list.sort(function (a, b) {
                    var countDiff = self.getEffectiveCount(b) - self.getEffectiveCount(a);
                    if (countDiff !== 0) {
                        return countDiff;
                    }
                    return a.name.localeCompare(b.name);
                });
                return list;
            },

            toggleSeries: function (seriesId) {
                var id = String(seriesId);
                if (this.selectedSeries.includes(id)) {
                    this.selectedSeries = [];
                } else {
                    this.selectedSeries = [id];
                }
                filters.series = this.selectedSeries.slice();
                this.$dispatch("filter-changed", { type: "series", items: this.selectedSeries });
            },

            isSelected: function (seriesId) {
                return this.selectedSeries.includes(String(seriesId));
            },
        };
    }

    function createHltbFilterComponent(config) {
        var filters = config.filters;

        return {
            _hltbCountsHandler: null,
            _hltbResetHandler: null,
            countsReady: false,
            presetCounts: {
                short: 0,
                medium: 0,
                long: 0,
            },
            showCustomRange: false,

            init: function () {
                var self = this;
                this._hltbCountsHandler = function (event) {
                    self.presetCounts = event.detail;
                    self.countsReady = true;
                };
                window.addEventListener("hltb-counts-update", this._hltbCountsHandler);

                this._hltbResetHandler = function () {
                    self.handleReset();
                };
                window.addEventListener("hltb-reset", this._hltbResetHandler);

                this.$watch("filters.hltb_min", function () {
                    self.updateCustomVisibility();
                });
                this.$watch("filters.hltb_max", function () {
                    self.updateCustomVisibility();
                });

                setTimeout(function () {
                    self.countsReady = true;
                }, 150);
            },

            destroy: function () {
                if (this._hltbCountsHandler) {
                    window.removeEventListener("hltb-counts-update", this._hltbCountsHandler);
                }
                if (this._hltbResetHandler) {
                    window.removeEventListener("hltb-reset", this._hltbResetHandler);
                }
            },

            handleReset: function () {
                this.showCustomRange = false;
            },

            updateCustomVisibility: function () {
                var hasValues =
                    (filters.hltb_min !== null && filters.hltb_min !== undefined) ||
                    (filters.hltb_max !== null && filters.hltb_max !== undefined);
                var hasPreset = filters.hltb_preset && filters.hltb_preset !== "custom";
                this.showCustomRange = hasValues && !hasPreset;
            },

            selectPreset: function (preset) {
                if (filters.hltb_preset === preset) {
                    filters.hltb_preset = "";
                    filters.hltb_min = null;
                    filters.hltb_max = null;
                } else {
                    var ranges = {
                        short: [0, 10],
                        medium: [10, 30],
                        long: [30, null],
                    };
                    var parsed = ranges[preset] || [null, null];
                    filters.hltb_preset = preset;
                    filters.hltb_min = parsed[0];
                    filters.hltb_max = parsed[1];
                }
                this.dispatchFilterChange();
            },

            updateSlider: function () {
                if (filters.hltb_min !== null && filters.hltb_min < 0) {
                    filters.hltb_min = 0;
                }
                if (filters.hltb_max !== null && filters.hltb_max < 0) {
                    filters.hltb_max = 0;
                }
                if (filters.hltb_min !== null && filters.hltb_max !== null && filters.hltb_max < filters.hltb_min) {
                    filters.hltb_max = filters.hltb_min;
                }
                filters.hltb_preset = "custom";
                this.dispatchFilterChange();
            },

            dispatchFilterChange: function () {
                this.$dispatch("filter-changed", {
                    type: "hltb",
                    mode: filters.hltb_mode,
                    min: filters.hltb_min,
                    max: filters.hltb_max,
                });
            },

            isPresetActive: function (preset) {
                return filters.hltb_preset === preset;
            },

            getPresetCount: function (preset) {
                return this.presetCounts[preset] || 0;
            },

            getRangeText: function () {
                var min = filters.hltb_min !== null && filters.hltb_min !== undefined ? filters.hltb_min : 0;
                var max = filters.hltb_max !== null && filters.hltb_max !== undefined ? filters.hltb_max : 100;
                if (max >= 100) {
                    return min + "+ hours";
                }
                return min + "-" + max + " hours";
            },
        };
    }

    function createMobilePlatformFilterComponent(config) {
        var filters = config.filters;
        var component = createPlatformFilterComponent(config || {});
        if (!Array.isArray(filters.platforms)) {
            filters.platforms = [];
        }

        component.expanded = JSON.parse(localStorage.getItem("mobileFilterExpanded_platform") || "true");
        component.expandedManufacturers = {};
        component.expandedFormFactors = {};
        component.groupCounts = {};
        component.countsReady = false;
        component.platformHierarchy = createPlatformHierarchy();

        component.init = function () {
            var self = this;
            this.$watch("expanded", function (val) {
                localStorage.setItem("mobileFilterExpanded_platform", JSON.stringify(val));
            });
            this._platformCountsHandler = function (event) {
                self.updateFilteredCounts(event.detail);
                self.countsReady = true;
            };
            this._platformGroupCountsHandler = function (event) {
                self.groupCounts = event.detail;
                self.countsReady = true;
            };
            window.addEventListener("platform-counts-update", this._platformCountsHandler);
            window.addEventListener("platform-group-counts-update", this._platformGroupCountsHandler);
        };

        component.destroy = function () {
            if (this._platformCountsHandler) {
                window.removeEventListener("platform-counts-update", this._platformCountsHandler);
            }
            if (this._platformGroupCountsHandler) {
                window.removeEventListener("platform-group-counts-update", this._platformGroupCountsHandler);
            }
        };

        component.formatPlatformYears = function (platform) {
            if (!platform || !platform.year_start) {
                return "";
            }
            var startShort = String.fromCharCode(39) + String(platform.year_start).slice(-2);
            if (!platform.year_end) {
                return startShort + "-now";
            }
            if (platform.year_start === platform.year_end) {
                return startShort;
            }
            var endShort = String.fromCharCode(39) + String(platform.year_end).slice(-2);
            return startShort + "-" + endShort;
        };

        component.isManufacturerExpanded = function (mfrKey) {
            return this.expandedManufacturers[mfrKey] === true;
        };

        component.toggleManufacturerExpansion = function (mfrKey) {
            var self = this;
            var newState = !this.isManufacturerExpanded(mfrKey);
            this.expandedManufacturers[mfrKey] = newState;
            var mfr = this.platformHierarchy[mfrKey];
            if (mfr && mfr.formFactors) {
                Object.keys(mfr.formFactors).forEach(function (ffKey) {
                    self.expandedFormFactors[mfrKey + "_" + ffKey] = newState;
                });
            }
        };

        component.isFormFactorExpanded = function (mfrKey, ffKey) {
            return this.expandedFormFactors[mfrKey + "_" + ffKey] === true;
        };

        component.toggleFormFactorExpansion = function (mfrKey, ffKey) {
            var key = mfrKey + "_" + ffKey;
            this.expandedFormFactors[key] = !this.isFormFactorExpanded(mfrKey, ffKey);
        };

        component.selectedCount = function () {
            return filters.platforms.length;
        };

        component.clearPlatforms = function () {
            filters.platforms = [];
        };

        component.resetExpanded = function () {
            this.expandedManufacturers = {};
            this.expandedFormFactors = {};
        };

        component.areAllExpanded = function () {
            for (var _i2 = 0, _arr2 = Object.keys(this.platformHierarchy); _i2 < _arr2.length; _i2++) {
                var mfrKey = _arr2[_i2];
                if (!this.expandedManufacturers[mfrKey]) {
                    return false;
                }
            }
            return true;
        };

        component.toggleAllExpanded = function () {
            var shouldExpand = !this.areAllExpanded();
            for (var _i3 = 0, _arr3 = Object.keys(this.platformHierarchy); _i3 < _arr3.length; _i3++) {
                this.expandedManufacturers[_arr3[_i3]] = shouldExpand;
            }
        };

        return component;
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

    function createMobileSeriesFilterComponent(config) {
        var filters = config.filters;
        var seriesList = config.seriesList;
        var component = createSeriesFilterComponent(config || {});
        if (!Array.isArray(filters.series)) {
            filters.series = [];
        }

        component.expanded = JSON.parse(localStorage.getItem("mobileFilterExpanded_series") || "true");
        component.searchQuery = "";

        component.init = function () {
            var self = this;
            this.$watch("expanded", function (val) {
                localStorage.setItem("mobileFilterExpanded_series", JSON.stringify(val));
            });
            this.selectedSeries = (filters.series || []).slice();
            this._seriesCountsHandler = function (event) {
                self.updateFilteredCounts(event.detail);
            };
            window.addEventListener("series-counts-update", this._seriesCountsHandler);
        };

        component.destroy = function () {
            if (this._seriesCountsHandler) {
                window.removeEventListener("series-counts-update", this._seriesCountsHandler);
            }
        };

        component.updateFilteredCounts = function (countMap) {
            if (!seriesList) {
                return;
            }
            seriesList.forEach(function (s) {
                s.filtered_count = countMap[String(s.id)] || 0;
            });
        };

        defineComputed(component, "filteredSeries", function () {
            var self = this;
            var list = (seriesList || []).slice();
            if (this.searchQuery) {
                var query = this.normalizeSearchText(this.searchQuery);
                list = list.filter(function (s) {
                    return self.normalizeSearchText(s.name).includes(query);
                });
            }
            list.sort(function (a, b) {
                var countDiff = self.getEffectiveCount(b) - self.getEffectiveCount(a);
                if (countDiff !== 0) {
                    return countDiff;
                }
                return a.name.localeCompare(b.name);
            });
            return list;
        });

        component.isSeriesSelected = function (seriesId) {
            return (filters.series || []).includes(String(seriesId));
        };

        component.isSelected = function (seriesId) {
            return this.isSeriesSelected(seriesId);
        };

        component.toggleSeries = function (seriesId) {
            var id = String(seriesId);
            if (filters.series.includes(id)) {
                filters.series = [];
            } else {
                filters.series = [id];
            }
            this.selectedSeries = filters.series.slice();
        };

        component.isSeriesActive = function () {
            return (filters.series || []).length > 0;
        };

        component.clearSeries = function () {
            filters.series = [];
            this.selectedSeries = [];
            this.searchQuery = "";
        };

        return component;
    }

    function createMobileTimeFilterComponent(config) {
        var filters = config.filters;
        var minYear = config.minYear;
        var maxYear = config.maxYear;

        return {
            expanded: JSON.parse(localStorage.getItem("mobileFilterExpanded_time") || "true"),
            mode: "decade",
            decades: [
                { label: "1970s", start: 1970, end: 1979 },
                { label: "1980s", start: 1980, end: 1989 },
                { label: "1990s", start: 1990, end: 1999 },
                { label: "2000s", start: 2000, end: 2009 },
                { label: "2010s", start: 2010, end: 2019 },
                { label: "2020s", start: 2020, end: 2029 },
            ],

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

    function registerFactories() {
        Alpine.data("platformFilterComponent", function (config) {
            return createPlatformFilterComponent(config || {});
        });
        Alpine.data("genreFilterComponent", function (config) {
            return createGenreFilterComponent(config || {});
        });
        Alpine.data("yearGridComponent", function (config) {
            return createYearGridComponent(config || {});
        });
        Alpine.data("seriesFilterComponent", function (config) {
            return createSeriesFilterComponent(config || {});
        });
        Alpine.data("hltbFilterComponent", function (config) {
            return createHltbFilterComponent(config || {});
        });

        Alpine.data("mobilePlatformFilterComponent", function (config) {
            return createMobilePlatformFilterComponent(config || {});
        });
        Alpine.data("mobileGenreFilterComponent", function (config) {
            return createMobileGenreFilterComponent(config || {});
        });
        Alpine.data("mobileSeriesFilterComponent", function (config) {
            return createMobileSeriesFilterComponent(config || {});
        });
        Alpine.data("mobileTimeFilterComponent", function (config) {
            return createMobileTimeFilterComponent(config || {});
        });
    }

    document.addEventListener("alpine:init", registerFactories);
})();
