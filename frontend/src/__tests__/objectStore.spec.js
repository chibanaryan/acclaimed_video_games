import { describe, it, beforeEach, expect, vi } from 'vitest';
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

    it('works in SSR environment without localStorage', async () => {
        // Simulate SSR by temporarily removing window
        const originalWindow = global.window;
        // @ts-ignore
        global.window = undefined;

        // Re-import to get a fresh class definition
        vi.resetModules();

        // Test that constructor handles SSR
        const { objectStore: ssrObjectStore } = await import('@/objectStore');
        const store = ssrObjectStore('ssr-store');

        // Should work without localStorage
        store.set('foo', 'bar');
        expect(store.get('foo')).toBe('bar');

        // Clear should work
        store.clear();
        expect(store.get('foo')).toBeUndefined();

        // Restore window
        global.window = originalWindow;
    });
});
