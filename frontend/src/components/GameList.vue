<template>
    <h1 class="title">
        <template v-if="mode == 'simple'">
            Most Acclaimed Games of {{ $route.params.slug }}
        </template>
        <template v-else>
            {{ pageTitle }}
        </template>
    </h1>
    <div v-if="mode == 'advanced'">
        <div class="control is-pulled-right">
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
    <div v-else>
        <div class="control is-pulled-right">
            <router-link :to="{ name: 'games-search' }"
                class="button is-link">
                Advanced Filters
            </router-link>
        </div>
        <div class="field is-grouped is-multiline">
            <div class="control">
                <a @click="selected.alltime = true"
                    class="button">
                    Alltime
                </a>
            </div>
            <div class="control">
                <div class="select">
                    <select v-model="selected.year">
                        <option :value="null">All years</option>
                        <option v-for="year in meta.games.years"
                            :key="year.year"
                            :value="year.year">{{ year.year }} ({{ year.count }})</option>
                    </select>
                </div>
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

    <div v-if="loading"
        class="loading">
        <span class="mdi mdi-loading mdi-spin mdi-48px"></span>
    </div>
    <div v-if="items && !loading"
        class="mt-5">
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
        console.log(this.$route);
        if (this.$route.params.slug) {
            let { start, end } = parseSlug(this.$route.params.slug);
            this.filters.start = start;
            this.filters.end = end;
            this.mode = 'simple';
        } else {
            this.mode = 'advanced';
        }

        let data = await fetch(`${process.env.VUE_APP_API_URL}genres/`)
            .then(resp => resp.json());
        this.genres = data.results.map(x => new Genre(x));

        data = await fetch(`${process.env.VUE_APP_API_URL}platforms/`)
            .then(resp => resp.json());
        this.platforms = data.results.map(x => new Platform(x));

        this.loadUrlArgs();
    },
    computed: {
        cleanedFilters() {
            let filters = Object.assign({}, cleanData(this.filters));

            if (filters.genres.length)
                filters.genres = filters.genres.map(x => x.id).join(',');

            if (filters.platforms.length)
                filters.platforms = filters.platforms.map(x => x.id).join(',');

            return new URLSearchParams(filters);
        }
    },
    methods: {
        async loadItems() {
            let url = `${process.env.VUE_APP_API_URL}games/?${this.cleanedFilters}`;
            let data = await fetch(url)
                .then(resp => resp.json());
            this.items = data.results.map(x => new Game(x));
            this.resultsCount = data.count;
        },
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
        onPageChange(e) {
            Object.assign(this.filters, e);
        }
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
    }
}
</script>
