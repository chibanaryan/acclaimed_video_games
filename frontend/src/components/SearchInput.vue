<template>
    <div class="control">
        <div :class="{ 'has-addons': q }"
            class="field">
            <div class="control has-icons-left">
                <span class="icon is-left">
                    <span class="mdi mdi-magnify"></span>
                </span>
                <input class="input custom-input"
                    ref="searchinput"
                    v-model="q"
                    @keyup.enter="$emit('change')"
                    :placeholder="placeholder">
            </div>
            <div class="control is-clear">
                <button v-if="q"
                    @click="clearSearch"
                    title="Clear search text"
                    class="button">
                    <span class="icon">
                        <span class="mdi mdi-close"></span>
                    </span>
                </button>
            </div>
            <div v-if="showSubmitButton"
                class="control">
                <button v-if="q"
                    @click="$emit('change')"
                    title="Submit search text"
                    class="button">
                    Submit
                </button>
            </div>
        </div>
    </div>
</template>


<script>
import debounce from "lodash/debounce";

export default {
    props: {
        modelValue: String,
        placeholder: String,
        showSubmitButton: {
            default: false,
        },
        debounceInput: {
            default: true,
        }
    },
    emits: ['update:modelValue', 'change'],
    data() {
        return {
            q: null,
        }
    },
    created() {
        this.q = this.modelValue;

        let qWatcher = null;

        const watchFunc = (val) => {
            this.$emit('update:modelValue', val);
            //this.$emit('change');
            if (!val)
                this.clearSearch();
        };

        if (this.debounceInput)
            qWatcher = debounce(watchFunc, 1000);
        else
            qWatcher = watchFunc;

        this.$watch('q', qWatcher);
    },
    methods: {
        clearSearch() {
            this.q = null;
            this.$emit('update:modelValue', null);
            this.$emit('change');
        },
    },
    watch: {
        modelValue(val) {
            this.q = val;

            if (val)
                this.$refs.searchinput.focus();
        }
    }
}
</script>
