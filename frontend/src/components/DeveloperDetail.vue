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
import { getApiUrl } from "@/config";
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
        const slug = this.$route.params.slug;

        // Check if data was pre-fetched during SSR
        if (this.$route.meta.ssrData) {
            const { developer: developerData, games: gamesData } = this.$route.meta.ssrData;
            this.developer = new Developer(developerData);
            this.developer.aliases.forEach(x => x.selected = true);
            this.games = gamesData.map(x => new Game(x));

            // Cache the SSR data in the store for later reuse
            this.$store.commit('setDeveloper', {
                slug,
                result: { developer: this.developer, games: this.games }
            });
            console.log('[SSG] Using pre-fetched developer data and caching in store');

            // Emitter may not be available during SSR
            if (this.emitter) {
                this.emitter.emit('title', this.developer.name);
            }
            return;
        }

        // Otherwise fetch via store (which checks cache first)
        try {
            const { developer, games } = await this.$store.dispatch('fetchDeveloper', { slug });
            this.developer = developer;
            this.developer.aliases.forEach(x => x.selected = true);
            this.games = games;

            if (this.emitter) {
                this.emitter.emit('title', this.developer.name);
            }
        } catch (err) {
            console.error('Error fetching developer or games:', err);
            if (err.status === 404) {
                this.error = 'Developer not found';
            } else if (err.status > 0) {
                this.error = `Failed to load developer (${err.status})`;
            } else {
                this.error = 'Network error - please check your connection and try again';
            }
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
