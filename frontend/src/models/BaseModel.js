import { snakeToCamel } from "@/utils";
import moment from 'moment';

const DATETIME_PAT = /^20\d{2}-\d{2}-\d{2}T/;

class BaseData {
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