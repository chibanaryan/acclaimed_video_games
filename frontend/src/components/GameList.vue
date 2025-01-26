<template>
    <h1 class="title">
        Most Acclaimed Games of {{ prettySlug }}
    </h1>

    <router-link :to="{ name: 'games-search' }"
        class="button is-link is-pulled-right">
        <span class="icon">
            <span class="mdi mdi-tune-variant"></span>
        </span>
        <span>
            Advanced Search
        </span>
    </router-link>

    <simple-filters v-model="filters"></simple-filters>

    <div class="columns">
        <div class="column">
            filters
            <pre>{{ filters }}</pre>
        </div>
        <div class="column">
            getArgs
            <pre>{{ getArgs }}</pre>
        </div>
        <div class="column">
            pagination
            <pre>{{ pagination }}</pre>
        </div>
        <div class="column">
            objectStore
            <pre>{{ objectStore.data }}</pre>
        </div>
    </div>

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
import { objectStore } from "@/objectStore";
import { parseSlug } from "@/utils";
import { cloneDeep } from "lodash";
import Game from "../models/Game";
import BaseListComponent from "./BaseListComponent";
import GameRow from "./GameRow";
import PaginationComponent from "./PaginationComponent";
import SimpleFilters from "./SimpleFilters";


let controller = null;

export default {
    mixins: [BaseListComponent],
    components: {
        GameRow,
        PaginationComponent,
        SimpleFilters,
    },
    data() {
        return {
            filters: {
                year: null,
                decade: null,
            },
            pagination: {
                limit: 100,
                offset: 0,
            },
            objectStore: objectStore(this.$route.name),
        };
    },
    computed: {
        prettySlug() {
            if (this.filters?.year)
                return this.filters.year;
            else if (this.filters?.decade)
                return this.filters.decade;
            else
                return 'All Time';
        },
        getArgs() {
            let filters = {};

            if (this.filters.decade) {
                let { start, end } = parseSlug(this.filters.decade);
                filters.start = start;
                filters.end = end;
            }

            if (this.filters.year) {
                filters.start = this.filters.year;
                filters.end = this.filters.year;
            }

            filters.limit = this.pagination.limit;
            filters.offset = this.pagination.offset;

            return filters;
        },
    },
    methods: {
        async init() {
            let savedFilters = this.objectStore.get('filters');

            if (savedFilters) {
                this.pagination.limit = savedFilters.limit;
                this.pagination.offset = savedFilters.offset;
                this.updateFilters(savedFilters);
                //this.objectStore.set('filters', null)
                this.updateUrl(this.getArgs);
            } else {
                this.updateFilters(this.$route.query);
            }

            await this.loadItems();
        },
        async loadItems() {
            if (controller)
                controller.abort();

            controller = new AbortController();

            let url = `${process.env.VUE_APP_API_URL}games/?${new URLSearchParams(this.getArgs)}`;

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
    watch: {
        pagination: {
            handler(val) {
                console.log(val);
            },
            deep: true
        },
    },
    beforeRouteLeave() {
        let savedFilters = cloneDeep(this.getArgs);
        savedFilters.stored = true;
        this.objectStore.set('filters', savedFilters);
    },
}
</script>