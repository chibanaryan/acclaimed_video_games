<template>
    <h1 class="title">
        <template v-if="mode == 'simple'">
            Most Acclaimed Games of {{ prettySlug }}
        </template>
        <template v-else> {{ pageTitle }} Results </template>
    </h1>
    <div v-if="mode == 'advanced'">
        <div class="columns">
            <div class="column">
                <div class="p-2">
                    <label class="has-text-weight-bold">Release year</label>
                </div>
                <div class="field">
                    <div class="control">
                        <table class="table plain">
                            <tr>
                                <td>From:</td>
                                <td>{{ filters.start }}</td>
                                <td>
                                    <input type="range"
                                        min="1970"
                                        :max="maxYear"
                                        v-model="filters.start"
                                        placeholder="Start year" />
                                </td>
                            </tr>
                            <tr>
                                <td>To:</td>
                                <td>{{ filters.end }}</td>
                                <td>
                                    <input type="range"
                                        v-model="filters.end"
                                        min="1970"
                                        :max="maxYear"
                                        placeholder="End year" />
                                </td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>
            <div v-if="genres.length"
                class="column">
                <div class="p-2">
                    <div class="control is-pulled-right">
                        <label class="radio">
                            All
                            <input v-model="filters.genre_option"
                                type="radio"
                                value="L" />
                        </label>
                        <label class="radio">
                            Any
                            <input v-model="filters.genre_option"
                                type="radio"
                                value="A" />
                        </label>
                    </div>
                    <label class="has-text-weight-bold">Genres</label>
                </div>
                <select v-model="filters.genres"
                    multiple
                    class="is-hidden-tablet">
                    <option :value="null">All genres</option>
                    <option v-for="genre in genres"
                        :key="genre.id"
                        :value="genre">
                        {{ genre.name }}
                    </option>
                </select>
                <div class="is-hidden-mobile">
                    <selectable-tag-list v-model="filters.genres"></selectable-tag-list>
                    <multi-select-component :items="genres"
                        v-model="filters.genres"></multi-select-component>
                </div>
            </div>
            <div v-if="platforms.length"
                class="column">
                <div class="p-2">
                    <label class="has-text-weight-bold">Platforms</label>
                </div>
                <select v-model="filters.platforms"
                    multiple
                    class="is-hidden-tablet">
                    <option :value="null">All platforms</option>
                    <option v-for="platform in platforms"
                        :key="platform.id"
                        :value="platform">
                        {{ platform.name }}
                    </option>
                </select>
                <div class="is-hidden-mobile">
                    <selectable-tag-list v-model="filters.platforms"></selectable-tag-list>
                    <multi-select-component :items="platforms"
                        v-model="filters.platforms"></multi-select-component>
                </div>
            </div>
        </div>
        <div class="buttons">
            <a @click="clearFilters"
                v-if="isFiltered"
                class="button">
                <span class="icon">
                    <span class="mdi mdi-close"></span>
                </span>
                <span>Clear filters</span>
            </a>
            <router-link :to="{ name: 'games-list', params: { slug: 'alltime' } }"
                v-if="mode == 'advanced'"
                class="button is-link">
                <span class="icon">
                    <span class="mdi mdi-form-select"></span>
                </span>
                <span> Simple Filters </span>
            </router-link>
        </div>
    </div>
    <div v-if="mode == 'simple'"
        class="field is-grouped is-grouped-multiline">
        <div class="control">
            <a @click="selected.alltime = true"
                class="button is-link"> All time </a>
        </div>
        <div class="control">
            <div class="select">
                <select v-model="selected.decade">
                    <option :value="null">Decades</option>
                    <option v-for="decade in meta.games.decades"
                        :key="decade"
                        :value="decade">
                        {{ decade }}
                    </option>
                </select>
            </div>
        </div>
        <div class="control">
            <div class="select">
                <select v-model="selected.year">
                    <option :value="null">Years</option>
                    <option v-for="year in meta.games.years"
                        :key="year.year"
                        :value="year.year">
                        {{ year.year }} ({{ year.count }})
                    </option>
                </select>
            </div>
        </div>
        <div v-if="isFiltered"
            class="control">
            <a @click="clearFilters"
                class="button">
                <span class="icon">
                    <span class="mdi mdi-close"></span>
                </span>
                <span>Clear filters</span>
            </a>
        </div>
        <div class="control">
            <router-link :to="{ name: 'games-list', params: { slug: 'search' } }"
                class="button is-link">
                <span class="icon">
                    <span class="mdi mdi-tune-variant"></span>
                </span>
                <span> Advanced Filters </span>
            </router-link>
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
import _ from "lodash";
import Game from "../models/Game";
import Genre from "../models/Genre";
import Platform from "../models/Platform";
import BaseListComponent from "./BaseListComponent";
import GameRow from "./GameRow";
import MultiSelectComponent from "./MultiSelectComponent";
import PaginationComponent from "./PaginationComponent";
import SelectableTagList from "./SelectableTagList";

