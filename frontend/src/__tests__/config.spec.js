import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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

    it('returns absolute URL during SSR', () => {
        // Mock SSR environment
        import.meta.env.SSR = true;
        delete process.env.VITE_SSG_API_URL;

        const url = getApiUrl();
        expect(url).toBe('http://127.0.0.1:8000/api/');
    });

    it('returns custom SSR URL when VITE_SSG_API_URL is set', () => {
        // Mock SSR environment with custom URL
        import.meta.env.SSR = true;
        process.env.VITE_SSG_API_URL = 'http://localhost:9000/api/';

        const url = getApiUrl();
        expect(url).toBe('http://localhost:9000/api/');
    });

    it('returns relative URL in browser', () => {
        // Mock browser environment
        import.meta.env.SSR = false;
        delete import.meta.env.VITE_API_URL;

        const url = getApiUrl();
        expect(url).toBe('/api/');
    });

    it('returns custom client URL when VITE_API_URL is set', () => {
        // Mock browser environment with custom URL
        import.meta.env.SSR = false;
        import.meta.env.VITE_API_URL = 'https://api.example.com/api/';

        const url = getApiUrl();
        expect(url).toBe('https://api.example.com/api/');
    });
});
