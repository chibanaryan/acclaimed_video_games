<template>
    <h1 class="title is-size-4">News</h1>
    <post-item v-for="post in items"
        :key="post.id"
        :post="post"></post-item>
    <div class="level">
        <div class="level-left">
            <div class="level-item"
                v-if="hasPrev">
                <router-link :to="{ name: 'home' }"
                    v-if="pagination.offset <= pagination.limit"
                    class="button">
                    <span class="icon">
                        <span class="mdi mdi-chevron-double-left"></span>
                    </span>
                    <span>
                        Return to home page
                    </span>
                </router-link>
                <a v-else
                    @click="onPageChange('previous')"
                    class="button">
                    <span class="icon">
                        <span class="mdi mdi-chevron-double-left"></span>
                    </span>
                    <span>
                        Previous
                    </span>
                </a>
            </div>
        </div>
        <div class="level-right">
            <div class="level-item"
                v-if="hasNext">
                <a @click="onPageChange('next')"
                    class="button">
                    <span>
                        Next
                    </span>
                    <span class="icon">
                        <span class="mdi mdi-chevron-double-right"></span>
                    </span>
                </a>
            </div>
        </div>
    </div>
</template>

<script>
import { getApiUrl } from "@/config";
import BaseListComponent from './BaseListComponent';
import Post from '../models/Post';
import PostItem from './PostItem';

export default {
    mixins: [BaseListComponent],
    components: { PostItem },
    methods: {
        async loadItems() {
            let data = await fetch(`${getApiUrl()}posts/?${new URLSearchParams(this.getArgs)}`)
                .then(resp => resp.json());
            this.items = data.results.map(x => new Post(x));
            this.resultsCount = data.count;
        },
    },
}
</script>