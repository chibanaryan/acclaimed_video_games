<template>
    <nav class="pagination is-centered"
        v-if="pages.length > 1">
        <ul class="pagination-list">
            <li v-for="page in pages"
                :key="page">
                <template v-if="page">
                    <a v-if="!loading"
                        class="pagination-link"
                        :class="{ 'is-current': currentPage == page }"
                        @click="onPageClick(page)">
                        {{ page }}
                    </a>
                    <span v-else
                        :class="{ 'is-current': currentPage == page }"
                        class="pagination-link"> {{ page }}</span>
                </template>
                <span v-else
                    class="pagination-ellipsis">&hellip;</span>
            </li>
        </ul>
    </nav>
</template>

<script>
export default {
    props: ["total", "limit", "offset", "showAllPages"],
    emits: ["pagechanged"],
    computed: {
        pages() {
            const numPages = Math.ceil(this.total / this.limit);
            let pages = Array.from(
                Array(numPages)
                    .keys()
            )
                .map(x => x + 1);

            const currentPageIsFirstPage = this.currentPage == 1
            const currentPageIsSecondPage = this.currentPage == 2
            const currentPageIsSecondLastPage = this.currentPage == pages.length - 1;
            const currentPageIsLastPage = this.currentPage == pages.length;

            pages = pages.filter(x => {

                if (this.showAllPages)
                    return true;

                const firstPage = x == 1;
                const lastPage = x == pages.length;
                const isCurrent = x == this.currentPage;
                const distanceFromCurrent = Math.abs(this.currentPage - x);

                let minDistance = 2;
                if (currentPageIsFirstPage || currentPageIsLastPage)
                    minDistance = 4;
                else if (currentPageIsSecondPage || currentPageIsSecondLastPage)
                    minDistance = 3;

                const isCloseToCurrent = distanceFromCurrent < minDistance;

                return firstPage || lastPage || isCurrent || isCloseToCurrent;
            })

            let lastPage = 0;
            for (let i = 0; i < pages.length; i++) {
                let page = pages[i];
                if ((page - lastPage) > 1)
                    pages.splice(i, 0, null);
                lastPage = page;
            }

            return pages;
        },
        currentPage() {
            return parseInt(this.offset / this.limit) + 1;
        },
        loading() {
            return this.$store.state.loading;
        },
    },
    methods: {
        onPageClick(page) {
            if (this.loading)
                return;

            this.$emit("pagechanged", { offset: this.limit * (page - 1) });
            document.getElementById('header').scrollIntoView({ behavior: "smooth" });
        },
    },
};
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
