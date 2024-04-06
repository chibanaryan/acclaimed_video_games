const cleanData = (data) => {
    let cleaned = Object.assign({}, data);

    Object.keys(cleaned).forEach(key => {
        let val = cleaned[key];
        if (val === null || val == undefined || val.isNaN) {
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


export { snakeToCamel, camelToSnake, cleanData };