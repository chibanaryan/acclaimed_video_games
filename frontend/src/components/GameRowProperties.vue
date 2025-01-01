<template>
    <div v-if="showRank"
        class="py-0">
        <label class="has-text-weight-medium is-size-6">
            All time rank:
        </label>
        <span class="has-text-weight-medium is-size-6">
            {{ game.rank }}
        </span>
    </div>
    <div class="py-0">
        <label class="has-text-weight-medium is-size-6">
            Developer{{ game.developers.length == 1 ? '' : 's' }}:
        </label>
        <span v-for="developer, i in game.developers"
            :key="developer.id"
            class="is-size-6">
            <router-link :to="{ name: 'developer-alias-redirect', params: { id: developer.id } }"
                :key="developer.id"
                class="is-size-6">
                {{ developer.name }}
            </router-link><template v-if="i < (game.developers.length - 1)">, </template>
        </span>
    </div>
    <div class="py-0">
        <label class="has-text-weight-medium is-size-6">
            Platform{{ game.platforms.length == 1 ? '' : 's' }}:
        </label>
        <span v-for="platform, i in game.platforms"
            :key="platform.id"
            class="is-size-6">
            <router-link :to="{ name: 'games-list', query: { platforms: platform.id } }">
                {{ platform.code }}
            </router-link>
            <template v-if="i < (game.platforms.length - 1)">, </template>
        </span>
    </div>
    <div class="py-0">
        <label class="has-text-weight-medium is-size-6">
            Genre{{ game.genres.length == 1 ? '' : 's' }}:
        </label>
        <span v-for="genre, i in game.genres"
            :key="genre.id"
            class="is-size-6">
            <router-link :to="{ name: 'games-list', query: { genres: genre.id } }">
                {{ genre.name }}
            </router-link>
            <template v-if="i < (game.genres.length - 1)">, </template>
        </span>
    </div>
</template>

<script>
export default {
    props: {
        game: null,
        showRank: {
            default: true,
        },
    }
}

</script>