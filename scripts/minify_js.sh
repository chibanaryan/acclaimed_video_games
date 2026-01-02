#!/bin/bash
# Minify JavaScript files that have corresponding .min.js versions
# This script is run during deploy/commit to ensure minified files are up to date

set -e

JS_DIR="games/static/games/js"

CHANGED=0

# Find all .min.js files and minify their source counterparts
for min in "$JS_DIR"/*.min.js; do
    # Skip bundle files (they're created from other minified files)
    if [[ "$min" == *".bundle.min.js" ]]; then
        continue
    fi

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

# Bundle client-side filtering scripts (order matters for dependencies)
BUNDLE="$JS_DIR/client-side-filtering.bundle.min.js"
BUNDLE_SOURCES=(
    "$JS_DIR/game-cache.min.js"
    "$JS_DIR/client-filter.min.js"
    "$JS_DIR/game-list-renderer.min.js"
    "$JS_DIR/client-filtering.min.js"
)

# Check if any source is newer than bundle
NEEDS_BUNDLE=0
for src in "${BUNDLE_SOURCES[@]}"; do
    if [ ! -f "$BUNDLE" ] || [ "$src" -nt "$BUNDLE" ]; then
        NEEDS_BUNDLE=1
        break
    fi
done

if [ $NEEDS_BUNDLE -eq 1 ]; then
    echo "Creating client-side-filtering.bundle.min.js..."
    cat "${BUNDLE_SOURCES[@]}" > "$BUNDLE"
    git add "$BUNDLE"
    CHANGED=1
fi

if [ $CHANGED -eq 1 ]; then
    echo "Minified JS files updated and staged."
else
    echo "All minified JS files are up to date."
fi
