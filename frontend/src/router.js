import { createRouter, createWebHashHistory } from 'vue-router';
import GamesList from './components/GamesList';
import GameDetail from './components/GameDetail';
import HomePage from './components/HomePage';
import ListList from './components/ListList';
import PageDetail from './components/PageDetail';
import DeveloperList from './components/DeveloperList';
import DeveloperDetail from './components/DeveloperDetail';
import DeveloperAliasRedirect from './components/DeveloperAliasRedirect';
import PostList from './components/PostList';
import GameSearch from './components/GameSearch';

const routes = [
    { path: '/', component: HomePage, name: 'home' },
    { path: '/developer-alias/:id/', component: DeveloperAliasRedirect, name: 'developer-alias-redirect' },
    { path: '/developers/', component: DeveloperList, name: 'developers-list' },
    { path: '/developers/:slug/', component: DeveloperDetail, name: 'developer-detail' },
    { path: '/games/:slug/', component: GamesList, name: 'games-list' },
    { path: '/games/game/:slug/', component: GameDetail, name: 'game-detail' },
    { path: '/games/search/', component: GameSearch, name: 'games-search' },
    { path: '/lists/', component: ListList, name: 'list-list' },
    { path: '/page/:slug/', component: PageDetail, name: 'page-detail' },
    { path: '/posts/', component: PostList, name: 'post-list' },
]

const router = createRouter({
    history: createWebHashHistory(''),
    routes,
})

export default router;
