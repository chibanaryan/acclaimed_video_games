<template>
    <div v-if="meta.games"
        class="field is-grouped is-grouped-multiline">
        <div class="control">
            <a @click="filters.alltime = true"
                class="button is-link">All time </a>
        </div>
        <div class="control">
            <div class="select">
                <select v-model="filters.decade">
                    <option :value="null">Decades</option>
                    <option v-for="decade in meta.games.decades"
                        :key="decade"
                        :value="decade">
                        {{ decade }}
                    </option>
                </select>
            </div>
        </div>
        <div class="control">
            <div class="select">
                <select v-model="filters.year">
                    <option :value="null">Years</option>
                    <option v-for="year in meta.games.years"
                        :key="year.year"
                        :value="year.year">
                        {{ year.year }} ({{ year.count }})
                    </option>
                </select>
            </div>
        </div>
        <div class="control">
            <a @click="clearFilters"
                v-if="isFiltered"
                class="button">
                <span class="icon">
                    <span class="mdi mdi-close"></span>
                </span>
                <span>Clear filters</span>
            </a>
        </div>
    </div>
</template>

<script>
export default {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    data() {
        return {
            meta: {},
            filters: {
                decade: null,
                year: null,
                alltime: true,
            },
        }
    },
    computed: {
        isFiltered() {
            return this.filters.decade || this.filters.year;
        }
    },
    methods: {
        clearFilters() {
            this.filters.decade = null;
            this.filters.year = null;
            this.filters.alltime = true;
        }
    },
    watch: {
        modelValue(val) {
            this.filters = val;
        },
        "filters.alltime": function (val) {
            if (!val)
                return;

            this.filters.decade = null;
            this.filters.year = null;
            this.$emit('update:modelValue', this.filters);
        },
        "filters.year": function (val) {
            if (!val)
                return;

            this.filters.decade = null;
            this.filters.alltime = false;
            this.$emit('update:modelValue', this.filters);
        },
        "filters.decade": function (val) {
            if (!val)
                return;

            this.filters.year = null;
            this.filters.alltime = false;
            this.$emit('update:modelValue', this.filters);
        },
    },
    async created() {
        this.filters = this.modelValue;

        await this.$store.dispatch('loadMeta');
        this.meta = this.$store.state.meta;
    },
}
</script>
