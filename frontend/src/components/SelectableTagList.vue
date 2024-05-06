<template>
    <div v-if="modelValue?.length"
        class="tags m-0">
        <span v-for="item in modelValue"
            :key="item.id"
            class="tag is-primary">{{ item }}
            <button @click="deselect(item)"
                title="Deselect item"
                class="delete is-small"></button>
        </span>
    </div>
</template>

<script>
export default {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    methods: {
        deselect(item) {
            this.$emit('update:modelValue', this.modelValue.filter(x => x != item));
        }
    }
}
</script>