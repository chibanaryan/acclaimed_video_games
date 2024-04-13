<template>
    <div class="control multiple-select">
        <div v-for="item in selectableItems"
            :key="item.item">
            <label>
                <input type="checkbox"
                    v-model="item.selected"
                    @change="$emit('update:modelValue', selected)">
                {{ item.item }}
            </label>
        </div>
    </div>
</template>

<script>

class SelectableItem {
    constructor(item) {
        this.item = item;
        this.selected = false;
    }
}

export default {
    props: ['modelValue', 'items'],
    emits: ['update:modelValue'],
    data() {
        return {
            selectableItems: [],
        }
    },
    created() {
        this.selectableItems = this.items.map(x => new SelectableItem(x));
        this.modelValue.forEach(x => {
            const match = this.selectableItems.find(y => y.id == x.id);
            match.selected = true;
        })
    },
    computed: {
        selected() {
            return this.selectableItems.filter(x => x.selected).map(x => x.item);
        }
    },
}
</script>

<style>
.multiple-select {
    max-height: 170px;
    overflow-y: auto;
}
</style>