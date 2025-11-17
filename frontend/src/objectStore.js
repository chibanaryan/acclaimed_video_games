/**
 * A persistent key-value store backed by localStorage
 *
 * Provides a simple interface for storing and retrieving objects in localStorage,
 * with automatic JSON serialization/deserialization.
 */
class PersistentObjectStore {
    /**
     * Create a new persistent object store
     * @param {string} storeKey - The localStorage key to use for storage
     */
    constructor(storeKey) {
        this.storeKey = storeKey;

        // Guard against SSR - localStorage is only available in browser
        if (typeof window === 'undefined') {
            this.data = {};
            return;
        }

        if (!localStorage[this.storeKey])
            localStorage[this.storeKey] = "{}";

        this.data = JSON.parse(localStorage[this.storeKey]);
    }

    /**
     * Set a value in the store
     * @param {string} key - The key to set
     * @param {*} val - The value to store (will be JSON serialized)
     */
    set(key, val) {
        this.data[key] = val;
        // Guard against SSR - only persist to localStorage in browser
        if (typeof window !== 'undefined') {
            localStorage[this.storeKey] = JSON.stringify(this.data);
        }
    }

    /**
     * Get a value from the store
     * @param {string} key - The key to retrieve
     * @returns {*} The stored value, or undefined if not found
     */
    get(key) {
        return this.data[key];
    }

    /**
     * Clear all data from the store
     */
    clear() {
        this.data = {};
        // Guard against SSR - only persist to localStorage in browser
        if (typeof window !== 'undefined') {
            localStorage[this.storeKey] = "{}";
        }
    }
}

/**
 * Global persistent store instance for application-wide state
 * @type {PersistentObjectStore}
 */
const globalStore = new PersistentObjectStore('global');

/**
 * Factory function to create a new persistent object store
 * @param {string} key - The localStorage key to use
 * @returns {PersistentObjectStore} A new persistent object store instance
 */
const objectStore = (key) => new PersistentObjectStore(key);

export { globalStore, objectStore };