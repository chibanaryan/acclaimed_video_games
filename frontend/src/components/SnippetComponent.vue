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
        this.snippet = await fetch(`${import.meta.env.VITE_API_URL}snippets/${this.slug}/`)
            .then(resp => resp.json());
    }
}
</script>