/**
 * Get the appropriate API URL based on environment
 *
 * During SSG build, we need to use absolute URLs to fetch data from the Django server.
 * In the browser (client-side), we use relative URLs.
 *
 * @returns {string} The API base URL
 */
export function getApiUrl() {
    // During SSG build, use absolute URL to Django server
    if (import.meta.env.SSR) {
        return import.meta.env.VITE_SSG_API_URL || 'http://127.0.0.1:8000/api/';
    }

    // In browser, use configured URL or default to relative path
    return import.meta.env.VITE_API_URL || '/api/';
}
