import DeveloperAliasRedirect from './components/DeveloperAliasRedirect';
import DeveloperDetail from './components/DeveloperDetail';
import DeveloperList from './components/DeveloperList';
import GameDetail from './components/GameDetail';
import GameList from './components/GameList';
import GameSearch from './components/GameSearch';
import HomePage from './components/HomePage';
import ListList from './components/ListList';
import NotFound from './components/NotFound';
import PageDetail from './components/PageDetail';
import PostList from './components/PostList';
import { DEFAULT_TITLE } from './constants';
import { globalStore } from './objectStore';

export const routes = [
    {
        path: '/',
        component: HomePage,
        name: 'home',
        meta: {
            title: DEFAULT_TITLE,
        }
    },
    {
        path: '/developer-alias/:id/',
        component: DeveloperAliasRedirect,
        name: 'developer-alias-redirect',
        meta: {},
    },
    {
        path: '/developers/',
        component: DeveloperList,
        name: 'developers-list',
        meta: {
            title: 'Developers',
        }
    },
    {
        path: '/developers/:slug/',
        component: DeveloperDetail,
        name: 'developer-detail',
        meta: {},
        async beforeEnter(to) {
            // Pre-fetch developer data during SSG for Wayback Machine compatibility
            if (import.meta.env.SSR) {
                const apiUrl = import.meta.env.VITE_SSG_API_URL || 'http://127.0.0.1:8000/api/';
                try {
                    // Fetch developer details
                    const developerResponse = await fetch(`${apiUrl}developers/${to.params.slug}/`);
                    if (!developerResponse.ok) {
                        console.error(`[SSG] Failed to fetch developer ${to.params.slug}: ${developerResponse.status}`);
                        return;
                    }
                    const developerData = await developerResponse.json();

                    // Fetch games for this developer
                    const gamesResponse = await fetch(`${apiUrl}games/?developer=${developerData.id}&order_by=year_of_release`);
                    if (!gamesResponse.ok) {
                        console.error(`[SSG] Failed to fetch games for developer ${to.params.slug}: ${gamesResponse.status}`);
                        // Still save developer data even if games fail
                        to.meta.ssrData = { developer: developerData, games: [] };
                        return;
                    }
                    const gamesData = await gamesResponse.json();

                    to.meta.ssrData = {
                        developer: developerData,
                        games: gamesData.results
                    };
                    console.log(`[SSG] Pre-fetched developer: ${developerData.name} with ${gamesData.results.length} games`);
                } catch (err) {
                    console.error(`[SSG] Failed to fetch developer ${to.params.slug}:`, err);
                }
            }
        }
    },
    {
        path: '/games/',
        component: GameList,
        name: 'games-list',
        meta: {
            title: 'All time',
        },
        async beforeEnter(to) {
            // Pre-fetch game data during SSG for Wayback Machine compatibility
            if (import.meta.env.SSR) {
                const apiUrl = import.meta.env.VITE_SSG_API_URL || 'http://127.0.0.1:8000/api/';

                // Check if this is a filtered view (has year/decade filters)
                const isFiltered = to.query.start && to.query.end;

                let params;
                if (isFiltered) {
                    // For filtered views, fetch with filters and pagination
                    params = new URLSearchParams({
                        limit: to.query.limit || 100,
                        offset: to.query.offset || 0,
                        start: to.query.start,
                        end: to.query.end,
                    });
                } else {
                    // For unfiltered view, fetch ALL games (used for client-side pagination)
                    params = new URLSearchParams({
                        limit: 9999,
                    });
                }

                try {
                    const response = await fetch(`${apiUrl}games/?${params}`);
                    const data = await response.json();
                    to.meta.ssrData = data;
                    console.log(`[SSG] Pre-fetched ${data.results.length} games for /games/`);
                } catch (err) {
                    console.error('[SSG] Failed to fetch games for pre-rendering:', err);
                }
            }
        }
    },
    {
        path: '/games/search/',
        component: GameSearch,
        name: 'games-search',
        meta: {
            title: 'Search',
        },
    },
    {
        path: '/game/:slug/',
        component: GameDetail,
        name: 'game-detail',
        meta: {},
        async beforeEnter(to) {
            // Pre-fetch game data during SSG for Wayback Machine compatibility
            if (import.meta.env.SSR) {
                const apiUrl = import.meta.env.VITE_SSG_API_URL || 'http://127.0.0.1:8000/api/';
                try {
                    const response = await fetch(`${apiUrl}games/${to.params.slug}/`);
                    if (response.ok) {
                        const data = await response.json();
                        to.meta.ssrData = data;
                        console.log(`[SSG] Pre-fetched game: ${data.name}`);
                    } else {
                        console.error(`[SSG] Failed to fetch game ${to.params.slug}: ${response.status}`);
                    }
                } catch (err) {
                    console.error(`[SSG] Failed to fetch game ${to.params.slug}:`, err);
                }
            }
        }
    },
    {
        path: '/lists/',
        component: ListList,
        name: 'list-list',
        meta: {
            title: 'Source Lists',
        }
    },
    {
        path: '/page/:slug/',
        component: PageDetail,
        name: 'page-detail',
        meta: {}
    },
    {
        path: '/posts/',
        component: PostList,
        name: 'post-list',
        meta: {
            title: 'News',
        }
    },
    {
        path: '/:pathMatch(.*)*',
        component: NotFound,
        name: 'not-found',
    },

]

/**
 * Setup router navigation guards
 * This function should be called from main.js after the router is created by ViteSSG
 * @param {Router} router - The Vue Router instance
 */
export function setupRouter(router) {
    router.beforeEach((to, from) => {
        // Guard against SSR - window is only available in browser
        if (typeof window === 'undefined') return;

        // Remember scroll position for game list pages on the next page only
        const gameListRoutes = ['games-search', 'games-list'];
        if (gameListRoutes.includes(from.name))
            globalStore.set('scrollY', window.scrollY);
        else if (!gameListRoutes.includes(to.name))
            globalStore.set('scrollY', null);
    })
}
