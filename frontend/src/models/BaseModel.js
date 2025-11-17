import { snakeToCamel } from "@/utils";
import moment from 'moment';

/** Pattern to match ISO 8601 datetime strings */
const DATETIME_PAT = /^20\d{2}-\d{2}-\d{2}T/;

/**
 * Base class for all data models
 *
 * Automatically converts snake_case properties from API responses to camelCase,
 * and parses ISO 8601 datetime strings to moment objects.
 *
 * @example
 * // API returns: { user_name: "John", created_at: "2023-01-15T10:30:00Z" }
 * class User extends BaseData {}
 * const user = new User(apiData);
 * // user.userName === "John"
 * // user.createdAt is a moment object
 */
class BaseData {
    /**
     * Create a new model instance from API data
     * @param {Object} data - The raw data object (typically from API with snake_case keys)
     */
    constructor(data) {
        data = data || {};
        Object.keys(data).forEach(k => {
            let key = snakeToCamel(k);
            let value = data[k];

            // Is it a datetime string?
            if (typeof value == 'string' && value.match(DATETIME_PAT))
                value = moment(value);

            this[key] = value;
        });
    }
}

export default BaseData;