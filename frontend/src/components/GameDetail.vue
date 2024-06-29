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
        <div v-for="group in groupedLists"
            :key="group[0]">
            <h2 class="title is-5">{{ group[0] }} Lists</h2>
            <list-results-component :items="group[1]"
                :show-type="false"
                :show-rank="true">
            </list-results-component>
        </div>
    </div>
</template>

<script>
import { LIST_TYPE_LABELS } from "@/constants";
import _ from "lodash";
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
        }
    },
    async created() {
        let data = await fetch(`${process.env.VUE_APP_API_URL}games/${this.$route.params.slug}/`)
            .then(resp => resp.json());
        this.game = new Game(data);
        this.emitter.emit('title', this.game.name);
    },
    computed: {
        groupedLists() {
            let grouped = Object.entries(_.groupBy(this.game.lists, 'type'));
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