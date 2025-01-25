import { createRouter, createWebHistory } from 'vue-router';
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

const routes = [
    {
        path: '/',
        component: HomePage,
        name: 'home',
        meta: {
            title: 'Home',
        },
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
        meta: {}
    },
    {
        path: '/games/',
        component: GameList,
        name: 'games-list',
        meta: {}
    },
    {
        path: '/games/search/',
        component: GameSearch,
        name: 'games-search',
        meta: {}
    },
    {
        path: '/game/:slug/',
        component: GameDetail,
        name: 'game-detail',
        meta: {}
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

const router = createRouter({
    history: createWebHistory(),
    routes,
})


// router.afterEach((to, from) => {
//     if(to.name != from.name) {
//         if(from.name == 'games-list')
//             objectStore.set('lastQuery', from.query);
//     }

// })

export default router;
