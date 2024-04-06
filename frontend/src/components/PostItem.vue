<template>
    <div class="is-clearfix my-5 content box">
        <h4>{{ post.title }}</h4>
        <div v-html="post.text"></div>
        <div class="has-text-grey-dark is-pulled-right">{{ post.date.fromNow() }}</div>
    </div>
</template>

<script>
export default {
    props: ['post']
}
</script>

<style>
.content h4 {
    font-size: 1.25em;
    margin-bottom: .8em;
}
</style>