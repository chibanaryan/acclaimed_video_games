import { describe, it, expect } from 'vitest';
import Genre from '@/models/Genre';
import Platform from '@/models/Platform';

describe('model classes', () => {
    it('Genre toString returns name', () => {
        const genre = new Genre({ name: 'Action' });
        expect(genre.toString()).toBe('Action');
    });

    it('Platform toString returns name', () => {
        const platform = new Platform({ name: 'PC' });
        expect(platform.toString()).toBe('PC');
    });
});
