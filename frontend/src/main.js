import '@mdi/font/css/materialdesignicons.css';
import 'bulma/css/bulma.css';
import { ViteSSG } from 'vite-ssg';
import App from './App.vue';
import fetchIntercept from "fetch-intercept";
import mitt from 'mitt';
import { routes, setupRouter } from './router';
import store from './store';
import vueGTag from 'vue-gtag';
import Genre from './models/Genre';
import Platform from './models/Platform';
import Game from './models/Game';
import Developer from './models/Developer';

export const createApp = ViteSSG(
    App,
    {
        routes,
        scrollBehavior: (to, from, savedPosition) => {
            // If user clicked browser back button and savedPosition exists, use it
            if (savedPosition) {
                return savedPosition;
            }
            // Otherwise, scroll to top of page for all navigation
            return { top: 0 };
        }
    },
    async ({ app, router, initialState, isClient }) => {
        // Setup Vuex store
        app.use(store);

        // Pre-load store data during SSR for Wayback Machine compatibility
        if (import.meta.env.SSR) {
            try {
                // Load all store data before rendering
                await Promise.all([
                    store.dispatch('loadGenres'),
                    store.dispatch('loadPlatforms'),
                    store.dispatch('loadMeta'),
                ]);
                console.log('[SSG] Pre-loaded store data (genres, platforms, meta)');
            } catch (err) {
                console.error('[SSG] Failed to pre-load store data:', err);
            }
        }

        // Sync Vuex state between server and client
        if (import.meta.env.SSR) {
            // During SSG, save state to be sent to client
            // Always ensure loading is false in serialized state
            const stateToSerialize = { ...store.state, loading: false };
            initialState.store = stateToSerialize;
        } else if (initialState.store) {
            // On client, restore state from server
            // Re-instantiate model classes that were serialized as plain objects
            const restoredState = {
                ...initialState.store,
                genres: initialState.store.genres.map(g => new Genre(g)),
                platforms: initialState.store.platforms.map(p => new Platform(p)),
                // Restore cached games (from game detail pages)
                games: Object.fromEntries(
                    Object.entries(initialState.store.games).map(([slug, game]) => [
                        slug,
                        new Game(game)
                    ])
                ),
                // Restore cached developers and their games
                developers: Object.fromEntries(
                    Object.entries(initialState.store.developers).map(([slug, data]) => [
                        slug,
                        {
                            developer: new Developer(data.developer),
                            games: data.games.map(g => new Game(g))
                        }
                    ])
                ),
                // Restore cached games lists
                gamesLists: Object.fromEntries(
                    Object.entries(initialState.store.gamesLists).map(([queryKey, data]) => [
                        queryKey,
                        {
                            results: data.results.map(g => new Game(g)),
                            count: data.count
                        }
                    ])
                ),
            };
            store.replaceState(restoredState);
            console.log('[Client] Restored cached data from SSR:', {
                games: Object.keys(restoredState.games).length,
                developers: Object.keys(restoredState.developers).length,
                gamesLists: Object.keys(restoredState.gamesLists).length,
            });
        }

        // Setup router navigation guards
        setupRouter(router);

        // Client-only plugins and features
        if (isClient) {
            // Google Analytics (production only)
            if (import.meta.env.PROD) {
                app.use(vueGTag, {
                    config: {
                        id: import.meta.env.VITE_GOOGLE_ANALYTICS_PROPERTY_ID
                    },
                    router,
                });
            }

            // Event emitter for component communication
            app.config.globalProperties.emitter = mitt();

            // Fetch interceptor for loading state (register after mount)
            // We need to wait a tick to ensure it's registered after the app is mounted
            setTimeout(() => {
                fetchIntercept.register({
                    request: (url, config) => {
                        store.commit('setLoading', true);
                        return [url, config];
                    },
                    response: (response) => {
                        store.commit('setLoading', false);
                        return response;
                    },
                });
            }, 0);
        } else {
            // Provide no-op emitter during SSG to prevent errors
            app.config.globalProperties.emitter = {
                emit: () => {},
                on: () => {},
                off: () => {},
                all: new Map(),
            };
        }
    }
);