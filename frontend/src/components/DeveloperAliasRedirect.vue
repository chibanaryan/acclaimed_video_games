<script>
import DeveloperAlias from '../models/DeveloperAlias';

export default {
    async created() {
        let data = await fetch(`${import.meta.env.VITE_API_URL}developer-aliases/${this.$route.params.id}/`)
            .then(resp => resp.json());
        let alias = new DeveloperAlias(data);
        this.$router.replace({ name: 'developer-detail', params: { slug: alias.developer.slug } })
    }
}
</script>