import { createStore } from 'vuex'
import Genre from "./models/Genre";
import Platform from "./models/Platform";
import { getApiUrl } from './config';
import _ from 'lodash';
const { isEmpty } = _;

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
                `${getApiUrl()}genres/?limit=999`
            ).then((resp) => resp.json());

            commit('setGenres', data.results.map((x) => new Genre(x)));
        },
        async loadPlatforms({ commit, state }) {
            if (state.platforms.length)
                return;

            let data = await fetch(
                `${getApiUrl()}platforms/?limit=999`
            ).then((resp) => resp.json());

            commit('setPlatforms', data.results.map((x) => new Platform(x)));
        },
        async loadMeta({ commit, state }) {
            if (!isEmpty(state.meta))
                return;

            try {
                let data = await fetch(
                    `${getApiUrl()}meta/`
                ).then((resp) => {
                    if (!resp.ok)
                        throw new Error(`Meta request failed: ${resp.status}`);
                    return resp.json();
                });

                commit('setMeta', data);
            } catch (err) {
                console.error('Unable to load metadata', err);
                commit('setMeta', {});
                throw err;
            }
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
