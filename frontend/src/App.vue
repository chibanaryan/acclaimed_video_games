<template>

    <head>
        <title>{{ title }}</title>
    </head>

    <body>
        <header id="header">
            <div class="container">
                <nav-component></nav-component>
            </div>
        </header>
        <section>
            <div class="container">
                <div v-if="loading"
                    class="loading">
                    <span class="mdi mdi-loading mdi-spin mdi-48px"></span>
                </div>
                <router-view class="view"
                    :key="$route.path"></router-view>
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
import NavComponent from "./components/NavComponent";

export default {
    name: 'App',
    components: {
        NavComponent,
    },
    data() {
        return {
            pageTitle: null,
        }
    },
    created() {
        this.emitter.on('title', (title) => {
            if (title)
                this.pageTitle = title;
        })
    },
    computed: {
        loading() {
            return this.$store.state.loading;
        },
        title() {
            if (this.pageTitle)
                return `${this.pageTitle} | Acclaimed Games`;
            else
                return 'Acclaimed Games';
        }
    },
    watch: {
        '$route.meta.title': {
            handler(val) {
                this.pageTitle = val;
            }
        }
    }
}
</script>

<style lang="sass">
html 
    background-color: #000

header 
    border-bottom: 2px solid
    margin-bottom: 1em

section 
    min-height: 800px

footer 
    min-height: 15em
    background-color: #444
    margin-top: 2em
    padding-top: 2em
    text-align: center
    color: #8b8b8b

    a 
        color: #8b8b8b

dl.detail 
    dt 
        font-weight: bold
        float: left
        width: 10em

#content 
    min-height: 1024px

header,
.container 
    padding: 0 1em

.messages 
    position: fixed
    top: 20px
    left: 43%
    right: 43%
    z-index: 100

/* Dark theme changes */
.navbar 
    border: None
    background-color: transparent

.table 
    background-color: transparent

.table.plain th,
.table.plain td 
    border: none

.game-row 
    border-bottom: 1px solid #4a4a4a

.game-header 
    border-bottom: 1px solid #4a4a4a
    color: #fff

header,
footer 
    background-color: #131313

header 
    border-bottom: 1px solid #4a4a4a

footer 
    border-top: 1px solid #4a4a4a

.box 
    background-color: #242424
    color: rgb(235, 236, 240)
    box-shadow: none

.title 
    font-weight: 600

.loading 
    position: fixed
    top: 50%
    left: 50%
    transform: translate(-50%, -50%)

.navbar 
    .navbar-menu 
        background-color: #131313

a.dropdown-item:hover 
    color: #fff

.v-enter-active,
.v-leave-active 
    transition: opacity 0.5s ease

.v-enter-from,
.v-leave-to 
    opacity: 0

</style>
