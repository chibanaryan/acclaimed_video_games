import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
    camelToSnake,
    cleanData,
    loadPreviousScrollPosition,
    parseSlug,
    snakeToCamel,
} from '@/utils';
import { globalStore } from '@/objectStore';

describe('utils', () => {
    it('snakeToCamel converts strings correctly', () => {
        expect(snakeToCamel('foo_bar')).toBe('fooBar');
        expect(snakeToCamel('foo-bar_baz')).toBe('fooBarBaz');
    });

    it('camelToSnake converts strings correctly', () => {
        expect(camelToSnake('fooBarBaz')).toBe('foo_bar_baz');
    });

    it('parseSlug handles all cases', () => {
        expect(parseSlug('1970-79')).toEqual({ start: 1970, end: 1979, type: 'decade' });
        expect(parseSlug('1985')).toEqual({ start: 1985, end: 1985, type: 'year' });
        expect(parseSlug('all-time')).toEqual({ start: undefined, end: undefined, type: 'alltime' });
    });

    it('cleanData removes nullish and empty values', () => {
        const cleaned = cleanData({
            a: 1,
            b: null,
            c: undefined,
            d: { },
            e: { x: 1 },
        });
        expect(cleaned).toEqual({ a: 1, e: { x: 1 } });
    });

    describe('loadPreviousScrollPosition', () => {
        beforeEach(() => {
            vi.useFakeTimers();
            globalStore.set('scrollY', null);
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it('restores scroll position and clears stored value', () => {
            globalStore.set('scrollY', 100);
            const scrollSpy = vi.spyOn(window, 'scroll');
            loadPreviousScrollPosition(0);
            vi.advanceTimersByTime(0);
            expect(scrollSpy).toHaveBeenCalledWith(0, 100);
            expect(globalStore.get('scrollY')).toBe(null);
            scrollSpy.mockRestore();
        });
    });
});
