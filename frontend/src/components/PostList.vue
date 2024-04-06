<template>
    <h1 class="title is-size-4">News</h1>
    <post-item v-for="post in items"
        :key="post.id"
        :post="post"></post-item>
    <pagination-component :hasPrev="hasPrev"
        hasNext="hasNext"
        @pagechanged="onPageChange"></pagination-component>
</template>

<script>
import BaseListComponent from './BaseListComponent';
import PaginationComponent from './PaginationComponent';
import Post from '../models/Post';
import PostItem from './PostItem';

export default {
    mixins: [BaseListComponent],
    components: { PaginationComponent, PostItem },
    data() {
        return {
            filters: {
                limit: 5,
                offset: 0,
            }
        }
    },
    methods: {
        async loadItems() {
            let data = await fetch(`${process.env.VUE_APP_API_URL}posts/?${this.cleanedFilters}`)
                .then(resp => resp.json());
            this.items = data.results.map(x => new Post(x));
            this.resultsCount = data.count;
        }
    },
}
</script>