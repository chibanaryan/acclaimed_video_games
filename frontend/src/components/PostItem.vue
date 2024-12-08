<template>
    <div class="is-clearfix my-5 box">
        <h4 class="title is-size-5">{{ post.title }}</h4>
        <div class="content" v-html="post.text"></div>
        <div class="has-text-grey-dark is-pulled-right">{{ post.date.fromNow() }}</div>
    </div>
</template>

<script>
export default {
    props: ['post']
}
</script>

<style scoped>
h4.title {
    font-size: 1.25em;
    margin-bottom: 0.8em;
}
</style>