<template>
    <div class="field is-grouped">
        <label class="label">{{ label }}</label>
        <div class="control">
            <input :min="min"
                :max="max"
                :placeholder="placeholder"
                v-model="val"
                @input="handleInput"
                @change="handleChange"
                type="range" />
        </div>
    </div>
</template>

<script>
export default {
    props: {
        modelValue: String,
        min: {
            default: 1970,
        },
        max: {
            default: new Date().getFullYear(),
        },
        placeholder: String,
    },
    data() {
        return {
            label: null,
            val: null,
        }
    },
    methods: {
        handleInput() {
            this.label = this.val;
        },
        handleChange() {
            this.$emit('update:modelValue', this.val);
        },
    },
    watch: {
        modelValue(val) {
            this.label = val;
            this.val = val;
        }
    }
}
</script>