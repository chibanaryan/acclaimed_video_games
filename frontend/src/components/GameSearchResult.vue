<template>
    <router-link :to="{ name: 'game-detail', params: { slug: result.slug } }"
        class="result">
        <div class="media">
            <div class="media-left">
                <figure class="image">
                    <img :src="result.thumbnail">
                </figure>
            </div>
            <div class="media-content">
                <div class="has-text-weight-semibold">
                    {{ result.name }} ({{ result.yearOfRelease }})
                </div>
                <div class="has-text-weight-light">
                    All time rank: {{ result.rank }}
                </div>
            </div>
        </div>
    </router-link>
</template>

<script>
export default {
    props: ['result']
}
</script>