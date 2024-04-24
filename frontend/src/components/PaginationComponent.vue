<template>
    <nav class="pagination is-centered"
        v-if="pages.length > 1">
        <ul class="pagination-list">
            <li v-for="page in pages"
                :key="page">
                <a class="pagination-link"
                    :class="{ 'is-current': currentPage == page }"
                    @click="onPageClick(page)">
                    {{ page }}
                </a>
            </li>
        </ul>
    </nav>
</template>

<script>
export default {
    props: ['total', 'limit', 'offset'],
    emits: ['pagechanged'],
    computed: {
        pages() {
            const numPages = parseInt(this.total / this.limit) + 1;
            const pages = Array(numPages).keys().map(x => x + 1);
            return Array.from(pages);
        },
        currentPage() {
            return parseInt(this.offset / this.limit) + 1;
        }
    },
    methods: {
        onPageClick(page) {
            this.$emit('pagechanged', { offset: this.limit * (page - 1) });
        }
    }
}
</script>

<style scoped>
nav {
    display: flex;
    align-content: center;
    justify-content: center;
}

nav .navbar-menu {
    flex-grow: initial;
    flex-shrink: initial;
}
</style>