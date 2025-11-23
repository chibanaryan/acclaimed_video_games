import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { getApiUrl } from '../config';

describe('getApiUrl', () => {
    let originalImportMetaEnv;

    beforeEach(() => {
        // Save original import.meta.env
        originalImportMetaEnv = { ...import.meta.env };
    });

    afterEach(() => {
        // Restore original import.meta.env
        Object.keys(originalImportMetaEnv).forEach(key => {
            import.meta.env[key] = originalImportMetaEnv[key];
        });
    });

    it('returns default relative URL when VITE_API_URL is not set', () => {
        delete import.meta.env.VITE_API_URL;

        const url = getApiUrl();
        expect(url).toBe('/api/');
    });

    it('returns custom URL when VITE_API_URL is set', () => {
        import.meta.env.VITE_API_URL = 'https://api.example.com/api/';

        const url = getApiUrl();
        expect(url).toBe('https://api.example.com/api/');
    });
});
