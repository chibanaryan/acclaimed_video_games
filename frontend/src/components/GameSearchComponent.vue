<template>
    <div class="dropdown"
        :class="{ 'is-active': results.length }">
        <div class="field has-addons m-0">
            <div class="control has-icons-left">
                <span class="icon">
                    <span class="mdi mdi-magnify"></span>
                </span>
                <input v-model="q"
                    @focus="loadResults()"
                    @blur="clearResults()"
                    placeholder="Search games"
                    type="text"
                    class="input">
            </div>
            <div v-if="q"
                class="control">
                <a @click="q = null"
                    class="button">
                    <span class="icon">
                        <span class="mdi mdi-close"></span>
                    </span>
                </a>
            </div>
        </div>
        <div class="dropdown-menu">
            <div class="dropdown-content">
                <div v-for="result in results"
                    :key="result.id">
                    <router-link :to="{ name: 'game-detail', params: { slug: result.slug } }"
                        class="dropdown-item">
                        <div class="media">
                            <div class="media-left">
                                <figure class="image is-32x32">
                                    <img :src="result.thumbnail">
                                </figure>
                            </div>
                            <div class="media-content">
                                <div class="has-text-weight-semibold">{{ result.name }} ({{ result.yearOfRelease }})
                                </div>
                                <div class="has-text-weight-light">{{ result.developers.map(x => x.name).join(', ')
                                    }}
                                </div>
                            </div>
                        </div>
                    </router-link>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import Game from '@/models/Game';
import _ from "lodash";

export default {
    data() {
        return {
            q: null,
            results: [],
        }
    },
    methods: {
        loadResults: _.debounce(async function () {
            let url = `${process.env.VUE_APP_API_URL}games/?q=${this.q}&limit=5&order_by=rank`;
            let data = await fetch(url)
                .then(resp => resp.json());
            this.results = data.results.map(x => new Game(x));
        }, 200, { leading: true }),
        clearResults() {
            // Need to wait before clearing results or clicking on them won't work
            setTimeout(() => {
                this.q = null;
                this.results = [];
            }, 200)
        }
    },
    watch: {
        q(val) {
            if (val)
                this.loadResults();
            else
                this.clearResults();
        }
    }
}
</script>