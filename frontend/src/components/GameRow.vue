<template>
    <div class="columns is-mobile game-row">
        <div class="column is-narrow">
            <div class="columns">
                <div v-if="showRank"
                    class="column">
                    <span class="rank large px-5 py-3 is-hidden-mobile">
                        {{ game.rank }}
                    </span>
                    <span class="rank medium px-5 py-3 is-hidden-tablet">
                        {{ game.rank }}
                    </span>
                </div>
                <div class="column">
                    <router-link :to="{ name: 'game-detail', params: { slug: game.slug } }">
                        <img :src="game.thumbnail">
                    </router-link>
                </div>
            </div>
        </div>
        <div class="column">
            <div>
                <router-link :to="{ name: 'game-detail', params: { slug: game.slug } }"
                    class="game-name has-text-weight-bold is-size-6 mb-3">
                    {{ game.name }}
                </router-link>
                <router-link :to="{ name: 'games-list', params: { slug: game.yearOfRelease } }">
                    ({{ game.yearOfRelease }})
                </router-link>
            </div>
            <div v-if="!showRank"
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
                    </router-link><template v-if="i < (game.developers.length - 1)">,&nbsp;</template>
                </span>
            </div>
            <div class="py-0">
                <label class="has-text-weight-medium is-size-6">
                    Platform{{ game.platforms.length == 1 ? '' : 's' }}:
                </label>
                <span v-for="platform, i in game.platforms"
                    :key="platform.id"
                    class="is-size-6">
                    <router-link
                        :to="{ name: 'games-list', params: { slug: 'search' }, query: { platforms: platform.id } }">
                        {{ platform.code }}
                    </router-link>
                    <template v-if="i < (game.platforms.length - 1)">,&nbsp;</template>
                </span>
            </div>
            <div class="py-0">
                <label class="has-text-weight-medium is-size-6">
                    Genre{{ game.genres.length == 1 ? '' : 's' }}:
                </label>
                <span v-for="genre, i in game.genres"
                    :key="genre.id"
                    class="is-size-6">
                    <router-link :to="{ name: 'games-list', params: { slug: 'search' }, query: { genres: genre.id } }">
                        {{ genre.name }}
                    </router-link>
                    <template v-if="i < (game.genres.length - 1)">,&nbsp;</template>
                </span>
            </div>
        </div>
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

<style scoped>
.game-row .rank {
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-family: Handjet, sans-serif;
    font-weight: 800;
    text-shadow: -3px 3px 0px #5d5b5b;
    min-width: 122px;
}

.game-row .rank.large {
    font-size: 60px;
}

.game-row .rank.medium {
    font-size: 30px;
}
</style>