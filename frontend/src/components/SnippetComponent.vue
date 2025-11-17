<template>
    {{ snippet?.snippet }}
</template>

<script>
import { getApiUrl } from "@/config";
export default {
    props: ['slug'],
    data() {
        return {
            snippet: null,
        }
    },
    async created() {
        this.snippet = await fetch(`${getApiUrl()}snippets/${this.slug}/`)
            .then(resp => resp.json());
    }
}
</script>