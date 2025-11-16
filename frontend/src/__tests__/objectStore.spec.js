import { describe, it, beforeEach, expect } from 'vitest';
import { objectStore, globalStore } from '@/objectStore';

describe('PersistentObjectStore', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it('persists values to localStorage', () => {
        const store = objectStore('test-store');
        store.set('foo', 'bar');
        expect(store.get('foo')).toBe('bar');

        const store2 = objectStore('test-store');
        expect(store2.get('foo')).toBe('bar');
    });

    it('clears stored values', () => {
        const store = objectStore('clear-store');
        store.set('foo', 'bar');
        store.clear();
        expect(store.get('foo')).toBeUndefined();
    });
});
