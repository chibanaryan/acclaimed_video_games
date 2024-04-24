<template>
    <div v-if="developer">
        <h1 class="title">{{ developer.name }}</h1>
        <h2>Including:</h2>
        <ul>
            <li v-for="alias in developer.aliases"
                :key="alias.id">
                <em>{{ alias.name }}</em>
            </li>
        </ul>
        <h2 class="subtitle is-4 mt-5">
            {{ games.length }} Game{{ games.length == 1 ? '' : 's' }}
        </h2>
        <div>
            <game-row v-for="game in games"
                :key="game.id"
                :game="game"
                :show-rank="false"></game-row>
        </div>
    </div>
</template>

<script>
import Developer from '../models/Developer';
import Game from '../models/Game';
import GameRow from './GameRow';

export default {
    components: { GameRow },
    data() {
        return {
            developer: null,
            games: [],
        }
    },
    async created() {
        let data = await fetch(`${process.env.VUE_APP_API_URL}developers/${this.$route.params.slug}/`)
            .then(resp => resp.json());
        this.developer = new Developer(data);

        data = await fetch(`${process.env.VUE_APP_API_URL}games/?developer=${this.developer.id}&order_by=year_of_release`)
            .then(resp => resp.json());
        this.games = data.results.map(x => new Game(x));
    }
}
</script>
