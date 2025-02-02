<template>
    <div v-if="meta.games && filters"
        class="field is-grouped is-grouped-multiline">
        <div class="control">
            <a @click="clearFilters"
                class="button is-link">All time</a>
        </div>
        <div class="control">
            <div class="select" @change="onSelectChange">
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
            <div class="select" @change="onSelectChange">
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
    emits: ['update:modelValue', 'changed'],
    data() {
        return {
            meta: {},
            filters: {
                decade: null,
                year: null,
            },
        }
    },
    async created() {
        this.filters = this.modelValue;
        await this.$store.dispatch('loadMeta');
        this.meta = this.$store.state.meta;
    },
    computed: {
        isFiltered() {
            return this.filters.decade || this.filters.year;
        },
    },
    methods: {
        clearFilters() {
            this.filters.decade = null;
            this.filters.year = null;
            this.$emit('changed');
        },
        onSelectChange() {
            this.$emit('changed');
        },
    },
    watch: {
        modelValue(val) {
            this.filters = val;
        },
        "filters.year": function (val) {
            if (!val)
                return;

            this.filters.decade = null;
            this.$emit('update:modelValue', this.filters);
        },
        "filters.decade": function (val) {
            if (!val)
                return;

            this.filters.year = null;
            this.$emit('update:modelValue', this.filters);
        },
    },
}
</script>
