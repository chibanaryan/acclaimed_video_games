<template>
    <h1 class="title">Developers</h1>
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
    <table v-if="items"
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
    <simple-pagination-component :hasPrev="hasPrev"
        hasNext="hasNext"
        @pagechanged="onPageChange"></simple-pagination-component>
</template>

<script>
import BaseListComponent from './BaseListComponent';
import SimplePaginationComponent from './SimplePaginationComponent';
import DeveloperAlias from '../models/DeveloperAlias';

export default {
    mixins: [BaseListComponent],
    components: { SimplePaginationComponent },
    data() {
        return {
            filters: {
                limit: 20,
                offset: 0,
                q: null,
            },
            resultsCount: 0,
        }
    },
    methods: {
        async loadItems() {
            let data = await fetch(`${process.env.VUE_APP_API_URL}developer-aliases/?${this.cleanedFilters}`)
                .then(resp => resp.json());
            this.items = data.results.map(x => new DeveloperAlias(x));
            this.resultsCount = data.count;
        }
    },
}
</script>