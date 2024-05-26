<template>
    <table v-if="items && !loading"
        class="table is-fullwidth is-hidden-mobile">
        <thead>
            <tr>
                <th>Publication</th>
                <th>Year</th>
                <th v-if="showRank">Rank</th>
                <th>Name</th>
                <th v-if="showType">Type</th>
            </tr>
        </thead>
        <tbody>
            <tr v-for="list in items"
                :key="list.id">
                <td class="publication">{{ list.publication }}</td>
                <td class="year">{{ list.year }}</td>
                <td v-if="showRank"
                    class="rank">{{ list.rank }}</td>
                <td>
                    <a :href="list.url"
                        v-if="list.url"
                        target="_blank">
                        {{ list.name }}
                    </a>
                    <span v-else>{{ list.name }}</span>
                </td>
                <td v-if="showType">{{ list.typeName }}</td>
            </tr>
        </tbody>
    </table>
    <div class="is-hidden-tablet">
        <div v-for="list in items"
            :key="list.id"
            class="list-item">
            <div>{{ list.publication }}</div>
            <div>
                <a :href="list.url"
                    v-if="list.url"
                    target="_blank">
                    {{ list.name }}
                </a>
            </div>
            <div>
                <label>Year:</label>
                {{ list.year }}
            </div>
            <div v-if="showRank">
                <label>Rank:</label>
                {{ list.rank }}
            </div>
            <div v-if="showType">
                <label>Type:</label>
                {{ list.typeName }}
            </div>
        </div>
    </div>
</template>

<script>
export default {
    props: ['items', 'showType', 'showRank'],
}
</script>

<style scoped>
td.publication {
    width: 15em;
}

td.year {
    width: 4em;
}
td.rank {
    width: 3em;
}
</style>