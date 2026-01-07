---
name: icons
description: Add Material Design Icons to the site. Use when asked to add, use, or find icons.
---

# Adding Material Design Icons (MDI)

This project uses Material Design Icons via a self-hosted font file with **inline CSS** in base.html.

## Current Setup

- **Font file**: `games/static/games/fonts/materialdesignicons-webfont.woff2` (full 403KB font)
- **Icon definitions**: **INLINE** in `games/templates/base.html` (lines 83-86)
- **Icon reference**: https://pictogrammers.com/library/mdi/

**IMPORTANT**: Icons are defined inline in base.html for performance (eliminates render-blocking CSS request). The external file `games/static/games/css/mdi-subset.css` is NOT used at runtime.

## How to Add a New Icon

### Step 1: Find the icon codepoint

Look up the icon at https://pictogrammers.com/library/mdi/ or fetch from CDN:

```bash
curl -s "https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.css" | grep "mdi-ICONNAME"
```

Example output: `.mdi-sort::before { content: "\F04BA"; }`

### Step 2: Add CSS rule to base.html inline styles

Edit `games/templates/base.html` and find the `<style>` block around line 79-87. Add the icon to the appropriate line (83-86) in minified format:

```css
.mdi-sort::before{content:"\F04BA"}.mdi-arrow-down::before{content:"\F0045"}
```

**Icon categories in base.html:**
- Line 83: UI icons (magnify, close, download, chevrons, etc.)
- Line 84: Platform icons (playstation, xbox, nintendo, etc.)
- Line 85: Navigation/misc icons (menu, home, trophy, etc.)
- Line 86: Genre category icons (crosshairs, puzzle, etc.)

### Step 3: Use the icon in templates

```html
<span class="mdi mdi-sort"></span>
```

With sizing:
```html
<span class="mdi mdi-sort text-base"></span>
<span class="mdi mdi-sort text-xl"></span>
```

## Important Notes

1. **Icons are INLINE in base.html**: NOT in a separate CSS file. Edit base.html directly.

2. **CSS codepoints must be correct**: Look them up from the official source (pictogrammers.com or CDN). Don't guess.

3. **Minified format**: Add icons without spaces: `.mdi-name::before{content:"\FXXXX"}`

4. **No collectstatic needed**: Since it's inline HTML, changes take effect immediately on page refresh.

## Troubleshooting

**Icon not showing?**
1. Verify codepoint is correct (check official MDI CSS at pictogrammers.com)
2. Verify the rule is in base.html inline styles (lines 83-86)
3. Hard refresh browser (Cmd+Shift+R)
4. Check for typos in class name or codepoint

## Syncing External CSS File (Optional)

The file `games/static/games/css/mdi-subset.css` exists for documentation/backup but is NOT loaded at runtime. If you want to keep it in sync with base.html inline styles, update both files.
