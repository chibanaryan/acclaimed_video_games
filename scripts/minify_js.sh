#!/bin/bash
# Minify JavaScript files that have corresponding .min.js versions
# This script is run by pre-commit to ensure minified files are up to date

set -e

JS_DIR="games/static/games/js"

# List of files to minify (source -> min)
FILES=(
    "client-filter.js"
    "client-filtering.js"
    "game-cache.js"
    "game-list-renderer.js"
    "utils-base.js"
    "utils-loadmore.js"
)

CHANGED=0

for file in "${FILES[@]}"; do
    src="$JS_DIR/$file"
    min="$JS_DIR/${file%.js}.min.js"

    if [ -f "$src" ]; then
        # Check if minified file is older than source
        if [ ! -f "$min" ] || [ "$src" -nt "$min" ]; then
            echo "Minifying $file..."
            npx terser "$src" -o "$min" -c -m
            git add "$min"
            CHANGED=1
        fi
    fi
done

if [ $CHANGED -eq 1 ]; then
    echo "Minified JS files updated and staged."
fi
