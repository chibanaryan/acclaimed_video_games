# Developer Log

## 2025-11-22

- **Major IGDB import optimizations**: Implemented 7.8x performance improvements for IGDB data imports
  - Field expansion eliminates 3-5 API calls per game (cover and genre data fetched in main query)
  - Concurrent processing with thread-safe rate limiting (default: 4 concurrent requests)
  - Multi-query batching fetches multiple games per API request (default: 10 games/batch)
  - Pro tier support with 750x faster rate limits (3,000 req/sec vs 4 req/sec)
  - Performance: 15.53 games/sec vs previous 2 games/sec (7.8x faster)
  - Import time: 1000 games in 64 seconds vs 500 seconds (8.3 min → 1.1 min)
  - Command now uses optimized defaults (concurrency=4, batch-games=10) out of the box
  - Full parity verified: all fields, developers, aliases, and genres imported correctly
  - Added 8 new unit tests for concurrent/batch processing (all 37 tests passing)
  - Tested with complete database wipe and fresh import - zero errors

- **Enhanced get_igdb command**: Added flags for individual game updates (`--game`, `--slug`, `--id`, `--force`) to update specific games without batch processing. Fixed 13 games on production missing IGDB artwork (Age of Empires II, Halo 2, etc.).

- **Real-time search without page refreshes**: Developer page search now filters in real-time (200ms) with URL updates only on Enter key press. Used `router.replace()` instead of `push()` to eliminate page refresh sensation.

- **Fixed vue-gtag SSR build issue**: Changed to dynamic import to prevent vite-ssg build failures.

