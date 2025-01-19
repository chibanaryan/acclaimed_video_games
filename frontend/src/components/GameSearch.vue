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
import { cleanData } from "@/utils";
import { cloneDeep } from "lodash";
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
    async created() {
        this.$store.commit("setLoading", true);

        await this.$store.dispatch('loadGenres');
        this.genres = this.$store.state.genres;

        await this.$store.dispatch('loadPlatforms');
        this.platforms = this.$store.state.platforms;

        this.$store.commit("setLoading", false);
    },
    computed: {
        cleanedFilters() {
            let filters = cleanData(this.filters);

            console.log(filters);
            

            if (filters.genres?.length)
                filters.genres = filters.genres.filter(x => x).map((x) => x.id).join(",");

            if (filters.platforms?.length)
                filters.platforms = filters.platforms.filter(x => x).map((x) => x.id).join(",");

            filters.limit = this.pagination.limit;
            filters.offset = this.pagination.offset;

            return filters;
        },
    },
    methods: {
        async init() {
            let savedFilters = this.objectStore.get('filters');
            if (savedFilters) {
                this.loadFilters(savedFilters);
                this.objectStore.set('filters', null)
                this.updateUrl();
            } else {
                this.loadFilters(this.$route.query);
            }

            await this.loadItems();
        },
        async loadItems() {
            if (controller)
                controller.abort();

            controller = new AbortController();

            let args = cloneDeep(this.cleanedFilters);
            delete args.mode;

            let url = `${process.env.VUE_APP_API_URL}games/?${new URLSearchParams(args)}`;

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