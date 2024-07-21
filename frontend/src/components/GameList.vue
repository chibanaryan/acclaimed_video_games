<template>
    <h1 class="title">
        <template v-if="mode == 'simple'">
            Most Acclaimed Games of {{ prettySlug }}
        </template>
        <template v-else> {{ pageTitle }} Results </template>
    </h1>

    <!-- Advanced filters -->
    <div v-if="mode == 'advanced'">
        <div class="buttons">
            <router-link :to="{ name: 'games-list', params: { slug: 'alltime' } }"
                v-if="mode == 'advanced'"
                class="button is-link">
                <span class="icon">
                    <span class="mdi mdi-form-select"></span>
                </span>
                <span> Simple Filters </span>
            </router-link>
            <a @click="clearFilters"
                v-if="isFiltered"
                class="button">
                <span class="icon">
                    <span class="mdi mdi-close"></span>
                </span>
                <span>Clear filters</span>
            </a>
        </div>
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
                                <td>
                                    <range-slider v-model.lazy="filters.start"
                                        placeholder="Start year"></range-slider>
                                </td>
                            </tr>
                            <tr>
                                <td>To:</td>
                                <td>
                                    <range-slider v-model.lazy="filters.end"
                                        placeholder="End year"></range-slider>
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
        <search-input v-model="filters.q"
            :debounce-input="true"
            placeholder="Search by name">
        </search-input>
    </div>

    <!-- Simple filters -->
    <div v-if="mode == 'simple' && meta?.games"
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
            :game="game"
            :highlight="highlight"></game-row>
        <pagination-component :total="resultsCount"
            :limit="filters.limit"
            :offset="filters.offset"
            @pagechanged="onPageChange"
            class="mt-5">
        </pagination-component>
    </div>
</template>

<script>
import { cleanData, parseSlug } from "@/utils.js";
import Game from "../models/Game";
import Genre from "../models/Genre";
import Platform from "../models/Platform";
import BaseListComponent from "./BaseListComponent";
import GameRow from "./GameRow";
import MultiSelectComponent from "./MultiSelectComponent";
import PaginationComponent from "./PaginationComponent";
import SearchInput from "./SearchInput";
import SelectableTagList from "./SelectableTagList";
import RangeSlider from "./RangeSlider";

let controller = null;

export default {
    mixins: [BaseListComponent],
    components: {
        GameRow,
        MultiSelectComponent,
        PaginationComponent,
        SearchInput,
        SelectableTagList,
        RangeSlider,
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
                genre_option: "L",
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
            highlight: null,
            initialized: false,
        };
    },
    async mounted() {
        this.highlight = this.$route.query.highlight;
        this.$store.commit("loading", true);
        await this.init();
        this.$store.commit("loading", false);
    },
    computed: {
        isFiltered() {
            if (this.mode == 'simple')
                return false;
            else
                return this.filters.q ||
                    this.filters.genres.length ||
                    this.filters.platforms.length ||
                    this.filters.start != this.minYear ||
                    this.filters.end != this.maxYear;
        },
        cleanedFilters() {
            let filters = Object.assign({}, cleanData(this.filters));

            if (!filters.start)
                delete filters.start;

            if (!filters.end)
                delete filters.end;

            if (filters.genres?.length)
                filters.genres = filters.genres.map((x) => x.id).join(",");

            if (filters.platforms?.length)
                filters.platforms = filters.platforms.map((x) => x.id).join(",");

            if (this.mode == 'simple') {
                delete filters.genre_option;
            }

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
        minYear() {
            if (this.meta?.games?.years.length)
                return this.meta.games.years[0]['year'];
            else
                return 1970;
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
                const slug = this.$route.params.slug;
                let { start, end, type } = parseSlug(slug);
                this.filters.start = parseInt(start);
                this.filters.end = parseInt(end);

                if (type == 'decade')
                    this.selected.decade = slug;
                else if (type == 'year')
                    this.selected.year = slug;

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

            this.filters.start = this.filters.start || this.minYear;
            this.filters.end = this.filters.end || this.maxYear;

            this.loadUrlArgs();
            this.updateTitle();

            setTimeout(() => {
                this.initialized = true;
            }, 1000)
        },
        async loadItems() {
            if (controller)
                controller.abort();

            controller = new AbortController();

            let url = `${process.env.VUE_APP_API_URL}games/?${this.cleanedFilters}`;

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
                    if (highlightElement)
                        highlightElement.scrollIntoView({ behavior: "smooth" });
                }, 1000)
            }
        },
        async loadUrlArgs() {
            let args = this.$route.query || new URL(location.url).searchParams;

            if (args.platforms) {
                let platformId = parseInt(args.platforms);
                this.filters.platforms = [this.platforms.find((x) => x.id == platformId)];
            }

            if (args.genres) {
                let genreId = parseInt(args.genres);
                this.filters.genres = [this.genres.find((x) => x.id == genreId)];
            }

            if (args.limit)
                this.filters.limit = parseInt(args.limit);

            if (args.offset)
                this.filters.offset = parseInt(args.offset);

            if (args.q)
                this.filters.q = args.q;
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
                genre_option: "L",
            };

            this.selected = {
                year: null,
                decade: null,
                alltime: null,
            };

            this.filters.start = this.minYear;
            this.filters.end = this.maxYear;

            if (this.mode == "simple")
                this.updateUrl({ name: "games-list", params: { slug: "alltime" } });
            else
                this.updateUrl({ name: "games-list", params: { slug: "search" } });
        },
        updateUrl(route) {
            let url = this.$router.resolve(route).path;
            history.pushState(null, document.title, url);
            this.updateTitle(route);
        },
        updateTitle(route) {
            let slug = (route || this.$route).params.slug;
            if (slug == 'alltime')
                slug = "All time";
            else if (slug == 'search')
                slug = 'Advanced';
            else {
                let slugData = parseSlug(slug);
                if (slugData.type == 'decade')
                    slug = slugData.start + 's';
            }

            this.emitter.emit('title', slug);
        },
        resetOffset() {
            if (this.initialized)
                this.filters.offset = 0;
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
            this.resetOffset()
        },
        "filters.start": function () {
            this.resetOffset()
            if (this.filters.end < this.filters.start)
                this.filters.end = this.filters.start;
        },
        "filters.end": function () {
            this.resetOffset()
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