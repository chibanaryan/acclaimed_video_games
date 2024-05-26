<template>
    <h1 class="title is-spaced">Developers</h1>
    <h2 class="subtitle">{{ pageTitle }} results</h2>
    <div class="field">
        <div class="control has-icons-left">
            <input v-model="filters.q"
                class="input"
                placeholder="Search by name">
            <span class="icon is-small is-left">
                <i class="mdi mdi-magnify"></i>
            </span>
        </div>
    </div>
    <pagination-component :total="resultsCount"
        :limit="filters.limit"
        :offset="filters.offset"
        @pagechanged="onPageChange">
    </pagination-component>
    <table v-if="items && !loading"
        class="table is-fullwidth">
        <thead>
            <tr>
                <th>Name</th>
                <td># Games</td>
            </tr>
        </thead>
        <tbody>
            <tr v-for="alias in items"
                :key="alias.id">
                <td>
                    <router-link :to="{ name: 'developer-detail', params: { slug: alias.developer.slug } }"
                        v-if="alias.developer.slug">
                        {{ alias }}
                    </router-link>
                    <span v-else>
                        {{ alias }}
                    </span>
                </td>
                <td>{{ alias.gamesCount }}</td>
            </tr>
        </tbody>
    </table>
    <pagination-component :total="resultsCount"
        :limit="filters.limit"
        :offset="filters.offset"
        @pagechanged="onPageChange">
    </pagination-component>
</template>

<script>
import BaseListComponent from './BaseListComponent';
import PaginationComponent from './PaginationComponent';
import DeveloperAlias from '../models/DeveloperAlias';
import _ from "lodash";

export default {
    mixins: [BaseListComponent],
    components: { PaginationComponent },
    data() {
        return {
            filters: {
                limit: 100,
                offset: 0,
                q: null,
            },
            resultsCount: 0,
        }
    },
    methods: {
        loadItems: _.debounce(async function () {
            let data = await fetch(`${process.env.VUE_APP_API_URL}developer-aliases/?${this.cleanedFilters}`)
                .then(resp => resp.json());
            this.items = data.results.map(x => new DeveloperAlias(x));
            this.resultsCount = data.count;
        }, 200, { leading: true }),
    },
    watch: {
        'filters.q': function () {
            this.filters.offset = 0;
        }
    }
}
</script>