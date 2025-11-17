import '@mdi/font/css/materialdesignicons.css';
import 'bulma/css/bulma.css';
import { ViteSSG } from 'vite-ssg';
import App from './App.vue';
import fetchIntercept from "fetch-intercept";
import mitt from 'mitt';
import { routes, setupRouter } from './router';
import store from './store';
import vueGTag from 'vue-gtag';

export const createApp = ViteSSG(
    App,
    { routes },
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
            store.replaceState(initialState.store);
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