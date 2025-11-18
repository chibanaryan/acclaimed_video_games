import { createStore } from 'vuex'
import Genre from "./models/Genre";
import Platform from "./models/Platform";
import Game from "./models/Game";
import Developer from "./models/Developer";
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
            // Caching for games and developers
            games: {}, // Indexed by slug
            developers: {}, // Indexed by slug, includes { developer, games }
            gamesLists: {}, // Indexed by query key (e.g., "limit=100&offset=0")
        }
    },
    getters: {
        // Get a cached game by slug
        getGameBySlug: (state) => (slug) => {
            return state.games[slug];
        },
        // Get a cached developer by slug
        getDeveloperBySlug: (state) => (slug) => {
            return state.developers[slug];
        },
        // Get a cached games list by query parameters
        getGamesList: (state) => (queryKey) => {
            return state.gamesLists[queryKey];
        },
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
        // Fetch a single game by slug, with caching
        async fetchGame({ commit, state }, { slug, force = false }) {
            // Check cache first (unless force refresh)
            if (!force && state.games[slug]) {
                console.log(`[Cache] Using cached game: ${slug}`);
                return state.games[slug];
            }

            console.log(`[API] Fetching game: ${slug}`);
            const response = await fetch(`${getApiUrl()}games/${slug}/`);

            if (!response.ok) {
                const error = new Error(`Failed to fetch game: ${response.status}`);
                error.status = response.status;
                throw error;
            }

            const data = await response.json();
            const game = new Game(data);
            commit('setGame', { slug, game });
            return game;
        },
        // Fetch a list of games with filters/pagination, with caching
        async fetchGamesList({ commit, state }, { queryParams, force = false }) {
            const queryKey = new URLSearchParams(queryParams).toString();

            // Check cache first (unless force refresh)
            if (!force && state.gamesLists[queryKey]) {
                console.log(`[Cache] Using cached games list: ${queryKey}`);
                return state.gamesLists[queryKey];
            }

            console.log(`[API] Fetching games list: ${queryKey}`);
            const response = await fetch(`${getApiUrl()}games/?${queryKey}`);

            if (!response.ok) {
                const error = new Error(`Failed to fetch games list: ${response.status}`);
                error.status = response.status;
                throw error;
            }

            const data = await response.json();
            const result = {
                results: data.results.map((x) => new Game(x)),
                count: data.count,
            };

            commit('setGamesList', { queryKey, result });
            return result;
        },
        // Fetch the complete unfiltered games list (for client-side pagination)
        async fetchAllGamesList({ commit, state }, { force = false } = {}) {
            const cacheKey = 'all';

            // Check cache first (unless force refresh)
            if (!force && state.gamesLists[cacheKey]) {
                console.log(`[Cache] Using cached full games list`);
                return state.gamesLists[cacheKey];
            }

            console.log(`[API] Fetching complete games list`);
            const response = await fetch(`${getApiUrl()}games/?limit=9999`);

            if (!response.ok) {
                const error = new Error(`Failed to fetch all games: ${response.status}`);
                error.status = response.status;
                throw error;
            }

            const data = await response.json();
            const result = {
                results: data.results.map((x) => new Game(x)),
                count: data.count,
            };

            commit('setGamesList', { queryKey: cacheKey, result });
            return result;
        },
        // Fetch a developer and their games, with caching
        async fetchDeveloper({ commit, state }, { slug, force = false }) {
            // Check cache first (unless force refresh)
            if (!force && state.developers[slug]) {
                console.log(`[Cache] Using cached developer: ${slug}`);
                return state.developers[slug];
            }

            console.log(`[API] Fetching developer: ${slug}`);

            // Fetch developer details
            const developerResponse = await fetch(`${getApiUrl()}developers/${slug}/`);

            if (!developerResponse.ok) {
                const error = new Error(`Failed to fetch developer: ${developerResponse.status}`);
                error.status = developerResponse.status;
                throw error;
            }

            const developerData = await developerResponse.json();
            const developer = new Developer(developerData);

            // Fetch developer's games
            const gamesResponse = await fetch(
                `${getApiUrl()}games/?developer=${developer.id}&order_by=year_of_release`
            );

            if (!gamesResponse.ok) {
                const error = new Error(`Failed to fetch developer games: ${gamesResponse.status}`);
                error.status = gamesResponse.status;
                throw error;
            }

            const gamesData = await gamesResponse.json();
            const games = gamesData.results.map(x => new Game(x));

            const result = { developer, games };
            commit('setDeveloper', { slug, result });
            return result;
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
        setGame(state, { slug, game }) {
            state.games[slug] = game;
        },
        setGamesList(state, { queryKey, result }) {
            state.gamesLists[queryKey] = result;
        },
        setDeveloper(state, { slug, result }) {
            state.developers[slug] = result;
        },
    },
})

export default store;
