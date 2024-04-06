<template>
    {{ snippet?.snippet }}
</template>

<script>
export default {
    props: ['slug'],
    data() {
        return {
            snippet: null,
        }
    },
    async created() {
        this.snippet = await fetch(`${process.env.VUE_APP_API_URL}snippets/${this.slug}/`)
            .then(resp => resp.json());
    }
}
</script>