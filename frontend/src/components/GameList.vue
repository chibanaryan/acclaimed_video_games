<template>
    <h1 class="title">
        {{ pageTitle }}
    </h1>
    <div class="is-clearfix">
        <simple-filters v-model="filters"
            @change="onFormChange"
            class="is-pulled-left"></simple-filters>
        <div class="is-pulled-right">
            <router-link :to="{ name: 'games-search' }"
                class="button is-link is-hidden-mobile">
                <span class="icon is-small">
                    <span class="mdi mdi-tune-variant">
                    </span>
                </span>
                <span>
                    Advanced Search
                </span>
            </router-link>
            <router-link :to="{ name: 'games-search' }"
                class="button is-link is-hidden-tablet">
                <span class="icon is-small">
                    <span class="mdi mdi-tune-variant">
                    </span>
                </span>
            </router-link>
        </div>
    </div>
    <div v-if="error" class="notification is-danger mt-5">
        <p><strong>Error:</strong> {{ error }}</p>
    </div>
    <div v-else-if="items"
        class="mt-5">
        <template v-if="!loading">
            <pagination-component :total="resultsCount"
                :limit="pagination.limit"
                :offset="pagination.offset"
                :show-all-pages="true"
                @pagechanged="onPageChange"
                class="is-hidden-mobile">
            </pagination-component>
            <pagination-component :total="resultsCount"
                :limit="pagination.limit"
                :offset="pagination.offset"
                @pagechanged="onPageChange"
                class="is-hidden-tablet">
            </pagination-component>

            <game-row v-for="(game, index) in items"
                :index="parseInt(pagination.offset) + index + 1"
                :show-rank="isFiltered ? 'filtered' : 'alltime'"
                :show-rank-in-details="isFiltered"
                :key="game.id"
                :game="game"
                :highlight="highlight"></game-row>

            <pagination-component :total="resultsCount"
                :limit="pagination.limit"
                :offset="pagination.offset"
                :show-all-pages="true"
                @pagechanged="onPageChange"
                class="is-hidden-mobile">
            </pagination-component>
            <pagination-component :total="resultsCount"
                :limit="pagination.limit"
                :offset="pagination.offset"
                @pagechanged="onPageChange"
                class="is-hidden-tablet mt-3">
            </pagination-component>
        </template>
    </div>
</template>

<script>
import { getApiUrl } from "@/config";
import { loadPreviousScrollPosition, parseSlug } from "@/utils";
import Game from "../models/Game";
import GameRow from "./GameRow";
import PaginationComponent from "./PaginationComponent";
import SimpleFilters from "./SimpleFilters";

let controller = null;

