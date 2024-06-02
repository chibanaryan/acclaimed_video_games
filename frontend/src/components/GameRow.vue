<template>
    <div class="columns is-hidden-mobile game-row desktop">
        <div class="column is-narrow">
            <div class="columns">
                <div v-if="showRank"
                    class="column is-narrow">
                    <span class="rank">
                        {{ game.rank }}
                    </span>
                </div>
                <div class="column is-narrow">
                    <router-link :to="{ name: 'game-detail', params: { slug: game.slug } }">
                        <img :src="game.thumbnail" />
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
            <game-row-properties :game="game"
                :show-rank="false"> </game-row-properties>
        </div>
    </div>

    <div class="is-hidden-desktop is-hidden-tablet game-row mobile pb-4">
        <div class="py-3">
            <router-link :to="{ name: 'game-detail', params: { slug: game.slug } }"
                class="game-name has-text-weight-bold is-size-6">
                <span v-if="showRank"
                    class="rank">{{ game.rank }}</span>
                {{ game.name }} </router-link>
            <router-link :to="{ name: 'games-list', params: { slug: game.yearOfRelease } }">
                ({{ game.yearOfRelease }})
            </router-link>
        </div>
        <div class="columns is-mobile">
            <div class="column is-narrow">
                <router-link :to="{ name: 'game-detail', params: { slug: game.slug } }">
                    <img :src="game.thumbnail" />
                </router-link>
            </div>
            <div class="column">
                <game-row-properties :game="game"
                    :show-rank="false">
                </game-row-properties>
            </div>
        </div>
    </div>
</template>

<script>
import GameRowProperties from "./GameRowProperties";

export default {
    props: {
        game: null,
        showRank: {
            default: true,
        },
    },
    components: { GameRowProperties },
};
</script>

<style lang="sass" scoped>

.game-row 
    border-bottom: 1px solid #616161

    .thumbnail img 
        max-width: inherit

    &.desktop
        .rank 
            text-align: center
            display: flex
            align-items: center
            justify-content: center
            color: #fff
            font-family: Handjet, sans-serif
            font-weight: 800
            text-shadow: -3px 3px 0px #5d5b5b
            min-width: 122px
            font-size: 60px

    &.mobile
        .rank 
            color: #fff
            font-family: Handjet, sans-serif
            font-weight: 800
            text-shadow: -2px 2px 0px #5d5b5b
            font-size: 25px
            margin-right: 5px
            vertical-align: middle

</style>
