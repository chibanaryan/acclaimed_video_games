<template>
    <h1 class="title">{{ pageTitle }} Games</h1>
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
    <div v-if="loading"
        class="loading">
        <span class="mdi mdi-loading mdi-spin mdi-48px"></span>
    </div>
    <div v-if="items && !loading"
        class="mt-5">
        <game-row v-for="game in items"
            :key="game.id"
            :game="game"></game-row>
        <pagination-component :hasPrev="hasPrev"
            hasNext="hasNext"
            @pagechanged="onPageChange"></pagination-component>
    </div>
</template>


<script>
import { cleanData } from "@/utils.js";
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
                limit: 20,
                offset: 0,
                start: null,
                end: null,
                genres: [],
                platforms: [],
                genre_option: 'A',
            },
            genres: [],
            platforms: [],
        }
    },
    async created() {
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
        },
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
        }
    }
}
</script>
