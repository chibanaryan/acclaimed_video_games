#!/bin/bash
# Minify JavaScript files that have corresponding .min.js versions
# This script is run during deploy/commit to ensure minified files are up to date

set -e

GAMES_JS_DIR="games/static/games/js"
BOOKS_JS_DIR="books/static/books/js"
CORE_JS_DIR="core/static/core/js"

CHANGED=0

# Function to minify files in a directory
minify_dir() {
    local dir="$1"

    # Skip if directory doesn't exist
    if [ ! -d "$dir" ]; then
        return
    fi

    # Find all .min.js files and minify their source counterparts
    for min in "$dir"/*.min.js; do
        # Skip if no matches (glob didn't expand)
        [ -e "$min" ] || continue

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
}

# Minify all directories
minify_dir "$GAMES_JS_DIR"
minify_dir "$BOOKS_JS_DIR"
minify_dir "$CORE_JS_DIR"

# Bundle games client-side filtering scripts (order matters for dependencies)
# base-renderer must come before game-list-renderer (GameListRenderer extends BaseMediaListRenderer)
GAMES_BUNDLE="$GAMES_JS_DIR/client-side-filtering.bundle.min.js"
GAMES_BUNDLE_SOURCES=(
    "$CORE_JS_DIR/base-renderer.min.js"
    "$GAMES_JS_DIR/game-cache.min.js"
    "$GAMES_JS_DIR/client-filter.min.js"
    "$GAMES_JS_DIR/game-list-renderer.min.js"
    "$GAMES_JS_DIR/client-filtering.min.js"
)

# Check if any games source is newer than bundle
NEEDS_GAMES_BUNDLE=0
for src in "${GAMES_BUNDLE_SOURCES[@]}"; do
    if [ ! -f "$GAMES_BUNDLE" ] || [ "$src" -nt "$GAMES_BUNDLE" ]; then
        NEEDS_GAMES_BUNDLE=1
        break
    fi
done

if [ $NEEDS_GAMES_BUNDLE -eq 1 ]; then
    echo "Creating games client-side-filtering.bundle.min.js..."
    cat "${GAMES_BUNDLE_SOURCES[@]}" > "$GAMES_BUNDLE"
    git add "$GAMES_BUNDLE"
    CHANGED=1
fi

# Bundle books client-side filtering scripts (order matters for dependencies)
BOOKS_BUNDLE="$BOOKS_JS_DIR/book-client-side-filtering.bundle.min.js"
BOOKS_BUNDLE_SOURCES=(
    "$BOOKS_JS_DIR/book-cache.min.js"
    "$BOOKS_JS_DIR/book-client-filter.min.js"
    "$BOOKS_JS_DIR/book-list-renderer.min.js"
    "$BOOKS_JS_DIR/book-client-filtering.min.js"
)

# Check if books bundle needs update (only if books dir exists)
if [ -d "$BOOKS_JS_DIR" ]; then
    NEEDS_BOOKS_BUNDLE=0
    for src in "${BOOKS_BUNDLE_SOURCES[@]}"; do
        if [ -f "$src" ]; then
            if [ ! -f "$BOOKS_BUNDLE" ] || [ "$src" -nt "$BOOKS_BUNDLE" ]; then
                NEEDS_BOOKS_BUNDLE=1
                break
            fi
        fi
    done

    if [ $NEEDS_BOOKS_BUNDLE -eq 1 ]; then
        # Only create bundle if all source files exist
        ALL_EXIST=1
        for src in "${BOOKS_BUNDLE_SOURCES[@]}"; do
            if [ ! -f "$src" ]; then
                ALL_EXIST=0
                break
            fi
        done

        if [ $ALL_EXIST -eq 1 ]; then
            echo "Creating books book-client-side-filtering.bundle.min.js..."
            cat "${BOOKS_BUNDLE_SOURCES[@]}" > "$BOOKS_BUNDLE"
            git add "$BOOKS_BUNDLE"
            CHANGED=1
        fi
    fi
fi

if [ $CHANGED -eq 1 ]; then
    echo "Minified JS files updated and staged."
else
    echo "All minified JS files are up to date."
fi