export default {
    mixins: [BaseListComponent],
    components: {
        GameRow,
        MultiSelectComponent,
        PaginationComponent,
        SelectableTagList,
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
                genre_option: "A",
            },
            selected: {
                year: null,
                decade: null,
                alltime: null,
            },
            genres: [],
            platforms: [],
            mode: "simple",
            loading: false,
        };
    },
    async created() {
        this.$store.commit("loading", true);
        this.filters.start = 1970;
        this.filters.end = this.maxYear;
        await this.init();
        this.$store.commit("loading", false);
    },
    computed: {
        isFiltered() {
            return this.filters.start || this.filters.end;
        },
        cleanedFilters() {
            let filters = Object.assign({}, cleanData(this.filters));

            if (!filters.start)
                delete filters.start;

            if (!filters.end)
                delete filters.end;

            if (filters.genres.length)
                filters.genres = filters.genres.map((x) => x.id).join(",");

            if (filters.platforms.length)
                filters.platforms = filters.platforms.map((x) => x.id).join(",");

            return new URLSearchParams(filters);
        },
        prettySlug() {
            if (this.selected.year)
                return this.selected.year;
            else if (this.selected.decade)
                return this.selected.decade;
            else
                return 'All Time';
        },
        maxYear() {
            return new Date().getFullYear();
        },
    },
    methods: {
        async init() {
            if (this.$route.params.slug == "search") {
                this.mode = "advanced";
            } else {
                let { start, end } = parseSlug(this.$route.params.slug);
                this.filters.start = parseInt(start);
                this.filters.end = parseInt(end);
                this.mode = "simple";
            }

            let data = await fetch(
                `${process.env.VUE_APP_API_URL}genres/?limit=999`
            ).then((resp) => resp.json());
            this.genres = data.results.map((x) => new Genre(x));

            data = await fetch(
                `${process.env.VUE_APP_API_URL}platforms/?limit=999`
            ).then((resp) => resp.json());
            this.platforms = data.results.map((x) => new Platform(x));

            this.loadUrlArgs();
        },
        loadItems: _.debounce(
            async function () {
                let url = `${process.env.VUE_APP_API_URL}games/?${this.cleanedFilters}`;
                let data = await fetch(url).then((resp) => resp.json());
                this.items = data.results.map((x) => new Game(x));
                this.resultsCount = data.count;
            },
            200,
            { leading: true }
        ),
        async loadUrlArgs() {
            if (!this.genres.length || !this.platforms.length) return;

            let args = this.$route.query;
            if (!args) return;

            if (args.platforms) {
                let platformId = parseInt(args.platforms);
                this.filters.platforms = [this.platforms.find((x) => x.id == platformId)];
            }

            if (args.genres) {
                let genreId = parseInt(args.genres);
                this.filters.genres = [this.genres.find((x) => x.id == genreId)];
            }

            if (args.limit) this.filters.limit = parseInt(args.limit);

            if (args.offset) this.filters.offset = parseInt(args.offset);
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
                genre_option: "A",
            };

            this.selected = {
                year: null,
                decade: null,
                alltime: null,
            };

            if (this.mode == "simple")
                this.updateUrl({ name: "games-list", params: { slug: "alltime" } });
            else
                this.updateUrl({ name: "games-list", params: { slug: "search" } });
        },
        updateUrl(route) {
            let url = this.$router.resolve(route).path;
            history.pushState(null, document.title, url);
        }
    },
    watch: {
        "selected.alltime": function (val) {
            if (!val)
                return;

            this.selected.decade = null;
            this.selected.year = null;
            this.filters.start = null;
            this.filters.end = null;

            this.updateUrl({ name: 'games-list', params: { slug: 'alltime' } })
        },
        "selected.year": function (val) {
            if (!val)
                return;

            this.selected.decade = null;
            this.selected.alltime = null;
            this.filters.start = this.selected.year;
            this.filters.end = this.selected.year;

            this.updateUrl({ name: 'games-list', params: { slug: this.selected.year.toString() } });
        },
        "selected.decade": function (val) {
            if (!val)
                return;

            this.selected.year = null;
            this.selected.alltime = null;
            let { start, end } = parseSlug(this.selected.decade);
            this.filters.start = start;
            this.filters.end = end;

            this.updateUrl({ name: 'games-list', params: { slug: this.selected.decade.toString() } });
        },
        "filters.q": function () {
            this.filters.offset = 0;
        },
        "filters.start": function () {
            this.filters.offset = 0;
            if (this.filters.end < this.filters.start)
                this.filters.end = this.filters.start;
        },
        "filters.end": function () {
            this.filters.offset = 0;
            if (this.filters.start > this.filters.end)
                this.filters.start = this.filters.end;
        },
        $route: {
            async handler() {
                await this.init();
            },
        },
    },
};
</script>

<style lang="sass" scoped>
input[type=range]
    width: 15em
</style>