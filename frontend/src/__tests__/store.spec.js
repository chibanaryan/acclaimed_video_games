import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import store from '../store';
import Genre from '../models/Genre';
import Platform from '../models/Platform';
import Game from '../models/Game';
import Developer from '../models/Developer';
import { isEmpty } from 'lodash';

describe('Vuex store', () => {
    beforeEach(() => {
        store.replaceState({
            loading: false,
            genres: [],
            platforms: [],
            meta: {},
            games: {},
            developers: {},
            gamesLists: {},
        });
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
        expect(store.state.genres[0]).toBeInstanceOf(Genre);

        await store.dispatch('loadGenres');
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('loads platforms once when empty', async () => {
        const mockResponse = {
            results: [{ id: 1, name: 'PC', code: 'PC' }],
        };
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve(mockResponse),
        });

        await store.dispatch('loadPlatforms');
        expect(global.fetch).toHaveBeenCalledTimes(1);
        expect(store.state.platforms[0]).toBeInstanceOf(Platform);

        await store.dispatch('loadPlatforms');
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

    it('skips loadMeta when meta already populated', async () => {
        store.state.meta = { foo: 'bar' };
        global.fetch = vi.fn();

        await store.dispatch('loadMeta');
        expect(global.fetch).not.toHaveBeenCalled();
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

    it('fetches and caches a game by slug', async () => {
        const mockGame = {
            id: 1,
            name: 'Test Game',
            slug: 'test-game',
            rank: 1,
        };
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockGame),
        });

        const game = await store.dispatch('fetchGame', { slug: 'test-game' });
        expect(game).toBeInstanceOf(Game);
        expect(game.name).toBe('Test Game');
        expect(store.state.games['test-game']).toBeInstanceOf(Game);
        expect(global.fetch).toHaveBeenCalledTimes(1);

        // Second call should use cache
        await store.dispatch('fetchGame', { slug: 'test-game' });
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('fetches and caches a games list with query params', async () => {
        const mockResponse = {
            count: 100,
            results: [
                { id: 1, name: 'Game 1', slug: 'game-1', rank: 1 },
                { id: 2, name: 'Game 2', slug: 'game-2', rank: 2 },
            ],
        };
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockResponse),
        });

        const queryParams = { limit: 100, offset: 0 };
        const result = await store.dispatch('fetchGamesList', { queryParams });
        expect(result.count).toBe(100);
        expect(result.results).toHaveLength(2);
        expect(result.results[0]).toBeInstanceOf(Game);
        expect(global.fetch).toHaveBeenCalledTimes(1);

        // Second call should use cache
        await store.dispatch('fetchGamesList', { queryParams });
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('fetches and caches a developer with games', async () => {
        const mockDeveloper = { id: 1, name: 'Test Studio', slug: 'test-studio' };
        const mockGames = {
            results: [
                { id: 1, name: 'Game 1', slug: 'game-1', rank: 1 },
            ],
        };

        let fetchCallCount = 0;
        global.fetch = vi.fn().mockImplementation((url) => {
            fetchCallCount++;
            if (url.includes('developers/')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve(mockDeveloper),
                });
            } else {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve(mockGames),
                });
            }
        });

        const result = await store.dispatch('fetchDeveloper', { slug: 'test-studio' });
        expect(result.developer).toBeInstanceOf(Developer);
        expect(result.games).toHaveLength(1);
        expect(result.games[0]).toBeInstanceOf(Game);
        expect(store.state.developers['test-studio']).toBeDefined();
        expect(fetchCallCount).toBe(2); // Developer + games

        // Second call should use cache
        await store.dispatch('fetchDeveloper', { slug: 'test-studio' });
        expect(fetchCallCount).toBe(2); // No additional fetches
    });

    it('handles game fetch errors', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 404,
        });

        await expect(
            store.dispatch('fetchGame', { slug: 'nonexistent' })
        ).rejects.toThrow('Failed to fetch game: 404');
    });

    it('handles games list fetch errors', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
        });

        await expect(
            store.dispatch('fetchGamesList', { queryParams: {} })
        ).rejects.toThrow('Failed to fetch games list: 500');
    });

    it('forces refetch when force flag is true', async () => {
        const mockGame = { id: 1, name: 'Test Game', slug: 'test-game', rank: 1 };
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockGame),
        });

        // First fetch
        await store.dispatch('fetchGame', { slug: 'test-game' });
        expect(global.fetch).toHaveBeenCalledTimes(1);

        // Force refetch
        await store.dispatch('fetchGame', { slug: 'test-game', force: true });
        expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('handles developer fetch error', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 404,
        });

        await expect(
            store.dispatch('fetchDeveloper', { slug: 'nonexistent' })
        ).rejects.toThrow('Failed to fetch developer: 404');
    });

    it('handles developer games fetch error', async () => {
        const mockDeveloper = { id: 1, name: 'Test Studio', slug: 'test-studio' };

        let callCount = 0;
        global.fetch = vi.fn().mockImplementation((url) => {
            callCount++;
            if (url.includes('developers/')) {
                // Developer fetch succeeds
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve(mockDeveloper),
                });
            } else {
                // Games fetch fails
                return Promise.resolve({
                    ok: false,
                    status: 500,
                });
            }
        });

        await expect(
            store.dispatch('fetchDeveloper', { slug: 'test-studio' })
        ).rejects.toThrow('Failed to fetch developer games: 500');
    });

    it('getGameBySlug getter returns cached game', async () => {
        const mockGame = { id: 1, name: 'Test Game', slug: 'test-game', rank: 1 };
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockGame),
        });

        await store.dispatch('fetchGame', { slug: 'test-game' });
        const cachedGame = store.getters.getGameBySlug('test-game');
        expect(cachedGame).toBeInstanceOf(Game);
        expect(cachedGame.name).toBe('Test Game');
    });

    it('getDeveloperBySlug getter returns cached developer', async () => {
        const mockDeveloper = { id: 1, name: 'Test Studio', slug: 'test-studio' };
        const mockGames = { results: [] };

        global.fetch = vi.fn().mockImplementation((url) => {
            if (url.includes('developers/')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve(mockDeveloper),
                });
            } else {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve(mockGames),
                });
            }
        });

        await store.dispatch('fetchDeveloper', { slug: 'test-studio' });
        const cachedDev = store.getters.getDeveloperBySlug('test-studio');
        expect(cachedDev.developer).toBeInstanceOf(Developer);
        expect(cachedDev.developer.name).toBe('Test Studio');
    });

    it('getGamesList getter returns cached games list', async () => {
        const mockResponse = {
            count: 10,
            results: [{ id: 1, name: 'Game 1', slug: 'game-1', rank: 1 }],
        };
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockResponse),
        });

        const queryParams = { limit: 10, offset: 0 };
        await store.dispatch('fetchGamesList', { queryParams });
        const queryKey = new URLSearchParams(queryParams).toString();
        const cachedList = store.getters.getGamesList(queryKey);
        expect(cachedList.count).toBe(10);
        expect(cachedList.results[0]).toBeInstanceOf(Game);
    });

    it('fetchAllGamesList fetches and caches complete games list', async () => {
        const mockResponse = {
            count: 500,
            results: Array.from({ length: 500 }, (_, i) => ({
                id: i + 1,
                name: `Game ${i + 1}`,
                slug: `game-${i + 1}`,
                rank: i + 1,
            })),
        };
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockResponse),
        });

        const result = await store.dispatch('fetchAllGamesList');
        expect(result.count).toBe(500);
        expect(result.results).toHaveLength(500);
        expect(result.results[0]).toBeInstanceOf(Game);
        expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('limit=9999'));
        expect(global.fetch).toHaveBeenCalledTimes(1);

        // Second call should use cache
        await store.dispatch('fetchAllGamesList');
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('fetchAllGamesList handles errors', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
        });

        await expect(
            store.dispatch('fetchAllGamesList')
        ).rejects.toThrow('Failed to fetch all games: 500');
    });

    describe('LRU cache eviction', () => {
        it('evicts oldest game when cache exceeds 100 entries', () => {
            // Add 101 games to the cache
            for (let i = 1; i <= 101; i++) {
                const game = new Game({ id: i, name: `Game ${i}`, slug: `game-${i}`, rank: i });
                store.commit('setGame', { slug: `game-${i}`, game });
            }

            // Cache should have exactly 100 entries
            expect(Object.keys(store.state.games).length).toBe(100);

            // First game (game-1) should have been evicted
            expect(store.state.games['game-1']).toBeUndefined();

            // Last 100 games should still be in cache
            expect(store.state.games['game-2']).toBeInstanceOf(Game);
            expect(store.state.games['game-101']).toBeInstanceOf(Game);
        });

        it('evicts oldest developer when cache exceeds 50 entries', () => {
            // Add 51 developers to the cache
            for (let i = 1; i <= 51; i++) {
                const developer = new Developer({ id: i, name: `Studio ${i}`, slug: `studio-${i}` });
                store.commit('setDeveloper', {
                    slug: `studio-${i}`,
                    result: { developer, games: [] }
                });
            }

            // Cache should have exactly 50 entries
            expect(Object.keys(store.state.developers).length).toBe(50);

            // First developer should have been evicted
            expect(store.state.developers['studio-1']).toBeUndefined();

            // Last 50 developers should still be in cache
            expect(store.state.developers['studio-2']).toBeDefined();
            expect(store.state.developers['studio-51']).toBeDefined();
        });

        it('evicts oldest games list when cache exceeds 50 entries', () => {
            // Add 51 games lists to the cache
            for (let i = 0; i < 51; i++) {
                const queryKey = `limit=100&offset=${i * 100}`;
                const result = {
                    count: 1000,
                    results: [new Game({ id: i, name: `Game ${i}`, slug: `game-${i}`, rank: i })],
                };
                store.commit('setGamesList', { queryKey, result });
            }

            // Cache should have exactly 50 entries
            expect(Object.keys(store.state.gamesLists).length).toBe(50);

            // First query should have been evicted
            expect(store.state.gamesLists['limit=100&offset=0']).toBeUndefined();

            // Last 50 queries should still be in cache
            expect(store.state.gamesLists['limit=100&offset=100']).toBeDefined();
            expect(store.state.gamesLists['limit=100&offset=5000']).toBeDefined();
        });

        it('updates position when re-adding existing game (LRU behavior)', () => {
            // Fill cache to capacity
            for (let i = 1; i <= 100; i++) {
                const game = new Game({ id: i, name: `Game ${i}`, slug: `game-${i}`, rank: i });
                store.commit('setGame', { slug: `game-${i}`, game });
            }

            // Re-add an existing game (e.g., game-2)
            const game2Updated = new Game({ id: 2, name: 'Game 2 Updated', slug: 'game-2', rank: 2 });
            store.commit('setGame', { slug: 'game-2', game: game2Updated });

            // Cache should still have 100 entries
            expect(Object.keys(store.state.games).length).toBe(100);

            // game-2 should still be in cache with updated data
            expect(store.state.games['game-2']).toBeInstanceOf(Game);
            expect(store.state.games['game-2'].name).toBe('Game 2 Updated');

            // Add one more game
            const game101 = new Game({ id: 101, name: 'Game 101', slug: 'game-101', rank: 101 });
            store.commit('setGame', { slug: 'game-101', game: game101 });

            // Now game-1 should be evicted (it's the oldest), but game-2 should remain
            expect(store.state.games['game-1']).toBeUndefined();
            expect(store.state.games['game-2']).toBeInstanceOf(Game);
            expect(store.state.games['game-101']).toBeInstanceOf(Game);
        });

        it('logs eviction messages to console', () => {
            const consoleSpy = vi.spyOn(console, 'log');

            // Add games until eviction occurs
            for (let i = 1; i <= 101; i++) {
                const game = new Game({ id: i, name: `Game ${i}`, slug: `game-${i}`, rank: i });
                store.commit('setGame', { slug: `game-${i}`, game });
            }

            // Should have logged eviction message
            expect(consoleSpy).toHaveBeenCalledWith(
                expect.stringContaining('[Cache] Evicted oldest game from cache: game-1')
            );

            consoleSpy.mockRestore();
        });
    });
});
