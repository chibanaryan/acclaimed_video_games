<template>
    <div class="navbar-item">

        <!-- Desktop version -->
        <div class="is-hidden-mobile desktop-search">
            <div class="dropdown "
                :class="{ 'is-active': showMenu }">

                <div class="field has-addons m-0">
                    <div class="control has-icons-left">
                        <span class="icon">
                            <span class="mdi mdi-magnify"></span>
                        </span>
                        <input v-model="q"
                            @focus="onFocus()"
                            @blur="onBlur()"
                            ref="searchInputDesktop"
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
                        <div v-if="results.length == 0"
                            class="dropdown-item">{{ message }}</div>
                        <div v-for="result in results"
                            :key="result.id">
                            <game-search-result :result="result"
                                class="dropdown-item"></game-search-result>
                        </div>
                        <router-link :to="{ name: 'games-search', query: { q: q } }"
                            v-if="results.length"
                            class="dropdown-item">
                            See all results &hellip;
                        </router-link>
                    </div>
                </div>

            </div>
        </div>

        <!-- Mobile version -->
        <div class="is-hidden-tablet mobile-search">

            <button @click="toggleInputMobile"
                v-show="!active">
                <span class="icon">
                    <span class="mdi mdi-magnify mdi-24px"></span>
                </span>
            </button>

            <div v-show="active"
                class="results-wrapper">

                <div class="field has-addons">
                    <div class="control has-icons-left is-expanded">
                        <span class="icon">
                            <span class="mdi mdi-magnify"></span>
                        </span>
                        <input v-model="q"
                            @focus="onFocus()"
                            @blur="onBlur()"
                            @keyup="onKeyup"
                            ref="searchInputMobile"
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

                <div v-if="showMenu"
                    class="results">
                    <div v-if="results.length == 0"
                        class="dropdown-item">{{ message }}</div>
                    <game-search-result v-for="result in results"
                        :key="result.id"
                        :result="result"></game-search-result>
                    <router-link :to="{ name: 'games-search', query: { q: q } }"
                        v-if="results.length"
                        class="dropdown-item">
                        See all results &hellip;
                    </router-link>
                </div>
            </div>

        </div>

    </div>
</template>

<script>
import Game from '@/models/Game';
import _ from "lodash";
import GameSearchResult from "./GameSearchResult";

export default {
    components: { GameSearchResult },
    data() {
        return {
            q: null,
            results: [],
            active: false,
            showMenu: false,
        }
    },
    methods: {
        loadResults: _.debounce(async function () {
            let url = `${process.env.VUE_APP_API_URL}games/?q=${this.q}&limit=5&order_by=rank`;
            let data = await fetch(url)
                .then(resp => resp.json());
            this.results = data.results.map(x => new Game(x));
        }, 200, { leading: true }),
        toggleInputDesktop() {
            this.active = !this.active;
            if (this.active)
                setTimeout(() => {
                    this.$refs.searchInputDesktop.focus()
                }, 100)
        },
        toggleInputMobile() {
            this.active = !this.active;
            if (this.active)
                setTimeout(() => {
                    this.$refs.searchInputMobile.focus()
                }, 100)
        },
        onBlur() {
            setTimeout(() => {
                this.q = null;
                this.results = [];
                this.active = false;
                this.showMenu = false;
            }, 200)
        },
        onFocus() {
            this.showMenu = true;
        },
    },
    computed: {
        message() {
            return (!this.q || this.q.length <= 1)
                ? "Please enter two or more characters"
                : "No results found";
        }
    },
    watch: {
        q(val) {
            val?.length > 1
                ? this.loadResults()
                : this.results = [];
        }
    }
}
</script>

<style lang="sass" scoped>
.mobile-search 
    .results-wrapper
        position: fixed
        top: 0
        left: 0
        right: 0
        z-index: 100
        background-color: #131313        

        .field
            padding: 1rem

        .results
            padding: 0
            padding-bottom: 0.375rem

            .result
                display: block
                font-size: 0.875rem
                line-height: 1.5
                padding-inline-end: 3rem
                padding:  0.375rem 1rem 
                text-align: inherit
                white-space: nowrap
                width: 100%

            .result:first-child
                padding-top: 0

</style>