/**
 * Runs the year grid under Node for core/tests/test_year_grid_baseline.py.
 *
 *   node core/tests/js/year_grid_baseline.js
 *
 * Builds the grid as a page loaded with a narrow filter would - its
 * `year-counts-data` the filter's counts - once with the page's whole-corpus
 * `year-baseline-counts-data` and once without, and prints the colour scale
 * each ends up with, plus the opacity of a count above a stale scale. Also
 * reports which neighbours a tile sees around a year missing from the counts.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..', '..', '..');
const noop = () => {};
const documentListeners = {};
let elements = {};
globalThis.window = globalThis;
globalThis.document = {
    addEventListener: (type, handler) => {
        (documentListeners[type] = documentListeners[type] || []).push(handler);
    },
    getElementById: id => (id in elements ? { textContent: JSON.stringify(elements[id]) } : null),
};
globalThis.CustomEvent = class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } };
globalThis.addEventListener = noop;
globalThis.removeEventListener = noop;
globalThis.dispatchEvent = noop;

const factories = {};
globalThis.Alpine = { data: (name, factory) => { factories[name] = factory; } };
vm.runInThisContext(
    fs.readFileSync(path.join(root, 'core/static/core/js/filter-subcomponents.js'), 'utf8')
);
documentListeners['alpine:init'].forEach(handler => handler());

const filtered = [{ year: 1970, count: 1 }, { year: 1971, count: 0 }, { year: 1972, count: 0 }];
const corpus = [{ year: 1970, count: 20 }, { year: 1971, count: 12 }, { year: 1972, count: 3 }];

function build(withBaseline) {
    elements = { 'year-counts-data': filtered };
    if (withBaseline) elements['year-baseline-counts-data'] = corpus;
    const grid = factories.yearGridComponent({ filters: {}, minYear: 1970, maxYear: 1972 });
    grid.init();
    return {
        maxCount: grid.maxCount,
        originalMaxCount: grid.originalMaxCount,
        current: grid.yearCounts.map(y => y.count),
        cells: grid.decades[0].cells.filter(c => c.year).map(c => c.year),
    };
}

const stale = factories.yearGridComponent({ filters: {}, minYear: 1970, maxYear: 1972 });
stale.maxCount = 1;

// 1971 has no count, so its cell is filled in; 1983 on have no cell at all.
elements = {
    'year-counts-data': [1970, 1972, 1980, 1981, 1982].map(year => ({ year, count: 1 })),
};
const gappy = factories.yearGridComponent({ filters: { start: 1970, end: 1989 }, minYear: 1960, maxYear: 1990 });
gappy.init();

process.stdout.write(JSON.stringify({
    neighbours: {
        rightOntoFilledCell: gappy.hasSelectedRight(1970),
        belowOntoFilledCell: gappy.hasSelectedBelow(1981),
        cornerOntoFilledCell: gappy.hasSelectedDiagonalBR(1980),
        rightOntoNoCell: gappy.hasSelectedRight(1982),
    },
    withBaseline: build(true),
    withoutBaseline: build(false),
    opacityAboveScale: stale.getOpacity(20),
}));
