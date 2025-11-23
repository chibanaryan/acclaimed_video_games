import '@mdi/font/css/materialdesignicons.css';
import 'bulma/css/bulma.css';
import * as Vue from 'vue';
import App from './App.vue';
import fetchIntercept from "fetch-intercept";
import mitt from 'mitt';
import router from './router';
import store from './store';
import vueGTag from 'vue-gtag';

const app = Vue.createApp(App);
app.use(router);
app.use(store);

if (import.meta.env.PROD) {
    app.use(vueGTag, {
        config: {
            id: import.meta.env.VITE_GOOGLE_ANALYTICS_PROPERTY_ID
        },
        router,
    });
}

app.config.globalProperties.emitter = mitt();

app.mount('#app');

fetchIntercept.register({
    request: (url, config) => {
        store.commit('setLoading', true);
        return [url, config];
    },
    response: (response) => {
        store.commit('setLoading', false);
        return response;
    },
})

export default app;
