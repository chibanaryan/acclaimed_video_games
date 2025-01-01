<template>
    <div class="columns">
        <div class="column">
            <img :src="logoLarge" />
            <div class="is-size-4">
                <snippet-component slug="front-page"></snippet-component>
            </div>
            <h3 class="title is-size-4 mt-5">Current Top {{ games.length }}</h3>
            <div class="top-ten is-clearfix">
                <div class="game"
                    v-for="game in games"
                    :key="game.id">
                    <router-link :to="{ name: 'game-detail', params: { slug: game.slug } }">
                        <span class="rank">{{ game.rank }}</span>
                        <img :src="game.thumbnail">
                    </router-link>
                </div>
                <div class="link">
                    <router-link :to="{ name: 'games-list' }"
                        class="button">
                        See the full list&hellip;
                    </router-link>
                </div>
            </div>
            <div class="py-3">
                Last update: {{ lastUpdate?.fromNow() }}
            </div>
        </div>
        <div class="column">
            <h3 class="title is-size-4">Latest News</h3>
            <post-item v-for="post in posts"
                :key="post.id"
                :post="post"></post-item>
            <div class="is-clearfix">
                <router-link :to="{ name: 'post-list', query: { offset: 5 } }"
                    class="button is-link is-pulled-right">
                    <span>Older posts</span>
                    <span class="icon">
                        <span class="mdi mdi-chevron-double-right"></span>
                    </span>
                </router-link>
            </div>
        </div>
    </div>
</template>

<script>
import { IMAGES } from '@/constants';
import moment from 'moment';
import Game from '../models/Game';
import Post from '../models/Post';
import PostItem from './PostItem';
import SnippetComponent from './SnippetComponent';

export default {
    components: { SnippetComponent, PostItem },
    data() {
        return {
            posts: [],
            games: [],
            lastUpdate: null,
        }
    },
    async created() {
        let data = await fetch(`${process.env.VUE_APP_API_URL}posts/?limit=5`)
            .then(resp => resp.json());
        this.posts = data.results.map(x => new Post(x));

        data = await fetch(`${process.env.VUE_APP_API_URL}games/?limit=10`)
            .then(resp => resp.json());
        this.games = data.results.map(x => new Game(x));

        await this.$store.dispatch('loadMeta');
        this.lastUpdate = moment(this.$store.state.meta?.games?.last_update);
    },
    computed: {
        logoLarge() {
            return IMAGES.LOGO_LARGE;
        }
    }
}
</script>

<style>
.top-ten {
    border-top: 2px solid #4a4a4a;
    padding-top: 15px;
    border-bottom: 2px solid #4a4a4a;
    padding-bottom: 10px;
}

.top-ten .game {
    float: left;
    width: 155px;
    margin-bottom: 20px;
}

.top-ten .link {
    float: left;
    width: 322px;
    height: 120px;
    padding: 40px;
    position: relative;
}

.top-ten .game .rank {
    vertical-align: top;
    display: inline-block;
    font-family: Handjet, sans-serif;
    font-size: 60px;
    font-weight: 800;
    text-shadow: -3px 3px 0px #5d5b5b;
    color: #fff;
    width: 60px;
    text-align: center;
    padding-top: 15px;
}
</style>