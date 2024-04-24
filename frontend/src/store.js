import { createStore } from 'vuex'

const store = createStore({
    state() {
        return {
            loading: false,
        }
    },
    mutations: {
        loading(state, val) {
            state.loading = val;
        }
    }
})

export default store;