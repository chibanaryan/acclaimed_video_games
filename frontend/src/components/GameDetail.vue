<template>
    <div v-if="game">
        <h1 class="title">{{ game.name }}</h1>
        <div class="columns">
            <div class="column">
                <game-properties :game="game"></game-properties>
            </div>
            <div class="column">
                <img :src="game.image">
            </div>
        </div>
        <div class="description box">
            <div v-html="game.renderedDescription">
            </div>
            <small class="has-text-grey-dark mt-3">from IGDB.com</small>
        </div>
    </div>
</template>

<script>
import Game from '../models/Game';
import GameProperties from './GameProperties';
export default {
    components: { GameProperties },
    data() {
        return {
            game: null,
        }
    },
    async created() {
        let data = await fetch(`${process.env.VUE_APP_API_URL}games/${this.$route.params.slug}/`)
            .then(resp => resp.json());
        this.game = new Game(data);
    }
}
</script>

<style>
.description p {
    margin-bottom: 1em;
}
</style>