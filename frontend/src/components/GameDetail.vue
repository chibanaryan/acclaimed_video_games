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
        <!-- <div class="description box">
            <div v-html="game.renderedDescription">
            </div>
            <small class="has-text-grey-dark mt-3">from IGDB.com</small>
        </div> -->
        <div v-for="group in groupedLists"
            :key="group[0]">
            <h2 class="title is-5">{{ group[0] }} Lists</h2>
            <table class="table is-fullwidth mb-5">
                <thead>
                    <tr>
                        <th style="width: 15em">Publication</th>
                        <th>List</th>
                        <th style="width: 5em">Year</th>
                        <th style="width: 5em">Rank</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="list in group[1]"
                        :key="list">
                        <td>{{ list.publication }}</td>
                        <td>
                            <a :href="list.url"
                                target="_blank">
                                {{ list.name }}
                            </a>
                        </td>
                        <td>{{ list.year }}</td>
                        <td>{{ list.rank }}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script>
import { LIST_TYPE_LABELS } from "@/constants";
import _ from "lodash";
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
    },
    computed: {
        groupedLists() {
            let grouped = Object.entries(_.groupBy(this.game.lists, 'type'));
            grouped = grouped.map(x => {
                return [LIST_TYPE_LABELS[x[0]], x[1]];
            })
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