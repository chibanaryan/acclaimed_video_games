<template>
    <div class="columns">
        <div class="column">
            <img src="/static/games/avg_logo.png">
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
                    <router-link :to="{ name: 'games-list', params: { slug: 'alltime' } }"
                        class="button">
                        See the full list&hellip;
                    </router-link>
                </div>
            </div>
        </div>
        <div class="column">
            <post-item v-for="post in posts"
                :key="post.id"
                :post="post"></post-item>
        </div>
    </div>
</template>

<script>
import SnippetComponent from './SnippetComponent';
import PostItem from './PostItem';
import Post from '../models/Post';
import Game from '../models/Game';

export default {
    components: { SnippetComponent, PostItem },
    data() {
        return {
            posts: [],
            games: [],
        }
    },
    async created() {
        let data = await fetch(`${process.env.VUE_APP_API_URL}posts/?limit=5`)
            .then(resp => resp.json());
        this.posts = data.results.map(x => new Post(x));

        data = await fetch(`${process.env.VUE_APP_API_URL}games/?limit=10`)
            .then(resp => resp.json());
        this.games = data.results.map(x => new Game(x));
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
    padding: 10px;
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