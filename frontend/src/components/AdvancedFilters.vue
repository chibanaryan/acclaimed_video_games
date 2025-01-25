<template>
    <div>
        <div class="buttons">
            <a @click="clearFilters"
                v-if="isFiltered"
                class="button">
                <span class="icon">
                    <span class="mdi mdi-close"></span>
                </span>
                <span>Clear filters</span>
            </a>
        </div>
        <div class="columns">
            <div class="column">
                <div class="p-2">
                    <label class="has-text-weight-bold">Release year</label>
                </div>
                <div class="field">
                    <div class="control">
                        <table class="table plain">
                            <tr>
                                <td>From:</td>
                                <td>
                                    <range-slider v-model.lazy="filters.start"
                                        placeholder="Start year"></range-slider>
                                </td>
                            </tr>
                            <tr>
                                <td>To:</td>
                                <td>
                                    <range-slider v-model.lazy="filters.end"
                                        placeholder="End year"></range-slider>
                                </td>
                            </tr>
                        </table>
                    </div>
                </div>
                <div class="p-2">
                    <label class="has-text-weight-bold">Displayed rank</label>
                </div>
                <div class="field ml-3">
                    <div class="control">
                        <div class="select">
                            <select v-model="filters.rank_display">
                                <option value="alltime">All time</option>
                                <option value="filtered">Filtered</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>
            <div v-if="genres.length"
                class="column">
                <div class="p-2">
                    <div class="control is-pulled-right">
                        <label class="radio">
                            All
                            <input v-model="filters.genre_option"
                                type="radio"
                                value="L" />
                        </label>
                        <label class="radio">
                            Any
                            <input v-model="filters.genre_option"
                                type="radio"
                                value="A" />
                        </label>
                    </div>
                    <label class="has-text-weight-bold">Genres</label>
                </div>

                <select v-model="filters.genres"
                    multiple
                    class="is-hidden-tablet">
                    <option :value="null">All genres</option>
                    <option v-for="genre in genres"
                        :key="genre.id"
                        :value="genre">
                        {{ genre.name }}
                    </option>
                </select>

                <div class="is-hidden-mobile">
                    <multi-select-component :items="genres"
                        v-model="filters.genres"></multi-select-component>
                    <selectable-tag-list v-model="filters.genres"
                        class="mt-3"></selectable-tag-list>
                </div>

            </div>
            <div v-if="platforms.length"
                class="column">
                <div class="p-2">
                    <label class="has-text-weight-bold">Platforms</label>
                </div>

                <select v-model="filters.platforms"
                    multiple
                    class="is-hidden-tablet">
                    <option :value="null">All platforms</option>
                    <option v-for="platform in platforms"
                        :key="platform.id"
                        :value="platform">
                        {{ platform.name }}
                    </option>
                </select>

                <div class="is-hidden-mobile">
                    <multi-select-component :items="platforms"
                        v-model="filters.platforms"></multi-select-component>
                    <selectable-tag-list v-model="filters.platforms"
                        class="mt-3"></selectable-tag-list>
                </div>

            </div>
        </div>
        <search-input v-model="filters.q"
            :debounce-input="true"
            placeholder="Search by name"
            class="is-flex">
        </search-input>
    </div>
</template>

<script>
import MultiSelectComponent from "./MultiSelectComponent";
import RangeSlider from "./RangeSlider";
import SearchInput from "./SearchInput";
import SelectableTagList from "./SelectableTagList";

export default {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    components: {
        MultiSelectComponent,
        RangeSlider,
        SearchInput,
        SelectableTagList,
    },
    data() {
        return {
            meta: {},
            genres: [],
            platforms: [],
            filters: {
                q: null,
                start: null,
                end: null,
                genres: [],
                platforms: [],
                genre_option: null,
                rank_display: 'alltime',
            },
        }
    },
    async created() {
        this.filters = this.modelValue;
        
        await this.$store.dispatch('loadGenres');
        this.genres = this.$store.state.genres;

        await this.$store.dispatch('loadPlatforms');
        this.platforms = this.$store.state.platforms;

        await this.$store.dispatch('loadMeta');
        this.meta = this.$store.state.meta;
    },
    computed: {
        isFiltered() {
            if (!this.filters)
                return false;
            else
                return this.filters.q ||
                    this.filters.genres.length ||
                    this.filters.platforms.length ||
                    this.filters.start != this.minYear ||
                    this.filters.end != this.maxYear;
        },
        minYear() {
            if (this.meta?.games?.years.length)
                return this.meta.games.years[0]['year'];
            else
                return 1970;
        },
        maxYear() {
            return new Date().getFullYear();
        },
    },
    methods: {
        clearFilters() {
            this.filters = {
                q: null,
                start: null,
                end: null,
                genres: [],
                platforms: [],
                genre_option: "L",
            };

            this.pagination = {
                limit: 100,
                offset: 0,
            }

            this.selected = {
                year: null,
                decade: null,
                alltime: null,
            };

            this.filters.start = this.minYear;
            this.filters.end = this.maxYear;
        },
    },
    watch: {
        modelValue(val) {  
            this.filters = val;
        },
        filters: {
            handler(val) {
                this.$emit('update:modelValue', val);
            },
            deep: true,
        },
        "filters.start": function () {
            if (this.filters.end < this.filters.start)
                this.filters.end = this.filters.start;
        },
        "filters.end": function () {
            if (this.filters.start > this.filters.end)
                this.filters.start = this.filters.end;
        },
    }
}
</script>

<style lang="sass" scoped>
input[type=range]
    width: 15em
</style>