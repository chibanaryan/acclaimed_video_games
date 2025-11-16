import { describe, it, expect } from 'vitest';
import Genre from '@/models/Genre';
import Platform from '@/models/Platform';
import BaseModel from '@/models/BaseModel';
import moment from 'moment';

describe('model classes', () => {
    it('Genre toString returns name', () => {
        const genre = new Genre({ name: 'Action' });
        expect(genre.toString()).toBe('Action');
    });

    it('Platform toString returns name', () => {
        const platform = new Platform({ name: 'PC' });
        expect(platform.toString()).toBe('PC');
    });

    it('BaseModel converts datetime strings to moment instances', () => {
        const data = new BaseModel({ created_at: '2023-03-04T12:00:00' });
        expect(moment.isMoment(data.createdAt)).toBe(true);
        expect(data.createdAt.year()).toBe(2023);
    });

    it('BaseModel keeps non-string values intact', () => {
        const data = new BaseModel({ total: 42 });
        expect(data.total).toBe(42);
    });

    it('BaseModel safely handles empty payloads', () => {
        const data = new BaseModel();
        expect(Object.keys(data)).toHaveLength(0);
    });
});
