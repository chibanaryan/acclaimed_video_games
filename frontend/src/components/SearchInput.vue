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
                    @keyup="onKeyUp"
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
import { objectStore } from "@/objectStore";
import debounce from "lodash/debounce";

export default {
    props: {
        modelValue: String,
        placeholder: String,
        showSubmitButton: {
            default: false,
        },
    },
    emits: ['update:modelValue', 'change'],
    data() {
        return {
            q: null,
            store: objectStore(this.$route.name),
        }
    },
    mounted() {
        this.q = this.modelValue;

        if (this.store.get('inputActive'))
            this.$refs.searchinput.focus();
    },
    methods: {
        onKeyUp: debounce(function () {
            this.store.set('inputActive', true);
            this.$emit('update:modelValue', this.q);
            this.$emit('change', this.q);
        }, 200),
        clearSearch() {
            this.q = null;
            this.store.set('inputActive', false);
            this.$emit('update:modelValue', null);
            this.$emit('change', null);
        },
    },
    watch: {
        modelValue(val) {
            this.q = val;
        }
    }
}
</script>
