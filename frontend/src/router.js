import { createRouter, createWebHistory } from 'vue-router';
import DeveloperAliasRedirect from './components/DeveloperAliasRedirect';
import DeveloperDetail from './components/DeveloperDetail';
import DeveloperList from './components/DeveloperList';
import GameDetail from './components/GameDetail';
import GameList from './components/GameList';
import HomePage from './components/HomePage';
import ListList from './components/ListList';
import PageDetail from './components/PageDetail';
import PostList from './components/PostList';
import store from './store';

const routes = [
    { path: '/', component: HomePage, name: 'home' },
    { path: '/developer-alias/:id/', component: DeveloperAliasRedirect, name: 'developer-alias-redirect' },
    { path: '/developers/', component: DeveloperList, name: 'developers-list' },
    { path: '/developers/:slug/', component: DeveloperDetail, name: 'developer-detail' },
    { path: '/games/:slug/', component: GameList, name: 'games-list' },
    { path: '/game/:slug/', component: GameDetail, name: 'game-detail' },
    { path: '/lists/', component: ListList, name: 'list-list' },
    { path: '/page/:slug/', component: PageDetail, name: 'page-detail' },
    { path: '/posts/', component: PostList, name: 'post-list' },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

router.beforeEach((to, from, next) => {
    store.commit('loading', true);
    next();
})

router.afterEach(() => {
    setTimeout(() => {
        store.commit('loading', false);
    }, 200)
})

export default router;