export default {
    components: {
        GameRow,
        PaginationComponent,
        SimpleFilters,
    },
    data() {
        return {
            filters: {
                year: null,
                decade: null,
            },
            pagination: {
                limit: 100,
                offset: 0,
            },
            highlight: null,
            resultsCount: 0,
            items: [],
            loading: false,
            error: null,
            allGames: null, // Store the complete unfiltered list for client-side pagination
        }
    },
    async created() {
        // Check if we have SSR pre-fetched data (from beforeEnter guard)
        const ssrData = this.$route.meta?.ssrData;

        if (ssrData) {
            // Use pre-fetched data during SSG/initial hydration
            this.items = ssrData.results.map((x) => new Game(x));
            this.resultsCount = ssrData.count;
            this.updateFilters(this.$route.query);

            // Cache the SSR data in the store for later reuse
            // For unfiltered views, cache it under 'all' key so client-side pagination reuses it
            const isFiltered = this.filters.decade || this.filters.year;
            const queryKey = isFiltered ? new URLSearchParams(this.getArgs).toString() : 'all';
            this.$store.commit('setGamesList', {
                queryKey,
                result: { results: this.items, count: this.resultsCount }
            });

            // For unfiltered views, set allGames so client-side pagination works
            if (!isFiltered) {
                this.allGames = this.items;
            }

            delete this.$route.meta.ssrData; // Clean up to avoid memory leaks
            console.log('[SSG] Using pre-fetched game data and caching in store');
            this.loading = false; // SSR already supplied data, stop spinner
        } else {
            // Client-side navigation - use store (with cache check)
            this.updateFilters(this.$route.query);
            await this.loadItems();
        }

        loadPreviousScrollPosition();
    },
    computed: {
        isFiltered() {
            return this.filters.decade || this.filters.year;
        },
        pageTitle() {
            let bits = ['Most Acclaimed Games of'];

            if (this.filters?.year)
                bits.push(this.filters.year);
            else if (this.filters?.decade)
                bits.push(this.filters.decade);
            else
                bits.push('All Time');

            return bits.join(' ');
        },
        shortPageTitle() {
            if (this.filters.decade) {
                let slug = parseSlug(this.filters.decade);
                return `${slug.start}s`;
            } else if (this.filters.year) {
                return this.filters.year;
            } else {
                return 'All time';
            }
        },
        getArgs() {
            let args = {};

            if (this.filters.decade) {
                let { start, end } = parseSlug(this.filters.decade);
                args.start = start;
                args.end = end;
            } else if (this.filters.year) {
                args.start = this.filters.year;
                args.end = this.filters.year;
            }

            args.limit = this.pagination.limit;
            args.offset = this.pagination.offset;

            if (this.highlight)
                args.highlight = this.highlight;

            return args;
        },
    },
    methods: {
        async clearFilters() {
            this.filters.year = null;
            this.filters.decade = null;
            this.$router.push({
                name: 'games-list',
            });
            await this.loadItems();
        },
        updateFilters(args) {
            if (args.start && args.end) {
                if (args.start == args.end)
                    this.filters.year = args.start;
                else
                    this.filters.decade = `${args.start}-${args.end.substring(2, 4)}`;
            }

            if (args.limit)
                this.pagination.limit = args.limit;

            if (args.offset)
                this.pagination.offset = args.offset;

            if (args.highlight)
                this.highlight = args.highlight;

        },
        async updateUrl() {
            let newRoute = {
                name: 'games-list',
                query: this.getArgs,
            };
            this.$router.push(newRoute);
            await this.loadItems();
            this.emitter.emit('title', this.shortPageTitle);
        },
        async loadItems() {
            this.error = null;

            if (controller)
                controller.abort();

            controller = new AbortController();

            try {
                // Check if this is the default unfiltered view
                if (!this.isFiltered) {
                    // For the default view, fetch all games once and use client-side pagination
                    if (!this.allGames) {
                        // Check if we already have the complete list cached
                        const cachedAll = this.$store.state.gamesLists['all'];

                        if (!cachedAll) {
                            this.loading = true;
                        }

                        const data = await this.$store.dispatch('fetchAllGamesList');
                        this.allGames = data.results;
                        this.resultsCount = data.count;
                    }

                    // Client-side pagination: slice the complete list
                    const start = parseInt(this.pagination.offset) || 0;
                    const end = start + parseInt(this.pagination.limit);
                    this.items = this.allGames.slice(start, end);
                    this.loading = false;
                } else {
                    // For filtered views (year/decade), use API pagination
                    const queryKey = new URLSearchParams(this.getArgs).toString();
                    const cachedData = this.$store.state.gamesLists[queryKey];

                    if (!cachedData) {
                        // Only show loading if we need to fetch
                        this.loading = true;
                    }

                    // Use store action which checks cache first
                    const data = await this.$store.dispatch('fetchGamesList', {
                        queryParams: this.getArgs,
                        force: false // Use cache if available
                    });

                    this.items = data.results;
                    this.resultsCount = data.count;
                    this.loading = false;
                }
            } catch (err) {
                // Ignore abort errors (user navigated away or initiated new search)
                if (err.name === 'AbortError') {
                    return;
                }
                console.error('Error loading games:', err);
                if (err.status === 404) {
                    this.error = 'No games found';
                } else if (err.status > 0) {
                    this.error = `Failed to load games (${err.status})`;
                } else {
                    this.error = 'Network error - please check your connection and try again';
                }
                this.loading = false;
            } finally {
                controller = null;

                if (this.highlight && !this.error)
                    setTimeout(() => {
                        let highlightElement = document.getElementById(`game-${this.highlight}`);
                        if (highlightElement) {
                            highlightElement.scrollIntoView({ behavior: "smooth" });

                            setTimeout(() => {
                                this.highlight = null;
                            }, 2000);
                        }
                    }, 1000)
            }
        },
        onPageChange(e) {
            Object.assign(this.pagination, e);

            // For client-side pagination (unfiltered view), update data immediately without router navigation
            if (!this.isFiltered) {
                const start = parseInt(this.pagination.offset) || 0;
                const end = start + parseInt(this.pagination.limit);
                this.items = this.allGames.slice(start, end);

                // Instant scroll to top
                window.scrollTo(0, 0);

                // Update URL asynchronously (non-blocking)
                this.$nextTick(() => {
                    const newQuery = this.getArgs;
                    this.$router.replace({ name: 'games-list', query: newQuery });
                });
            } else {
                // For filtered views, use the existing updateUrl flow
                this.updateUrl();
            }
        },
        onFormChange() {
            this.pagination.offset = 0;
            // When switching between filtered/unfiltered, ensure we use the right data source
            if (this.isFiltered) {
                // Switching to a filtered view - clear allGames to force API fetch
                this.allGames = null;
            }
            this.updateUrl();
        }
    },
}
</script>
