<template>
    <h1 class="title">
        {{ pageTitle }} Results
    </h1>

    <router-link :to="{ name: 'games-list' }"
        class="button is-link is-pulled-right">
        <span class="icon">
            <span class="mdi mdi-form-select"></span>
        </span>
        <span>
            Basic Search
        </span>
    </router-link>

    <advanced-filters v-model="filters"></advanced-filters>

    <!-- <div class="columns">
        <div class="column">
            filters
            <pre>{{ filters }}</pre>
        </div>
        <div class="column">
            cleanedFilters
            <pre>{{ cleanedFilters }}</pre>
        </div>
        <div class="column">
            urlArgs
            <pre>{{ urlArgs }}</pre>
        </div>
    </div> -->

    <div v-if="items"
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

        </template>
    </div>
</template>

<script>
import { objectStore } from "@/objectStore";
import { cleanData } from "@/utils";
import { isArray, isEmpty, isString } from "lodash";
import Game from "../models/Game";
import AdvancedFilters from "./AdvancedFilters";
import BaseListComponent from "./BaseListComponent";
import GameRow from "./GameRow";
import PaginationComponent from "./PaginationComponent";

let controller = null;

export default {
    mixins: [BaseListComponent],
    components: {
        GameRow,
        PaginationComponent,
        AdvancedFilters,
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
            genres: [],
            platforms: [],
            pagination: {
                limit: 100,
                offset: 0,
            },
            objectStore: objectStore(this.$route.name),
        };
    },
    async created() {
        this.$store.commit("setLoading", true);

        await this.$store.dispatch('loadGenres');
        this.genres = this.$store.state.genres;

        await this.$store.dispatch('loadPlatforms');
        this.platforms = this.$store.state.platforms;

        this.$store.commit("setLoading", false);
    },
    computed: {
        /** Convert filters to post data */
        cleanedFilters() {
            let filters = cleanData(this.filters);

            delete filters.rank_display;

            if (isArray(filters.genres))
                filters.genres = filters.genres.filter(x => x).map((x) => x.id).join(",");

            if (isArray(filters.platforms))
                filters.platforms = filters.platforms.filter(x => x).map((x) => x.id).join(",");

            filters.limit = this.pagination.limit;
            filters.offset = this.pagination.offset;

            return filters;
        },
        /** Convert filters to URL parameters */
        urlArgs() {
            let filters = cleanData(this.filters);

            if (isArray(filters.genres))
                filters.genres = filters.genres.map((x) => x.id).join(",");

            if (isArray(filters.platforms))
                filters.platforms = filters.platforms.map((x) => x.id).join(",");

            filters.limit = this.pagination.limit;
            filters.offset = this.pagination.offset;

            return filters;
        },
    },
    methods: {
        async init() {
            await this.$store.dispatch('loadGenres');
            this.genres = this.$store.state.genres;

            await this.$store.dispatch('loadPlatforms');
            this.platforms = this.$store.state.platforms;

            let savedFilters = this.objectStore.get('filters');
            if (savedFilters) {
                this.updateFilters(savedFilters);
                this.updateUrl();
                this.objectStore.set('filters', null)
            } else {
                this.updateFilters(this.$route.query);
            }

            await this.loadItems();
        },
        /** Populate filters from URL args or local storage */
        updateFilters(args) {
            if (isEmpty(args))
                return;

            if (args.limit) {
                this.pagination.limit = parseInt(args.limit);
                delete args.limit;
            }

            if (args.offset) {
                this.pagination.offset = parseInt(args.offset);
                delete args.offset;
            }

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
        async loadItems() {
            if (controller)
                controller.abort();

            controller = new AbortController();

            let url = `${process.env.VUE_APP_API_URL}games/?${new URLSearchParams(this.cleanedFilters)}`;

            try {
                let data = await fetch(url, { signal: controller.signal })
                    .then((resp) => resp.json());

                this.items = data.results.map((x) => new Game(x));
                this.resultsCount = data.count;
            } catch (err) {
                // Do nothing
            } finally {
                controller = null;

                setTimeout(() => {
                    let highlightElement = document.getElementById(`game-${this.highlight}`);
                    if (highlightElement) {
                        highlightElement.scrollIntoView({ behavior: "smooth" });
                    }
                }, 1000)

            }
        },
    },
    beforeRouteLeave() {
        this.objectStore.set('filters', this.urlArgs);
    },
}
</script>