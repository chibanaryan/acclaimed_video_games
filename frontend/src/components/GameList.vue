<template>
    <h1 class="title">
        <template v-if="mode == 'simple'">
            Most Acclaimed Games of {{ prettySlug }}
        </template>
        <template v-else> {{ pageTitle }} Results </template>
    </h1>

    <div class="buttons is-pulled-right">
        <a v-if="mode == 'simple'"
            @click="mode = 'advanced'"
            class="button is-link">
            <span class="icon">
                <span class="mdi mdi-tune-variant"></span>
            </span>
            <span>Advanced Filters</span>
        </a>
        <a v-if="mode == 'advanced'"
            @click="mode = 'simple'"
            class="button is-link">
            <span class="icon">
                <span class="mdi mdi-form-select"></span>
            </span>
            <span> Simple Filters </span>
        </a>
    </div>

    <!-- Advanced filters -->
    <advanced-filters v-if="mode == 'advanced'"
        v-model="filters"></advanced-filters>

    <!-- Simple filters -->
    <simple-filters v-if="mode == 'simple'"
        v-model="simpleFilters"></simple-filters>

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
                :show-rank="showRank"></game-row>

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
import { cleanData, parseSlug } from "@/utils.js";
import Game from "../models/Game";
import AdvancedFilters from "./AdvancedFilters";
import BaseListComponent from "./BaseListComponent";
import GameRow from "./GameRow";
import PaginationComponent from "./PaginationComponent";
import SimpleFilters from "./SimpleFilters";
import objectStore from "@/objectStore";

let controller = null;

export default {
    mixins: [BaseListComponent],
    components: {
        AdvancedFilters,
        GameRow,
        PaginationComponent,
        SimpleFilters,
    },
    data() {
        return {
            filters: {
                q: null,
                start: null,
                end: null,
                genres: [],
                platforms: [],
                genre_option: "L",
            },
            pagination: {
                limit: 100,
                offset: 0,
            },
            simpleFilters: {
                year: null,
                decade: null,
                alltime: null,
            },
            mode: "simple",
            //loading: false,
            //highlight: null,
            initialized: false,
            showRank: 'alltime',
            genres: [],
            platforms: [],
        };
    },
    async mounted() {
        //this.highlight = this.$route.query.highlight;
        this.$store.commit("setLoading", true);
        //await this.init();

        await this.$store.dispatch('loadGenres');
        this.genres = this.$store.state.genres;

        await this.$store.dispatch('loadPlatforms');
        this.platforms = this.$store.state.platforms;

        this.mode = localStorage.gamesListMode || this.mode;

        this.$store.commit("setLoading", false);
    },
    computed: {
        highlight() {
            return this.$route.query.highlight;
        },
        cleanedFilters() {
            //console.log('GamesList cleanedFilters');
            //console.log(JSON.stringify(this.filters));
            //console.log(JSON.stringify(this.filters));

            let filters = cleanData(this.filters);

            if (!filters.start)
                delete filters.start;

            if (!filters.end)
                delete filters.end;

            if (filters.genres?.length)
                filters.genres = filters.genres.filter(x => x).map((x) => x.id).join(",");

            if (filters.platforms?.length)
                filters.platforms = filters.platforms.filter(x => x).map((x) => x.id).join(",");

            if (this.mode == 'simple') {
                delete filters.genre_option;

                if (filters.start == this.minYear)
                    delete filters.start;

                if (filters.end == this.maxYear)
                    delete filters.end;
            }

            filters.limit = this.pagination.limit;
            filters.offset = this.pagination.offset;

            return filters;
        },
        prettySlug() {
            if (this.simpleFilters?.year)
                return this.simpleFilters.year;
            else if (this.simpleFilters?.decade)
                return this.simpleFilters.decade;
            else
                return 'All Time';
        },
    },
    methods: {
        async init() {
            //console.log(this.$route.query);
            this.filters.start = this.filters.start || this.minYear;
            this.filters.end = this.filters.end || this.maxYear;

            this.loadFilters(this.$route.query);
            await this.loadItems();

            if (objectStore.get('lastQuery')) {
                this.loadFilters(objectStore.get('lastQuery'));
                objectStore.set('lastQuery', null);
            }

            setTimeout(() => {
                this.initialized = true;

            }, 1000)
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
        loadFilters(args) {
            //let args = this.$route.query;// || new URL(location.href).searchParams;

            if (args.platforms) {
                let ids = args.platforms.split(',').map(x => parseInt(x))
                this.filters.platforms = this.platforms.filter((x) => ids.includes(x.id));
            }

            if (args.genres) {
                let ids = args.genres.split(',').map(x => parseInt(x))
                this.filters.genres = this.genres.filter((x) => ids.includes(x.id));
            }

            if (args.limit)
                this.pagination.limit = parseInt(args.limit);

            if (args.offset)
                this.pagination.offset = parseInt(args.offset);

            if (args.q)
                this.filters.q = args.q;

            if (args.start)
                this.filters.start = args.start;

            if (args.end)
                this.filters.end = args.end;

            if (args.start && args.end)
                if (args.start == args.end)
                    this.simpleFilters.year = args.start;
                else
                    this.simpleFilters.decade = `${args.start}-${args.end.toString().substring(2, 4)}`;

            console.log(this.filters);

        },
        resetOffset() {
            if (this.initialized)
                this.pagination.offset = 0;
        },
    },
    watch: {
        "simpleFilters.alltime": function (val) {
            if (!val)
                return;

            this.showRank = 'alltime';
            this.filters.start = null;
            this.filters.end = null;

            this.$route.params.slug = 'alltime';

            this.resetOffset();
        },
        "simpleFilters.year": function (val) {
            if (!val)
                return;

            this.showRank = 'filtered';
            this.filters.start = this.simpleFilters?.year;
            this.filters.end = this.simpleFilters?.year;

            this.$route.params.slug = this.simpleFilters.year;

            this.resetOffset();
        },
        "simpleFilters.decade": function (val) {
            if (!val)
                return;

            this.showRank = 'filtered';
            let { start, end } = parseSlug(this.simpleFilters.decade);
            this.filters.start = start;
            this.filters.end = end;

            this.$route.params.slug = this.simpleFilters.decade;

            this.resetOffset()
        },
        mode(val) {
            if (val == 'advanced')
                this.$route.params.slug = 'search';
            else if (val == 'simple')
                this.$route.params.slug = 'alltime';

            localStorage.gamesListMode = val;
        },
        simpleFilters: {
            handler() {
                this.resetOffset();
            },
            deep: true,
        },
        filters: {
            handler() {
                this.resetOffset();
            },
            deep: true,
        },
    },
};
</script>