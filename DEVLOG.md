# Developer Log

## 2025-11-17

### Server-Side Static Generation (SSG) Integration
- Integrated vite-ssg (v28.2.2) for server-side static generation to make the site compatible with web crawlers and the Wayback Machine
- Restructured Vue.js app initialization to use ViteSSG instead of createApp
- Refactored router to export routes array instead of router instance
- Created `frontend/src/config.js` with `getApiUrl()` helper for SSR-safe API calls

### SSR Compatibility Improvements
- Added SSR guards (`typeof window !== 'undefined'`) to all browser-specific code:
  - localStorage access in `objectStore.js`
  - window API usage in `utils.js` and `router.js`
  - Client-only plugins (Google Analytics, mitt emitter, fetch-intercept) in `main.js`
- Fixed lodash imports for ESM compatibility (changed from named imports to default import pattern)
- Updated all Vue components to use `getApiUrl()` for SSR-safe API URL resolution

### Build Configuration
- Updated build script in `package.json` to use `vite-ssg build`
- Added SSG configuration to `vite.config.js`:
  - `includedRoutes()` function fetches game/developer slugs from Django API during build
  - Currently limited to 10 games and 5 developers for testing (configurable)
  - Supports environment variable `VITE_SSG_API_URL` for custom API URL during builds
- Added `.vite-ssg-temp/` to `.gitignore` for temporary build files
- Updated `index.html` with SSG placeholder comment (`<!--app-html-->`)

### Verification
- Successfully tested SSG build with Django dev server running
- Verified pre-rendered HTML contains server-rendered content and initial state
- All existing tests passing (21/21) with 100% coverage maintained
- Static HTML files now visible to web crawlers without JavaScript

### Documentation
- Updated `CLAUDE.md` with SSG build instructions and SSR-safe architecture notes
- Updated `readme.md` with SSG deployment requirements
- Added this DEVLOG entry

### Statistics
**Modified files:** ~20 source files + configuration + documentation
**Key additions:** New SSR guards, API URL abstraction, SSG build configuration

### SSG Data Pre-rendering for Wayback Machine (In Progress)
- **Problem:** Initial SSG implementation produced HTML with empty initial state, causing Wayback Machine to capture loading spinners instead of content
- **Root cause:** Components fetched data in `created()` hooks without using Vue's SSR-specific data fetching patterns
- Added `serverPrefetch()` hook to HomePage component for SSR-aware data loading
- Implemented automatic Vuex store pre-loading (genres, platforms, meta) during SSG builds in `main.js`
- Added route-level `beforeEnter` guards for game and developer detail pages to pre-fetch data during SSG
- Updated GameDetail and DeveloperDetail components to check for and use pre-fetched SSR data
- Verified build produces pages with full content (home: 37KB, game details: 80-115KB vs previous ~3KB empty templates)
- **Status:** Significant improvement - data now pre-rendered in HTML, but Wayback Machine capture still has some issues. Work ongoing.

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