- **IGDB API rate limiting implementation**: Prevent rate limit errors from IGDB API
  - Implemented 3.5 requests/second rate limiter (safely under IGDB's 4 req/sec limit)
  - Added `_wait_for_rate_limit()` to enforce minimum delays between API requests
  - Added `_make_request_with_retry()` with exponential backoff for 429 (Too Many Requests) errors
  - Max 3 automatic retries with exponential backoff (1s, 2s, 4s)
  - Updated all API methods to use rate limiting (games, covers, companies, genres, themes, release statuses)
  - Enhanced `get_igdb` and `refresh_igdb_developers` commands with:
    - `--delay` argument (default 0.5s) to space out batch processing
    - `--batch-size` argument (default 50) for progress checkpoints
    - Real-time progress reporting with ETA calculations
    - Improved error handling and logging
  - Added 5 comprehensive unit tests for rate limiting (total: 114 tests passing)
  - Prevents hitting rate limits during bulk IGDB imports and refreshes

- **IGDB developer data fix**: Fixed missing developer IGDB data for games
  - Root cause: `get_igdb` management command only processes games without artwork, so games with missing developer data were never updated
  - Created new `refresh_igdb_developers` command to find and refresh games with IGDB IDs but missing developer IGDB data
  - Supports refreshing by game slug, game ID, or all games with `--all` flag
  - Added 9 comprehensive unit tests with full coverage of command functionality
  - Fixed Super Mario Odyssey and all affected games with missing developer data
  - All 109 tests passing (100 existing + 9 new tests)

- **Repository migration**: Moved repository from BitBucket to GitHub (chibanaryan/acclaimedgames)

- **Heroku stack upgrade**: Upgraded from heroku-22 to heroku-24
  - Added Node.js 24.x engine specification to `frontend/package.json`
  - Updated `psycopg2` to `psycopg2-binary==2.9.11` for better Heroku compatibility
  - Python 3.11 confirmed compatible with heroku-24
  - All tests passing (100% coverage maintained)
  - Deployment successful with zero downtime
  - Application verified and running on heroku-24 stack

- **Documentation updates**: Fixed deployment instructions to reference 'main' branch instead of deprecated 'master'

## 2025-11-19

- **Memory leak fix**: Fixed Vue.js route watchers not being cleaned up on component unmount, causing memory accumulation during pagination. Converted to explicit `$watch()` calls with proper cleanup in `beforeUnmount()`.

- **Beta migration progress**: Major components and pages migrated to Django + HTMX + Alpine.js:
  - Game list, search, and detail pages with filtering, pagination, and HTMX support
  - Developer list and detail pages
  - Advanced search with genre/platform filtering and "Any"/"All" options
  - All page views implemented with graceful pagination error handling
  - Added `HTMXPushURLMiddleware` for HTMX history support

- **Frontend updates**: Rebuilt dist with memory leak fix, added `sass-embedded` dependency for Vite SASS preprocessing.

- **IGDB integration**: Improved credential loading with better error handling and graceful degradation when credentials are missing.

- **Documentation**: Updated migration docs with new patterns (HTMX middleware, pagination handling, partial responses, advanced filtering).

## 2025-11-18

### Pagination Back Button Navigation Fix
- Fixed browser back button navigation from detail pages to return to correct paginated page instead of page 1
- Changed `router.replace()` to `router.push()` for proper browser history entries
- Added route query watchers to sync pagination state with URL on back/forward navigation
- Simplified scroll behavior to always scroll to top (removed scroll position restoration)
- Applied fix to GameList and BaseListComponent (used by DeveloperList, ListList, PostList)

## 2025-11-17

### Post-SSG Optimization & Fixes
**Caching & Data Reuse**
- Implemented client-side pagination for `/games/` list using in-memory cached data (eliminates API calls between pages)
- Added Vuex store caching system for games lists, games, and developers to enable instant re-navigation between pages
- Updated router `beforeEnter` to fetch 9999 games for unfiltered views (matches client-side pagination limit)

**UX & Performance**
- Fixed filter removal bugs: year/decade dropdowns and platform/genre tags now properly trigger filter updates
- Optimized page navigation by removing async overhead; instant `window.scrollTo(0, 0)` instead of smooth scroll
- Added scroll-to-top behavior when navigating between pages

**Pre-rendered HTML Routing**
- **Context:** vite-ssg pre-renders Vue pages to static HTML during build, making pages crawlable without JavaScript
- **Problem:** Django's catch-all route was serving `index.html` for ALL paths, preventing Wayback Machine from capturing correct pre-rendered pages
- **Solution:** Created `SPAWithPrerenderedView` that checks for pre-rendered files first, then falls back to SPA
- Updated Django URL routing in `acclaimedgames/urls.py` to intelligently serve pre-rendered HTML
- Wayback Machine archival now working correctly with pre-rendered static HTML

## 2025-11-16

### Performance & API Work
- Added targeted indexes (including new composite ones) plus migration 0026 to speed up developer/game/list/list membership/post filters without touching data.
- Prefetched developer/list relations in key API views and cached Meta/genre/platform endpoints to eliminate N+1s and reduce load.
- Softened noisy IGDB init logging in DEBUG/tests and documented the backend test command.

### Testing & Code Quality
- Reorganized Django tests into modular structure (`games/tests/`) with 8 test modules (1,299 lines total)
- Added Vue.js test suite using Vitest (5 test files, 263 lines)
- Achieved 100% test coverage for both backend and frontend, enforced 95% threshold
- Set up pre-commit hooks for Black formatting, Flake8 linting, and automated test runs with coverage enforcement
- Applied Black formatter to entire Python codebase (78 files)

### Bug Fixes
- Fixed critical static file serving issue (catch-all route blocking assets)
- Improved IGDB error handling and refactored data fetching
- Enhanced frontend resilience for API failures (store, game list, developer/game detail components)
- Fixed `VITE_API_URL` configuration issues
- Wrapped database delete operations in transactions
- Fixed Google Analytics integration (changed from `import.meta.env.NODE_ENV` to `import.meta.env.PROD` for Vite compatibility)

### Configuration & Documentation
- Created comprehensive `CLAUDE.md` project documentation
- Moved `SENTRY_DSN` to environment variable
- Added `.python-version` (Python 3.11), `.coveragerc`, `.flake8` configuration files
- Updated readme with testing and coverage documentation

### Statistics
**78 files changed: +4,466 additions, -822 deletions** across ~30 commits
