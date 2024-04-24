<template>
    <h1 class="title is-size-4">Source Lists</h1>
    <div class="field is-grouped is-multiline">
        <div class="select">
            <select v-model="filters.publisher">
                <option :value="null">All publishers</option>
                <option v-for="publisher in publishers"
                    :key="publisher.id"
                    :value="publisher.id">{{ publisher.name }}</option>
            </select>
        </div>
        <div class="select">
            <select v-model="filters.year">
                <option :value="null">All years</option>
                <option v-for="year in meta.lists.years"
                    :key="year.year"
                    :value="year.year">{{ year.year }} ({{ year.count }})</option>
            </select>
        </div>
        <div class="select">
            <select v-model="filters.type">
                <option :value="null">All list types</option>
                <option v-for="type in listTypes"
                    :key="type[0]"
                    :value="type[0]">{{ type[1] }}</option>
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
    <pagination-component :total="resultsCount"
        :limit="filters.limit"
        :offset="filters.offset"
        @pagechanged="onPageChange">
    </pagination-component>
    <div v-if="loading"
        class="loading">
        <span class="mdi mdi-loading mdi-spin mdi-48px"></span>
    </div>
    <table v-if="items && !loading"
        class="table is-fullwidth">
        <thead>
            <tr>
                <th>Publication</th>
                <th>Year</th>
                <th>Name</th>
                <th>Type</th>
            </tr>
        </thead>
        <tbody>
            <tr v-for="list in items"
                :key="list.id">
                <td>{{ list.publisher }}</td>
                <td>{{ list.year }}</td>
                <td>
                    <a :href="list.url"
                        v-if="list.url"
                        target="_blank">
                        {{ list.name }}
                    </a>
                    <span v-else>{{ list.name }}</span>
                </td>
                <td>{{ list.typeName }}</td>
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
import { LIST_TYPE_LABELS } from '../constants';
import List from '../models/List';
import BaseListComponent from './BaseListComponent';
import PaginationComponent from './PaginationComponent';

export default {
    mixins: [BaseListComponent],
    components: { PaginationComponent },
    data() {
        return {
            filters: {
                limit: 100,
                offset: 0,
                type: null,
                publisher: null,
                year: null,
            },
            publishers: [],
            resultsCount: 0,
        }
    },
    async created() {
        let data = await fetch(`${process.env.VUE_APP_API_URL}publications/`)
            .then(resp => resp.json());
        this.publishers = data.results;
    },
    computed: {
        listTypes() {
            return Object.entries(LIST_TYPE_LABELS);
        }
    },
    methods: {
        async loadItems() {
            let data = await fetch(`${process.env.VUE_APP_API_URL}lists/?${this.cleanedFilters}`)
                .then(resp => resp.json());
            this.items = data.results.map(x => new List(x));
            this.resultsCount = data.count;
        }
    },
}
</script>