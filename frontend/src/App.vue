<template>

    <head></head>

    <body>
        <header>
            <div class="container">

                <nav class="navbar mx-1"
                    role="navigation"
                    aria-label="main navigation">
                    <div class="navbar-brand is-hidden-mobile">
                        <router-link :to="{ name: 'home' }"
                            class="navbar-item has-text-weight-bold pl-0">
                            <img src="/static/games/avg_logo_small.png">
                        </router-link>
                        <router-link :to="{ name: 'games-list', params: { slug: 'alltime' } }"
                            class="navbar-item">
                            Top 750
                        </router-link>
                        <router-link :to="{ name: 'developers-list' }"
                            class="navbar-item">
                            Developers
                        </router-link>
                        <router-link :to="{ name: 'list-list' }"
                            class="navbar-item">
                            Source Lists
                        </router-link>
                        <router-link :to="{ name: 'page-detail', params: { slug: 'about' } }"
                            class="navbar-item">
                            About / FAQ
                        </router-link>
                        <router-link :to="{ name: 'page-detail', params: { slug: 'palestine' } }"
                            class="navbar-item">
                            <img src="/static/games/palestine-flag-xs.png"
                                style="height: 15px"
                                title="Statement on Palestine">
                        </router-link>
                    </div>
                </nav>
            </div>
        </header>
        <section>
            <div class="container">
                <router-view class="view"></router-view>
            </div>
        </section>
        <footer>
            <div class="container">
                <router-link :to="{ name: 'home' }">
                    Home
                </router-link>
                •
                <router-link :to="{ name: 'post-list' }">
                    News
                </router-link>
                •
                <router-link :to="{ name: 'page-detail', params: { slug: 'about' } }">
                    About / FAQ
                </router-link>
            </div>
        </footer>
    </body>

</template>

<script>

export default {
    name: 'App',
}
</script>

<style>
html {
    background-color: #000;
}

section {
    min-height: 800px;
}

footer {
    min-height: 15em;
    background-color: #444;
    margin-top: 2em;
    padding-top: 2em;
    text-align: center;
    color: #363636;
}

footer a {
    color: #363636;
}

dl.detail dt {
    font-weight: bold;
    float: left;
    width: 10em;
}

header {
    border-bottom: 2px solid;
    margin-bottom: 1em;
}

#content {
    min-height: 1024px;
}

header,
.container {
    padding: 0 1em;
}

.messages {
    position: fixed;
    top: 20px;
    left: 43%;
    right: 43%;
    z-index: 100;
}

.game-row {
    border-bottom: 1px solid #dbdbdb;
}

.game-header {
    border-bottom: 1px solid #dbdbdb;
    color: #363636;
}

.game-row .thumbnail img {
    max-width: inherit;
}

/* Dark theme changes */
.navbar {
    border: None;
    background-color: transparent;
}

.table {
    background-color: transparent;
}

.game-name {
    display: inline-block;
}

.game-row {
    border-bottom: 1px solid #4a4a4a;
}

.game-header {
    border-bottom: 1px solid #4a4a4a;
    color: #fff;
}

header,
footer {
    background-color: #131313;
}

header {
    border-bottom: 1px solid #4a4a4a;
}

footer {
    border-top: 1px solid #4a4a4a;
}

/* 
.game-row .rank {
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-family: Handjet, sans-serif;
    font-weight: 800;
    text-shadow: -3px 3px 0px #5d5b5b;
}

.game-row .rank .large {
    font-size: 60px;
}

.game-row .rank .medium {
    font-size: 30px;
} 
*/

.navbar {
    border: None;
    background-color: transparent;
}

.table {
    background-color: transparent;
}

.game-name {
    display: inline-block;
}

.game-row {
    border-bottom: 1px solid #4a4a4a;
}

.game-header {
    border-bottom: 1px solid #4a4a4a;
    color: #fff;
}

header,
footer {
    background-color: #131313;
}

header {
    border-bottom: 1px solid #4a4a4a;
}

footer {
    border-top: 1px solid #4a4a4a;
}

.box {
    background-color: #242424;
    box-shadow: none;
}

.title {
    font-weight: 600;
}

.loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 30vh;
}
</style>
