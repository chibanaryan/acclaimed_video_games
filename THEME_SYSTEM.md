# Theme System Documentation

## Overview

The site uses a unified DaisyUI theme system with two themes:
- **lofi** (light theme)
- **forest** (dark theme)

The theme is stored in `localStorage` under the key `'theme'` and automatically syncs across all pages including the Django admin.

## Architecture

### 1. Centralized Theme Script

All pages include the same theme initialization script from [`games/templates/includes/_theme_script.html`](games/templates/includes/_theme_script.html):

- **Validates** theme on page load - only allows `'lofi'` or `'forest'`
- **Cleans up** invalid theme values from previous configurations
- **Auto-detects** system preference if no valid theme is stored
- **Removes** Django admin theme conflicts (`'admin-theme'` key)

### 2. Page Integration

**Main Site** (base.html)
- Includes `_theme_script.html` at the top of `<head>`
- Provides theme toggle in navigation
- Persists theme choice in localStorage

**Import Page** (import.html)
- Uses the same `_theme_script.html`
- Inherits theme from localStorage
- No separate theme system

**Django Admin** (admin/base_site.html)
- Custom template overrides Django's admin base
- Applies our DaisyUI theme system
- Hides Django's built-in theme toggle
- Styles admin interface to match site themes

### 3. Theme Configuration

Themes are defined in [`theme/static_src/src/styles.css`](theme/static_src/src/styles.css):

```css
@plugin "daisyui" {
  themes: ["lofi", "forest"];
}
```

## Troubleshooting

### Problem: Theme keeps changing or reverting

**Cause:** Stale theme values in localStorage from previous configurations

**Solution:**
1. Open browser DevTools Console (F12)
2. Run: `localStorage.clear()` or `localStorage.removeItem('theme')`
3. Reload page - theme will auto-detect based on system preference

### Problem: Admin pages have different theme

**Cause:** Django admin was using its own theme system

**Solution:**
- Already fixed with custom `admin/base_site.html`
- Admin now uses the same lofi/forest themes
- Django's theme toggle is hidden

### Problem: Import page styling looks wrong

**Cause:** Theme script not running or localStorage has invalid value

**Solution:**
1. Check browser console for theme errors
2. Run `resetTheme()` in console (if theme-reset.js is loaded)
3. Clear localStorage and reload

## Development Tools

### Theme Reset Utility

The file [`games/static/games/js/theme-reset.js`](games/static/games/js/theme-reset.js) provides console utilities:

**Check theme status:**
```javascript
checkTheme()
```

**Reset theme to system default:**
```javascript
resetTheme()
```

### Manual Theme Testing

Set theme directly in console:
```javascript
// Set to light theme
localStorage.setItem('theme', 'lofi')
location.reload()

// Set to dark theme
localStorage.setItem('theme', 'forest')
location.reload()

// Clear theme (will auto-detect system preference)
localStorage.removeItem('theme')
location.reload()
```

## How It Works

### Page Load Sequence

1. **Theme script runs FIRST** (in `<head>`, before any content)
   - Reads `localStorage.getItem('theme')`
   - Validates: must be `'lofi'` or `'forest'`
   - Invalid? Detects system preference and sets accordingly
   - Applies: `document.documentElement.setAttribute('data-theme', t)`

2. **CSS loads** with theme applied
   - DaisyUI reads `data-theme` attribute
   - Applies correct color variables
   - No flash of unstyled content (FOUC)

3. **Page renders** with correct theme

### Theme Toggle

User clicks theme toggle → JavaScript function `setTheme(newTheme)`:
1. Saves to localStorage: `localStorage.setItem('theme', newTheme)`
2. Updates DOM: `document.documentElement.setAttribute('data-theme', newTheme)`
3. Updates toggle UI state
4. No page reload needed

## Files Changed

### Created
- `games/templates/includes/_theme_script.html` - Centralized theme initialization
- `games/templates/admin/base_site.html` - Custom admin template with theme support
- `games/static/games/js/theme-reset.js` - Debug utilities

### Modified
- `games/templates/base.html` - Now includes `_theme_script.html`
- `games/templates/import.html` - Now includes `_theme_script.html`

## Testing Checklist

- [ ] Main site pages (games, developers, lists, posts) use correct theme
- [ ] Theme toggle switches between lofi and forest
- [ ] Theme persists across page navigation
- [ ] Import page (`/import/`) uses same theme as main site
- [ ] Django admin (`/admin/`) uses same theme as main site
- [ ] Theme survives browser refresh
- [ ] Invalid theme values get automatically corrected
- [ ] System dark/light mode preference works for first-time visitors

## Migration Notes

**Existing Users:**
- Old theme values (night, business, black, auto) will be automatically cleared
- Users will get theme based on their system preference (dark → forest, light → lofi)
- Theme choice will be remembered going forward

**New Users:**
- Theme auto-detects from system preference
- Choice is saved and persists across all pages
