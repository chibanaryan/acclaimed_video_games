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
            delete this.$route.meta.ssrData; // Clean up to avoid memory leaks
            console.log('[SSG] Using pre-fetched game data');
            this.loading = false; // SSR already supplied data, stop spinner
        } else {
            // Client-side navigation or no SSR data - fetch normally
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

            this.loading = true;
            this.error = null;

            if (controller)
                controller.abort();

            controller = new AbortController();
            let url = `${getApiUrl()}games/?${new URLSearchParams(this.getArgs)}`;

            try {
                const response = await fetch(url, { signal: controller.signal });

                if (!response.ok) {
                    this.error = `Failed to load games (${response.status})`;
                    return;
                }

                const data = await response.json();
                this.items = data.results.map((x) => new Game(x));
                this.resultsCount = data.count;
            } catch (err) {
                // Ignore abort errors (user navigated away or initiated new search)
                if (err.name === 'AbortError') {
                    return;
                }
                console.error('Error loading games:', err);
                this.error = 'Network error - please check your connection and try again';
            } finally {
                controller = null;
                this.loading = false;

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
        async onPageChange(e) {
            Object.assign(this.pagination, e);
            this.updateUrl();
        },
        onFormChange() {
            this.pagination.offset = 0;
            this.updateUrl();
        }
    },
}
</script>
