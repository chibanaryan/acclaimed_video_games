<template>
    <div v-if="error" class="notification is-danger">
        <p><strong>Error:</strong> {{ error }}</p>
        <p>The game you're looking for could not be found or there was a problem loading it.</p>
    </div>
    <div v-else-if="game">
        <h1 class="title">{{ game.name }}</h1>
        <div class="columns">
            <div class="column">
                <game-properties :game="game"></game-properties>
            </div>
            <div class="column">
                <img :src="game.image">
            </div>
        </div>
        <div v-for="group in groupedLists"
            :key="group[0]">
            <h2 class="title is-5">{{ group[0] }} Lists</h2>
            <list-results-component :items="group[1]"
                :show-type="false"
                :show-rank="true">
            </list-results-component>
        </div>
    </div>
    <div v-else class="has-text-centered">
        <p>Loading...</p>
    </div>
</template>

<script>
import { getApiUrl } from "@/config";
import { LIST_TYPE_LABELS } from "@/constants";
import { apiGet } from "@/api";
import _ from "lodash";
const { groupBy } = _;
import Game from '../models/Game';
import GameProperties from './GameProperties';
import ListResultsComponent from './ListResultsComponent';

export default {
    components: {
        ListResultsComponent,
        GameProperties
    },
    data() {
        return {
            game: null,
            error: null,
        }
    },
    async created() {
        // Check if data was pre-fetched during SSR
        if (this.$route.meta.ssrData) {
            this.game = new Game(this.$route.meta.ssrData);
            // Emitter may not be available during SSR
            if (this.emitter) {
                this.emitter.emit('title', this.game.name);
            }
            return;
        }

        // Otherwise fetch data client-side
        try {
            const data = await apiGet(`${getApiUrl()}games/${this.$route.params.slug}/`);
            this.game = new Game(data);
            if (this.emitter) {
                this.emitter.emit('title', this.game.name);
            }
        } catch (err) {
            if (err.status === 404) {
                this.error = 'Game not found';
            } else if (err.status > 0) {
                this.error = `Failed to load game (${err.status})`;
            } else {
                this.error = 'Network error - please check your connection and try again';
            }
            console.error('Error fetching game:', err);
        }
    },
    computed: {
        groupedLists() {
            let grouped = Object.entries(groupBy(this.game.lists, 'type'));
            grouped = grouped.map(x => {
                return [LIST_TYPE_LABELS[x[0]], x[1]];
            })

            let sortingArr = ['All time', 'Decade', 'Miscellaneous', 'End of year'];
            grouped.sort((a, b) => sortingArr.indexOf(a[0]) - sortingArr.indexOf(b[0]));
            return grouped;
        }
    }
}
</script>

<style>
.description p {
    margin-bottom: 1em;
}
</style>