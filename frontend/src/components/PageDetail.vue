<template>
    <h1 class="title">{{ page?.title }}</h1>
    <div v-if="page"
        v-html="page.content"
        class="content"></div>
</template>

<script>

export default {
    data() {
        return {
            page: null,
        }
    },
    async created() {
        this.page = await fetch(`${process.env.VUE_APP_API_URL}pages/${this.$route.params.slug}/`)
            .then(resp => resp.json());

        this.emitter.emit('title', this.page.title);
    }
}

</script>