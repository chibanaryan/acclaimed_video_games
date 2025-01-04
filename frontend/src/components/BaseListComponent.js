import { cleanData } from "@/utils.js";
import { cloneDeep, isEqual } from "lodash";
//import PersistentObjectStore from "@/objectStore";

export default {
    async created() {
        //this._store = new PersistentObjectStore(this.$route.name);
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
            //_store: null,
            loading: false,
        }
    },
    computed: {
        cleanedFilters() {
            //console.log('BaseListComponent cleanedFilters');
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
    },
    methods: {
        async init() {
            this.loadFilters(this.$route.query);
            await this.loadItems();
        },
        loadFilters(args) {
            args = args || this.$route.query;
            if (!args)
                return;

            if (args.limit)
                this.pagination.limit = parseInt(args.limit);

            if (args.offset)
                this.pagination.offset = parseInt(args.offset);

            if (args.q)
                this.filters.q = args.q;
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

            // Update the current route's query with the new limit and offset
            let route = cloneDeep(this.$route);
            route.query.offset = e.offset;

            this.updateRoute(route);
        },
        updateRoute(route) {
            // FIXME The default filters object is being passed here and overriding the correct route query

            // if (!size(route.query) < size(this.$route.query))
            //     return;

            //console.log(this.$route.query);
            //console.log(route.query);

            this.$router.push(route);
            //history.pushState(null, document.title, `?${new URLSearchParams(route.query)}`);
        }
    },
    watch: {
        filters: {
            async handler() {
                //console.log(JSON.stringify(val));
                let route = cloneDeep(this.$route);
                route.query = this.cleanedFilters;
                this.updateRoute(route);
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
