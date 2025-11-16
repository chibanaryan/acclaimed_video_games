import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import store from './store';

const resetState = () => {
    store.replaceState({
        loading: false,
        genres: [],
        platforms: [],
        meta: {},
    });
};

describe('Vuex store', () => {
    beforeEach(() => {
        resetState();
    });

    afterEach(() => {
        vi.restoreAllMocks();
        delete global.fetch;
    });

    it('updates loading flag via mutation', () => {
        store.commit('setLoading', true);
        expect(store.state.loading).toBe(true);
        store.commit('setLoading', false);
        expect(store.state.loading).toBe(false);
    });

    it('loads genres once when empty', async () => {
        const mockResponse = {
            results: [{ id: 1, name: 'Action' }],
        };
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve(mockResponse),
        });

        await store.dispatch('loadGenres');
        expect(global.fetch).toHaveBeenCalledTimes(1);
        expect(store.state.genres).toHaveLength(1);
        expect(store.state.genres[0].name).toBe('Action');

        await store.dispatch('loadGenres');
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('loads metadata and commits result', async () => {
        const meta = { lists: { years: [] } };
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(meta),
        });

        await store.dispatch('loadMeta');
        expect(store.state.meta).toEqual(meta);
    });

    it('rethrows when metadata fetch fails', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
        });

        await expect(store.dispatch('loadMeta')).rejects.toThrow(
            'Meta request failed: 500'
        );
        expect(store.state.meta).toEqual({});
    });
});
