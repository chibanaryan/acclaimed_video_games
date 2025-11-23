# Developer Log

## 2025-11-23

- Fixed memory leaks in Vue components and import page (7 leaks total)
- Fixed "Last Updated" to show date only and update only on Games file import
- Optimized server-side memory usage (50-90% reduction for large datasets)
- Fixed IGDB import progress bar bug (queryset filtering issue causing Zeno's paradox)
- Added development-only "Load Test Data" button for quick database seeding
- Fixed Game Positions duplicating on re-import (now clears before importing)
- Fixed decade rank calculation bug (SQLite was ordering by year then rank instead of global rank)
- Enhanced "Delete All Data" to include Genres and reset ID sequences on both PostgreSQL and SQLite
- Removed vite-ssg and server-side prerendering (reverted to standard client-side Vue.js SPA)
- Fixed font loading with preloading and display=block for immediate pixelated font rendering
- Added font and image prefetching to beta site for improved initial load performance
- Implemented genre/platform filter bubbles on beta site with immediate removal and Alpine.js reactivity
- Fixed Advanced Search to always show Clear Filters button and reset to defaults instead of clearing entirely
- Fixed beta site link colors to match original Vue.js site (removed dimmer blue overrides, now uses default Bulmaswatch Cyborg theme)
- Added pagination hover effect to beta site (numbers turn blue on hover to match original site)
- Fixed beta site filter badge spacing and colors to exactly match Vue original
- Updated beta Advanced Search title to show result counts with commas ("Showing X to Y of Z Results")
- Fixed beta year slider layout (labels now to left, adjusted width to match original)

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
