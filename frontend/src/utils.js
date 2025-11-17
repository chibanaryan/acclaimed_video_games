import { globalStore } from "@/objectStore";
import _ from "lodash";
const { cloneDeep, isEmpty, isObject } = _;

/**
 * Remove null, undefined, NaN, and empty object values from an object
 * @param {Object} data - The object to clean
 * @returns {Object} A new object with nullish and empty values removed
 */
const cleanData = (data) => {
    let cleaned = cloneDeep(data);
    Object.keys(cleaned).forEach(key => {
        let val = cleaned[key];
        if (val === null || val == undefined || Number.isNaN(val) || (isObject(val) && isEmpty(val))) {
            delete cleaned[key];
        }
    });
    return cleaned;
};

/**
 * Convert snake_case or kebab-case strings to camelCase
 * @param {string} str - The string to convert
 * @returns {string} The camelCase version of the string
 */
const snakeToCamel = (str) => str.replace(
    /([-_][a-z])/g,
    (group) => group.toUpperCase()
        .replace('-', '')
        .replace('_', '')
);

/**
 * Convert camelCase strings to snake_case
 * @param {string} str - The string to convert
 * @returns {string} The snake_case version of the string
 */
const camelToSnake = str => str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);

const decadePattern = /\d{2}(\d{2})-(\d{2})/;
const yearPattern = /(\d{4})/;

/**
 * Parse a URL slug to extract year/decade range and type information
 * @param {string} slug - The slug to parse (e.g., "1990-99", "2005", "all-time")
 * @returns {{start: number|undefined, end: number|undefined, type: string}}
 *   Object containing start year, end year, and type ('decade', 'year', or 'alltime')
 * @example
 * parseSlug('1990-99') // { start: 1990, end: 1999, type: 'decade' }
 * parseSlug('2005')    // { start: 2005, end: 2005, type: 'year' }
 * parseSlug('all-time') // { start: undefined, end: undefined, type: 'alltime' }
 */
const parseSlug = (slug) => {
    let start;
    let end;
    let type;

    if (decadePattern.test(slug)) {
        let match = slug.match(decadePattern);

        start = parseInt(match[1]);
        end = parseInt(match[2]);

        if (start > 50)
            start += 1900;
        else
            start += 2000;

        if (end > 50)
            end += 1900;
        else
            end += 2000;

        type = 'decade';

    } else if (yearPattern.test(slug)) {
        let match = slug.match(yearPattern);
        let year = parseInt(match[1]);

        start = year;
        end = year;
        type = 'year';
    } else {
        type = 'alltime';
    }

    return { start, end, type };
}

/**
 * Restore the previously saved scroll position from localStorage
 * @param {number} [delay=500] - Delay in milliseconds before scrolling
 */
const loadPreviousScrollPosition = (delay = 500) => {
    // Guard against SSR - window is only available in browser
    if (typeof window === 'undefined') return;

    const scrollY = globalStore.get('scrollY');
    if (scrollY)
        setTimeout(() => {
            window.scroll(0, scrollY);
            globalStore.set('scrollY', null)
        }, delay);
}

export {
    camelToSnake,
    cleanData,
    loadPreviousScrollPosition,
    parseSlug,
    snakeToCamel
};

