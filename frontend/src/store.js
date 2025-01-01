import { createStore } from 'vuex'
import Genre from "./models/Genre";
import Platform from "./models/Platform";
import { isEmpty } from 'lodash';

const store = createStore({
    state() {
        return {
            loading: false,
            genres: [],
            platforms: [],
            meta: {},
        }
    },
    actions: {
        async loadGenres({ commit, state }) {
            if (state.genres.length)
                return;

            let data = await fetch(
                `${process.env.VUE_APP_API_URL}genres/?limit=999`
            ).then((resp) => resp.json());

            commit('setGenres', data.results.map((x) => new Genre(x)));
        },
        async loadPlatforms({ commit, state }) {
            if (state.platforms.length)
                return;

            let data = await fetch(
                `${process.env.VUE_APP_API_URL}platforms/?limit=999`
            ).then((resp) => resp.json());

            commit('setPlatforms', data.results.map((x) => new Platform(x)));
        },
        async loadMeta({ commit, state }) {
            if (!isEmpty(state.meta))
                return;

            let data = await fetch(
                `${process.env.VUE_APP_API_URL}meta/`
            ).then((resp) => resp.json());

            commit('setMeta', data);
        },
    },
    mutations: {
        setLoading(state, val) {
            state.loading = val;
        },
        setGenres(state, val) { 
            state.genres = val;
        },
        setPlatforms(state, val) { 
            state.platforms = val;
        },
        setMeta(state, val) {             
            state.meta = val;
        },
    },
})

export default store;