<template>
    <div v-if="error" class="notification is-danger">
        <p><strong>Error:</strong> {{ error }}</p>
        <p>The developer you're looking for could not be found or there was a problem loading it.</p>
    </div>
    <div v-else-if="developer">
        <h1 class="title">{{ developer.name }}</h1>
        <h2>Including:</h2>
        <ul v-if="developer.aliases.length > 1">
            <li v-for="alias in developer.aliases"
                :key="alias.id">
                <label class="checkbox">
                    <input v-model="alias.selected"
                        type="checkbox">
                    {{ alias.name }}
                </label>
            </li>
        </ul>
        <h2 class="subtitle is-4 mt-5">
            {{ games.length }} Game{{ games.length == 1 ? '' : 's' }}
        </h2>
        <div>
            <game-row v-for="game in filteredGames"
                :key="game.id"
                :game="game"
                :show-rank="false"
                :show-rank-in-details="true"></game-row>
        </div>
    </div>
    <div v-else class="has-text-centered">
        <p>Loading...</p>
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
            error: null,
        }
    },
    async created() {
        try {
            // Fetch developer details
            const developerResponse = await fetch(`${import.meta.env.VITE_API_URL}developers/${this.$route.params.slug}/`);

            if (!developerResponse.ok) {
                if (developerResponse.status === 404) {
                    this.error = 'Developer not found';
                } else {
                    this.error = `Failed to load developer (${developerResponse.status})`;
                }
                return;
            }

            const developerData = await developerResponse.json();
            this.developer = new Developer(developerData);
            this.developer.aliases.forEach(x => x.selected = true);

            // Fetch games for this developer
            const gamesResponse = await fetch(`${import.meta.env.VITE_API_URL}games/?developer=${this.developer.id}&order_by=year_of_release`);

            if (!gamesResponse.ok) {
                this.error = `Failed to load games for developer (${gamesResponse.status})`;
                return;
            }

            const gamesData = await gamesResponse.json();
            this.games = gamesData.results.map(x => new Game(x));

            this.emitter.emit('title', this.developer.name);
        } catch (err) {
            console.error('Error fetching developer or games:', err);
            this.error = 'Network error - please check your connection and try again';
        }
    },
    computed: {
        selectedAliases() {
            return this.developer.aliases.filter(x => x.selected);
        },
        filteredGames() {
            const selectedAliasIds = this.selectedAliases.map(x => x.id);
            return this.games.filter(x => {
                const developerIds = x.developers.map(y => y.id);
                const intersection = selectedAliasIds.filter(y => developerIds.includes(y));
                return intersection.length > 0;
            })
        }
    }
}
</script>
