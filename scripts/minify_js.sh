#!/bin/bash
# Minify JavaScript files that have corresponding .min.js versions
# This script is run during deploy/commit to ensure minified files are up to date

set -e

JS_DIR="games/static/games/js"

CHANGED=0

# Find all .min.js files and minify their source counterparts
for min in "$JS_DIR"/*.min.js; do
    # Get the source file name by removing .min from the path
    src="${min%.min.js}.js"

    if [ -f "$src" ]; then
        # Check if minified file is older than source
        if [ "$src" -nt "$min" ]; then
            filename=$(basename "$src")
            echo "Minifying $filename..."
            npx terser "$src" -o "$min" -c -m
            git add "$min"
            CHANGED=1
        fi
    fi
done

if [ $CHANGED -eq 1 ]; then
    echo "Minified JS files updated and staged."
else
    echo "All minified JS files are up to date."
fi
