class LocalStorageMock {
    constructor() {
        this.store = {};
    }

    clear() {
        this.store = {};
    }

    getItem(key) {
        return Object.prototype.hasOwnProperty.call(this.store, key)
            ? this.store[key]
            : null;
    }

    setItem(key, value) {
        this.store[key] = String(value);
    }

    removeItem(key) {
        delete this.store[key];
    }
}

let localStorageAvailable = true;
try {
    void globalThis.localStorage;
} catch (err) {
    localStorageAvailable = false;
}

if (!localStorageAvailable) {
    globalThis.localStorage = new LocalStorageMock();
}
