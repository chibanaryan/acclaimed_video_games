import { cleanData, getMeta } from "@/utils.js";
import _ from "lodash";

export default {
    async created() {
        this.meta = await getMeta();
        this._cache.filters = Object.assign({}, this.filters);
        this.loadUrlArgs();
        await this.loadItems();
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
            return !(_.isEqual(this.filters, this._cache.filters));
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
        loadUrlArgs() {
            let args = this.$route.query;
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
            this.filters = Object.assign({}, this._cache.filters);
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
            if (e == 'previous')
                this.pagination.offset -= parseInt(this.pagination.limit);
            else if (e == 'next')
                this.pagination.offset += parseInt(this.pagination.limit);
            else
                Object.assign(this.pagination, e);

            // Update the current route's query with the new limit and offset
            let query = Object.assign({}, this.$route.query);
            query.limit = this.pagination.limit;
            query.offset = this.pagination.offset;

            let route = this.$route;
            route.query = query;

            // Need to push a dummy route so the next one will register as a change
            this.$router.push({});

            setTimeout(() => {
                this.$router.replace(route);
            }, 1);

            // Update the browser URL
            history.pushState(null, document.title, `?${this.cleanedFilters}`);

            await this.loadItems();
        },
    },
    watch: {
        filters: {
            async handler() {
                history.pushState(null, document.title, `?${this.cleanedFilters}`);
                await this.loadItems();
            },
            deep: true
        },
    }
};
