<template>
    <nav class="navbar"
        role="navigation"
        aria-label="main navigation">
        <div class="navbar-brand">
            <router-link :to="{ name: 'home' }"
                class="navbar-item has-text-weight-bold pl-0">
                <img :src="logoSmall" />
            </router-link>
            <game-search-component class="navbar-item">
            </game-search-component>
            <router-link :to="{ name: 'games-list', params: { slug: 'alltime' } }"
                class="navbar-item">
                Top 1000
            </router-link>
            <a @click="expanded = !expanded"
                class="navbar-burger"
                :class="{ 'is-active': expanded }"
                aria-label="menu"
                aria-expanded="false"
                role="button">
                <span aria-hidden="true"></span>
                <span aria-hidden="true"></span>
                <span aria-hidden="true"></span>
                <span aria-hidden="true"></span>
            </a>
        </div>
        <div class="navbar-menu"
            :class="{ 'is-active': expanded }" @click="handleMenuClick">
            <div class="navbar-start">
                <router-link :to="{ name: 'developers-list' }"
                    class="navbar-item">
                    Developers
                </router-link>
                <router-link :to="{ name: 'list-list' }"
                    class="navbar-item">
                    Lists
                </router-link>
                <router-link :to="{ name: 'page-detail', params: { slug: 'about' } }"
                    class="navbar-item">
                    About
                </router-link>
                <router-link :to="{ name: 'page-detail', params: { slug: 'palestine' } }"
                    class="navbar-item"
                    title="Statement on Palestine">
                    <span class="icon">
                        <img :src="flagPalestine">
                    </span>
                </router-link>
            </div>
        </div>
    </nav>
</template>

<script>
import { IMAGES } from '@/constants';
import GameSearchComponent from "./GameSearchComponent";

export default {
    components: {
        GameSearchComponent,
    },
    data() {
        return {
            expanded: false,
        }
    },
    computed: {
        logoSmall() {
            return IMAGES.LOGO_SMALL;
        },
        flagPalestine() {
            return IMAGES.FLAG_PALESTINE;
        }
    },
    methods: {
        handleMenuClick() {
            this.expanded = false;
        }
    }
}
</script>
