<script>
import { getApiUrl } from "@/config";
import DeveloperAlias from '../models/DeveloperAlias';

export default {
    async created() {
        let data = await fetch(`${getApiUrl()}developer-aliases/${this.$route.params.id}/`)
            .then(resp => resp.json());
        let alias = new DeveloperAlias(data);
        this.$router.replace({ name: 'developer-detail', params: { slug: alias.developer.slug } })
    }
}
</script>