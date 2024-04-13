<template>
    <h1 class="title">{{ pageTitle }}</h1>
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
import GameRow from './GameRow';
import Game from '../models/Game';
import BaseListComponent from './BaseListComponent';
import PaginationComponent from './PaginationComponent';

const decadePattern = /\d{2}(\d{2})-(\d{2})/;
const yearPattern = /(\d{4})/;

const parseSlug = (slug) => {
    let start;
    let end;

    if (decadePattern.test(slug)) {
        let match = slug.match(decadePattern);

        start = parseInt(match[1]);
        end = parseInt(match[2]);

        if (start > 50)
            start += 1900;
        else
            start += 2000;

        if (end > 50)
            end += 1900;
        else
            end += 2000;

    } else if (yearPattern.test(slug)) {
        let match = slug.match(yearPattern);
        let year = parseInt(match[1]);

        start = year;
        end = year;
    } else {
        // Alltime
    }

    return { start, end };
}

export default {
    mixins: [BaseListComponent],
    components: { GameRow, PaginationComponent },
    data() {
        return {
            filters: {
                start: null,
                end: null,
            },
            selected: {
                year: null,
                decade: null,
                alltime: null,
            }
        }
    },
    created() {
        let { start, end } = parseSlug(this.$route.params.slug);
        this.filters.start = start;
        this.filters.end = end;
    },
    computed: {
        pageTitle() {
            return `Most Acclaimed Games of ${this.$route.params.slug}`;
        },
    },
    methods: {
        async loadItems() {
            let data = await fetch(`${process.env.VUE_APP_API_URL}games/?${this.cleanedFilters}`)
                .then(resp => resp.json());
            this.items = data.results.map(x => new Game(x));
            this.resultsCount = data.count;
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
