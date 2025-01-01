import { isObject, isEmpty } from "lodash";

const cleanData = (data) => {
    let cleaned = Object.assign({}, data);
    Object.keys(cleaned).forEach(key => {
        let val = cleaned[key];
        if (val === null || val == undefined || val.isNaN || (isObject(val) && isEmpty(val))) {
            delete cleaned[key];
        }
    });
    return cleaned;
};

const snakeToCamel = (str) => str.replace(
    /([-_][a-z])/g,
    (group) => group.toUpperCase()
        .replace('-', '')
        .replace('_', '')
);

const camelToSnake = str => str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);

const decadePattern = /\d{2}(\d{2})-(\d{2})/;
const yearPattern = /(\d{4})/;

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

// let metadata = null;

// const getMeta = async () => {
//     if (!metadata)
//         metadata = await fetch(`${process.env.VUE_APP_API_URL}meta/`)
//             .then(resp => resp.json());

//     return metadata;
// }

export { snakeToCamel, camelToSnake, cleanData, parseSlug };