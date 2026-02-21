---
name: icons
description: Add Material Design Icons to the site. Use when asked to add, use, or find icons.
---

# Adding Material Design Icons (MDI)

This project uses Material Design Icons via a self-hosted **subset** font with runtime icon CSS in `base.html`.

## Current Setup

- **Font file**: `games/static/games/fonts/materialdesignicons-webfont.woff2` (generated subset)
- **Runtime icon definitions**: `games/templates/base.html` inline CSS
- **Subset source mappings**: `games/static/games/css/mdi-subset.css` (must stay in sync)
- **Subset rebuild script**: `scripts/build_mdi_subset.sh`
- **Icon reference**: https://pictogrammers.com/library/mdi/

**IMPORTANT**: If you add or change icon codepoints, you must rebuild the subset font. Otherwise the glyph may be missing at runtime even if CSS is correct.

## How to Add a New Icon

### Step 1: Find the icon codepoint

Look up the icon at https://pictogrammers.com/library/mdi/ or fetch from CDN:

```bash
curl -s "https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.css" | grep "mdi-ICONNAME"
```

Example output: `.mdi-sort::before { content: "\F04BA"; }`

### Step 2: Add CSS rule to `base.html` inline styles

Edit `games/templates/base.html` and find the `<style>` block around line 79-87. Add the icon to the appropriate line (83-86) in minified format:

```css
.mdi-sort::before{content:"\F04BA"}.mdi-arrow-down::before{content:"\F0045"}
```

**Icon categories in base.html:**
- Line 83: UI icons (magnify, close, download, chevrons, etc.)
- Line 84: Platform icons (playstation, xbox, nintendo, etc.)
- Line 85: Navigation/misc icons (menu, home, trophy, etc.)
- Line 86: Genre category icons (crosshairs, puzzle, etc.)

### Step 3: Add the same mapping to `mdi-subset.css`

Edit `games/static/games/css/mdi-subset.css` and add:

```css
.mdi-sort::before { content: "\F04BA"; }
```

Keep codepoints synchronized between `base.html` and `mdi-subset.css`.

### Step 4: Rebuild the subset font

Run:

```bash
./scripts/build_mdi_subset.sh
```

If dependencies are missing:

```bash
pip install fonttools brotli zopfli
```

### Step 5: Use the icon in templates

```html
<span class="mdi mdi-sort"></span>
```

With sizing:
```html
<span class="mdi mdi-sort text-base"></span>
<span class="mdi mdi-sort text-xl"></span>
```

## Important Notes

1. **Runtime CSS is inline in `base.html`**: update that file for live icon usage.

2. **Keep mappings in sync**: update both `base.html` and `mdi-subset.css`.

3. **Rebuild required**: run `./scripts/build_mdi_subset.sh` after any codepoint change.

4. **Codepoints must be exact**: use official MDI source (pictogrammers/CDN), do not guess.

## Troubleshooting

**Icon not showing?**
1. Verify codepoint is correct (check official MDI CSS).
2. Verify the mapping exists in both `base.html` and `mdi-subset.css`.
3. Hard refresh browser (Cmd+Shift+R)
4. Re-run `./scripts/build_mdi_subset.sh` and confirm it reports completion.
5. Check for typos in class name or codepoint.
