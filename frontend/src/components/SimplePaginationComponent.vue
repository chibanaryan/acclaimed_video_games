<template>
    <nav class="pagination"
        role="navigation"
        aria-label="pagination">
        <a class="pagination-previous"
            v-if="hasPrev"
            @click="showPrev">
            <span class="icon">
                <span class="mdi mdi-chevron-double-left"></span>
            </span>
            <span>
                Previous
            </span>
        </a>
        <a class="pagination-next"
            v-if="hasNext"
            @click="showNext">
            <span>
                Next
            </span>
            <span class="icon">
                <span class="mdi mdi-chevron-double-right"></span>
            </span>
        </a>
    </nav>
</template>

<script>
export default {
    props: ['hasPrev', 'hasNext'],
    methods: {
        showPrev() {
            this.$emit('pagechanged', 'previous');
        },
        showNext() {
            this.$emit('pagechanged', 'next');
        },
    }
}
</script>

<style scoped>
.pagination {
    margin: 0 auto;
    width: 30%;
}
</style>