---
name: minify
description: Minify JavaScript files and regenerate bundles. Use when asked to minify JS, update bundles, or after editing JavaScript source files.
---

# JavaScript Minification

Minify JavaScript source files and regenerate bundles for production.

## Command

```bash
./scripts/minify_js.sh
```

## What It Does

1. **Minifies source files**: For each `.js` file in `games/static/games/js/` that has a corresponding `.min.js` file, updates the minified version if the source is newer

2. **Regenerates the bundle**: Concatenates minified files into `client-side-filtering.bundle.min.js`:
   - `game-cache.min.js`
   - `client-filter.min.js`
   - `game-list-renderer.min.js`
   - `client-filtering.min.js`

3. **Stages files for git**: Automatically runs `git add` on updated files

## When to Run

- After editing any JavaScript source file (`.js`, not `.min.js`)
- Before committing changes that include JS modifications
- When troubleshooting JS behavior differences between dev and production

## File Locations

| Type | Location |
|------|----------|
| Source files | `games/static/games/js/*.js` |
| Minified files | `games/static/games/js/*.min.js` |
| Bundle | `games/static/games/js/client-side-filtering.bundle.min.js` |
| Script | `scripts/minify_js.sh` |

## Note

The `/commit` skill already includes minification as step 3. Use `/minify` when you want to minify without committing.
