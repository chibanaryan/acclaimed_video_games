<template>
    <div class="control multiple-select">
        <div v-for="item in selectableItems"
            :key="item.item">
            <label>
                <input type="checkbox"
                    v-model="item.selected"
                    @change="onInputChange">
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
    emits: ['update:modelValue', 'change'],
    data() {
        return {
            selectableItems: [],
        }
    },
    created() {
        this.selectableItems = this.items.map(x => new SelectableItem(x));
    },
    computed: {
        selected() {
            return this.selectableItems.filter(x => x.selected).map(x => x.item);
        }
    },
    methods: {
        onInputChange() {
            this.$emit('change');
            this.$emit('update:modelValue', this.selected);
        }
    },
    watch: {
        modelValue(val) {
            if (!val) {
                this.selectableItems.forEach(x => x.selected = false);
                return;
            }

            let selectedIds = val.map(x => x.id);
            this.selectableItems.forEach(x => {
                x.selected = selectedIds.includes(x.item.id);
            })
        },
    }
}
</script>

<style>
.multiple-select {
    max-height: 170px;
    overflow-y: auto;
}
</style>