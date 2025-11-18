import { describe, it, expect } from 'vitest';
import Genre from '@/models/Genre';
import Platform from '@/models/Platform';
import BaseModel from '@/models/BaseModel';
import Game from '@/models/Game';
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

    it('Game provides thumbnail and image URLs', () => {
        const game = new Game({
            id: 1,
            name: 'Test Game',
            igdb_artwork_id: 'abc123',
        });
        expect(game.thumbnail).toBe('https://images.igdb.com/igdb/image/upload/t_cover_small/abc123');
        expect(game.image).toBe('https://images.igdb.com/igdb/image/upload/t_cover_big/abc123');
    });

    it('Game renders description as HTML paragraphs', () => {
        const game = new Game({
            id: 1,
            name: 'Test Game',
            description: 'Line 1\nLine 2\n\nLine 3',
        });
        const rendered = game.renderedDescription;
        expect(rendered).toContain('<p>Line 1</p>');
        expect(rendered).toContain('<p>Line 2</p>');
        expect(rendered).toContain('<p>Line 3</p>');
    });

    it('Game calculates decade from year of release', () => {
        const game1998 = new Game({ id: 1, year_of_release: 1998 });
        expect(game1998.decade).toBe(1990);

        const game2015 = new Game({ id: 2, year_of_release: 2015 });
        expect(game2015.decade).toBe(2010);
    });

    it('Game generates decade slug', () => {
        const game1998 = new Game({ id: 1, year_of_release: 1998 });
        expect(game1998.decadeSlug).toBe('1990-99');

        const game2015 = new Game({ id: 2, year_of_release: 2015 });
        expect(game2015.decadeSlug).toBe('2010-19');
    });
});
