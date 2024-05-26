import '@mdi/font/css/materialdesignicons.css';
import 'bulma/css/bulma.css';
import * as Vue from 'vue';
import vueGTag from 'vue-gtag';
import App from './App.vue';
import router from './router';
import store from './store';

const app = Vue.createApp(App);
app.use(router);
app.use(store);
app.use(vueGTag, {
    config: {
        id: process.env.VUE_APP_GOOGLE_ANALYTICS_PROPERTY_ID
    },
    router,
});
app.mount('#app');

export default app;