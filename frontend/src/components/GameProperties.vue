<template>
    <dl class="detail">
        <dt>All time rank:</dt>
        <dd>
            <router-link :to="{ name: 'games-list', params: { slug: 'alltime' } }">
                {{ game.rank }}
            </router-link>
        </dd>
        <dt>{{ game.decade }}s rank:</dt>
        <dd>
            <router-link :to="{ name: 'games-list', params: { slug: game.decadeSlug } }">
                {{ game.decadeRank }}
            </router-link>
        </dd>
        <dt>{{ game.yearOfRelease }} rank:</dt>
        <dd>
            <router-link :to="{ name: 'games-list', params: { slug: game.yearOfRelease } }">
                {{ game.yearRank }}
            </router-link>
        </dd>
        <dt>Developers:</dt>
        <dd>
            <router-link :to="{ name: 'developer-alias-redirect', params: { id: developer.id } }"
                v-for="(developer, i) in game.developers"
                :key="developer.id">
                {{ developer.name }}
                <template v-if="i < game.developers.length - 1">,&nbsp;</template>
            </router-link>
        </dd>
        <dt>Platforms:</dt>
        <dd>
            <a v-for="(platform, i) in game.platforms"
                :key="platform.id"
                href="">
                {{ platform.name }}
                <template v-if="i < game.platforms.length - 1">,&nbsp;</template>
            </a>
        </dd>
        <dt>Year of release:</dt>
        <dd>{{ game.yearOfRelease }}</dd>
        <dt>Genres:</dt>
        <dd>
            <a v-for="(genre, i) in game.genres"
                :key="genre.id"
                href="">
                {{ genre.name }}
                <template v-if="i < game.genres.length - 1">,&nbsp;</template>
            </a>
        </dd>
        <dt>IGDB Link:</dt>
        <dd>
            <a :href="game.igdbUrl"
                target="_blank">{{ game.igdbUrl }}</a>
        </dd>
    </dl>
</template>

<script>
export default {
    props: ['game'],
}
</script>
