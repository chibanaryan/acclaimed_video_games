import { cleanData } from "@/utils.js";
import _ from "lodash";
const { cloneDeep, isEmpty, isEqual } = _;

export default {
    async created() {
        await this.$store.dispatch('loadMeta');
        this.meta = this.$store.state.meta;
        this._cache.filters = cloneDeep(this.filters);
        await this.init();
    },
    data() {
        return {
            filters: {
                q: null,
                order_by: null,
            },
            pagination: {
                limit: 100,
                offset: 0,
            },
            sortField: null,
            sortOrder: 'DESC',
            items: [],
            resultsCount: 0,
            meta: {
                lists: {
                    years: [],
                },
                games: {
                    years: [],
                    decades: [],
                }
            },
            _cache: {},
            isNavigatingProgrammatically: false, // Track if we initiated the navigation
            unwatchFilters: null, // Store unwatch function for filters watcher
            unwatchRoute: null, // Store unwatch function for route watcher
        }
    },
    computed: {
        getArgs() {
            let filters = cleanData(this.filters);

            filters.limit = this.pagination.limit;
            filters.offset = this.pagination.offset;

            return filters;
        },
        hasPrev() {
            return this.pagination.offset > 0;
        },
        hasNext() {
            return this.items.length > 0 && (this.resultsCount > this.pagination.offset + this.items.length);
        },
        isFiltered() {
            return !(isEqual(this.filters, this._cache.filters));
        },
        pageTitle() {
            let start = this.pagination.offset + 1;
            let end = this.pagination.offset + this.items.length;
            let total = this.resultsCount || 0;

            if (end > total)
                end = total;

            if (end == 0)
                return 'Showing 0';
            else
                return `Showing ${start.toLocaleString()} to ${end.toLocaleString()} of ${total.toLocaleString()}`
        },
        loading() {
            return this.$store.state.loading;
        },
    },
    methods: {
        async init() {            
            this.updateFilters(this.$route.query);
            await this.loadItems();
        },
        updateFilters(args) {
            if (isEmpty(args))
                return;

            if (args.limit) {
                this.pagination.limit = parseInt(args.limit);
            }

            if (args.offset) {
                this.pagination.offset = parseInt(args.offset);
            }

            Object.assign(this.filters, args);

        },
        clearFilters() {
            this.filters = cloneDeep(this._cache.filters);
        },
        sortBy(field) {
            if (field == this.sortField) {
                this.sortOrder = this.sortOrder == 'DESC' ? 'ASC' : 'DESC';
            } else {
                this.sortField = field;
            }
            this.filters.order_by = this.sortOrder == 'DESC' ? this.sortField : `-${this.sortField}`
        },
        async onPageChange(e) {
            Object.assign(this.pagination, e);

            // Scroll to top
            if (typeof window !== 'undefined') {
                window.scrollTo(0, 0);
            }

            await this.loadItems();
            this.updateUrl();
        },
        updateUrl() {
            // Use replace instead of push to avoid creating new history entries
            // This makes URL updates invisible and prevents the "page refresh" sensation
            this.isNavigatingProgrammatically = true;
            this.$router.replace({
                query: this.getArgs
            });
        },
    },
    mounted() {
        // Set up filters watcher with explicit cleanup
        this.unwatchFilters = this.$watch(
            () => this.filters,
            async () => {
                await this.loadItems();
                // Note: URL is NOT updated automatically anymore
                // Only updated on specific user actions (e.g., pressing Enter in search, clicking pagination)
            },
            { deep: true }
        );

        // Set up route watcher with explicit cleanup
        this.unwatchRoute = this.$watch(
            () => this.$route.query,
            () => {
                // Skip if we initiated the navigation ourselves
                if (this.isNavigatingProgrammatically) {
                    this.isNavigatingProgrammatically = false;
                    return;
                }

                // Browser back/forward navigation - reload items
                this.init();
            }
        );
    },
    beforeUnmount() {
        // Clean up all watchers
        if (this.unwatchFilters) {
            this.unwatchFilters();
            this.unwatchFilters = null;
        }

        if (this.unwatchRoute) {
            this.unwatchRoute();
            this.unwatchRoute = null;
        }
    },
};
