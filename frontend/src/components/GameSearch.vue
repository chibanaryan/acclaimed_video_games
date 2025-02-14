<template>
    <h1 class="title">
        <span v-html="pageTitle"></span>
    </h1>
    <div class="buttons is-pulled-right">
        <a @click="clearFilters"
            v-if="isFiltered"
            class="is-hidden-mobile button">
            <span class="icon">
                <span class="mdi mdi-close"></span>
            </span>
            <span>Clear filters</span>
        </a>
        <a @click="clearFilters"
            v-if="isFiltered"
            class="is-hidden-tablet button">
            <span class="icon">
                <span class="mdi mdi-close"></span>
            </span>
        </a>
        <router-link :to="{ name: 'games-list' }"
            class="button is-link is-pulled-right">
            <span class="icon">
                <span class="mdi mdi-form-select">
                </span>
            </span>
            <span>
                Basic Search
            </span>
        </router-link>
    </div>
    <advanced-filters v-model="filters"
        :genres="genres"
        :platforms="platforms"
        @change="onFormChange"></advanced-filters>
    <div v-if="items"
        class="mt-5">
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
            :index="pagination.offset + index + 1"
            :key="game.id"
            :game="game"
            :highlight="highlight"
            :show-rank="filters.rank_display"></game-row>
        <pagination-component :total="resultsCount"
            :limit="pagination.limit"
            :offset="pagination.offset"
            :show-all-pages="true"
            @pagechanged="onPageChange"
            class="mt-5 is-hidden-mobile">
        </pagination-component>
        <pagination-component :total="resultsCount"
            :limit="pagination.limit"
            :offset="pagination.offset"
            @pagechanged="onPageChange"
            class="mt-5 is-hidden-tablet">
        </pagination-component>
    </div>
</template>

<script>
import { loadPreviousScrollPosition } from "@/utils";
import { isEmpty, isString } from "lodash";
import Game from "../models/Game";
import AdvancedFilters from './AdvancedFilters.vue';
import GameRow from "./GameRow";
import PaginationComponent from "./PaginationComponent";

let controller = null;

export default {
    components: {
        AdvancedFilters,
        GameRow,
        PaginationComponent,
    },
    data() {
        return {
            filters: {
                q: null,
                start: 1970,
                end: new Date().getFullYear(),
                genres: [],
                platforms: [],
                genre_option: 'L',
                rank_display: 'alltime',
            },
            items: [],
            genres: [],
            platforms: [],
            pagination: {
                limit: 100,
                offset: 0,
            },
            resultsCount: 0,
            meta: {},
        };
    },
    async created() {
        this.$store.commit("setLoading", true);

        await this.$store.dispatch('loadGenres');
        this.genres = this.$store.state.genres;

        await this.$store.dispatch('loadPlatforms');
        this.platforms = this.$store.state.platforms;

        await this.$store.dispatch('loadMeta');
        this.meta = this.$store.state.meta;

        this.updateFilters(this.$route.query);
        await this.loadItems();

        this.$store.commit("setLoading", false);

        loadPreviousScrollPosition(this.$route.name)
    },
    computed: {
        minYear() {
            if (this.meta?.games?.years.length)
                return this.meta.games.years[0]['year'];
            else
                return 1970;
        },
        maxYear() {
            return new Date().getFullYear();
        },
        pageTitle() {
            if (this.$store.state.loading)
                return "Loading&hellip;";

            let start = this.pagination.offset + 1;
            let end = this.pagination.offset + this.pagination.limit;

            if (end > this.resultsCount)
                end = this.resultsCount;

            return `Showing ${start.toLocaleString()} to ${end.toLocaleString()} of ${this.resultsCount.toLocaleString()} Results`;
        },
        isFiltered() {
            if (!this.filters)
                return false;
            else
                return this.filters.q ||
                    this.filters.genres.length ||
                    this.filters.platforms.length ||
                    this.filters.start != this.minYear ||
                    this.filters.end != this.maxYear;
        },
    },
    methods: {
        clearFilters() {
            this.filters = {
                q: null,
                start: null,
                end: null,
                genres: [],
                platforms: [],
                genre_option: "L",
            };

            this.filters.start = this.minYear;
            this.filters.end = this.maxYear;
            this.updateUrl();
        },
        getUrlArgs() {
            let args = {};
            args.rank_display = this.filters.rank_display;
            args.genre_option = this.filters.genre_option;
            args.limit = this.pagination.limit;
            args.offset = this.pagination.offset;

            if (this.filters.start)
                args.start = this.filters.start;

            if (this.filters.end)
                args.end = this.filters.end;

            if (this.filters.q)
                args.q = this.filters.q;

            if (this.filters.genres.length)
                args.genres = this.filters.genres.filter(x => x).map((x) => x.id).join(",");

            if (this.filters.platforms.length)
                args.platforms = this.filters.platforms.filter(x => x).map((x) => x.id).join(",");

            return args;
        },
        updateFilters(args) {

            if (isEmpty(args))
                return;

            if (args.start)
                args.start = parseInt(args.start);
            else
                args.start = this.minYear;

            if (args.end)
                args.end = parseInt(args.end);
            else
                args.end = this.maxYear;

            if (args.limit)
                this.pagination.limit = parseInt(args.limit);

            if (args.offset)
                this.pagination.offset = parseInt(args.offset);

            if (isString(args.genres)) {
                let ids = args.genres.split(',').map(x => parseInt(x));
                args.genres = this.genres.filter(x => ids.includes(x.id));
            }

            if (isString(args.platforms)) {
                let ids = args.platforms.split(',').filter(x => x).map(x => parseInt(x));
                args.platforms = this.platforms.filter(x => ids.includes(x.id));
            }

            Object.assign(this.filters, args);
        },
        async updateUrl() {
            let newRoute = {
                name: 'games-search',
                query: this.getUrlArgs(),
            };
            this.$router.push(newRoute);
            await this.loadItems();
        },
        async loadItems() {
            if (controller)
                controller.abort();

            controller = new AbortController();

            let url = `${process.env.VUE_APP_API_URL}games/?${new URLSearchParams(this.getUrlArgs())}`;

            try {
                let data = await fetch(url, { signal: controller.signal })
                    .then((resp) => resp.json());

                this.items = data.results.map((x) => new Game(x));
                this.resultsCount = data.count;
            } catch (err) {
                // Do nothing
            } finally {
                controller = null;

                if (this.highlight)
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
        onFormChange() {
            //console.log('onFormChange');
            
            this.pagination.offset = 0;
            this.updateUrl();
        },
        async onPageChange(e) {
            Object.assign(this.pagination, e);
            this.updateUrl();
        },
    },
}
</script>