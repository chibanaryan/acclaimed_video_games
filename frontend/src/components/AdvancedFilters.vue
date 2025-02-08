<template>
    <div>
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
                                    <range-slider v-model.number="filters.start"
                                        @change="onSelectChange"
                                        placeholder="Start year"></range-slider>
                                </td>
                            </tr>
                            <tr>
                                <td>To:</td>
                                <td>
                                    <range-slider v-model.number="filters.end"
                                        @change="onSelectChange"
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
                            <select v-model="filters.rank_display"
                                @change="onSelectChange">
                                <option value="alltime">All time</option>
                                <option value="filtered">Filtered</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Genres -->
            <div v-if="genres.length"
                class="column">
                <div class="p-2">
                    <div class="control is-pulled-right">
                        <label class="radio">
                            All
                            <input v-model="filters.genre_option"
                                @change="onSelectChange"
                                type="radio"
                                value="L" />
                        </label>
                        <label class="radio">
                            Any
                            <input v-model="filters.genre_option"
                                @change="onSelectChange"
                                type="radio"
                                value="A" />
                        </label>
                    </div>
                    <label class="has-text-weight-bold">Genres</label>
                </div>
                <select v-model="filters.genres"
                    multiple
                    class="is-hidden-tablet"
                    @change="onSelectChange">
                    <option :value="null">All genres</option>
                    <option v-for="genre in genres"
                        :key="genre.id"
                        :value="genre">
                        {{ genre.name }}
                    </option>
                </select>
                <div class="is-hidden-mobile">
                    <multi-select-component v-model="filters.genres"
                        :items="genres"
                        @change="onSelectChange"></multi-select-component>
                    <selectable-tag-list v-model="filters.genres"
                        class="mt-3"
                        @change="onSelectChange"></selectable-tag-list>
                </div>
            </div>

            <!-- Platforms-->
            <div v-if="platforms.length"
                class="column">
                <div class="p-2">
                    <label class="has-text-weight-bold">Platforms</label>
                </div>
                <select v-model="filters.platforms"
                    multiple
                    class="is-hidden-tablet"
                    @change="onSelectChange">
                    <option :value="null">All platforms</option>
                    <option v-for="platform in platforms"
                        :key="platform.id"
                        :value="platform">
                        {{ platform.name }}
                    </option>
                </select>
                <div class="is-hidden-mobile">
                    <multi-select-component v-model="filters.platforms"
                        :items="platforms"
                        @change="onSelectChange"></multi-select-component>
                    <selectable-tag-list v-model="filters.platforms"
                        class="mt-3"
                        @change="onSelectChange"></selectable-tag-list>
                </div>
            </div>

        </div>
        <search-input v-model="filters.q"
            @change="onSelectChange"
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
    props: ['modelValue', 'change', 'genres', 'platforms'],
    emits: ['update:modelValue'],
    components: {
        MultiSelectComponent,
        RangeSlider,
        SearchInput,
        SelectableTagList,
    },
    data() {
        return {
            //meta: {},
            //genres: [],
            //platforms: [],
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
        //console.log('created');

        this.filters = this.modelValue;

        // await this.$store.dispatch('loadGenres');
        // await this.$store.dispatch('loadPlatforms');
        // await this.$store.dispatch('loadMeta');

        // this.genres = this.$store.state.genres;
        // this.platforms = this.$store.state.platforms;
        // this.meta = this.$store.state.meta;
    },
    methods: {
        onSelectChange() {
            this.$emit('change');
        },
    },
    watch: {
        modelValue(val) {
            this.filters = val;
        },
        "filters.start": function () {
            if (this.filters.end < this.filters.start)
                this.filters.end = this.filters.start;
        },
        "filters.end": function () {
            if (this.filters.start > this.filters.end)
                this.filters.start = this.filters.end;
        },
        filters: {
            handler(val) {
                this.$emit('update:modelValue', val);
            },
            deep: true,
        }
    }
}
</script>

<style lang="sass" scoped>
input[type=range]
    width: 15em
</style>