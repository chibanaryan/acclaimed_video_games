/**
 * Get the appropriate API URL based on environment
 *
 * In the browser (client-side), we use relative URLs by default
 * or the configured VITE_API_URL from environment variables.
 *
 * @returns {string} The API base URL
 */
export function getApiUrl() {
    // Use configured URL or default to relative path
    return import.meta.env.VITE_API_URL || '/api/';
}
