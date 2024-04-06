<template>
    <h1 class="title">{{ pageTitle }} Games</h1>
    <div class="field is-grouped is-multiline">
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
        <div class="control">
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
        <div class="select">
            <select v-model="filters.genres"
                multiple>
                <option :value="null">All genres</option>
                <option v-for="genre in genres"
                    :key="genre.id"
                    :value="genre">{{ genre.name }}</option>
            </select>
        </div>
        <div class="select">
            <select v-model="filters.platforms"
                multiple>
                <option :value="null">All platforms</option>
                <option v-for="platform in platforms"
                    :key="platform.id"
                    :value="platform">{{ platform.name }}</option>
            </select>
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
    <div v-if="items">
        <game-row v-for="game in items"
            :key="game.id"
            :game="game"></game-row>
    </div>
    <pagination-component :hasPrev="hasPrev"
        hasNext="hasNext"
        @pagechanged="onPageChange"></pagination-component>
</template>


<script>
import GameRow from './GameRow';
import Game from '../models/Game';
import BaseListComponent from './BaseListComponent';
import PaginationComponent from './PaginationComponent';
import { cleanData } from "@/utils.js";

export default {
    mixins: [BaseListComponent],
    components: { GameRow, PaginationComponent },
    data() {
        return {
            filters: {
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
        this.genres = data.results;

        data = await fetch(`${process.env.VUE_APP_API_URL}platforms/`)
            .then(resp => resp.json());
        this.platforms = data.results;
    },
    computed: {
        cleanedFilters() {
            let filters = Object.assign({}, this.filters);

            if (filters.genres.length)
                filters.genres = filters.genres.map(x => x.id).join(',');

            if (filters.platforms.length)
                filters.platforms = filters.platforms.map(x => x.id).join(',');

            return new URLSearchParams(cleanData(filters));
        },
    },
    methods: {
        async loadItems() {
            let data = await fetch(`${process.env.VUE_APP_API_URL}games/?${this.cleanedFilters}`)
                .then(resp => resp.json());
            this.items = data.results.map(x => new Game(x));
            this.resultsCount = data.count;
        }
    }
}
</script>