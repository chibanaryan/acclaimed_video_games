<template>
    <div class="control is-pulled-right">
        <router-link :to="{ name: 'games-list', params: { slug: 'search' } }"
            v-if="mode == 'simple'"
            class="button is-link">
            Advanced Filters
        </router-link>
        <router-link :to="{ name: 'games-list', params: { slug: 'alltime' } }"
            v-if="mode == 'advanced'"
            class="button is-link">
            Simple Filters
        </router-link>
    </div>
    <h1 class="title">
        <template v-if="mode == 'simple'">
            Most Acclaimed Games of {{ prettySlug }}
        </template>
        <template v-else>
            {{ pageTitle }} Results
        </template>
    </h1>
    <div v-if="mode == 'advanced'">
        <div class="control is-pulled-right ml-5">
            <a @click="clearFilters"
                v-if="isFiltered"
                class="button">
                <span class="icon">
                    <span class="mdi mdi-close"></span>
                </span>
                <span>Clear filters</span>
            </a>
        </div>
        <div class="field is-grouped is-grouped-multiline filters">
            <div class="control is-expanded">
                <input type="text"
                    v-model="filters.q"
                    class="input"
                    placeholder="Search">
            </div>
            <div class="control">
                <input type="number"
                    v-model="filters.start"
                    class="input"
                    placeholder="Start year">
            </div>
            <div class="control">
                <input type="number"
                    v-model="filters.end"
                    class="input"
                    placeholder="End year">
            </div>
        </div>
        <div class="field is-grouped is-grouped-multiline filters">
            <div v-if="genres.length">
                <div class="p-2">
                    <div class="control is-pulled-right">
                        <label class="radio">
                            All
                            <input v-model="filters.genre_option"
                                type="radio"
                                value="L">
                        </label>
                        <label class="radio">
                            Any
                            <input v-model="filters.genre_option"
                                type="radio"
                                value="A">
                        </label>
                    </div>
                    <label>Genres</label>
                </div>
                <div v-if="filters.genres?.length"
                    class="tags">
                    <span v-for="genre in filters.genres"
                        :key="genre.id"
                        class="tag is-primary">{{ genre.name }}</span>
                </div>
                <select v-model="filters.genres"
                    multiple
                    class="is-hidden-tablet">
                    <option :value="null">All genres</option>
                    <option v-for="genre in genres"
                        :key="genre.id"
                        :value="genre">{{ genre.name }}</option>
                </select>
                <multi-select-component :items="genres"
                    v-model="filters.genres"
                    class="is-hidden-mobile"></multi-select-component>
            </div>
            <div v-if="platforms.length">
                <div class="p-2">
                    <label>Platforms</label>
                </div>
                <div v-if="filters.platforms?.length"
                    class="tags">
                    <span v-for="platform in filters.platforms"
                        :key="platform.id"
                        class="tag is-primary">{{ platform.name
                        }}</span>
                </div>
                <select v-model="filters.platforms"
                    multiple
                    class="is-hidden-tablet">
                    <option :value="null">All platforms</option>
                    <option v-for="platform in platforms"
                        :key="platform.id"
                        :value="platform">{{ platform.name }}</option>
                </select>
                <multi-select-component :items="platforms"
                    v-model="filters.platforms"
                    class="is-hidden-mobile"></multi-select-component>
            </div>
        </div>
    </div>
    <div v-if="mode == 'simple'">
        <div class="field is-grouped is-multiline">
            <div class="control">
                <a @click="selected.alltime = true"
                    class="button is-link">
                    All time
                </a>
            </div>
            <div class="control">
                <div class="select">
                    <select v-model="selected.decade">
                        <option :value="null">All decades</option>
                        <option v-for="decade in meta.games.decades"
                            :key="decade"
                            :value="decade">{{ decade }}</option>
                    </select>
                </div>
            </div>
            <div class="control">
                <div class="select">
                    <select v-model="selected.year">
                        <option :value="null">All years</option>
                        <option v-for="year in meta.games.years"
                            :key="year.year"
                            :value="year.year">{{ year.year }} ({{
                            year.count }})</option>
                    </select>
                </div>
            </div>
            <div class="control is-expanded">
                <input type="text"
                    v-model="filters.q"
                    class="input"
                    placeholder="Search">
            </div>
            <div class="control">
                <a @click="clearFilters"
                    v-if="isFiltered"
                    class="button">
                    <span class="icon">
                        <span class="mdi mdi-close"></span>
                    </span>
                    <span>Clear filters</span>
                </a>
            </div>
        </div>
    </div>
    <div v-if="items"
        class="mt-5">
        <pagination-component :total="resultsCount"
            :limit="filters.limit"
            :offset="filters.offset"
            @pagechanged="onPageChange">
        </pagination-component>
        <game-row v-for="game in items"
            :key="game.id"
            :game="game"></game-row>
        <pagination-component :total="resultsCount"
            :limit="filters.limit"
            :offset="filters.offset"
            @pagechanged="onPageChange">
        </pagination-component>
    </div>
