# Beta Version Testing Guide

## What You Should See Right Now

### 1. Beta Home Page (`/beta/`)
- **URL**: http://localhost:8000/beta/
- **What to see**: A placeholder page saying "Home Page (Beta)"
- **Status**: ✅ Should load (basic placeholder)
- **What to confirm**:
  - Page loads without errors
  - Navigation bar appears at top
  - Footer appears at bottom
  - Dark theme styling is applied
  - All CSS frameworks loaded (Bulma, Bulmaswatch, MDI icons, Handjet font)

### 2. Beta Games List (`/beta/games/`)
- **URL**: http://localhost:8000/beta/games/
- **What to see**:
  - A list of games (first 100 games from database)
  - Simple text list: "Game Name - Rank: X"
  - A section "Testing GameRowProperties Component" with the migrated component
- **Status**: ⚠️ Partially working (games should show, but GameRowProperties may have issues)
- **What to confirm**:
  - Games list appears (even if just text)
  - GameRowProperties component renders
  - Styling matches Vue version (colors, fonts, spacing)

### 3. Visual Comparison
- **Vue version**: http://localhost:8000/games/
- **Beta version**: http://localhost:8000/beta/games/
- **What to compare**:
  - Open both in separate browser tabs
  - Compare the GameRowProperties component styling
  - Check colors, fonts, spacing match exactly

## Current Limitations (Expected)

### What's NOT Working Yet:
1. **Filtering** - No year/decade filters
2. **Pagination** - Basic Django pagination, not HTMX-enhanced
3. **Search** - Not implemented
4. **GameRowProperties** - May have relationship issues (developers, platforms, genres)
5. **Navigation** - Basic placeholder
6. **Other pages** - All placeholders

### What IS Working:
1. ✅ Base template with all CSS dependencies
2. ✅ Basic game list (fetches from database)
3. ✅ GameRowProperties component structure (may need relationship fixes)
4. ✅ URL routing
5. ✅ Dark theme styling

## What to Confirm

### Immediate Checks:

1. **Does `/beta/` load?**
   - [ ] Page loads without errors
   - [ ] Navigation visible
   - [ ] Footer visible
   - [ ] Dark theme applied

2. **Does `/beta/games/` show games?**
   - [ ] Games list appears
   - [ ] At least some games show up
   - [ ] GameRowProperties section appears

3. **Does GameRowProperties render?**
   - [ ] Component HTML structure appears
   - [ ] Styling is applied (check with DevTools)
   - [ ] Compare with Vue version side-by-side

4. **Visual Parity Check:**
   - [ ] Open Vue version: http://localhost:8000/games/
   - [ ] Open Beta version: http://localhost:8000/beta/games/
   - [ ] Compare GameRowProperties styling
   - [ ] Use browser DevTools to inspect elements
   - [ ] Compare computed styles (colors, fonts, spacing)

## Known Issues to Fix

### GameRowProperties Component
The component may have issues with:
- **Relationships**: `game.developers.all`, `game.platforms.all`, `game.genres.all`
- These need to be properly prefetched in the view

### Next Steps After Confirmation

1. **Fix GameListView** to properly prefetch relationships
2. **Fix GameRowProperties** template to handle relationships correctly
3. **Continue migrating** more components
4. **Add filtering** functionality
5. **Add HTMX** for dynamic updates

## Testing Checklist

For each page/component:

- [ ] Page loads without errors
- [ ] Data appears (games, developers, etc.)
- [ ] Styling matches Vue version
- [ ] Colors match exactly (use color picker)
- [ ] Fonts match exactly (inspect computed styles)
- [ ] Spacing matches exactly (measure with DevTools)
- [ ] Responsive behavior works
- [ ] No console errors

