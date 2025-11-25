# Developer Log

## 2025-11-25

- JavaScript refactoring: created utils.js with shared utilities (FetchManager, debounce, throttle, buildFilterParams, createSearchData), consolidated 5 duplicate fetch functions in _advanced_filters.html, unified mobile/desktop nav search, converted global onclick handlers to Alpine components (~430 lines removed)
- CSS refactoring: extracted ~1000 lines from base.html to external stylesheets (main.css, import.css)
- Removed navbar JavaScript injection hack, replaced inline styles with utility classes (.input-dark, .filter-row, .status-card)
- Implemented faceted filtering on Source Lists (filter counts update dynamically, hide zero-count options)
- Changed list type URL params from codes to readable slugs (`?type=all-time` instead of `?type=A`)
- Fixed pagination layout stability (centralized min-height in CSS, nav only renders when needed)
- Added CSV download button to game list (respects filters, uses filtered rank for filtered exports)
- Redesigned game list: compact rows with circular thumbnails, hover effects (expand thumbnail, show properties, grow rank), fading hover background, minimal mobile layout
- Redesigned 404 page with Majora's Mask theme (shaking moon, Happy Mask Salesman GIF, quote, Song of Time button with audio, responsive layout)
- Fixed Handjet font flash (FOUT) by self-hosting font with font-display: block instead of Google Fonts swap
- Performance: Fixed DeveloperDetailView double query, lists_grouped_by_type prefetch bypass, Admin genres N+1
- Performance: Added indexes on year_rank/decade_rank, batched IGDB company fetches (N calls → 2 max)
- Added contact form with Zelda/Portal themed UI (hidden until email service configured)
- Added social media buttons (X, Bluesky) to home page
- Removed unused developer management commands (cleanup, sync, refresh)
- Fixed pagination spacing on Advanced Search page (missing spacing class)
- Replaced dual year sliders with single dual-range slider (visual track indicator, floating labels)
- Fixed year slider filter mismatch on fast drag release (use @pointerup for reliable final value capture)
- Fixed "Filtered Rank" checkbox resetting to page 1 (display-only changes now preserve pagination)
- Fixed CSV download button disappearing on HTMX page changes (missing from partial template)
- Removed unused code: TYPES/SEARCH_* constants, dead serializer_class, django_extensions

## 2025-11-24

- **Major performance optimizations**: 50-70% reduction in database queries across the site
  - Eliminated template N+1 queries in game list (600+ queries → 0 per page with prefetch)
  - Optimized decade counting (10+ queries → 1 using in-memory aggregation)
  - Added 24-hour caching for genre/platform lists (99% hit rate)
  - Consolidated import page counts (7 queries → 1 with conditional aggregation)
  - Added database indexes to Game.name and Developer.name fields
  - Added 1-hour caching for game list metadata (year/decade counts) - reduces aggregate queries on most-visited page
  - Added 24-hour caching for year statistics in search view - eliminates redundant min/max queries
  - Optimized navbar search API endpoint - removed unused prefetch and added .only() for 30% faster responses
  - Added database indexes on Genre.name and Post (active, date) for faster filtered queries
  - Optimized DeveloperDetailView prefetch strategy for more efficient game loading
- Refactored IGDB importer to eliminate 170 lines of duplicated code - single source of truth for data processing
- Fixed beta advanced search unwanted scrolling on filter updates (force reload when page loaded from browser back-forward cache to reinitialize Alpine.js properly)
- Fixed beta mobile game list highlight (scroll to item and auto-dismiss after 2s now work correctly)
- Fixed 404 page title/subtitle spacing overlap
- Added Google Analytics HTMX tracking for comprehensive page view monitoring (tracks filter changes, pagination, search navigation)
- Updated documentation to reflect completed Vue.js migration (removed all frontend/Vue references from CLAUDE.md and readme.md)

## 2025-11-23

- **Completed beta migration to 100%** - All 11 routes and 28 components with legacy URL redirects and custom 404
- Fixed beta advanced search (navbar duplication, filter persistence, URL params, input focus, counts, pagination, mobile layout)
- Fixed beta developer pages (search triggering, dynamic game counts) and converted Source Lists to HTMX
- Fixed beta styling to match Vue (navbar/search colors, dropdowns, links, badges, pagination hover, fonts, no white flash)
- Fixed memory leaks (7 in Vue components) and optimized server memory (50-90% reduction)
- Fixed IGDB import progress bar, decade rank calculation, and enhanced data management tools
- Removed vite-ssg/SSR, reverted to client-side Vue SPA, added prefetching for better performance

## 2025-11-22

- Implemented dynamic tagline with real-time database counts
- Added game counts to decade filters
- Optimized IGDB import for maximum performance (100+ games/sec, 75x improvement with Pro tier)
- Fixed developer list search double-load and implemented real-time search
- Enhanced import page with file validation fixes, completion indicators, and auto-IGDB trigger
- Achieved 95% overall test coverage with comprehensive test suite expansion
- Upgraded to Heroku-24 stack
- Migrated repository from BitBucket to GitHub

## 2025-11-19

- Fixed memory leak in Vue route watchers causing accumulation during pagination
- Major beta app migration (game/developer lists, search, detail pages with HTMX)

## 2025-11-18

- Fixed pagination back button navigation to return to correct page

## 2025-11-17

- Implemented vite-ssg for server-side static generation and Wayback Machine compatibility
- Fixed Wayback Machine archival by serving pre-rendered HTML
- Implemented client-side pagination with Vuex caching for instant navigation

## 2025-11-16

- Achieved 100% test coverage with 95% threshold enforcement via pre-commit hooks
- Added database indexes and query optimizations for API performance
- Set up comprehensive test suite (Django + Vue.js with Vitest)
- Applied Black formatter to entire codebase