</template>


<script>
import { cleanData, parseSlug } from "@/utils.js";
import Game from '../models/Game';
import Genre from '../models/Genre';
import Platform from '../models/Platform';
import BaseListComponent from './BaseListComponent';
import GameRow from './GameRow';
import MultiSelectComponent from './MultiSelectComponent';
import PaginationComponent from './PaginationComponent';
import _ from "lodash";

export default {
    mixins: [BaseListComponent],
    components: {
        GameRow,
        PaginationComponent,
        MultiSelectComponent
    },
    data() {
        return {
            filters: {
                q: null,
                limit: 100,
                offset: 0,
                start: null,
                end: null,
                genres: [],
                platforms: [],
                genre_option: 'A',
            },
            selected: {
                year: null,
                decade: null,
                alltime: null,
            },
            genres: [],
            platforms: [],
            mode: 'simple',
        }
    },
    async created() {
        await this.init();
    },
    computed: {
        cleanedFilters() {
            let filters = Object.assign({}, cleanData(this.filters));

            if (filters.genres.length)
                filters.genres = filters.genres.map(x => x.id).join(',');

            if (filters.platforms.length)
                filters.platforms = filters.platforms.map(x => x.id).join(',');

            return new URLSearchParams(filters);
        },
        prettySlug() {
            const slug = this.$route.params.slug;
            if (!slug)
                return null;
            else if (slug == 'alltime')
                return 'All Time';
            else if (slug.includes('-'))
                return `the ${slug.split('-')[0]}s`;
            else
                return slug;
        },
    },
    methods: {
        async init() {
            if (this.$route.params.slug == 'search') {
                this.mode = 'advanced';
            } else {
                let { start, end } = parseSlug(this.$route.params.slug);
                this.filters.start = start;
                this.filters.end = end;
                this.mode = 'simple';
            }

            let data = await fetch(`${process.env.VUE_APP_API_URL}genres/`)
                .then(resp => resp.json());
            this.genres = data.results.map(x => new Genre(x));

            data = await fetch(`${process.env.VUE_APP_API_URL}platforms/`)
                .then(resp => resp.json());
            this.platforms = data.results.map(x => new Platform(x));

            this.loadUrlArgs();
        },
        loadItems: _.debounce(async function () {
            this.$store.commit('loading', true);
            let url = `${process.env.VUE_APP_API_URL}games/?${this.cleanedFilters}`;
            let data = await fetch(url)
                .then(resp => resp.json());
            this.items = data.results.map(x => new Game(x));
            this.resultsCount = data.count;
            this.$store.commit('loading', false);
        }, 200),
        async loadUrlArgs() {
            if (!this.genres.length || !this.platforms.length)
                return;

            let args = this.$route.query;
            if (!args)
                return;

            if (args.platforms) {
                let platformId = parseInt(args.platforms);
                this.filters.platforms = [this.platforms.find(x => x.id == platformId)];
            }

            if (args.genres) {
                let genreId = parseInt(args.genres);
                this.filters.genres = [this.genres.find(x => x.id == genreId)];
            }
        },
        clearFilters() {
            this.filters = {
                q: null,
                limit: 100,
                offset: 0,
                start: null,
                end: null,
                genres: [],
                platforms: [],
                genre_option: 'A',
            };

            this.selected = {
                year: null,
                decade: null,
                alltime: null,
            };

            if (this.mode == 'simple')
                this.$router.push({ name: 'games-list', params: { slug: 'alltime' } });
            else
                this.$router.push({ name: 'games-list', params: { slug: 'search' } });
        },
    },
    watch: {
        'selected.alltime': function (val) {
            if (!val)
                return;

            this.selected.decade = null;
            this.selected.year = null;
            this.filters.start = null;
            this.filters.end = null;
            this.$router.push({ name: 'games-list', params: { slug: 'alltime' } });
        },
        'selected.year': function (val) {
            if (!val)
                return;

            this.selected.decade = null;
            this.selected.alltime = null;
            this.filters.start = this.selected.year;
            this.filters.end = this.selected.year;
            this.$router.push({ name: 'games-list', params: { slug: this.selected.year.toString() } });
        },
        'selected.decade': function (val) {
            if (!val)
                return;

            this.selected.year = null;
            this.selected.alltime = null;
            let { start, end } = parseSlug(this.selected.decade);
            this.filters.start = start;
            this.filters.end = end;
            this.$router.push({ name: 'games-list', params: { slug: this.selected.decade.toString() } });
        },
        'filters.q': function () {
            this.filters.offset = 0;
        },
        'filters.start': function () {
            this.filters.offset = 0;
        },
        'filters.end': function () {
            this.filters.offset = 0;
        },
        $route: {
            async handler() {
                await this.init();
            }
        }
    }
}
</script>
