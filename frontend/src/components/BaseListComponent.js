import { cleanData } from "@/utils.js";
import { cloneDeep, isEmpty, isEqual } from "lodash";

export default {
    async created() {

        // window.addEventListener("popstate", (event) => {
        //     if (event.state?.filters) {
        //         this.loadFilters(event.state.filters);
        //     }
        // });

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
        }
    },
    computed: {
        cleanedFilters() {
            let filters = cleanData(this.filters);

            filters.limit = this.pagination.limit;
            filters.offset = this.pagination.offset;

            return new URLSearchParams(filters);
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
        urlArgs() {
            // Override this in component if necessary
            return this.cleanedFilters;
        },
    },
    methods: {
        async init() {
            this.loadFilters(this.$route.query);
            await this.loadItems();
        },
        loadFilters(args) {
            if (isEmpty(args))
                return;

            console.log("loadFilters", args);
            
            if (args.limit) {
                this.pagination.limit = parseInt(args.limit);
                delete args.limit;
            }

            if (args.offset) {
                this.pagination.offset = parseInt(args.offset);
                delete args.offset;
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
            await this.loadItems();
            this.updateUrl();
        },
        updateUrl() {                        
            history.pushState(
                {
                    filters: this.urlArgs,
                },
                document.title,
                `?${new URLSearchParams(this.urlArgs)}`);
        },
    },
    watch: {
        filters: {
            async handler(val) {
                this.pagination.offset = 0;
                console.log('filters changed', val);
                await this.loadItems();
                this.updateUrl();
            },
            deep: true
        },
        '$route.query': {
            handler() {
                this.init();
            },
        },
    },
};
