/**
 * Centralized API utilities for making HTTP requests
 */

/**
 * Custom error class for API errors
 */
export class ApiError extends Error {
    constructor(message, status, response) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.response = response;
    }
}

/**
 * Make a GET request to the API with standardized error handling
 *
 * @param {string} url - The API endpoint URL
 * @param {Object} [options={}] - Fetch options (headers, signal, etc.)
 * @returns {Promise<any>} The parsed JSON response
 * @throws {ApiError} If the response is not ok or network error occurs
 *
 * @example
 * try {
 *     const data = await apiGet('/api/games/');
 *     console.log(data);
 * } catch (error) {
 *     if (error.status === 404) {
 *         console.error('Not found');
 *     }
 * }
 */
export async function apiGet(url, options = {}) {
    try {
        const response = await fetch(url, {
            method: 'GET',
            ...options
        });

        if (!response.ok) {
            // Try to get error message from response
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                } else if (errorData.error) {
                    errorMessage = errorData.error;
                }
            } catch (e) {
                // Response wasn't JSON, use default message
            }

            throw new ApiError(errorMessage, response.status, response);
        }

        return await response.json();
    } catch (error) {
        // Re-throw ApiErrors as-is
        if (error instanceof ApiError) {
            throw error;
        }

        // Handle AbortError specially (from AbortController)
        if (error.name === 'AbortError') {
            throw error;
        }

        // Wrap other errors (network errors, etc.)
        throw new ApiError(
            `Network error: ${error.message}`,
            0,
            null
        );
    }
}

/**
 * Make a POST request to the API with standardized error handling
 *
 * @param {string} url - The API endpoint URL
 * @param {Object} data - The data to send in the request body
 * @param {Object} [options={}] - Additional fetch options
 * @returns {Promise<any>} The parsed JSON response
 * @throws {ApiError} If the response is not ok or network error occurs
 */
export async function apiPost(url, data, options = {}) {
    return apiRequest(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        body: JSON.stringify(data),
        ...options
    });
}

/**
 * Generic API request function with standardized error handling
 *
 * @param {string} url - The API endpoint URL
 * @param {Object} [options={}] - Fetch options
 * @returns {Promise<any>} The parsed JSON response
 * @throws {ApiError} If the response is not ok or network error occurs
 */
export async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, options);

        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                } else if (errorData.error) {
                    errorMessage = errorData.error;
                }
            } catch (e) {
                // Response wasn't JSON, use default message
            }

            throw new ApiError(errorMessage, response.status, response);
        }

        return await response.json();
    } catch (error) {
        if (error instanceof ApiError) {
            throw error;
        }

        if (error.name === 'AbortError') {
            throw error;
        }

        throw new ApiError(
            `Network error: ${error.message}`,
            0,
            null
        );
    }
}
