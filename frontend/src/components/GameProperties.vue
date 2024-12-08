<template>
    <table class="detail">
        <tr>
            <th>All time rank:</th>
            <td>
                <router-link :to="getGameRankRoute('alltime', game.rank)">
                    {{ game.rank }}
                </router-link>
            </td>
        </tr>
        <tr>
            <th>{{ game.decade }}s rank:</th>
            <td>
                <router-link :to="getGameRankRoute(game.decadeSlug, game.decadeRank)">
                    {{ game.decadeRank }}
                </router-link>
            </td>
        </tr>
        <tr>
            <th>{{ game.yearOfRelease }} rank:</th>
            <td>
                <router-link :to="getGameRankRoute(game.yearOfRelease, game.yearRank)">
                    {{ game.yearRank }}
                </router-link>
            </td>
        </tr>
        <tr>
            <th>Developers:</th>
            <td>
                <router-link
                    :to="{ name: 'developer-alias-redirect', params: { id: developer.id }, }"
                    v-for="(developer, i) in game.developers"
                    :key="developer.id">
                    {{ developer.name }}<template v-if="i < game.developers.length - 1">, </template>
                </router-link>
            </td>
        </tr>
        <tr>
            <th>Platforms:</th>
            <td>
                <router-link
                    :to="{ name: 'games-list', params: { slug: 'search' }, query: { platforms: platform.id }, }"
                    v-for="(platform, i) in game.platforms"
                    :key="platform.id">
                    {{ platform.name }}<template v-if="i < game.platforms.length - 1">, </template>
                </router-link>
            </td>
        </tr>
        <tr>
            <th>Year of release:</th>
            <td>
                <router-link :to="{ name: 'games-list', params: { slug: game.yearOfRelease } }">
                    {{ game.yearOfRelease }}
                </router-link>
            </td>
        </tr>
        <tr>
            <th>Genres:</th>
            <td>
                <router-link :to="{
                    name: 'games-list',
                    params: { slug: 'search' },
                    query: { genres: genre.id },
                }"
                    v-for="(genre, i) in game.genres"
                    :key="genre.id"
                    href="">
                    {{ genre.name
                    }}<template v-if="i < game.genres.length - 1">, </template>
                </router-link>
            </td>
        </tr>
        <tr>
            <th>
                IGDB Link:
            </th>
            <td>
                <a :href="game.igdbUrl"
                    target="_blank"
                    class="igdb-link">
                    <span class="icon">
                        <span class="mdi mdi-open-in-new"></span>
                    </span>
                </a>
            </td>
        </tr>
    </table>
</template>

<script>
export default {
    props: ["game"],
    methods: {
        getGameRankRoute(slug, rank) {
            return {
                name: 'games-list',
                params: {
                    slug: slug,
                },
                query: {
                    limit: 100,
                    offset: parseInt(rank / 100) * 100,
                    highlight: this.game.id,
                }
            }
        }
    }
};
</script>

<style lang="sass" scoped>
table.detail th 
    font-weight: 600
    min-width: 10em


table.detail th,
table.detail td 
    padding: 2px

.igdb-link
    overflow: hidden
    text-overflow: ellipsis
</style>
