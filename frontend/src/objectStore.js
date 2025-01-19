class PersistentObjectStore {
    constructor(storeKey) {
        this.storeKey = storeKey;

        if (!localStorage[this.storeKey])
            localStorage[this.storeKey] = "{}";

        this.data = JSON.parse(localStorage[this.storeKey]);
    }

    set(key, val) {
        this.data[key] = val;
        localStorage[this.storeKey] = JSON.stringify(this.data);
    }

    get(key) {
        return this.data[key];
    }

    clear() {
        this.data = {};
        localStorage[this.storeKey] = "{}";
    }
}

const globalStore = new PersistentObjectStore('global');

const objectStore = (key) => new PersistentObjectStore(key);

export { globalStore, objectStore };