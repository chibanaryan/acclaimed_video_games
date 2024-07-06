<template>
    <div class="control">
        <div :class="{ 'has-addons': q }"
            class="field">
            <div class="control has-icons-left">
                <span class="icon is-left">
                    <span class="mdi mdi-magnify"></span>
                </span>
                <input class="input custom-input"
                    v-model="q"
                    :placeholder="placeholder">
            </div>
            <div class="control is-clear">
                <button v-if="q"
                    @click="clearSearch"
                    class="button">
                    <span class="icon">
                        <span class="mdi mdi-close"></span>
                    </span>
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
        debounceInput: {
            default: true,
        }
    },
    emits: ['update:modelValue'],
    data() {
        return {
            q: null,
        }
    },
    created() {
        this.q = this.modelValue;

        let qWatcher = null;

        if (this.debounceInput)
            qWatcher = debounce(function (val) {
                this.$emit('update:modelValue', val);
            }, 300);
        else
            qWatcher = (val) => {
                this.$emit('update:modelValue', val);
            }

        this.$watch('q', qWatcher);
    },
    methods: {
        clearSearch() {
            this.q = null;
        },
    },
    watch: {
        modelValue(val) {
            this.q = val;
        }
    }
}
</script>