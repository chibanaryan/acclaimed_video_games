<template>
    <dl class="detail">
        <dt>All time rank:</dt>
        <dd>
            <a href="">
                {{ game.rank }}
            </a>
        </dd>
        <dt>{{ game.decade }}s rank:</dt>
        <dd>
            <a href="">
                ???
            </a>
        </dd>
        <dt>{{ game.yearOfRelease }} rank:</dt>
        <dd>
            <a href="">
                ???
            </a>
        </dd>
        <dt>Developers:</dt>
        <dd>
            <router-link :to="{ name: 'developer-alias-redirect', params: { id: developer.id } }"
                v-for="developer in game.developers"
                :key="developer.id">
                {{ developer.name }}
            </router-link>
        </dd>
        <dt>Platforms:</dt>
        <dd>
            <a v-for="platform in game.platforms"
                :key="platform.id"
                href="">
                {{ platform.name }}
            </a>
        </dd>
        <dt>Year of release:</dt>
        <dd>{{ game.yearOfRelease }}</dd>
        <dt>Genres:</dt>
        <dd>
            <a v-for="genre in game.genres"
                :key="genre.id"
                href="">
                {{ genre.name }}
            </a>
        </dd>
        <dt>IGDB Link:</dt>
        <dd>
            <a :href="game.igdbUrl"
                target="_blank">{{ game.igdb_url }}</a>
        </dd>
    </dl>
</template>


<script>
export default {

    props: ['game'],

}
</script>