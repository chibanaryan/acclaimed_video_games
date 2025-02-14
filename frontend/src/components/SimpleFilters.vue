<template>
    <div v-if="meta.games && filters"
        class="field is-grouped">
        <div class="control is-hidden-mobile">
            <a @click="clearFilters"
                class="button is-link">
                <span>All time</span>
            </a>
        </div>
        <div v-if="isFiltered"
            class="control is-hidden-tablet">
            <a @click="clearFilters"
                class="button">
                <span class="icon">
                    <span class="mdi mdi-close"></span>
                </span>
            </a>
        </div>
        <div class="control">
            <div class="select"
                @change="onSelectChange">
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
            <div class="select"
                @change="onSelectChange">
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
    </div>
</template>

<script>
export default {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
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
        }
    },
    methods: {
        onSelectChange() {
            this.$emit('change');
        },
        clearFilters() {
            this.filters.decade = null;
            this.filters.year = null;
            this.$emit('change');
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
        },
        "filters.decade": function (val) {
            if (!val)
                return;

            this.filters.year = null;
        },
        filters: {
            handler() {
                this.$emit('update:modelValue', this.filters);
            },
            deep: true,
        }
    },
}
</script>

<style lang="css">
.field.is-grouped>.control:not(:last-child) {
    margin-bottom: 0;
    margin-right: 0;
}
</style>
