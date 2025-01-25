<template>
    <div>
        <h1 class="title">Page Not Found</h1>
        Page with URL <code>{{ $route.params.pathMatch.join('/') }}</code> not found.
    </div>
</template>

<script>
export default {
    created() {
        setTimeout(() => {
            this.$router.push({name: 'games-list'});
        }, 3000)
    }
}
</script>