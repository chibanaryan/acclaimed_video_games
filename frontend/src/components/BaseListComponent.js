import { cleanData } from "@/utils.js";
import _ from "lodash";

export default {
    mounted() {
        this._cache.filters = Object.assign({}, this.filters);
        this.loadUrlArgs();
        this.loadItems();
        this.loadMeta();
    },
    data() {
        return {
            filters: {
                q: null,
                limit: null,
                offset: 0,
                order_by: null,
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
            return new URLSearchParams(cleanData(this.filters));
        },
        hasPrev() {
            return this.filters.offset > 0;
        },
        hasNext() {
            return this.items.length > 0 && (this.resultsCount > this.filters.offset + this.items.length);
        },
        isFiltered() {
            return !(_.isEqual(this.filters, this._cache.filters));
        },
        pageTitle() {
            let start = this.filters.offset + 1;
            let end = this.filters.offset + this.items.length;
            let total = this.resultsCount || 0;

            if (end > total)
                end = total;

            if (end == 0)
                return 'Showing 0';
            else
                return `Showing ${start.toLocaleString()} to ${end.toLocaleString()} of ${total.toLocaleString()}`
        },
    },
    methods: {
        loadUrlArgs() {
            // Override in sub components
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

        onPageChange(e) {
            if (e == 'previous')
                this.filters.offset -= this.filters.limit;
            else if (e == 'next')
                this.filters.offset += this.filters.limit;
        },
        async loadMeta() {
            this.meta = await fetch(`${process.env.VUE_APP_API_URL}meta/`)
                .then(resp => resp.json());
        }
    },
    watch: {
        filters: {
            handler() {
                this.loadItems();
            },
            deep: true
        }
    }
};
